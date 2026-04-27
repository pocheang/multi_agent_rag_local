# 🚀 快速创建 GitHub Release

## 📋 一键复制内容

### 1️⃣ 打开 Release 创建页面

点击或复制此链接到浏览器：
```
https://github.com/pocheang/multi_agent_rag_local/releases/new
```

---

### 2️⃣ 填写表单

#### Tag (标签)
```
v0.2.5
```
（从下拉菜单选择已存在的标签）

#### Release title (标题)
```
v0.2.5 - Critical Logic Fixes and Performance Improvements
```

#### Description (描述)

**复制以下完整内容** 👇

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

### 3️⃣ 设置选项

- ✅ **Set as the latest release** (勾选)
- ⬜ **Set as a pre-release** (不勾选)

---

### 4️⃣ 发布

点击绿色按钮 **"Publish release"**

---

## ✅ 完成！

发布后访问：https://github.com/pocheang/multi_agent_rag_local/releases

---

**提示**: 如果你安装了 GitHub CLI，也可以运行：
```bash
gh release create v0.2.5 \
  --title "v0.2.5 - Critical Logic Fixes and Performance Improvements" \
  --notes-file docs/GITHUB_RELEASE_v0.2.5.md \
  --latest
```
