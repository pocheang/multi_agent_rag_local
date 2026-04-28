#!/bin/bash

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.3.2"
    exit 1
fi

echo "=========================================="
echo "Version Documentation Check for v$VERSION"
echo "=========================================="
echo ""

# 检查必需文件
echo "📝 Checking required files..."
[ -f "CHANGELOG.md" ] && echo "  ✓ CHANGELOG.md" || echo "  ✗ CHANGELOG.md missing"
[ -f "docs/VERSION_HISTORY.md" ] && echo "  ✓ VERSION_HISTORY.md" || echo "  ✗ VERSION_HISTORY.md missing"
[ -f "V${VERSION}_COMPLETION_REPORT.md" ] || [ -f "docs/archive/V${VERSION}_COMPLETION_REPORT.md" ] && echo "  ✓ Completion report" || echo "  ✗ Completion report missing"
[ -f "pyproject.toml" ] && echo "  ✓ pyproject.toml" || echo "  ✗ pyproject.toml missing"
[ -f "CLAUDE.md" ] && echo "  ✓ CLAUDE.md" || echo "  ✗ CLAUDE.md missing"
echo ""

# 检查版本号一致性
echo "🔍 Checking version consistency..."
if grep -q "version = \"$VERSION\"" pyproject.toml; then
    echo "  ✓ pyproject.toml version matches"
else
    echo "  ✗ pyproject.toml version mismatch"
fi

if grep -q "\[$VERSION\]" CHANGELOG.md; then
    echo "  ✓ CHANGELOG.md has version entry"
else
    echo "  ✗ CHANGELOG.md missing version entry"
fi

if grep -q "v$VERSION" docs/VERSION_HISTORY.md; then
    echo "  ✓ VERSION_HISTORY.md has version entry"
else
    echo "  ✗ VERSION_HISTORY.md missing version entry"
fi
echo ""

# 检查 Git 标签
echo "🏷️  Checking git tag..."
if git tag -l | grep -q "^v$VERSION$"; then
    echo "  ✓ Git tag v$VERSION exists"
else
    echo "  ✗ Git tag v$VERSION missing"
fi
echo ""

echo "=========================================="
echo "Documentation check complete!"
echo "=========================================="
