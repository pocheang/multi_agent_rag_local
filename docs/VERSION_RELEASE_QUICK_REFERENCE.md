# 版本发布文档快速参考 / Version Release Documentation Quick Reference

**最后更新**: 2026-04-28


**版本**: v1.0  
**更新**: 2026-04-28

---

## 🚀 发布前快速检查

### 必需文档（5个）

```bash
# 1. 更新 CHANGELOG.md
## [X.Y.Z] - YYYY-MM-DD
### Added / Changed / Fixed / Documentation

# 2. 更新 VERSION_HISTORY.md
## vX.Y.Z (YYYY-MM-DD)
### 📊 版本信息 / 🎯 版本目标 / ✨ 主要改进

# 3. 创建版本完成报告
VX.Y.Z_COMPLETION_REPORT.md

# 4. 更新版本号
pyproject.toml: version = "X.Y.Z"

# 5. 更新项目指南
CLAUDE.md: Recent Changes (vX.Y.Z)
```

### Git 操作

```bash
# 提交文档
git add CHANGELOG.md docs/VERSION_HISTORY.md VX.Y.Z_COMPLETION_REPORT.md pyproject.toml CLAUDE.md
git commit -m "docs: update documentation for vX.Y.Z release"

# 创建标签
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# 推送
git push origin main --tags
```

---

## 📋 版本类型速查

| 类型 | 标识 | 版本号变化 | 额外文档 |
|------|------|-----------|---------|
| 🎉 首次发布 | Initial | 0.1.0 | - |
| ⚡ 功能版本 | Feature | X.Y.0 | 功能设计文档 |
| 🔧 修复版本 | Patch | X.Y.Z | 修复总结报告 |
| 🏗️ 架构版本 | Architecture | X.Y.0 | 架构重构报告 |
| 📚 文档版本 | Documentation | X.Y.Z | 文档组织报告 |
| 🔒 安全版本 | Security | X.Y.Z | 安全公告 |

---

## 📝 文档模板位置

```
docs/templates/
├── VERSION_COMPLETION_REPORT_TEMPLATE.md
├── FEATURE_DESIGN_TEMPLATE.md
├── REFACTORING_REPORT_TEMPLATE.md
└── FIXES_REPORT_TEMPLATE.md
```

---

## 🔗 完整文档链接

- 📘 [VERSION_DOCUMENTATION_STANDARD.md](docs/VERSION_DOCUMENTATION_STANDARD.md) - 详细标准
- 📗 [VERSION_DOCUMENTATION_GUIDE.md](docs/VERSION_DOCUMENTATION_GUIDE.md) - 完整流程
- 📙 [VERSION_DOCUMENTATION_CHECKLIST.md](docs/VERSION_DOCUMENTATION_CHECKLIST.md) - 检查清单

---

## ⚡ 快速命令

```bash
# 查看当前版本
grep 'version = ' pyproject.toml

# 查看最近提交
git log --oneline -10

# 查看自上次发布的变更
git log vX.Y.Z..HEAD --oneline

# 运行文档检查
./scripts/check_version_docs.sh X.Y.Z

# 创建发布
./scripts/release.sh X.Y.Z patch
```

---

**提示**: 发布前务必运行完整的检查清单！
