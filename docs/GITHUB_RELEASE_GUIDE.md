# 📝 GitHub Release 创建指南

## 🎯 创建 v0.2.5 Release

### 步骤 1: 访问 GitHub Release 页面

打开浏览器，访问：
```
https://github.com/pocheang/multi_agent_rag_local/releases/new
```

或者：
1. 访问你的仓库: https://github.com/pocheang/multi_agent_rag_local
2. 点击右侧的 "Releases"
3. 点击 "Draft a new release"

---

### 步骤 2: 填写 Release 信息

#### 2.1 选择标签 (Tag)
- **Tag**: 选择 `v0.2.5`（已存在）
- **Target**: `main` 分支

#### 2.2 填写标题 (Title)
```
v0.2.5 - Critical Logic Fixes and Performance Improvements
```

#### 2.3 填写描述 (Description)

复制以下内容到描述框：

---

## 🎯 Overview

v0.2.5 is a critical quality improvement release that fixes 18 logic issues across routing, retrieval, and concurrent execution, delivering significant performance gains and enhanced reliability.

---

## 🔧 Fixed Issues (18 Total)

### Critical (P0) - 2 Issues
- **[P0-001]** Retrieval strategy parameter passing inconsistency - Fixed document source filtering
- **[P0-002]** Hybrid routing concurrent execution error - **100-500ms latency reduction**

### High Priority (P1) - 5 Issues
- **[P1-001]** Router decision vs adaptive planner conflict - Router decisions now preserved
- **[P1-002]** Evidence sufficiency circular dependency - Cleaned up routing logic
- **[P1-003]** Query rewrite variant deduplication - **10-30% reduction in LLM API calls**
- **[P1-004]** Query rewrite LLM timeout control - **500-2000ms P99 latency improvement**
- **[P1-005]** State access parameter validation - Added clear error messages

### Medium Priority (P2) - 9 Issues
- Parent-child deduplication score preservation
- Smalltalk fast-path state inconsistency
- Web fallback semantic confusion
- Hybrid future cancellation incomplete
- Reranker fallback score normalization
- Citation sentence splitting improvement
- Web domain allowlist semantic clarity
- Graph signal score calculation optimization
- TTLCache concurrent performance optimization

### Low Priority (P3) - 2 Issues
- Neo4j allowed_sources filtering verification
- BM25 filtering logic clarification

---

## 🚀 Performance Improvements

| Metric | Improvement | Impact |
|--------|-------------|--------|
| LLM API Calls | **-10-30%** | Reduced redundant calls via deduplication |
| Hybrid Mode Latency | **-100-500ms** | Eliminated duplicate graph queries |
| P99 Latency | **-500-2000ms** | Added timeout controls |
| Concurrent Performance | **Improved** | Optimized TTLCache with lazy cleanup |

---

## ✅ Quality Assurance

- **Tests**: 29/29 passing (100%)
- **Regression Coverage**: Comprehensive test coverage for all fixes
- **Code Changes**: 19 files modified (604 insertions, 141 deletions)

---

## 📚 Documentation

Extensive documentation included:
- [Detailed Changelog](docs/CHANGELOG_2026-04-27.md)
- [Fix Summary](docs/FINAL_FIXES_SUMMARY_2026-04-27.md)
- [Fix Index](docs/FIXES_INDEX.md)
- [Deep Code Review](docs/DEEP_CODE_REVIEW_2026-04-27.md)
- [Version History](docs/VERSION_HISTORY.md)
- [Release Summary](docs/RELEASE_SUMMARY_v0.2.5.md)

---

## 🔄 Upgrade Guide

```bash
# Pull latest changes
git pull origin main

# Checkout v0.2.5
git checkout v0.2.5

# No breaking changes - all fixes are backward compatible
# Restart your services
uvicorn app.api.main:app --reload
```

**No configuration changes required.** All fixes are backward compatible.

---

## 📦 What's Next (v0.3.0)

- Code refactoring for better maintainability
- New features based on user feedback
- Continued performance optimization

See [REFACTORING_PLAN.md](docs/REFACTORING_PLAN.md) for details.

---

**Full Changelog**: https://github.com/pocheang/multi_agent_rag_local/compare/v0.2.4...v0.2.5

---

### 步骤 3: 设置 Release 选项

- ✅ **Set as the latest release** (勾选)
- ⬜ **Set as a pre-release** (不勾选)
- ⬜ **Create a discussion for this release** (可选)

---

### 步骤 4: 发布

点击 **"Publish release"** 按钮

---

## ✅ 完成后验证

发布后，访问以下链接验证：
- Release 页面: https://github.com/pocheang/multi_agent_rag_local/releases/tag/v0.2.5
- 所有 Releases: https://github.com/pocheang/multi_agent_rag_local/releases

---

## 📋 备用方案：使用 GitHub CLI

如果你安装了 GitHub CLI (`gh`)，可以使用命令行创建 Release：

```bash
gh release create v0.2.5 \
  --title "v0.2.5 - Critical Logic Fixes and Performance Improvements" \
  --notes-file docs/GITHUB_RELEASE_v0.2.5.md \
  --latest
```

---

## 🎊 完成！

Release 创建后，用户可以：
- 在 GitHub 上查看 Release 说明
- 下载源代码压缩包
- 查看完整的变更历史

---

**准备好的文件**:
- ✅ Release 内容: [docs/GITHUB_RELEASE_v0.2.5.md](GITHUB_RELEASE_v0.2.5.md)
- ✅ 创建指南: 本文件

**下一步**: 访问 https://github.com/pocheang/multi_agent_rag_local/releases/new 开始创建！
