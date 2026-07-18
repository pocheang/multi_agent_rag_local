#!/bin/bash
# GitHub 发布最终检查脚本
set -e

echo "=== GitHub 发布最终检查 ==="
echo ""

# 1. 确认没有数据文件
echo "[1/7] 检查数据文件..."
if git ls-files | grep -E '^data/' > /dev/null; then
    echo "❌ 仍有 data/ 文件被跟踪"
    git ls-files | grep '^data/'
else
    echo "✓ data/ 已完全清理"
fi
echo ""

# 2. 确认没有日志文件
echo "[2/7] 检查日志文件..."
if git ls-files | grep -E '\.(log|jsonl)$' > /dev/null; then
    echo "❌ 仍有日志文件被跟踪"
    git ls-files | grep -E '\.(log|jsonl)$'
else
    echo "✓ 日志文件已完全清理"
fi
echo ""

# 3. 确认没有运行时配置
echo "[3/7] 检查运行时配置..."
if git ls-files | grep -E 'config/env/.*\.env$' | grep -v '.example' > /dev/null; then
    echo "❌ 仍有运行时配置被跟踪"
    git ls-files | grep 'config/env/.*\.env$' | grep -v '.example'
else
    echo "✓ 运行时配置已完全清理"
fi
echo ""

# 4. 确认没有内部文档
echo "[4/7] 检查内部文档..."
if git ls-files | grep -E '_REPORT\.md|_PLAN\.md|_INTERNAL\.md|_AUDIT\.md' > /dev/null; then
    echo "❌ 仍有内部文档被跟踪"
    git ls-files | grep -E '_REPORT\.md|_PLAN\.md|_INTERNAL\.md|_AUDIT\.md'
else
    echo "✓ 内部文档已完全清理"
fi
echo ""

# 5. 检查个人信息
echo "[5/7] 检查个人信息..."
PERSONAL_COUNT=$(git grep -l "pocheang" docs/ 2>/dev/null | wc -l)
if [ "$PERSONAL_COUNT" -gt 0 ]; then
    echo "⚠️  发现 $PERSONAL_COUNT 个文件包含 'pocheang'"
    echo "   需要手动清理的文件："
    git grep -l "pocheang" docs/ 2>/dev/null | head -10
else
    echo "✓ 个人信息已清理"
fi
echo ""

# 6. 检查本地路径
echo "[6/7] 检查本地路径..."
LOCAL_PATH_COUNT=$(git grep -l "c:/Users/" docs/ 2>/dev/null | wc -l)
if [ "$LOCAL_PATH_COUNT" -gt 0 ]; then
    echo "⚠️  发现 $LOCAL_PATH_COUNT 个文件包含本地路径"
else
    echo "✓ 本地路径已清理"
fi
echo ""

# 7. 统计发布文件
echo "[7/7] 统计发布文件..."
TOTAL_FILES=$(git ls-files | wc -l)
CODE_FILES=$(git ls-files | grep -E '\.(py|js|jsx|ts|tsx)$' | wc -l)
CONFIG_FILES=$(git ls-files | grep -E '\.(json|yaml|yml|toml)$' | wc -l)
DOC_FILES=$(git ls-files | grep -E '\.md$' | wc -l)

echo "   总文件数: $TOTAL_FILES"
echo "   代码文件: $CODE_FILES"
echo "   配置文件: $CONFIG_FILES"
echo "   文档文件: $DOC_FILES"

if [ "$TOTAL_FILES" -lt 600 ]; then
    echo "✓ 文件数量合理"
else
    echo "⚠️  文件数量较多 ($TOTAL_FILES)，建议检查"
fi
echo ""

echo "==================================="
if [ "$PERSONAL_COUNT" -eq 0 ] && [ "$LOCAL_PATH_COUNT" -eq 0 ]; then
    echo "✅ 所有检查通过！可以安全推送到 GitHub"
else
    echo "⚠️  仍有问题需要处理（见上方）"
fi
echo "==================================="
