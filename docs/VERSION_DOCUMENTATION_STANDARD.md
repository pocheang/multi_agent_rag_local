# 版本文档标准 / Version Documentation Standard

**文档版本**: v1.0  
**最后更新**: 2026-04-28  
**适用范围**: 所有版本发布

---

## 📋 概述

本文档定义了项目版本发布时必须包含的文档标准，确保每个版本都有完整的企业级文档记录，包括修改细节、变更记录、升级指南等。

---

## 🎯 版本文档要求

### 必需文档（每个版本必须包含）

每个版本发布时，必须创建或更新以下文档：

#### 1. CHANGELOG.md（变更日志）
**位置**: 项目根目录  
**格式**: Keep a Changelog 标准  
**内容要求**:
- 版本号和发布日期
- Added（新增功能）
- Changed（变更内容）
- Fixed（修复问题）
- Deprecated（废弃功能）
- Removed（移除功能）
- Security（安全修复）
- Documentation（文档更新）
- Performance（性能改进）

**示例**:
```markdown
## [0.3.1] - 2026-04-27

### Added
- Enterprise-grade documentation organization system
- Comprehensive document deduplication

### Changed
- Reorganized documentation structure
- Updated all documentation references

### Fixed
- Removed duplicate archive documents
- Fixed documentation inconsistencies
```

#### 2. VERSION_HISTORY.md（版本历史）
**位置**: `docs/VERSION_HISTORY.md`  
**内容要求**:
- 版本信息表格（版本号、日期、类型、主要特性）
- 详细版本说明（目标、改进、统计、文档链接）
- 向后兼容性说明
- 升级指南

**必需章节**:
- 📊 版本信息
- 🎯 版本目标
- ✨ 主要改进/特性
- 📊 统计数据（代码行数、文件数、测试覆盖等）
- 📝 详细文档链接
- ⚠️ 向后兼容性
- 🚀 升级指南

#### 3. 版本完成报告（Version Completion Report）
**位置**: 项目根目录或 `docs/archive/`  
**命名**: `V{VERSION}_COMPLETION_REPORT.md`  
**内容要求**:
- 执行摘要
- 版本更新成果
- 详细变更说明
- 统计数据
- 验证清单
- 后续建议

**必需章节**:
- 📋 执行摘要
- 📊 版本更新成果
- 📈 统计数据
- 🎯 主要成就
- 📁 最终结构（如适用）
- ✅ 验证清单
- 🚀 后续建议
- 📞 维护信息

#### 4. pyproject.toml（版本号更新）
**位置**: 项目根目录  
**要求**: 更新 `version` 字段

```toml
[project]
name = "multi-agent-rag-local"
version = "0.3.1"
```

#### 5. CLAUDE.md（项目指南更新）
**位置**: 项目根目录  
**要求**: 更新项目概述中的版本信息和最新变更

```markdown
## Project Overview

Multi-Agent Local RAG system (v0.3.1) - ...

**Recent Changes (v0.3.1)**: ...
```

---

## 📦 可选文档（根据版本类型）

### 功能版本（Feature Release）

#### 功能设计文档
**位置**: `docs/design/specs/`  
**命名**: `YYYY-MM-DD-{feature-name}-design.md`  
**内容**:
- 功能背景和目标
- 技术设计方案
- API 设计
- 数据模型
- 实现计划
- 测试策略

### 架构版本（Architecture Release）

#### 架构重构报告
**位置**: `docs/archive/`  
**命名**: `REFACTORING_SUMMARY.md` 或 `V{VERSION}_REFACTORING.md`  
**内容**:
- 重构目标和动机
- 架构变更详情
- 模块划分说明
- 依赖关系图
- 迁移指南
- 性能对比

### 修复版本（Patch Release）

#### 修复总结报告
**位置**: `docs/archive/`  
**命名**: `FIXES_SUMMARY.md` 或 `V{VERSION}_FIXES.md`  
**内容**:
- 问题列表（按优先级）
- 修复详情
- 影响范围
- 测试验证
- 回归测试结果

### 文档版本（Documentation Release）

#### 文档组织报告
**位置**: `docs/archive/`  
**命名**: `V{VERSION}_DOCUMENTATION_REPORT.md`  
**内容**:
- 文档结构变更
- 去重合并说明
- 文档清理记录
- 质量改进措施

---

## 🏷️ 版本类型定义

### 版本类型标识

| 类型 | 标识 | 说明 | 示例 |
|------|------|------|------|
| 首次发布 | 🎉 Initial Release | 项目首次公开发布 | v0.1.0 |
| 功能版本 | ⚡ Feature Release | 新增重要功能 | v0.2.0, v0.2.1 |
| 修复版本 | 🔧 Patch Release | 问题修复和小改进 | v0.2.2.1, v0.2.5 |
| 架构版本 | 🏗️ Architecture Release | 架构重构和优化 | v0.3.0 |
| 文档版本 | 📚 Documentation Release | 文档系统改进 | v0.3.1 |
| 安全版本 | 🔒 Security Release | 安全漏洞修复 | - |

### 版本号规则

遵循语义化版本（Semantic Versioning）:

```
MAJOR.MINOR.PATCH

MAJOR: 不兼容的 API 变更
MINOR: 向后兼容的功能新增
PATCH: 向后兼容的问题修复
```

---

## 📝 文档模板

### 版本完成报告模板

```markdown
# v{VERSION} {版本类型}完成报告

**完成日期**: YYYY-MM-DD  
**版本**: v{VERSION}  
**状态**: ✅ 已完成

---

## 📋 执行摘要

[简要说明本版本的主要工作和成果，2-3 段]

---

## 📊 版本更新成果

### 版本号更新
- ✅ pyproject.toml: {old} → {new}
- ✅ CHANGELOG.md: 添加 v{VERSION} 完整条目
- ✅ CLAUDE.md: 更新版本和描述
- ✅ docs/VERSION_HISTORY.md: 添加 v{VERSION} 详细版本信息

### 主要变更
[列出主要变更项]

---

## 📈 统计数据

### 代码变更
| 指标 | 数值 |
|------|------|
| 修改文件 | X 个 |
| 新增代码 | +X 行 |
| 删除代码 | -X 行 |
| 测试覆盖 | X% |

### 文档变更
| 指标 | 数值 |
|------|------|
| 新增文档 | X 个 |
| 更新文档 | X 个 |
| 删除文档 | X 个 |

---

## 🎯 主要成就

### 1. [成就标题]
- ✅ [具体项目]
- ✅ [具体项目]

---

## ✅ 验证清单

### 版本信息验证
- [ ] pyproject.toml 版本号已更新
- [ ] CHANGELOG.md 已添加完整条目
- [ ] VERSION_HISTORY.md 已添加详细信息
- [ ] CLAUDE.md 已更新项目概述

### 代码质量验证
- [ ] 所有测试通过
- [ ] 代码审查完成
- [ ] 文档与代码同步

### 发布准备验证
- [ ] Git 标签已创建
- [ ] 发布说明已准备
- [ ] 升级指南已完成

---

## 🚀 后续建议

### 短期 (1-2 周)
1. [建议项目]

### 中期 (1 个月)
1. [建议项目]

### 长期 (持续)
1. [建议项目]

---

## 📞 维护信息

**文档维护者**: [团队名称]  
**版本**: v{VERSION}  
**完成日期**: YYYY-MM-DD  
**下次审查**: YYYY-MM-DD (3 个月后)

---

**✨ v{VERSION} 版本完成！**
```

---

## 🔄 版本发布流程

### 发布前检查清单

1. **代码准备**
   - [ ] 所有功能开发完成
   - [ ] 所有测试通过（单元测试、集成测试）
   - [ ] 代码审查完成
   - [ ] 性能测试通过（如适用）

2. **文档准备**
   - [ ] 更新 CHANGELOG.md
   - [ ] 更新 VERSION_HISTORY.md
   - [ ] 创建版本完成报告
   - [ ] 更新 pyproject.toml
   - [ ] 更新 CLAUDE.md
   - [ ] 更新 API 文档（如适用）

3. **版本控制**
   - [ ] 创建版本分支（如适用）
   - [ ] 创建 Git 标签
   - [ ] 推送到远程仓库

4. **发布验证**
   - [ ] 在测试环境验证
   - [ ] 升级路径测试
   - [ ] 回滚测试（如适用）

### 发布后任务

1. **文档归档**
   - [ ] 将临时文档移至 `docs/archive/`
   - [ ] 更新 `docs/archive/INDEX.md`
   - [ ] 更新 `docs/ARCHIVE_REFERENCE.md`

2. **通知和沟通**
   - [ ] 发布公告（如适用）
   - [ ] 更新项目 README
   - [ ] 通知相关团队

3. **监控和跟踪**
   - [ ] 监控生产环境（如适用）
   - [ ] 收集用户反馈
   - [ ] 跟踪已知问题

---

## 📂 文档组织结构

### 版本文档存放位置

```
项目根目录/
├── CHANGELOG.md                    # 所有版本的变更日志
├── pyproject.toml                  # 当前版本号
├── CLAUDE.md                       # 项目指南（含最新版本信息）
├── V{VERSION}_COMPLETION_REPORT.md # 最新版本完成报告（临时）
│
└── docs/
    ├── VERSION_HISTORY.md          # 完整版本历史
    ├── VERSION_DOCUMENTATION_STANDARD.md  # 本文档
    │
    ├── design/                     # 设计文档
    │   └── specs/
    │       └── YYYY-MM-DD-{feature}-design.md
    │
    └── archive/                    # 历史文档归档
        ├── INDEX.md                # 归档索引
        ├── V{VERSION}_COMPLETION_REPORT.md  # 历史版本报告
        ├── V{VERSION}_REFACTORING.md        # 重构报告
        ├── V{VERSION}_FIXES.md              # 修复报告
        ├── FIXES_SUMMARY.md                 # 修复总结
        ├── REFACTORING_SUMMARY.md           # 重构总结
        └── RELEASE_v{VERSION}_SUMMARY.md    # 发布总结
```

---

## 🎯 文档质量标准

### 必需元素

每个版本文档必须包含：

1. **元数据**
   - 文档版本
   - 最后更新日期
   - 适用版本范围
   - 维护者信息

2. **清晰的结构**
   - 使用标准化的章节标题
   - 使用表情符号标识（可选但推荐）
   - 使用表格展示数据
   - 使用代码块展示命令

3. **完整的内容**
   - 背景和目标
   - 详细的变更说明
   - 统计数据支持
   - 验证清单
   - 升级指南

4. **交叉引用**
   - 链接到相关文档
   - 引用相关 Git 提交
   - 指向详细设计文档

### 文档审查标准

发布前必须通过以下审查：

- [ ] **准确性**: 所有信息准确无误
- [ ] **完整性**: 包含所有必需章节
- [ ] **一致性**: 与其他文档保持一致
- [ ] **可读性**: 结构清晰，易于理解
- [ ] **可维护性**: 易于更新和扩展

---

## 📊 版本文档示例

### 优秀示例

项目中的优秀版本文档示例：

1. **v0.3.1 完成报告** (`V0.3.1_COMPLETION_REPORT.md`)
   - ✅ 完整的执行摘要
   - ✅ 详细的统计数据
   - ✅ 清晰的验证清单
   - ✅ 实用的后续建议

2. **版本历史** (`docs/VERSION_HISTORY.md`)
   - ✅ 标准化的版本表格
   - ✅ 详细的版本说明
   - ✅ 完整的升级指南
   - ✅ 清晰的版本类型标识

3. **变更日志** (`CHANGELOG.md`)
   - ✅ 遵循 Keep a Changelog 标准
   - ✅ 按类型分类变更
   - ✅ 清晰的版本分隔
   - ✅ 详细的变更描述

---

## 🔧 工具和自动化

### 推荐工具

1. **版本号管理**
   - `bump2version` - 自动更新版本号
   - `semantic-release` - 自动化语义化版本发布

2. **变更日志生成**
   - `git-changelog` - 从 Git 提交生成变更日志
   - `conventional-changelog` - 基于约定式提交生成变更日志

3. **文档验证**
   - `markdownlint` - Markdown 格式检查
   - 自定义脚本 - 验证文档完整性

### 自动化脚本示例

```bash
#!/bin/bash
# scripts/prepare_release.sh

VERSION=$1

# 1. 更新版本号
echo "Updating version to $VERSION..."
sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# 2. 生成变更日志
echo "Generating changelog..."
git-changelog -o CHANGELOG.md

# 3. 创建版本完成报告
echo "Creating completion report..."
cp templates/VERSION_COMPLETION_REPORT_TEMPLATE.md "V${VERSION}_COMPLETION_REPORT.md"

# 4. 更新版本历史
echo "Updating version history..."
# [添加版本历史更新逻辑]

# 5. 创建 Git 标签
echo "Creating git tag..."
git tag -a "v$VERSION" -m "Release v$VERSION"

echo "Release preparation complete!"
```

---

## 📚 参考资源

### 标准和最佳实践

- [Keep a Changelog](https://keepachangelog.com/) - 变更日志标准
- [Semantic Versioning](https://semver.org/) - 语义化版本规范
- [Conventional Commits](https://www.conventionalcommits.org/) - 约定式提交规范

### 项目文档

- [ENTERPRISE_DOCUMENTATION_STANDARD.md](ENTERPRISE_DOCUMENTATION_STANDARD.md) - 企业文档标准
- [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) - 文档政策
- [DOCUMENTATION_MAINTENANCE.md](DOCUMENTATION_MAINTENANCE.md) - 维护流程

---

## 🔄 持续改进

### 定期审查

每季度审查版本文档标准：

1. **评估当前标准的有效性**
   - 文档是否满足需求？
   - 流程是否高效？
   - 是否有改进空间？

2. **收集反馈**
   - 开发团队反馈
   - 用户反馈
   - 文档维护者反馈

3. **更新标准**
   - 根据反馈调整标准
   - 更新模板和示例
   - 改进自动化工具

### 版本文档指标

跟踪以下指标以评估文档质量：

- 文档完整性（必需文档覆盖率）
- 文档准确性（错误报告数量）
- 文档可用性（用户满意度）
- 文档维护成本（更新时间）

---

**维护者**: Bronit Team  
**文档版本**: v1.0  
**最后更新**: 2026-04-28  
**下次审查**: 2026-07-28 (3 个月后)
