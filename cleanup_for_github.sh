#!/bin/bash
# ============================================
# GitHub 发布清理脚本
# ============================================
# 功能：从 Git 跟踪中移除所有不应发布的文件
# 使用：bash cleanup_for_github.sh

set -e

echo "================================================"
echo "GitHub 发布清理脚本"
echo "================================================"
echo ""

# 1. 移除数据目录（保留 .gitkeep）
echo "📁 [1/8] 清理数据目录..."
git rm -r --cached data/ 2>/dev/null || true
git add data/.gitkeep 2>/dev/null || true
echo "✓ 数据目录已清理"
echo ""

# 2. 移除日志文件
echo "📋 [2/8] 清理日志文件..."
git rm --cached logs/**/*.jsonl 2>/dev/null || true
git rm --cached logs/**/*.json 2>/dev/null || true
git rm --cached logs/**/*.log 2>/dev/null || true
echo "✓ 日志文件已清理"
echo ""

# 3. 移除报告目录
echo "📊 [3/8] 清理报告目录..."
git rm -r --cached reports/ 2>/dev/null || true
git rm -r --cached artifacts/ 2>/dev/null || true
echo "✓ 报告目录已清理"
echo ""

# 4. 移除内部文档
echo "📝 [4/8] 清理内部文档..."
git rm -r --cached internal_docs/ 2>/dev/null || true
git rm -r --cached docs/archive/ 2>/dev/null || true
git add docs/archive/INDEX.md 2>/dev/null || true
git rm -r --cached docs/design/ 2>/dev/null || true
git rm -r --cached docs/plans/ 2>/dev/null || true
git rm -r --cached docs/security/ 2>/dev/null || true
echo "✓ 内部文档已清理"
echo ""

# 5. 移除临时和报告文件
echo "🗑️  [5/8] 清理临时和报告文件..."
git ls-files | grep -E '_REPORT\.md$|_PLAN\.md$|_INTERNAL\.md$|_AUDIT\.md$|_SUMMARY\.md$|_GUIDE\.md$|_CHECKLIST\.md$|_COMPLETION\.md$|_FIXES\.md$' | xargs git rm --cached 2>/dev/null || true
echo "✓ 临时文件已清理"
echo ""

# 6. 移除配置文件（非示例）
echo "⚙️  [6/8] 清理运行时配置..."
git rm --cached config/env/base.env 2>/dev/null || true
git rm --cached config/profiles/*.env 2>/dev/null || true
echo "✓ 运行时配置已清理"
echo ""

# 7. 移除 AI 助手配置
echo "🤖 [7/8] 清理 AI 助手配置..."
git rm -r --cached .claude/worktrees/ 2>/dev/null || true
git rm --cached .claude/settings.json 2>/dev/null || true
git rm --cached .claude/settings.local.json 2>/dev/null || true
echo "✓ AI 助手配置已清理"
echo ""

# 8. 移除运行时目录
echo "⚡ [8/8] 清理运行时目录..."
git rm -r --cached .runtime/ 2>/dev/null || true
echo "✓ 运行时目录已清理"
echo ""

echo "================================================"
echo "清理完成！"
echo "================================================"
echo ""
echo "📊 统计信息："
echo "当前跟踪的文件数量: $(git ls-files | wc -l)"
echo ""
echo "⚠️  下一步操作："
echo "1. 检查清理结果: git status"
echo "2. 提交更改: git add .gitignore && git commit -m 'chore: cleanup for github publication'"
echo "3. 清理个人信息（手动）: 编辑文档中的 pocheang 和本地路径"
echo ""
