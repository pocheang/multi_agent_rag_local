# 版本文档管理指南 / Version Documentation Management Guide

**文档版本**: v1.0  
**最后更新**: 2026-04-28  
**目标读者**: 开发团队、发布经理、文档维护者

---

## 📋 概述

本指南提供版本发布时的文档管理实践指南，确保每个版本都有完整、准确、易于维护的企业级文档。

---

## 🎯 文档管理目标

### 核心原则

1. **完整性**: 每个版本都有完整的文档记录
2. **准确性**: 所有文档信息准确无误
3. **一致性**: 文档格式和内容保持一致
4. **可追溯性**: 能够追溯每个版本的变更历史
5. **可维护性**: 文档易于更新和维护

### 文档价值

- **开发团队**: 了解代码变更和架构演进
- **运维团队**: 掌握部署和升级流程
- **用户**: 了解新功能和变更影响
- **管理层**: 评估项目进展和质量
- **审计**: 提供完整的变更记录

---

## 📚 版本文档体系

### 文档层次结构

```
版本文档体系
│
├── 核心文档（必需）
│   ├── CHANGELOG.md              # 所有版本的变更日志
│   ├── VERSION_HISTORY.md        # 完整版本历史
│   ├── pyproject.toml            # 当前版本号
│   ├── CLAUDE.md                 # 项目指南
│   └── V{VERSION}_COMPLETION_REPORT.md  # 版本完成报告
│
├── 类型特定文档（按需）
│   ├── 功能版本
│   │   ├── 功能设计文档
│   │   └── API 文档更新
│   ├── 架构版本
│   │   ├── 架构重构报告
│   │   └── 模块文档
│   ├── 修复版本
│   │   └── 修复总结报告
│   └── 文档版本
│       └── 文档组织报告
│
└── 支持文档（可选）
    ├── 升级指南
    ├── 迁移脚本
    ├── 性能报告
    └── 测试报告
```

### 文档存放位置

| 文档类型 | 存放位置 | 生命周期 |
|---------|---------|---------|
| 核心版本文档 | 项目根目录 | 当前版本在根目录，历史版本移至 archive/ |
| 设计文档 | docs/design/specs/ | 长期保留 |
| 历史文档 | docs/archive/ | 永久归档 |
| 项目文档 | docs/project/ | 长期保留并更新 |
| 运维文档 | docs/operations/ | 长期保留并更新 |

---

## 🔄 版本发布文档流程

### 阶段 1: 发布准备（Release Preparation）

#### 1.1 确定版本号和类型

```bash
# 确定版本号（遵循语义化版本）
CURRENT_VERSION=$(grep 'version = ' pyproject.toml | cut -d'"' -f2)
NEW_VERSION="0.3.2"  # 根据变更类型确定

# 确定版本类型
VERSION_TYPE="patch"  # major | minor | patch
RELEASE_TYPE="修复版本"  # 功能版本 | 架构版本 | 修复版本 | 文档版本
```

#### 1.2 收集变更信息

```bash
# 查看自上次发布以来的提交
git log v0.3.1..HEAD --oneline

# 查看文件变更
git diff v0.3.1..HEAD --stat

# 查看具体变更
git diff v0.3.1..HEAD
```

#### 1.3 创建版本分支（可选）

```bash
# 对于重要版本，创建发布分支
git checkout -b release/v0.3.2
```

---

### 阶段 2: 文档创建（Documentation Creation）

#### 2.1 更新 CHANGELOG.md

```markdown
## [0.3.2] - 2026-04-28

### Added
- [列出新增功能]

### Changed
- [列出变更内容]

### Fixed
- [列出修复问题]

### Documentation
- [列出文档更新]
```

**最佳实践**:
- 使用清晰、简洁的语言
- 按类型分组变更
- 包含相关的 issue/PR 编号
- 突出重要变更

#### 2.2 更新 VERSION_HISTORY.md

```markdown
## v0.3.2 (2026-04-28)

### 📊 版本信息
- **发布日期**: 2026-04-28
- **版本类型**: 修复版本（Patch Release）
- **Git 标签**: `v0.3.2`

### 🎯 版本目标
[描述本版本的主要目标]

### ✨ 主要改进
[列出主要改进项]

### 📊 统计数据
[提供统计数据]

### 📝 详细文档
- [链接到相关文档]

### ⚠️ 向后兼容性
[说明兼容性情况]

### 🚀 升级指南
[提供升级步骤]
```

#### 2.3 创建版本完成报告

```bash
# 使用模板创建报告
cp docs/templates/VERSION_COMPLETION_REPORT_TEMPLATE.md V0.3.2_COMPLETION_REPORT.md

# 编辑报告，填写所有章节
```

**必需章节**:
- 📋 执行摘要
- 📊 版本更新成果
- 📈 统计数据
- 🎯 主要成就
- ✅ 验证清单
- 🚀 后续建议
- 📞 维护信息

#### 2.4 更新 pyproject.toml

```toml
[project]
name = "multi-agent-rag-local"
version = "0.3.2"  # 更新版本号
```

#### 2.5 更新 CLAUDE.md

```markdown
## Project Overview

Multi-Agent Local RAG system (v0.3.2) - ...

**Recent Changes (v0.3.2)**: [描述最新变更]
```

#### 2.6 创建类型特定文档（按需）

**功能版本**: 创建功能设计文档
```bash
# 在 docs/design/specs/ 创建设计文档
touch docs/design/specs/2026-04-28-new-feature-design.md
```

**架构版本**: 创建架构重构报告
```bash
# 在 docs/archive/ 创建重构报告
touch docs/archive/V0.3.2_REFACTORING.md
```

**修复版本**: 创建修复总结报告
```bash
# 在 docs/archive/ 创建修复报告
touch docs/archive/V0.3.2_FIXES.md
```

---

### 阶段 3: 文档审查（Documentation Review）

#### 3.1 使用检查清单

```bash
# 复制检查清单
cp docs/VERSION_DOCUMENTATION_CHECKLIST.md V0.3.2_CHECKLIST.md

# 逐项检查并标记
```

#### 3.2 验证文档完整性

```bash
# 检查所有必需文档是否存在
ls -la | grep -E "CHANGELOG|pyproject|CLAUDE"
ls -la docs/ | grep -E "VERSION_HISTORY"
ls -la | grep "V0.3.2_COMPLETION_REPORT"

# 检查文档格式
markdownlint CHANGELOG.md
markdownlint docs/VERSION_HISTORY.md
markdownlint V0.3.2_COMPLETION_REPORT.md
```

#### 3.3 验证链接有效性

```bash
# 检查文档中的链接
# 可以使用 markdown-link-check 工具
markdown-link-check CHANGELOG.md
markdown-link-check docs/VERSION_HISTORY.md
```

#### 3.4 验证数据准确性

- [ ] 版本号在所有文档中一致
- [ ] 日期准确
- [ ] 统计数据准确
- [ ] Git 提交哈希正确
- [ ] 链接指向正确的文档

---

### 阶段 4: 版本控制（Version Control）

#### 4.1 提交文档变更

```bash
# 添加所有文档变更
git add CHANGELOG.md
git add docs/VERSION_HISTORY.md
git add V0.3.2_COMPLETION_REPORT.md
git add pyproject.toml
git add CLAUDE.md
git add docs/VERSION_DOCUMENTATION_CHECKLIST.md

# 提交变更
git commit -m "docs: update documentation for v0.3.2 release

- Update CHANGELOG.md with v0.3.2 changes
- Add v0.3.2 entry to VERSION_HISTORY.md
- Create V0.3.2_COMPLETION_REPORT.md
- Update version in pyproject.toml to 0.3.2
- Update CLAUDE.md with recent changes
"
```

#### 4.2 创建 Git 标签

```bash
# 创建带注释的标签
git tag -a v0.3.2 -m "Release v0.3.2

Major changes:
- [列出主要变更]

See V0.3.2_COMPLETION_REPORT.md for details.
"

# 验证标签
git tag -l -n9 v0.3.2
```

#### 4.3 推送到远程仓库

```bash
# 推送提交
git push origin main  # 或 release/v0.3.2

# 推送标签
git push origin v0.3.2

# 或推送所有标签
git push origin --tags
```

---

### 阶段 5: 发布后处理（Post-Release）

#### 5.1 归档文档

```bash
# 将版本完成报告移至 archive/
mv V0.3.2_COMPLETION_REPORT.md docs/archive/

# 更新 archive 索引
# 编辑 docs/archive/INDEX.md
```

#### 5.2 更新文档索引

```bash
# 更新 docs/archive/INDEX.md
# 添加新归档文档的条目

# 更新 docs/ARCHIVE_REFERENCE.md
# 更新文档列表和统计
```

#### 5.3 清理临时文件

```bash
# 删除检查清单（如果不需要保留）
rm V0.3.2_CHECKLIST.md

# 删除其他临时文件
rm -f *.tmp *.bak
```

#### 5.4 验证发布

```bash
# 验证标签已推送
git ls-remote --tags origin | grep v0.3.2

# 验证文档在远程仓库中
git ls-tree -r v0.3.2 --name-only | grep -E "CHANGELOG|VERSION_HISTORY"
```

---

## 📊 文档质量保证

### 质量检查清单

#### 内容质量
- [ ] 所有信息准确无误
- [ ] 描述清晰易懂
- [ ] 技术术语使用正确
- [ ] 包含必要的示例
- [ ] 数据有来源支持

#### 格式质量
- [ ] 遵循 Markdown 规范
- [ ] 使用统一的标题层级
- [ ] 代码块有语言标识
- [ ] 表格格式正确
- [ ] 列表格式一致

#### 结构质量
- [ ] 章节组织合理
- [ ] 信息层次清晰
- [ ] 导航便捷
- [ ] 交叉引用完整

#### 可维护性
- [ ] 元数据完整
- [ ] 版本信息明确
- [ ] 维护者信息清晰
- [ ] 更新日期准确

### 自动化检查

```bash
# 创建文档质量检查脚本
cat > scripts/check_version_docs.sh << 'EOF'
#!/bin/bash

VERSION=$1

echo "Checking documentation for version $VERSION..."

# 检查必需文件
echo "Checking required files..."
[ -f "CHANGELOG.md" ] && echo "✓ CHANGELOG.md" || echo "✗ CHANGELOG.md missing"
[ -f "docs/VERSION_HISTORY.md" ] && echo "✓ VERSION_HISTORY.md" || echo "✗ VERSION_HISTORY.md missing"
[ -f "V${VERSION}_COMPLETION_REPORT.md" ] && echo "✓ Completion report" || echo "✗ Completion report missing"

# 检查版本号一致性
echo "Checking version consistency..."
grep -q "version = \"$VERSION\"" pyproject.toml && echo "✓ pyproject.toml" || echo "✗ pyproject.toml version mismatch"
grep -q "## \[$VERSION\]" CHANGELOG.md && echo "✓ CHANGELOG.md" || echo "✗ CHANGELOG.md version missing"
grep -q "## v$VERSION" docs/VERSION_HISTORY.md && echo "✓ VERSION_HISTORY.md" || echo "✗ VERSION_HISTORY.md version missing"

# 检查 Git 标签
echo "Checking git tag..."
git tag -l | grep -q "v$VERSION" && echo "✓ Git tag exists" || echo "✗ Git tag missing"

echo "Documentation check complete!"
EOF

chmod +x scripts/check_version_docs.sh

# 运行检查
./scripts/check_version_docs.sh 0.3.2
```

---

## 🎯 最佳实践

### 文档编写

1. **及时记录**: 在开发过程中就记录变更，不要等到发布前
2. **清晰描述**: 使用清晰、简洁的语言，避免技术行话
3. **提供示例**: 对于复杂的变更，提供代码示例或配置示例
4. **说明影响**: 明确说明变更对用户的影响
5. **链接相关**: 链接到相关的 issue、PR、设计文档

### 版本管理

1. **语义化版本**: 严格遵循语义化版本规范
2. **一致性**: 确保所有文档中的版本号一致
3. **标签规范**: 使用规范的 Git 标签格式（v{VERSION}）
4. **分支策略**: 对于重要版本，使用发布分支

### 文档维护

1. **定期审查**: 每季度审查文档的准确性和完整性
2. **及时更新**: 发现错误立即修正
3. **归档管理**: 及时归档历史文档
4. **索引维护**: 保持文档索引的准确性

### 团队协作

1. **明确责任**: 指定文档维护者
2. **审查流程**: 建立文档审查流程
3. **知识共享**: 定期分享文档最佳实践
4. **工具使用**: 使用自动化工具提高效率

---

## 🔧 工具和模板

### 推荐工具

#### 文档编写
- **Markdown 编辑器**: VS Code, Typora, Mark Text
- **格式检查**: markdownlint, prettier
- **链接检查**: markdown-link-check
- **拼写检查**: cspell, aspell

#### 版本管理
- **版本号管理**: bump2version, semantic-release
- **变更日志生成**: git-changelog, conventional-changelog
- **Git 工具**: git, gh (GitHub CLI)

#### 自动化
- **CI/CD**: GitHub Actions, GitLab CI
- **脚本**: Bash, Python
- **任务运行**: Make, Task

### 文档模板

项目提供以下模板：

1. **版本完成报告模板**: `docs/templates/VERSION_COMPLETION_REPORT_TEMPLATE.md`
2. **功能设计文档模板**: `docs/templates/FEATURE_DESIGN_TEMPLATE.md`
3. **架构重构报告模板**: `docs/templates/REFACTORING_REPORT_TEMPLATE.md`
4. **修复总结报告模板**: `docs/templates/FIXES_REPORT_TEMPLATE.md`

### 自动化脚本

```bash
# 创建版本发布脚本
cat > scripts/release.sh << 'EOF'
#!/bin/bash

set -e

VERSION=$1
TYPE=$2  # major | minor | patch

if [ -z "$VERSION" ] || [ -z "$TYPE" ]; then
    echo "Usage: $0 <version> <type>"
    echo "Example: $0 0.3.2 patch"
    exit 1
fi

echo "Preparing release v$VERSION ($TYPE)..."

# 1. 更新版本号
echo "Updating version number..."
sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# 2. 创建版本完成报告
echo "Creating completion report..."
cp docs/templates/VERSION_COMPLETION_REPORT_TEMPLATE.md "V${VERSION}_COMPLETION_REPORT.md"
sed -i "s/{VERSION}/$VERSION/g" "V${VERSION}_COMPLETION_REPORT.md"
sed -i "s/YYYY-MM-DD/$(date +%Y-%m-%d)/g" "V${VERSION}_COMPLETION_REPORT.md"

# 3. 提示更新文档
echo "Please update the following files:"
echo "  - CHANGELOG.md"
echo "  - docs/VERSION_HISTORY.md"
echo "  - CLAUDE.md"
echo "  - V${VERSION}_COMPLETION_REPORT.md"
echo ""
echo "After updating, run:"
echo "  git add ."
echo "  git commit -m 'docs: update documentation for v$VERSION release'"
echo "  git tag -a v$VERSION -m 'Release v$VERSION'"
echo "  git push origin main --tags"

EOF

chmod +x scripts/release.sh
```

---

## 📚 参考资源

### 标准和规范
- [Keep a Changelog](https://keepachangelog.com/) - 变更日志标准
- [Semantic Versioning](https://semver.org/) - 语义化版本规范
- [Conventional Commits](https://www.conventionalcommits.org/) - 约定式提交规范

### 项目文档
- [VERSION_DOCUMENTATION_STANDARD.md](VERSION_DOCUMENTATION_STANDARD.md) - 版本文档标准
- [VERSION_DOCUMENTATION_CHECKLIST.md](VERSION_DOCUMENTATION_CHECKLIST.md) - 版本文档检查清单
- [ENTERPRISE_DOCUMENTATION_STANDARD.md](ENTERPRISE_DOCUMENTATION_STANDARD.md) - 企业文档标准
- [DOCUMENTATION_MAINTENANCE.md](DOCUMENTATION_MAINTENANCE.md) - 文档维护流程

### 外部资源
- [GitHub Docs - Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [GitLab Docs - Release management](https://docs.gitlab.com/ee/user/project/releases/)
- [Write the Docs](https://www.writethedocs.org/) - 文档社区

---

## 🔄 持续改进

### 反馈收集

定期收集以下反馈：

1. **开发团队**: 文档流程是否高效？
2. **用户**: 文档是否清晰易懂？
3. **运维团队**: 升级指南是否完整？
4. **管理层**: 文档是否满足审计需求？

### 流程优化

每季度评估和优化：

1. **流程效率**: 是否有可以自动化的步骤？
2. **文档质量**: 是否有常见的质量问题？
3. **工具使用**: 是否有更好的工具？
4. **模板更新**: 模板是否需要改进？

### 指标跟踪

跟踪以下指标：

- 文档完成时间
- 文档错误率
- 文档更新频率
- 用户满意度

---

## 📞 支持和帮助

### 遇到问题？

1. **查看文档**: 先查看相关文档和模板
2. **检查示例**: 参考历史版本的文档
3. **咨询团队**: 联系文档维护者
4. **提出改进**: 提交 issue 或 PR

### 联系方式

- **文档维护者**: Bronit Team
- **问题反馈**: GitHub Issues
- **改进建议**: Pull Requests

---

**维护者**: Bronit Team  
**文档版本**: v1.0  
**最后更新**: 2026-04-28  
**下次审查**: 2026-07-28 (3 个月后)
