#!/bin/bash

# 同步小红书爬虫项目到GitHub

# 确认用户名和仓库名称
read -p "请输入您的GitHub用户名: " USERNAME
read -p "请输入仓库名称(默认: xiaohongshu-scraper): " REPO_NAME
REPO_NAME=${REPO_NAME:-xiaohongshu-scraper}

echo "将项目同步到 https://github.com/$USERNAME/$REPO_NAME"
read -p "是否继续? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "已取消操作"
    exit 1
fi

# 检查是否已有.git目录
if [ -d ".git" ]; then
    echo "检测到已存在Git仓库，将更新远程地址..."
    git remote remove origin
else
    echo "初始化Git仓库..."
    git init
fi

# 添加文件并提交
echo "添加文件到Git..."
git add .gitignore
git add *.py
git add *.md
git add requirements.txt
git add sync_to_github.sh

# 提交更改
echo "提交更改..."
git commit -m "Initial commit: Xiaohongshu scraper with FastAPI"

# 添加远程仓库
echo "添加远程仓库..."
git remote add origin "https://github.com/$USERNAME/$REPO_NAME.git"

# 推送到GitHub
echo "推送到GitHub(可能需要您输入GitHub凭据)..."
git push -u origin master || git push -u origin main

echo "完成!"
echo "现在可以在 https://github.com/$USERNAME/$REPO_NAME 查看您的仓库。"
echo "在使用前，您需要在GitHub上先创建名为 $REPO_NAME 的仓库。" 