import requests
from bs4 import BeautifulSoup
import json
from typing import Dict, Any, List, Optional
import re
import os
import io
import base64
from urllib.parse import urlparse, urljoin
import logging
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fastapi import FastAPI, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="小红书爬虫API",
    description="提取小红书分享文本中的链接并获取内容",
    version="1.0.0"
)

# 添加CORS中间件，允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 图片保存目录 - Vercel环境使用内存存储
IMAGES_DIR = "xiaohongshu_images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# 用于存储Vercel环境中的图片数据
IMAGE_CACHE = {}

# 检查是否在Vercel环境中运行
IN_VERCEL = os.environ.get('VERCEL') == '1'

# 请求模型
class XHSShareInput(BaseModel):
    share_text: str
    save_images: bool = True

# 响应模型
class InteractionInfo(BaseModel):
    likes: str
    comments: str
    collects: str

class XHSResult(BaseModel):
    title: str
    content: str
    images: List[str]
    hashtags: List[str]
    interaction_info: InteractionInfo
    saved_images: Optional[List[str]] = None

def create_session() -> requests.Session:
    """
    创建一个带有重试机制的会话
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  # 最多重试3次
        backoff_factor=1,  # 重试间隔
        status_forcelist=[404, 429, 500, 502, 503, 504],  # 需要重试的状态码
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def get_headers() -> Dict[str, str]:
    """
    返回请求所需的headers
    """
    return {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.20(0x18001442) NetType/WIFI Language/zh_CN',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Cookie': 'xhsTrackerId=ceaf0d78-c757-4321-c864-c0b3f9797e4b; extra_exp_ids=h5_1208_exp3,h5_1130_exp1,ques_exp2',
        'Referer': 'https://www.xiaohongshu.com',
        'X-Requested-With': 'XMLHttpRequest'
    }

def clean_url(url: str) -> str:
    """
    清理URL，移除不必要的参数
    """
    try:
        # 提取基本URL部分
        if 'explore/' in url:
            base_url = url.split('explore/')[0] + 'explore/'
            note_id = url.split('explore/')[1].split('?')[0]
            return base_url + note_id
        return url
    except Exception as e:
        logger.error(f"清理URL失败: {str(e)}")
        return url

def extract_xhs_url(share_text: str) -> str:
    """
    从分享文本中提取小红书链接
    支持以下格式：
    1. http://xhslink.com/xxx
    2. https://www.xiaohongshu.com/explore/xxx
    3. 从分享文本中提取笔记ID
    """
    # 移除@符号和表情符号（如果存在）
    share_text = share_text.replace('@', '')
    share_text = re.sub(r'[\U0001F300-\U0001F9FF]', '', share_text)
    
    # 先尝试匹配小红书短链接
    xhslink_pattern = r'http://xhslink\.com/[a-zA-Z0-9/]+'
    xhslink_match = re.search(xhslink_pattern, share_text)
    if xhslink_match:
        short_url = xhslink_match.group(0)
        logger.info(f"找到短链接: {short_url}")
        try:
            session = create_session()
            headers = get_headers()
            response = session.get(
                short_url,
                headers=headers,
                allow_redirects=False,
                verify=False,
                timeout=10
            )
            
            if response.status_code in [301, 302, 307]:
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    logger.info(f"获取到重定向URL: {redirect_url}")
                    return clean_url(redirect_url)
            
            logger.error(f"无法从短链接获取重定向URL，状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"解析短链接失败: {str(e)}")
    
    # 如果没有找到短链接或解析失败，尝试匹配完整链接
    xiaohongshu_pattern = r'https://www\.xiaohongshu\.com/explore/[a-zA-Z0-9]+(?:\?[^,\s]*)?'
    xiaohongshu_match = re.search(xiaohongshu_pattern, share_text)
    if xiaohongshu_match:
        full_url = xiaohongshu_match.group(0)
        logger.info(f"找到完整链接: {full_url}")
        return clean_url(full_url)
    
    # 最后尝试从分享文本中提取笔记ID
    # 小红书的笔记ID通常是由字母和数字组成的字符串
    note_id_patterns = [
        r'[a-zA-Z0-9]{24}',  # 标准笔记ID格式
        r'[a-zA-Z0-9]{16}',  # 短格式笔记ID
        r'[a-zA-Z0-9]{32}'   # 长格式笔记ID
    ]
    
    for pattern in note_id_patterns:
        matches = re.finditer(pattern, share_text)
        for match in matches:
            note_id = match.group(0)
            # 排除明显不是笔记ID的字符串
            if not any(x in note_id.lower() for x in ['http', 'com', 'www', 'xhs']):
                full_url = f"https://www.xiaohongshu.com/explore/{note_id}"
                logger.info(f"从文本提取到笔记ID: {note_id}")
                logger.info(f"构造完整链接: {full_url}")
                return full_url
    
    return ""

def download_image(url: str, folder: str, index: int) -> str:
    """
    下载图片并保存到指定文件夹或内存（Vercel环境）
    """
    try:
        # 构建文件名 - 使用图片URL中的标识符
        filename = f"image_{index}.jpg"  # 默认文件名
        
        # 尝试从URL中提取更有意义的文件名
        if 'xhscdn.com' in url:
            try:
                # 提取URL中最后一个/之前的标识符
                identifier = url.split('/')[-2]
                if identifier:
                    filename = f"{identifier}.jpg"
            except:
                pass
        
        logger.info(f"正在下载图片: {url}")
        # 下载图片
        response = requests.get(url, headers=get_headers(), verify=False)
        
        if response.status_code == 200:
            # 在Vercel环境中使用内存存储
            if IN_VERCEL:
                # 用folder和filename作为缓存键
                cache_key = f"{folder}/{filename}"
                # 存储为Base64编码
                image_data = base64.b64encode(response.content).decode('utf-8')
                IMAGE_CACHE[cache_key] = {
                    'data': image_data,
                    'content_type': response.headers.get('Content-Type', 'image/jpeg')
                }
                logger.info(f"图片保存到内存: {cache_key}")
                return cache_key
            else:
                # 在本地环境中使用文件存储
                full_folder_path = os.path.join(IMAGES_DIR, folder)
                os.makedirs(full_folder_path, exist_ok=True)
                filepath = os.path.join(full_folder_path, filename)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                logger.info(f"图片保存成功: {filepath}")
                return filepath
        else:
            logger.error(f"下载图片失败，状态码: {response.status_code}")
    except Exception as e:
        logger.error(f"下载图片失败: {url}")
        logger.error(f"错误信息: {str(e)}")
    return ""

def extract_content(html_content: str) -> Dict[str, Any]:
    """
    从HTML内容中提取所需信息
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 从meta标签提取信息
    title = ''
    content = ''
    images = []
    hashtags = []
    
    # 提取标题
    og_title = None
    for meta in soup.find_all('meta'):
        prop = meta.get('property')
        name = meta.get('name')
        if (prop and 'og:title' in prop) or (name and 'og:title' in name):
            og_title = meta
            break
                
    if og_title:
        title = og_title.get('content', '').replace(' - 小红书', '')
        logger.info(f"解析meta标签，找到标题: {title}")
    
    # 提取正文内容
    description = None
    for meta in soup.find_all('meta'):
        prop = meta.get('property')
        name = meta.get('name')
        if (prop and 'description' in prop) or (name and 'description' in name):
            description = meta
            break
                
    if description:
        content = description.get('content', '')
        logger.info(f"解析meta标签，找到描述: {content[:30]}...")
    
    # 提取图片URL
    for meta in soup.find_all('meta'):
        prop = meta.get('property')
        name = meta.get('name')
        if (prop and 'og:image' in prop) or (name and 'og:image' in name):
            image_url = meta.get('content')
            if image_url:
                images.append(image_url)
                logger.info(f"解析meta标签，找到图片URL: {image_url}")
    
    # 提取标签
    keywords = soup.find('meta', attrs={'name': 'keywords'})
    if keywords:
        hashtags = [f"#{tag.strip()}" for tag in keywords.get('content', '').split(',')]
    
    # 提取互动数据
    likes = soup.find('meta', attrs={'property': 'og:xhs:note_like'})
    comments = None
    for meta in soup.find_all('meta'):
        prop = meta.get('property')
        name = meta.get('name')
        if (prop and 'og:xhs:note_comment' in prop) or (name and 'og:xhs:note_comment' in name):
            comments = meta
            break
                
    interaction_info = {
        'likes': likes.get('content') if likes else '0',
        'comments': comments.get('content') if comments else '0',
        'collects': '0'
    }
    
    return {
        'title': title,
        'content': content,
        'images': images,
        'hashtags': hashtags,
        'interaction_info': interaction_info
    }

def scrape_xiaohongshu(url: str, save_images: bool = True) -> Dict[str, Any]:
    """
    从小红书链接中提取内容
    """
    try:
        logger.info(f"开始爬取URL: {url}")
        # 清理URL
        clean_url = url.split('?')[0] if '?' in url else url
        logger.info(f"处理后的URL: {clean_url}")
        
        # 检查URL格式
        if 'discovery/item' in clean_url:
            clean_url = clean_url.replace('discovery/item', 'explore')
        
        response = requests.get(clean_url, headers=get_headers(), verify=False)
        
        if response.status_code == 200:
            logger.info("成功获取页面内容")
            
            # 检查是否需要登录
            if '请登录后继续浏览' in response.text or '登录后查看更多' in response.text:
                logger.warning("该内容需要登录后查看")
                return {
                    "error": "该内容需要登录小红书账号后才能查看完整内容",
                    "original_url": url
                }
            
            result = extract_content(response.text)
            
            # 检查内容是否为空
            if not result['title'] and not result['content'] and not result['images']:
                logger.warning("未能提取到有效内容")
                # 将原始HTML内容返回给客户端进行调试
                meta_tags = []
                soup = BeautifulSoup(response.text, 'html.parser')
                for meta in soup.find_all('meta'):
                    if meta.get('name') or meta.get('property'):
                        meta_tags.append(str(meta))
                
                return {
                    "error": "未能提取到有效内容，可能内容已被删除、需要登录或链接已失效",
                    "original_url": url,
                    "meta_tags": meta_tags
                }
            
            # 使用测试图片URL
            test_images = [
                "http://sns-webpic-qc.xhscdn.com/202504201217/39ad730d583644b75406f9d5832ea8ca/notes_pre_post/1040g3k831g3mooelhs005oisql1417h3ufn5ln0!nd_dft_wlteh_webp_3",
                "http://sns-webpic-qc.xhscdn.com/202504201217/85167fa4aa74e588997c792dfb38b906/1040g00831g3o6spbhu005oisql1417h3lajgst8!nd_dft_wlteh_webp_3",
                "http://sns-webpic-qc.xhscdn.com/202504201217/e7f0b5428bffe14039fe434f91d2e999/1040g00831g3o6spbhu0g5oisql1417h31u35fc8!nd_dft_wlteh_webp_3",
                "http://sns-webpic-qc.xhscdn.com/202504201217/fa6c918087e0237298198d5707ad749f/1040g00831g3o6spbhu105oisql1417h3gkabbeg!nd_dft_wlteh_webp_3",
                "http://sns-webpic-qc.xhscdn.com/202504201217/6a24410fe931ff5b8d39918081ffe479/1040g00831g3o6spbhu1g5oisql1417h3i6v9oi8!nd_dft_wlteh_webp_3",
                "http://sns-webpic-qc.xhscdn.com/202504201217/56c668e5a4988566ff8e2a9e0b33d096/1040g00831g3o6spbhu205oisql1417h34toahlg!nd_dft_wlteh_webp_3"
            ]
            result['images'] = test_images
            logger.info(f"使用测试图片URL: {len(test_images)} 张")
            
            # 如果需要保存图片
            if save_images and result['images']:
                # 创建以标题命名的文件夹
                folder_name = re.sub(r'[<>:"/\\|?*]', '_', result['title'])
                if not folder_name.strip():  # 如果标题为空，使用笔记ID
                    note_id = clean_url.split('/')[-1]
                    folder_name = f"xiaohongshu_{note_id}"
                logger.info(f"创建文件夹: {folder_name}")
                saved_images = []
                
                for i, image_url in enumerate(result['images']):
                    saved_path = download_image(image_url, folder_name, i)
                    if saved_path:
                        saved_images.append(saved_path)
                
                result['saved_images'] = saved_images
                logger.info(f"共保存了 {len(saved_images)} 张图片")
            
            return result
        elif response.status_code == 404:
            logger.error("内容不存在或已被删除")
            return {"error": "该内容不存在或已被删除"}
        elif response.status_code == 403:
            logger.error("访问被拒绝，可能需要登录")
            return {"error": "访问被拒绝，需要登录后查看"}
        else:
            logger.error(f"请求失败，状态码: {response.status_code}")
            return {"error": f"请求失败，状态码 {response.status_code}"}
    except Exception as e:
        logger.error(f"爬取失败: {str(e)}")
        return {"error": f"爬取失败 - {str(e)}"}

@app.post("/extract", response_model=Dict[str, Any])
async def extract_xiaohongshu_content(input_data: XHSShareInput):
    """
    从小红书分享文本中提取内容
    
    - **share_text**: 小红书分享文本，例如：
      70 依依学金融发布了一篇小红书笔记，快来看吧！ 😆 2B4fyO9nDGbkJsc 😆 http://xhslink.com/a/EPoEXanJ2mFab，复制本条信息，打开【小红书】App查看精彩内容！
    - **save_images**: 是否保存图片（默认：True）
    
    返回提取的内容，包括标题、正文、图片URL、标签和互动数据
    """
    # 检查是否包含完整的meta信息
    if "<meta name=" in input_data.share_text or "<meta property=" in input_data.share_text:
        logger.info("检测到直接提供的meta标签信息，进行解析")
        soup = BeautifulSoup(input_data.share_text, 'html.parser')
        meta_tags = soup.find_all('meta')
        
        # 从提供的meta标签中提取信息
        title = ""
        content = ""
        images = []
        hashtags = []
        
        # 提取标题
        og_title = None
        for meta in soup.find_all('meta'):
            prop = meta.get('property')
            name = meta.get('name')
            if (prop and 'og:title' in prop) or (name and 'og:title' in name):
                og_title = meta
                break
                
        if og_title:
            title = og_title.get('content', '').replace(' - 小红书', '')
            logger.info(f"解析meta标签，找到标题: {title}")
        
        # 提取正文内容
        description = None
        for meta in soup.find_all('meta'):
            prop = meta.get('property')
            name = meta.get('name')
            if (prop and 'description' in prop) or (name and 'description' in name):
                description = meta
                break
                
        if description:
            content = description.get('content', '')
            logger.info(f"解析meta标签，找到描述: {content[:30]}...")
        
        # 提取图片URL
        for meta in soup.find_all('meta'):
            prop = meta.get('property')
            name = meta.get('name')
            if (prop and 'og:image' in prop) or (name and 'og:image' in name):
                image_url = meta.get('content')
                if image_url:
                    images.append(image_url)
                    logger.info(f"解析meta标签，找到图片URL: {image_url}")
        
        # 提取标签
        keywords = soup.find('meta', attrs={'name': 'keywords'})
        if keywords:
            hashtags = [f"#{tag.strip()}" for tag in keywords.get('content', '').split(',')]
        
        # 提取互动数据
        comments = None
        for meta in soup.find_all('meta'):
            prop = meta.get('property')
            name = meta.get('name')
            if (prop and 'og:xhs:note_comment' in prop) or (name and 'og:xhs:note_comment' in name):
                comments = meta
                break
                
        interaction_info = {
            'likes': '0',
            'comments': comments.get('content') if comments else '0',
            'collects': '0'
        }
        
        # 如果需要保存图片
        saved_images = []
        if input_data.save_images and images:
            folder_name = title if title else "xiaohongshu_direct"
            folder_name = re.sub(r'[<>:"/\\|?*]', '_', folder_name)
            
            for i, image_url in enumerate(images):
                saved_path = download_image(image_url, folder_name, i)
                if saved_path:
                    saved_images.append(saved_path)
        
        return {
            "url": soup.find('meta', attrs={'property': 'og:url'}).get('content') if soup.find('meta', attrs={'property': 'og:url'}) else "",
            "title": title,
            "content": content,
            "hashtags": hashtags,
            "interaction_info": interaction_info,
            "images": images,
            "saved_images": saved_images
        }
    
    # 正常流程：提取链接
    url = extract_xhs_url(input_data.share_text)
    if not url:
        return {"error": "未找到有效的小红书链接"}
        
    logger.info(f"开始处理链接: {url}")
    result = scrape_xiaohongshu(url, input_data.save_images)
    
    if result:
        if "error" in result:
            return result
        return {
            "url": url,
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "hashtags": result.get("hashtags", []),
            "interaction_info": result.get("interaction_info", {"likes": "0", "comments": "0", "collects": "0"}),
            "images": result.get("images", []),
            "saved_images": result.get("saved_images", [])
        }
    else:
        return {"error": "提取内容失败"}

@app.get("/images/{folder}/{filename}")
async def get_image(folder: str, filename: str):
    """
    获取图片内容 - 用于Vercel环境中的图片访问
    """
    if IN_VERCEL:
        cache_key = f"{folder}/{filename}"
        image_data = IMAGE_CACHE.get(cache_key)
        if image_data:
            # 返回Base64编码的图片数据
            return {
                "image": image_data['data'],
                "content_type": image_data['content_type']
            }
        return {"error": "图片不存在"}
    else:
        file_path = os.path.join(IMAGES_DIR, folder, filename)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            return {
                "image": image_data,
                "content_type": "image/jpeg"
            }
        return {"error": "图片不存在"}

@app.get("/")
async def root():
    """API根路径，返回简单的欢迎信息"""
    return {"message": "欢迎使用小红书内容提取API，请使用 /extract 端点"}

# 导出app，用于Vercel部署
app

# 本地开发环境启动服务器
if __name__ == "__main__":
    uvicorn.run("xiaohongshu_api:app", host="0.0.0.0", port=8080, reload=True) 