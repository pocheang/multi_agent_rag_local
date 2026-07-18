#!/bin/bash
# ==========================================================
# GitHub 发布执行脚本 - 最终确认并推送
# ==========================================================

set -e

echo "=========================================="
echo "GitHub 发布 - 最终确认"
echo "=========================================="
echo ""

# 1. 运行最终检查
echo "步骤 1: 运行最终安全检查..."
bash check_github_ready.sh
echo ""

# 2. 显示即将推送的提交
echo "步骤 2: 查看即将推送的提交..."
echo ""
git log --oneline -5
echo ""

# 3. 统计变更
echo "步骤 3: 统计变更..."
echo "总提交数: $(git rev-list --count HEAD)"
echo "最近的标签: $(git describe --tags --abbrev=0 2>/dev/null || echo '无标签')"
echo ""

# 4. 确认推送
echo "=========================================="
echo "准备推送到 GitHub"
echo "=========================================="
echo ""
echo "即将执行的操作："
echo "  1. 推送所有提交到 origin/main"
echo "  2. 推送所有标签"
echo ""
echo "⚠️  警告：这将公开你的代码库"
echo ""

read -p "确认推送？(y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "开始推送..."

    # 推送主分支
    echo "推送 main 分支..."
    git push -u origin main

    # 推送标签
    echo "推送标签..."
    git push --tags

    echo ""
    echo "=========================================="
    echo "✅ 推送完成！"
    echo "=========================================="
    echo ""
    echo "下一步操作："
    echo "1. 访问 GitHub 仓库检查内容"
    echo "2. 配置仓库设置（Branch Protection, Dependabot）"
    echo "3. 创建 GitHub Release"
    echo "4. 更新仓库描述和 Topics"
    echo ""
else
    echo ""
    echo "❌ 推送已取消"
    echo ""
fi
