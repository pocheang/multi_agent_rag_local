#!/bin/bash
# GitHub开源发布脚本 - QueryMind v0.6.2.1
# 作者: Po Cheang (po.cheang@gmail.com)
# 日期: 2026-07-18

set -e  # 遇到错误立即退出

echo "=================================="
echo "QueryMind v0.6.2.1 GitHub发布脚本"
echo "=================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 步骤1: 检查git状态
echo -e "${YELLOW}步骤1: 检查git状态...${NC}"
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${GREEN}✓ 有未提交的更改，继续...${NC}"
else
    echo -e "${RED}✗ 没有未提交的更改${NC}"
    exit 1
fi
echo ""

# 步骤2: 显示将要添加的文件
echo -e "${YELLOW}步骤2: 将要添加的文件列表:${NC}"
git status --short
echo ""

# 步骤3: 添加所有文件
echo -e "${YELLOW}步骤3: 添加文件到暂存区...${NC}"
git add CHANGELOG.md
git add docs/DOCUMENTATION_POLICY.md
git add docs/history/VERSION_HISTORY.md
git add docs/releases/v0.6.2.1-release-notes.md
git add docs/releases/README.md
git add .github/
git add RELEASE_SUMMARY_v0.6.2.1.md
git add GITHUB_RELEASE_CHECKLIST.md
git add DOCUMENTATION_UPDATE_SUMMARY.md
git add GITHUB_RELEASE_READY_REPORT.md
echo -e "${GREEN}✓ 文件添加完成${NC}"
echo ""

# 步骤4: 显示将要提交的内容
echo -e "${YELLOW}步骤4: 确认提交内容:${NC}"
git status --short
echo ""
read -p "确认继续提交? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}✗ 取消提交${NC}"
    exit 1
fi

# 步骤5: 创建提交
echo -e "${YELLOW}步骤5: 创建提交...${NC}"
git commit -m "docs: comprehensive v0.6.2.1 documentation and GitHub release preparation

- Update CHANGELOG.md with complete v0.6.2.1 infrastructure changes (+350 lines)
- Add documentation governance policy (DOCUMENTATION_POLICY.md)
- Create detailed release notes and summaries
- Add GitHub Actions CI for documentation validation
- Update version history with v0.6.2.1, v0.6.2, v0.6.1
- Add comprehensive release preparation documents
- Prepare GitHub open source publication

Key achievements:
- Configuration governance system documented
- Deployment standardization verified
- Documentation restructuring complete (12 categories)
- All security checks passed
- Code-documentation consistency verified (284 files, 21 commits)

Status: ✅ Ready for public GitHub release"

echo -e "${GREEN}✓ 提交创建成功${NC}"
echo ""

# 步骤6: 创建版本标签
echo -e "${YELLOW}步骤6: 创建版本标签 v0.6.2.1...${NC}"
git tag -a v0.6.2.1 -m "Release v0.6.2.1 - Configuration Governance & Documentation

Major infrastructure and documentation release preparing QueryMind for 
public GitHub open source publication.

Key Features:
- Enterprise-grade configuration governance system
- Standardized deployment infrastructure (deploy/)
- Comprehensive documentation restructuring (12 categories)
- Security cleanup and publication preparation

Changes:
- 284 files changed (+12,856, -36,451 lines)
- 21 commits from v0.6.2
- 8 new configuration governance test suites
- Complete documentation governance established

Status: Production ready, all checks passed
Developer: Po Cheang (po.cheang@gmail.com)"

echo -e "${GREEN}✓ 版本标签创建成功${NC}"
echo ""

# 步骤7: 显示提交和标签信息
echo -e "${YELLOW}步骤7: 验证提交和标签...${NC}"
echo "最新提交:"
git log -1 --oneline
echo ""
echo "版本标签:"
git tag -l "v0.6.2.1" -n5
echo ""

# 步骤8: 推送到GitHub（需要确认）
echo -e "${YELLOW}步骤8: 准备推送到GitHub...${NC}"
echo -e "${RED}警告: 这将把代码推送到远程仓库并公开发布！${NC}"
echo ""
read -p "确认推送到GitHub? (yes/no) " -r
echo
if [[ $REPLY == "yes" ]]; then
    echo "推送主分支..."
    git push origin main
    echo ""
    echo "推送标签..."
    git push origin v0.6.2.1
    echo ""
    echo -e "${GREEN}✓ 推送完成！${NC}"
else
    echo -e "${YELLOW}⚠ 跳过推送步骤${NC}"
    echo "您可以稍后手动推送:"
    echo "  git push origin main"
    echo "  git push origin v0.6.2.1"
fi
echo ""

# 完成
echo "=================================="
echo -e "${GREEN}✅ 发布脚本执行完成！${NC}"
echo "=================================="
echo ""
echo "下一步操作:"
echo "1. 访问 GitHub 仓库的 Releases 页面"
echo "2. 点击 'Draft a new release'"
echo "3. 选择标签: v0.6.2.1"
echo "4. 标题: QueryMind v0.6.2.1 - Configuration Governance & Documentation"
echo "5. 描述: 复制 RELEASE_SUMMARY_v0.6.2.1.md 的内容"
echo "6. 点击 'Publish release'"
echo ""
echo "GitHub Release URL: https://github.com/YOUR_USERNAME/querymind/releases/new?tag=v0.6.2.1"
echo ""
echo "感谢您的耐心！QueryMind现在已经准备好与世界分享了！ 🚀"
