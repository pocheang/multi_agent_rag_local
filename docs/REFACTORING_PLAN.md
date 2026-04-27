# 代码重构计划

**日期**: 2026-04-27  
**版本**: v0.2.5 → v0.3.0  
**目标**: 将大文件拆分为更小、更易维护的模块

---

## 📊 当前状态分析

### 需要拆分的大文件

| 文件 | 行数 | 路由数 | 优先级 | 复杂度 |
|------|------|--------|--------|--------|
| `app/api/main.py` | 4150 | 74 | P0 | 极高 |
| `app/services/auth_db.py` | 930 | N/A | P1 | 高 |
| `app/graph/workflow.py` | 532 | N/A | P1 | 高 |
| `app/retrievers/hybrid_retriever.py` | 512 | N/A | P1 | 高 |
| `app/ingestion/loaders.py` | 508 | N/A | P2 | 中 |
| `app/graph/streaming.py` | 503 | N/A | P2 | 中 |

---

## 🎯 重构策略

### 阶段 1: 拆分 API 路由 (app/api/main.py)

**目标**: 将 4150 行的单文件拆分为按功能模块组织的多个文件

#### 新目录结构
```
app/api/
├── __init__.py
├── main.py (保留，作为应用入口，~200行)
├── dependencies.py (共享依赖，~300行)
├── middleware.py (中间件，~100行)
├── routes/
│   ├── __init__.py
│   ├── auth.py (认证路由，~400行)
│   ├── query.py (查询路由，~500行)
│   ├── sessions.py (会话路由，~300行)
│   ├── documents.py (文档管理，~400行)
│   ├── prompts.py (提示词管理，~300行)
│   ├── memory.py (记忆管理，~200行)
│   ├── admin_users.py (用户管理，~400行)
│   ├── admin_ops.py (运维管理，~500行)
│   ├── admin_settings.py (设置管理，~300行)
│   └── health.py (健康检查，~100行)
└── utils/
    ├── __init__.py
    ├── auth_helpers.py (认证辅助函数，~200行)
    ├── query_helpers.py (查询辅助函数，~300行)
    ├── response_helpers.py (响应辅助函数，~200行)
    └── validation.py (验证函数，~200行)
```

#### 路由分组

**认证相关** (`routes/auth.py`):
- POST `/auth/login`
- POST `/auth/logout`
- GET `/auth/me`
- POST `/auth/refresh`

**查询相关** (`routes/query.py`):
- POST `/query`
- POST `/query-sync`
- GET `/query/stream`

**会话管理** (`routes/sessions.py`):
- GET `/sessions`
- POST `/sessions`
- GET `/sessions/{session_id}`
- PUT `/sessions/{session_id}`
- DELETE `/sessions/{session_id}`
- GET `/sessions/{session_id}/messages`
- PUT `/sessions/{session_id}/messages/{message_id}`
- DELETE `/sessions/{session_id}/messages/{message_id}`

**文档管理** (`routes/documents.py`):
- POST `/upload`
- GET `/index`
- POST `/index/rebuild`
- DELETE `/index/{filename}`
- POST `/index/{filename}/rebuild`

**提示词管理** (`routes/prompts.py`):
- GET `/prompts`
- POST `/prompts`
- GET `/prompts/{prompt_id}`
- PUT `/prompts/{prompt_id}`
- DELETE `/prompts/{prompt_id}`
- POST `/prompts/check`

**记忆管理** (`routes/memory.py`):
- GET `/memory`
- POST `/memory`
- DELETE `/memory/{memory_id}`

**管理员 - 用户** (`routes/admin_users.py`):
- GET `/admin/users`
- POST `/admin/users/create-admin`
- PUT `/admin/users/{user_id}/role`
- PUT `/admin/users/{user_id}/status`
- POST `/admin/users/{user_id}/reset-password`

**管理员 - 运维** (`routes/admin_ops.py`):
- GET `/admin/ops/overview`
- GET `/admin/ops/export.csv`
- POST `/admin/ops/profile`
- POST `/admin/ops/canary`
- POST `/admin/ops/rollback`
- POST `/admin/ops/benchmark`
- POST `/admin/ops/ab-compare`

**管理员 - 设置** (`routes/admin_settings.py`):
- GET `/admin/settings/model`
- PUT `/admin/settings/model`
- POST `/admin/settings/model/test`

**健康检查** (`routes/health.py`):
- GET `/health`
- GET `/ready`
- GET `/metrics`

---

### 阶段 2: 拆分认证服务 (app/services/auth_db.py)

**目标**: 将 930 行的认证服务拆分为多个模块

#### 新结构
```
app/services/auth/
├── __init__.py
├── auth_service.py (主服务类，~200行)
├── user_manager.py (用户管理，~250行)
├── session_manager.py (会话管理，~200行)
├── password_utils.py (密码工具，~100行)
├── token_utils.py (令牌工具，~100行)
└── audit_logger.py (审计日志，~150行)
```

---

### 阶段 3: 拆分工作流 (app/graph/workflow.py)

**目标**: 将 532 行的工作流拆分为节点和路由逻辑

#### 新结构
```
app/graph/
├── __init__.py
├── workflow.py (主工作流，~150行)
├── state.py (状态定义，~50行)
├── nodes/
│   ├── __init__.py
│   ├── router_node.py (~80行)
│   ├── adaptive_planner_node.py (~100行)
│   ├── vector_node.py (~120行)
│   ├── graph_node.py (~80行)
│   ├── web_node.py (~80行)
│   └── synthesis_node.py (~100行)
└── routing/
    ├── __init__.py
    ├── route_after_vector.py (~100行)
    ├── route_after_graph.py (~80行)
    └── route_helpers.py (~100行)
```

---

### 阶段 4: 拆分混合检索器 (app/retrievers/hybrid_retriever.py)

**目标**: 将 512 行的混合检索器拆分为策略模块

#### 新结构
```
app/retrievers/
├── __init__.py
├── hybrid_retriever.py (主接口，~150行)
├── vector_retriever.py (向量检索，~100行)
├── bm25_retriever.py (已存在)
├── fusion/
│   ├── __init__.py
│   ├── rrf_fusion.py (RRF融合，~80行)
│   └── score_normalization.py (分数归一化，~60行)
├── strategies/
│   ├── __init__.py
│   ├── baseline_strategy.py (~80行)
│   ├── advanced_strategy.py (~80行)
│   └── safe_strategy.py (~80行)
└── parent_child/
    ├── __init__.py
    ├── parent_store.py (已存在)
    └── deduplication.py (去重逻辑，~100行)
```

---

### 阶段 5: 拆分数据加载器 (app/ingestion/loaders.py)

**目标**: 将 508 行的加载器按文件类型拆分

#### 新结构
```
app/ingestion/
├── __init__.py
├── loaders.py (主接口，~100行)
├── base_loader.py (基类，~80行)
├── loaders/
│   ├── __init__.py
│   ├── pdf_loader.py (~120行)
│   ├── image_loader.py (~100行)
│   ├── text_loader.py (~80行)
│   └── office_loader.py (~100行)
└── utils/
    ├── __init__.py
    ├── ocr_utils.py (~80行)
    └── text_extraction.py (~80行)
```

---

### 阶段 6: 拆分流式处理 (app/graph/streaming.py)

**目标**: 将 503 行的流式处理拆分为处理器和编码器

#### 新结构
```
app/graph/
├── streaming.py (主接口，~150行)
├── streaming/
│   ├── __init__.py
│   ├── sse_encoder.py (SSE编码，~100行)
│   ├── stream_processor.py (流处理器，~150行)
│   └── event_handlers.py (事件处理，~150行)
```

---

## 📋 实施步骤

### Step 1: 准备工作
1. ✅ 创建重构计划文档
2. ✅ 运行所有测试确保基线通过
3. ✅ 创建重构分支 `refactor/modularize-codebase`

### Step 2: 拆分 API 路由 (最高优先级) ✅ 已完成
1. ✅ 创建新目录结构 `app/api/routes/` 和 `app/api/utils/`
2. ✅ 提取共享依赖到 `dependencies.py`
3. ✅ 提取中间件到 `middleware.py`
4. ✅ 拆分路由到各个模块
5. ✅ 更新 `main.py` 导入和注册路由
6. ✅ 运行测试验证

**成果**: 
- main.py: 4150 行 → 140 行 (减少 96.6%)
- 创建 9 个路由模块，2 个工具模块
- 所有测试通过（与基线相同）

### Step 3: 拆分认证服务
1. ⬜ 创建 `app/services/auth/` 目录
2. ⬜ 拆分用户管理、会话管理等模块
3. ⬜ 更新导入路径
4. ⬜ 运行测试验证

### Step 4: 拆分工作流
1. ⬜ 创建 `app/graph/nodes/` 和 `app/graph/routing/` 目录
2. ⬜ 拆分节点函数
3. ⬜ 拆分路由逻辑
4. ⬜ 更新导入路径
5. ⬜ 运行测试验证

### Step 5: 拆分检索器
1. ⬜ 创建 `app/retrievers/fusion/` 和 `app/retrievers/strategies/` 目录
2. ⬜ 拆分检索策略
3. ⬜ 更新导入路径
4. ⬜ 运行测试验证

### Step 6: 拆分加载器和流式处理
1. ⬜ 创建相应目录结构
2. ⬜ 拆分模块
3. ⬜ 更新导入路径
4. ⬜ 运行测试验证

### Step 7: 最终验证
1. ⬜ 运行完整测试套件
2. ⬜ 更新文档
3. ⬜ 代码审查
4. ⬜ 合并到主分支

---

## 🎯 重构原则

1. **单一职责**: 每个模块只负责一个功能领域
2. **高内聚低耦合**: 相关功能放在一起，减少模块间依赖
3. **向后兼容**: 保持公共 API 不变
4. **渐进式重构**: 每次拆分后立即测试
5. **文档同步**: 更新导入路径和使用示例

---

## 📊 预期收益

### 代码质量
- ✅ 文件大小减少 60-80%
- ✅ 单个文件不超过 300 行（目标）
- ✅ 提高代码可读性和可维护性
- ✅ 更容易进行单元测试

### 开发效率
- ✅ 更快的代码导航
- ✅ 减少合并冲突
- ✅ 更容易并行开发
- ✅ 新人更容易理解代码结构

### 性能
- ✅ 更快的 IDE 加载速度
- ✅ 更精确的代码补全
- ✅ 更快的静态分析

---

## ⚠️ 风险和缓解措施

### 风险 1: 导入路径变更导致测试失败
**缓解**: 使用 `__init__.py` 保持向后兼容的导入路径

### 风险 2: 循环依赖
**缓解**: 使用依赖注入和接口抽象

### 风险 3: 重构时间过长
**缓解**: 分阶段进行，每个阶段独立可测试

---

## 📅 时间估算

| 阶段 | 预计时间 | 优先级 |
|------|----------|--------|
| 准备工作 | 0.5天 | P0 |
| 拆分 API 路由 | 2天 | P0 |
| 拆分认证服务 | 1天 | P1 |
| 拆分工作流 | 1天 | P1 |
| 拆分检索器 | 1天 | P1 |
| 拆分加载器 | 0.5天 | P2 |
| 拆分流式处理 | 0.5天 | P2 |
| 最终验证 | 0.5天 | P0 |
| **总计** | **7天** | - |

---

**最后更新**: 2026-04-27  
**状态**: [Step 2 已完成 - API 路由模块化]
