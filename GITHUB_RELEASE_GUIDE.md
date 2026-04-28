# 如何在 GitHub 上创建 v0.3.1 Release

## 📋 准备工作

✅ VERSION 文件已更新到 0.3.1
✅ Git 标签 v0.3.1 已创建并推送
✅ Release 说明文档已创建 (RELEASE_v0.3.1.md)
✅ 所有更改已推送到 GitHub

---

## 🚀 创建 Release 步骤

### 方法 1: 通过 GitHub 网页界面（推荐）

1. **访问 Releases 页面**
   - 打开: https://github.com/pocheang/multi_agent_rag_local/releases
   - 点击 "Draft a new release" 按钮

2. **选择标签**
   - 在 "Choose a tag" 下拉框中选择 `v0.3.1`
   - 标签已经存在，会自动识别

3. **填写 Release 标题**
   ```
   v0.3.1 - Enterprise Documentation System
   ```

4. **填写 Release 说明**
   - 复制 `RELEASE_v0.3.1.md` 的内容
   - 粘贴到 "Describe this release" 文本框
   - 或者直接引用: "See [RELEASE_v0.3.1.md](RELEASE_v0.3.1.md) for details"

5. **设置 Release 选项**
   - ✅ 勾选 "Set as the latest release"
   - ⬜ 不勾选 "Set as a pre-release"（这是正式版本）

6. **发布**
   - 点击 "Publish release" 按钮

---

### 方法 2: 使用 GitHub CLI（如果已安装）

```bash
# 安装 GitHub CLI (如果还没安装)
# Windows: winget install --id GitHub.cli
# macOS: brew install gh
# Linux: 参考 https://github.com/cli/cli#installation

# 登录 GitHub
gh auth login

# 创建 Release
gh release create v0.3.1 \
  --title "v0.3.1 - Enterprise Documentation System" \
  --notes-file RELEASE_v0.3.1.md \
  --latest

# 或者使用简短说明
gh release create v0.3.1 \
  --title "v0.3.1 - Enterprise Documentation System" \
  --notes "See [RELEASE_v0.3.1.md](RELEASE_v0.3.1.md) for complete release notes." \
  --latest
```

---

## 📝 Release 说明内容摘要

### 标题
```
v0.3.1 - Enterprise Documentation System
```

### 简短描述（可选，用于社交媒体）
```
🎉 v0.3.1 发布！建立了完整的企业级文档管理体系，包括：
✅ 版本文档标准和指南
✅ 5个文档模板
✅ 100%历史版本覆盖
✅ 版本计划框架
```

### 主要亮点（用于 Release 顶部）
```markdown
## 🎯 Release Highlights

v0.3.1 establishes a complete **enterprise-grade documentation management system**:

✅ **Complete Version Documentation System**
- Documentation standards, guides, and checklists
- 5 document templates for different release types
- 100% documentation coverage for all 9 historical versions

✅ **Version Planning Framework**
- Planning documentation with Before/Current/Future structure
- Comprehensive planning index for all versions

✅ **Team Standardization**
- Updated all documentation to reflect **Bronit Team**
- Standardized metadata across 33+ files
```

---

## ✅ 验证 Release

创建 Release 后，验证以下内容：

1. **Release 页面**
   - 访问: https://github.com/pocheang/multi_agent_rag_local/releases/tag/v0.3.1
   - 确认标题、说明、日期正确

2. **标签关联**
   - 确认 Release 关联到正确的 commit (5f92b1c)
   - 确认标签 v0.3.1 显示正确

3. **Latest Release 标记**
   - 确认 v0.3.1 显示为 "Latest" release
   - 在项目主页右侧应该显示最新 release

4. **文档链接**
   - 点击 Release 说明中的文档链接
   - 确认所有链接都能正确跳转

---

## 📊 Release 统计

创建后，您的项目将有：

- **总 Releases**: 10 个（v0.1.0 到 v0.3.1）
- **最新 Release**: v0.3.1
- **Release 类型**: 📚 Documentation Release
- **发布日期**: 2026-04-28

---

## 🔗 相关链接

- **GitHub Repository**: https://github.com/pocheang/multi_agent_rag_local
- **Releases 页面**: https://github.com/pocheang/multi_agent_rag_local/releases
- **v0.3.1 标签**: https://github.com/pocheang/multi_agent_rag_local/releases/tag/v0.3.1
- **完整 Release 说明**: [RELEASE_v0.3.1.md](RELEASE_v0.3.1.md)

---

## 💡 提示

1. **Release 说明格式**: GitHub 支持 Markdown 格式，所有格式都会正确渲染
2. **编辑 Release**: 创建后仍可以编辑 Release 说明
3. **删除 Release**: 如果需要，可以删除 Release（但标签会保留）
4. **通知**: Release 创建后，watching 该仓库的用户会收到通知

---

**准备好了吗？现在就去创建 Release 吧！** 🚀
