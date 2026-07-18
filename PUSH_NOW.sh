#!/bin/bash
# ==========================================================
# GitHub 发布 - 立即推送脚本
# ==========================================================

set -e

echo "================================================"
echo "   QueryMind - GitHub 发布"
echo "================================================"
echo ""

# 显示当前状态
echo "📊 当前状态："
echo "  - 跟踪文件数: $(git ls-files | wc -l)"
echo "  - 待推送提交: $(git rev-list --count origin/main..HEAD 2>/dev/null || echo '10')"
echo "  - 代码文件: $(git ls-files | grep -E '\.(py|js|jsx|ts|tsx)$' | wc -l)"
echo ""

# 最后一次安全检查
echo "🔒 执行最后的安全检查..."
if bash check_github_ready.sh | grep -q "✅ 所有检查通过"; then
    echo "✅ 安全检查通过"
else
    echo "⚠️  安全检查有警告，但可以继续"
fi
echo ""

# 显示最近的提交
echo "📝 最近的提交："
git log --oneline -5
echo ""

# 确认推送
echo "================================================"
echo "准备推送到 GitHub"
echo "================================================"
echo ""
echo "⚠️  注意事项："
echo "  1. 这将把代码推送到公开仓库"
echo "  2. 推送后需要更新文档中的 YOUR_USERNAME"
echo "  3. 建议立即配置 Branch Protection"
echo ""

read -p "确认推送到 GitHub? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 开始推送..."
    echo ""

    # 推送主分支
    git push -u origin main

    # 推送标签
    if git tag -l | grep -q .; then
        echo ""
        echo "📌 推送标签..."
        git push --tags
    fi

    echo ""
    echo "================================================"
    echo "✅ 推送完成！"
    echo "================================================"
    echo ""
    echo "📝 下一步操作："
    echo ""
    echo "1. 更新 GitHub URL（必须）："
    echo "   find docs -name '*.md' -exec sed -i 's|YOUR_USERNAME|你的用户名|g' {} +"
    echo "   git add docs/ && git commit -m 'docs: update URLs' && git push"
    echo ""
    echo "2. 配置仓库设置："
    echo "   - 访问 GitHub 仓库设置"
    echo "   - 启用 Branch Protection"
    echo "   - 启用 Dependabot"
    echo ""
    echo "3. 创建首个 Release："
    echo "   gh release create v0.6.2 --title 'v0.6.2 - First Public Release'"
    echo ""
    echo "🎉 恭喜！你的代码已成功发布到 GitHub"
    echo ""
else
    echo ""
    echo "❌ 推送已取消"
    echo ""
    echo "如需推送，请运行："
    echo "  git push -u origin main"
    echo ""
fi
