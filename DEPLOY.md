# 将小红书爬虫API部署到Vercel

本文档指导您如何将小红书爬虫API部署到Vercel，以获得一个可访问的API端点。

## 准备工作

1. 一个 [Vercel](https://vercel.com) 账号（可以使用GitHub账号登录）
2. [Git](https://git-scm.com/) 安装在本地环境

## 部署步骤

### 方法一：从GitHub仓库部署

1. 确保您已将项目推送到GitHub仓库（使用`sync_to_github.sh`脚本）

2. 登录Vercel账号 [https://vercel.com/login](https://vercel.com/login)

3. 在Vercel控制台中，点击 "Add New..." > "Project"

4. 从列表中选择您的GitHub仓库 (xiaohongshu)

5. 在配置页面上，保持默认设置，然后点击 "Deploy"

6. 等待部署完成后，Vercel会提供一个可以访问的URL（例如 `https://xiaohongshu-xxxx.vercel.app`）

### 方法二：使用Vercel CLI

1. 安装Vercel CLI

```bash
npm install -g vercel
```

2. 在项目目录下运行

```bash
vercel login
```

3. 部署项目

```bash
vercel
```

4. 按照提示配置您的项目，然后完成部署

## 使用API

部署完成后，您可以通过以下方式使用API：

### 通过网页界面

访问您的Vercel部署URL（例如 `https://xiaohongshu-xxxx.vercel.app`），您会看到一个可以输入小红书分享文本的页面。

### 通过API端点

```bash
curl -X POST "https://xiaohongshu-xxxx.vercel.app/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "share_text": "70 依依学金融发布了一篇小红书笔记，快来看吧！ 😆 2B4fyO9nDGbkJsc 😆 http://xhslink.com/a/EPoEXanJ2mFab，复制本条信息，打开【小红书】App查看精彩内容！", 
    "save_images": true
  }'
```

## 注意事项

1. Vercel的免费版有一些限制，包括：
   - 执行时间不超过10秒
   - 响应体大小限制
   - 每月有部署次数限制

2. 在Vercel环境中，文件是不可写的，因此我们修改了代码来使用内存存储图片数据。

3. 如果您的API调用频繁超时，可能需要考虑以下解决方案：
   - 优化代码减少执行时间
   - 升级到Vercel的付费版本
   - 使用其他服务器部署方案（如AWS、GCP或自己的服务器）

## 自定义域名

如果您想使用自己的域名，可以在Vercel项目设置中配置：

1. 在Vercel Dashboard中选择您的项目
2. 点击 "Settings" > "Domains"
3. 添加您的域名
4. 按照Vercel提供的说明配置DNS记录

## 更新部署

当您对代码进行更改后，可以通过以下方式更新部署：

1. 将更改推送到GitHub仓库（如果使用方法一）
2. 再次运行 `vercel` 命令（如果使用方法二）

Vercel会自动检测更改并重新部署您的应用。 