# dependencies.py 拆分建议

## 📊 当前状态

- **总行数**: 2000 行
- **辅助函数**: 68 个
- **问题**: 单文件过大，难以维护

---

## 🎯 拆分方案

### 方案 A: 按功能域拆分（推荐）

将 dependencies.py 拆分为 7 个模块：

```
app/api/
├── dependencies.py (核心依赖，~200 行)
├── utils/
│   ├── __init__.py
│   ├── auth_helpers.py (~300 行) - 认证相关
│   ├── query_helpers.py (~400 行) - 查询相关
│   ├── session_helpers.py (~200 行) - 会话相关
│   ├── document_helpers.py (~400 行) - 文档相关
│   ├── memory_helpers.py (~150 行) - 记忆相关
│   ├── admin_helpers.py (~250 行) - 管理员相关
│   └── response_helpers.py (~100 行) - 响应相关
```

#### 1. **dependencies.py** (核心，~200 行)
保留内容：
- 全局导入
- 服务实例（auth_service, query_guard, etc.）
- 最常用的 3-5 个辅助函数
- 从 utils 模块导入并重新导出

#### 2. **utils/auth_helpers.py** (~300 行)
包含函数：
- `_require_user()`
- `_require_user_and_token()`
- `_require_permission()`
- `_set_auth_cookie()`
- `_clear_auth_cookie()`
- `_enforce_cookie_csrf()`
- `_resolve_auth_token()`
- `_auth_cookie_name()`
- `_auth_cookie_samesite()`
- `_request_origin()`
- `_origin_is_allowed()`
- `_is_valid_admin_approval_token()`
- `_is_valid_admin_approval_token_for_actor()`

#### 3. **utils/query_helpers.py** (~400 行)
包含函数：
- `_query_limiter_key()`
- `_is_overload_mode()`
- `_query_cache_key()`
- `_run_with_query_runtime()`
- `_user_api_settings_for_runtime()`
- `_query_model_fingerprint_for_user()`
- `_trace_id()`
- `_call_with_supported_kwargs()`
- `_maybe_sign_response()`
- `_normalize_agent_class_hint()`
- `_normalize_retrieval_strategy()`
- `_resolve_effective_agent_class()`
- `_effective_strategy_for_session()`
- `_launch_shadow_run()`

#### 4. **utils/session_helpers.py** (~200 行)
包含函数：
- `_history_store_for_user()`
- `_require_valid_session_id()`
- `_require_existing_session_for_query()`
- `_latest_answer_for_same_question()`

#### 5. **utils/document_helpers.py** (~400 行)
包含函数：
- `_is_source_allowed_for_user()`
- `_is_source_manageable_for_user()`
- `_list_visible_documents_for_user()`
- `_allowed_sources_for_user()`
- `_allowed_sources_for_visible_filenames()`
- `_source_mtime_ns()`
- `_visible_index_fingerprint_for_user()`
- `_vector_context_from_citations()`
- `_enforce_result_source_scope()`
- `_source_scope_needs_resynthesis()`
- `_resynthesize_after_source_scope()`
- `_list_visible_pdf_names_for_user()`
- `_visible_doc_chunks_by_filename_for_user()`
- `_is_file_inventory_question()`
- `_build_user_file_inventory_answer()`
- `_guess_agent_class_for_upload()`
- `_is_probably_valid_upload_signature()`

#### 6. **utils/memory_helpers.py** (~150 行)
包含函数：
- `_memory_store_for_user()`
- `_memory_signals_from_result()`
- `_build_memory_context_for_session()`
- `_promote_long_term_memory()`

#### 7. **utils/admin_helpers.py** (~250 行)
包含函数：
- `_parse_audit_ts()`
- `_filter_audit_rows()`
- `_parse_request_ts()`
- `_extract_grounding_support_from_detail()`
- `_load_benchmark_queries()`
- `_check_ollama_ready()`
- `_check_chroma_ready()`
- `_runtime_diagnostics_summary()`

#### 8. **utils/response_helpers.py** (~100 行)
包含函数：
- `_sse_response()`
- `_mask_api_key()`
- `_api_settings_view()`
- `_admin_model_settings_view()`
- `_request_meta()`
- `_client_ip()`
- `_audit()`
- `_normalize_prompt_fields()`

---

## 📈 拆分收益

### 可维护性
- ✅ 单文件从 2000 行降至 ~200 行
- ✅ 每个模块职责单一，易于理解
- ✅ 更容易定位和修改特定功能

### 可测试性
- ✅ 每个模块可独立测试
- ✅ Mock 依赖更简单
- ✅ 测试覆盖率更容易提升

### 开发效率
- ✅ 减少 Git 合并冲突
- ✅ 并行开发更容易
- ✅ IDE 性能更好

---

## 🔧 实施步骤

### 阶段 1: 创建 utils 目录结构
```bash
mkdir -p app/api/utils
touch app/api/utils/__init__.py
```

### 阶段 2: 逐个拆分模块
1. 创建 `auth_helpers.py`，移动认证相关函数
2. 创建 `query_helpers.py`，移动查询相关函数
3. 创建 `session_helpers.py`，移动会话相关函数
4. 创建 `document_helpers.py`，移动文档相关函数
5. 创建 `memory_helpers.py`，移动记忆相关函数
6. 创建 `admin_helpers.py`，移动管理员相关函数
7. 创建 `response_helpers.py`，移动响应相关函数

### 阶段 3: 更新 dependencies.py
```python
# 从 utils 模块导入并重新导出
from app.api.utils.auth_helpers import (
    _require_user,
    _require_permission,
    # ...
)
from app.api.utils.query_helpers import (
    _query_cache_key,
    _run_with_query_runtime,
    # ...
)
# ... 其他导入
```

### 阶段 4: 验证
- 运行所有测试
- 检查导入路径
- 验证功能正常

---

## ⚠️ 注意事项

1. **向后兼容**: 保持 `from app.api.dependencies import xxx` 的导入路径不变
2. **循环依赖**: 避免 utils 模块之间的循环依赖
3. **共享依赖**: 服务实例（auth_service, settings 等）保留在 dependencies.py
4. **增量迁移**: 一次迁移一个模块，逐步验证

---

## 🎯 优先级建议

### P1 (高优先级)
- ✅ `auth_helpers.py` - 认证是核心功能
- ✅ `query_helpers.py` - 查询是最常用功能

### P2 (中优先级)
- ⚠️ `document_helpers.py` - 文档管理
- ⚠️ `admin_helpers.py` - 管理员功能

### P3 (低优先级)
- 📝 `session_helpers.py` - 会话管理
- 📝 `memory_helpers.py` - 记忆功能
- 📝 `response_helpers.py` - 响应辅助

---

## 📊 预期结果

| 指标 | 当前 | 拆分后 | 改进 |
|------|------|--------|------|
| dependencies.py 行数 | 2000 | ~200 | -90% |
| 最大模块行数 | 2000 | ~400 | -80% |
| 模块数量 | 1 | 8 | +700% |
| 平均模块行数 | 2000 | ~250 | -87.5% |

---

## 🚀 建议

**当前状态**: dependencies.py 虽然大，但功能完整，所有逻辑错误已修复。

**建议行动**:
1. **短期**: 保持现状，先验证运行时行为
2. **中期**: 按上述方案拆分（预计 2-3 小时）
3. **长期**: 持续优化，保持每个模块 < 300 行

**是否立即拆分**: 建议先运行测试验证功能正常，再进行拆分。拆分是优化，不是修复。
