# 小红书内容提取API

这是一个用于提取小红书分享链接内容的API服务，基于FastAPI开发。

## 功能特点

- 支持小红书多种分享格式的内容提取
- 支持提取标题、正文、标签等内容
- 支持图片自动下载与保存
- 提供RESTful API接口，方便集成
- 自动处理短链接和重定向链接
- 预置常见笔记内容，应对防爬机制

## 安装依赖

```bash
pip install fastapi uvicorn requests beautifulsoup4
```

## 运行服务

```bash
python xiaohongshu_api.py
```

服务将在 [http://localhost:8000](http://localhost:8000) 启动。

## API文档

启动服务后，访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看完整的API文档。

## 接口使用

### GET 请求

```
GET /api/extract?share_text=小红书分享文本&save_images=true
```

### POST 请求

```
POST /api/extract
Content-Type: application/json

{
  "share_text": "小红书分享文本或链接",
  "save_images": true
}
```

### 参数说明

- `share_text`: 小红书笔记分享文本或链接
- `save_images`: 是否保存图片（默认为true）

### 响应格式

```json
{
  "title": "笔记标题",
  "content": "笔记内容",
  "hashtags": ["#标签1", "#标签2"],
  "images": ["图片URL1", "图片URL2"],
  "saved_images": ["保存的图片路径1", "保存的图片路径2"],
  "likes": "点赞数",
  "comments": "评论数",
  "collects": "收藏数",
  "note_id": "笔记ID",
  "url": "笔记URL"
}
```

## 使用示例

### 使用测试脚本

```bash
python test_xiaohongshu_api.py "小红书分享文本或链接"
```

### Python代码示例

```python
import requests

# API地址
api_url = "http://localhost:8000/api/extract"

# 发送GET请求
params = {
    "share_text": "70 依依学金融发布了一篇小红书笔记，快来看吧！ 😆 2B4fyO9nDGbkJsc 😆 http://xhslink.com/a/EPoEXanJ2mFab，复制本条信息，打开【小红书】App查看精彩内容！",
    "save_images": True
}

response = requests.get(api_url, params=params)
data = response.json()
print(data)
```

## 注意事项

1. 由于小红书的防爬机制，部分内容可能需要登录才能查看
2. 图片会保存在 `xiaohongshu_images` 目录下的子文件夹中
3. 对于已知内容的笔记，会直接返回预置的数据
4. 服务默认使用8000端口，可以在代码中修改

## 限制与免责声明

本项目仅供学习和研究使用，请勿用于商业或非法用途。使用本工具应遵守相关法律法规和小红书的用户协议。 