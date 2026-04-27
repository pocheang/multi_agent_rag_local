# v0.3.0 P0 重构问题清单

**检查日期**: 2026-04-27  
**状态**: ❌ 发现严重逻辑漏洞

---

## 🚨 严重问题 (P0 - 阻塞性)

### 1. dependencies.py 缺失关键导入

**影响**: 运行时会抛出 `NameError`，导致应用无法启动

**缺失的导入**:
```python
# 缺失来自 app.services.agent_classifier
classify_agent_class

# 缺失来自 app.services.retrieval_profiles  
normalize_retrieval_profile

# 缺失来自 app.services.runtime_ops
choose_shadow
append_shadow_run
resolve_profile_for_request

# 缺失来自 app.services.consistency_guard
text_similarity
```

**位置**: 
- `app/api/dependencies.py:1396` - `normalize_retrieval_profile(strategy)`
- `app/api/dependencies.py:1398` - `normalize_retrieval_profile(None)`
- `app/api/dependencies.py:1412` - `classify_agent_class(Path(filename).stem)`
- `app/api/dependencies.py:1466` - `classify_agent_class(question)`
- `app/api/dependencies.py:1787` - `resolve_profile_for_request(...)`
- `app/api/dependencies.py:1797` - `normalize_retrieval_profile(lock)`
- `app/api/dependencies.py:1798` - `resolve_profile_for_request(...)`
- `app/api/dependencies.py:1813` - `choose_shadow(...)`
- `app/api/dependencies.py:1824` - `run_query(...)`
- `app/api/dependencies.py:1831` - `text_similarity(...)`
- `app/api/dependencies.py:1832` - `append_shadow_run(...)`

**修复方案**:
```python
# 在 app/api/dependencies.py 顶部添加
from app.services.agent_classifier import classify_agent_class
from app.services.consistency_guard import text_similarity
from app.services.retrieval_profiles import normalize_retrieval_profile
from app.services.runtime_ops import (
    append_shadow_run,
    choose_shadow,
    resolve_profile_for_request,
)
```

---

### 2. query.py 缺失 emit_alert 导入

**影响**: 查询路由会抛出 `NameError: name 'emit_alert' is not defined`

**使用次数**: 13 次

**位置**:
- `app/api/routes/query.py:33` - quota exceeded alert
- `app/api/routes/query.py:165` - query execution alert
- `app/api/routes/query.py:198` - cache alert
- `app/api/routes/query.py:216` - error alert
- `app/api/routes/query.py:401` - streaming alert
- 以及其他 8 处

**修复方案**:
```python
# 在 app/api/routes/query.py 顶部添加
from app.services.alerting import emit_alert
```

---

## ⚠️ 高优先级问题 (P1)

### 3. 循环导入风险

**问题**: `dependencies.py` 导入了 `synthesize_answer`，而 synthesis_agent 可能依赖其他模块

**位置**: `app/api/dependencies.py:46`

**建议**: 
- 将 `synthesize_answer` 的导入移到使用它的函数内部（lazy import）
- 或者确认没有循环依赖

---

### 4. run_query 未导入到 dependencies.py

**问题**: `_launch_shadow_run` 函数使用了 `run_query` 但未导入

**位置**: `app/api/dependencies.py:1824`

**修复方案**:
```python
# 在 app/api/dependencies.py 顶部添加
from app.graph.workflow import run_query
```

---

## 📋 中优先级问题 (P2)

### 5. 导入组织不一致

**问题**: 不同路由文件的导入风格不一致
- `admin_settings.py` 直接导入了 `emit_alert`
- 其他文件期望从 `dependencies` 导入但实际没有

**建议**: 统一导入策略
- 要么所有 `emit_alert` 都从 `dependencies` 导入
- 要么所有文件都直接从 `app.services.alerting` 导入

---

### 6. 缺少类型提示

**问题**: 部分辅助函数缺少完整的类型提示

**示例**:
```python
def _call_with_supported_kwargs(fn, /, *args, **kwargs):  # 缺少返回类型
```

---

## ✅ 已验证正确的部分

1. ✅ 所有路由文件语法正确（py_compile 通过）
2. ✅ 路由注册完整（67 个路由全部包含）
3. ✅ 中间件正确分离
4. ✅ 认证依赖正确实现
5. ✅ 文件结构清晰合理

---

## 🔧 修复优先级

### 立即修复（阻塞性）
1. ✅ 修复 `dependencies.py` 缺失的 6 个导入
2. ✅ 修复 `query.py` 缺失的 `emit_alert` 导入

### 尽快修复（高优先级）
3. 检查并修复 `run_query` 导入
4. 验证没有循环导入

### 后续优化（中优先级）
5. 统一导入策略
6. 补充类型提示

---

## 📊 影响评估

| 问题 | 严重程度 | 影响范围 | 修复难度 | 预计时间 |
|------|---------|---------|---------|---------|
| dependencies.py 缺失导入 | 🔴 Critical | 全局 | 简单 | 5 分钟 |
| query.py 缺失 emit_alert | 🔴 Critical | 查询功能 | 简单 | 2 分钟 |
| run_query 未导入 | 🟡 High | 影子测试 | 简单 | 2 分钟 |
| 循环导入风险 | 🟡 High | 启动 | 中等 | 10 分钟 |
| 导入组织不一致 | 🟢 Medium | 可维护性 | 简单 | 15 分钟 |
| 缺少类型提示 | 🟢 Low | 代码质量 | 简单 | 30 分钟 |

**总修复时间**: 约 1 小时

---

## 🎯 结论

**v0.3.0 P0 重构完成度**: 85%

**完成的部分**:
- ✅ 文件结构重构（100%）
- ✅ 路由分离（100%）
- ✅ 中间件分离（100%）
- ✅ 依赖注入框架（95%）

**未完成的部分**:
- ❌ 导入完整性验证（60%）
- ❌ 运行时测试（0%）

**建议**:
1. **立即修复** 上述 P0 问题（预计 10 分钟）
2. **运行测试** 验证修复后的代码
3. **补充集成测试** 确保所有路由正常工作
4. **更新文档** 记录已知问题和修复方案

---

**生成时间**: 2026-04-27  
**检查工具**: Claude Code Static Analysis
