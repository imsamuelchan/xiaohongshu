import os
import requests
import json
import argparse
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
import logging
from xiaohongshu_api import extract_content, download_image

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get API key from environment variables
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("No API_KEY found in .env file")

FIRECRAWL_API_URL = "https://api.firecrawl.dev/scrape"

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
        logger.info(f"Found short link: {short_url}")
        return short_url
    
    # 如果没有找到短链接，尝试匹配完整链接
    xiaohongshu_pattern = r'https://www\.xiaohongshu\.com/explore/[a-zA-Z0-9]+(?:\?[^,\s]*)?'
    xiaohongshu_match = re.search(xiaohongshu_pattern, share_text)
    if xiaohongshu_match:
        full_url = xiaohongshu_match.group(0)
        logger.info(f"Found full link: {full_url}")
        return full_url
    
    # 最后尝试从分享文本中提取笔记ID
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
                logger.info(f"Extracted note ID: {note_id}")
                logger.info(f"Constructed full link: {full_url}")
                return full_url
    
    return ""

def scrape_xiaohongshu_with_firecrawl(url_or_share_text: str, save_images: bool = True) -> Dict[str, Any]:
    """
    使用Firecrawl API爬取小红书内容
    
    Args:
        url_or_share_text: 小红书链接或分享文本
        save_images: 是否保存图片
        
    Returns:
        字典，包含提取的内容
    """
    # 如果输入是分享文本而不是URL，则提取URL
    if not (url_or_share_text.startswith('http://') or url_or_share_text.startswith('https://')):
        url = extract_xhs_url(url_or_share_text)
        if not url:
            logger.error("No valid Xiaohongshu URL found in input")
            return {"error": "No valid Xiaohongshu URL found"}
    else:
        url = url_or_share_text
    
    logger.info(f"Scraping Xiaohongshu URL: {url}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Build the request payload with options specific to Xiaohongshu
    payload = {
        "url": url,
        "options": {
            "waitForSelector": "meta[property='og:title']",
            "scrollToBottom": True,
            "waitFor": "2000"  # Wait 2 seconds to ensure content is loaded
        }
    }
    
    try:
        # Make the API request
        logger.info("Sending request to Firecrawl API")
        response = requests.post(
            FIRECRAWL_API_URL,
            headers=headers,
            json=payload
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            logger.info("Successfully retrieved data from Firecrawl API")
            result = response.json()
            
            # Save the raw HTML for debugging
            with open("firecrawl_raw.html", "w", encoding="utf-8") as f:
                f.write(result.get("html", ""))
            
            # Parse the HTML content
            html_content = result.get("html", "")
            
            # Use your existing parsing function to extract content
            extracted_data = extract_content(html_content)
            
            # Save the extracted data
            with open("xiaohongshu_extracted.json", "w", encoding="utf-8") as f:
                json.dump(extracted_data, f, ensure_ascii=False, indent=2)
            
            # Download images if needed
            if save_images and extracted_data['images']:
                # Create folder for images
                folder_name = re.sub(r'[<>:"/\\|?*]', '_', extracted_data['title'])
                if not folder_name.strip():
                    folder_name = "xiaohongshu_firecrawl"
                
                saved_images = []
                for i, image_url in enumerate(extracted_data['images']):
                    saved_path = download_image(image_url, folder_name, i)
                    if saved_path:
                        saved_images.append(saved_path)
                
                extracted_data['saved_images'] = saved_images
                logger.info(f"Saved {len(saved_images)} images")
            
            # Return the complete result
            return {
                "url": url,
                "title": extracted_data.get("title", ""),
                "content": extracted_data.get("content", ""),
                "hashtags": extracted_data.get("hashtags", []),
                "interaction_info": extracted_data.get("interaction_info", {"likes": "0", "comments": "0", "collects": "0"}),
                "images": extracted_data.get("images", []),
                "saved_images": extracted_data.get("saved_images", []) if save_images else []
            }
        else:
            logger.error(f"Error: API request failed with status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return {"error": f"API request failed: {response.text}"}
            
    except Exception as e:
        logger.error(f"Error making request to Firecrawl API: {str(e)}")
        return {"error": str(e)}

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Scrape Xiaohongshu content using Firecrawl API")
    
    parser.add_argument("input", help="Xiaohongshu URL or share text")
    parser.add_argument("--no-images", dest="save_images", action="store_false", 
                        help="Do not save images")
    parser.set_defaults(save_images=True)
    
    return parser.parse_args()

def main():
    """Main function to run the scraper"""
    args = parse_arguments()
    
    result = scrape_xiaohongshu_with_firecrawl(
        url_or_share_text=args.input,
        save_images=args.save_images
    )
    
    if "error" not in result:
        print("\nScraping completed successfully!")
        print(f"Title: {result.get('title', 'N/A')}")
        print(f"Content: {result.get('content', 'N/A')[:100]}...")
        print(f"Hashtags: {', '.join(result.get('hashtags', []))}")
        print(f"Images: {len(result.get('images', []))}")
        print(f"Likes: {result.get('interaction_info', {}).get('likes', 'N/A')}")
        print(f"Comments: {result.get('interaction_info', {}).get('comments', 'N/A')}")
        
        # Save full result to JSON
        with open("xiaohongshu_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("\nFull result saved to 'xiaohongshu_result.json'")
    else:
        print(f"\nScraping failed: {result.get('error')}")

if __name__ == "__main__":
    main() 