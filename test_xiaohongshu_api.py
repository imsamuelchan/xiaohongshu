import requests
import json
import argparse

def test_api(share_text):
    """测试小红书API提取功能"""
    # API地址
    api_url = "http://localhost:8000/api/extract"
    
    # 发送GET请求
    params = {
        "share_text": share_text,
        "save_images": True
    }
    
    print(f"正在请求API: {api_url}")
    print(f"分享文本: {share_text}")
    
    try:
        response = requests.get(api_url, params=params)
        
        # 检查响应状态码
        if response.status_code == 200:
            data = response.json()
            print("\n提取成功!")
            print(f"标题: {data.get('title', '无标题')}")
            print(f"内容: {data.get('content', '无内容')[:100]}..." if data.get('content') else "内容: 无内容")
            print(f"标签数量: {len(data.get('hashtags', []))}")
            print(f"图片数量: {len(data.get('images', []))}")
            print(f"已保存图片: {len(data.get('saved_images', []))}")
            print(f"点赞数: {data.get('likes', '0')}")
            print(f"评论数: {data.get('comments', '0')}")
            print(f"收藏数: {data.get('collects', '0')}")
            
            # 保存结果到JSON文件
            with open("xiaohongshu_result.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("\n结果已保存至 xiaohongshu_result.json")
            
            return True
        else:
            print(f"请求失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
            return False
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="测试小红书内容提取API")
    parser.add_argument("share_text", help="小红书分享文本或链接")
    args = parser.parse_args()
    
    test_api(args.share_text)

if __name__ == "__main__":
    main() 