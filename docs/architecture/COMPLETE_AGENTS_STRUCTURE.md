# 🏗️ 完整智能体架构结构文档

## 📊 架构演进状态

**当前状态**: 从 LangGraph 多智能体架构 → 服务化架构（迁移中）

```
旧架构 (Legacy)                    新架构 (Current)
─────────────────                  ──────────────────
LangGraph Workflow                 RAGPipeline
    ↓                                  ↓
  Nodes                          OrchestrationEngine
    ↓                                  ↓
Agent Classes                      Services
```

---

## 🗂️ 完整目录结构

### app/agents/ (总计 99 个文件)

#### ✅ **新架构：服务模块** (7个服务目录)

##### 1. **router/** - 路由服务 (11个文件)
```
app/agents/router/
├── __init__.py
├── service.py                    # 主服务入口
├── routing.py                    # 核心路由逻辑
├── enhanced_service.py           # 增强路由（澄清功能）
├── accuracy.py                   # 准确率跟踪
├── calibration.py                # 置信度校准
├── compatibility.py              # 兼容性适配器
├── config.py                     # 路由配置
├── examples.py                   # Few-shot示例
├── frontend_integration.py       # 前端集成
├── hybrid_clarification.py       # 混合澄清逻辑
├── hybrid_config.py              # 混合配置
└── validator.py                  # 路由验证
```

**功能**: 查询意图分类、路由选择、置信度校准、动态澄清

##### 2. **planner/** - 规划服务 (2个文件)
```
app/agents/planner/
├── __init__.py
└── service.py                    # 任务规划与分解
```

**功能**: 任务分解、执行策略决策

##### 3. **rag/** - 检索服务 (11个文件)
```
app/agents/rag/
├── __init__.py
├── service.py                    # 检索服务主入口
├── vector.py                     # 向量检索
├── graph.py                      # 图检索 (Neo4j)
├── enhanced_vector.py            # 增强向量检索
├── enhanced_graph.py             # 增强图检索
├── web.py                        # Web搜索
├── web_utils.py                  # Web工具
├── fusion.py                     # 结果融合 (RRF)
├── relevance.py                  # 相关性评分
├── retrieval_quality.py          # 检索质量评估
├── cache.py                      # 缓存管理
└── config.py                     # 检索配置
```

**功能**: 混合检索（向量+BM25+重排序）、知识图谱查询、Web搜索

##### 4. **synthesizer/** - 合成服务 (5个文件)
```
app/agents/synthesizer/
├── __init__.py
├── service.py                    # 合成服务主入口
├── generation.py                 # 答案生成
├── citations.py                  # 引用处理
└── templates.py                  # 提示模板
```

**功能**: 引用式答案生成、证据融合

##### 5. **tool/** - 工具执行服务 (4个文件)
```
app/agents/tool/
├── __init__.py
├── service.py                    # 工具服务主入口
├── react.py                      # ReAct模式实现
└── factory.py                    # 工具代理工厂
```

**功能**: 多跳推理、工具调用管理

##### 6. **validation/** - 验证服务 (11个文件)
```
app/agents/validation/
├── __init__.py
├── public.py                     # 公共接口
├── cascade.py                    # 验证级联
├── rules.py                      # 规则验证
├── citations.py                  # 引用验证
├── nli.py                        # 自然语言推理
├── deep.py                       # 深度LLM验证
├── fact_verification.py          # 事实验证
├── hallucination_patterns.py     # 幻觉模式检测
├── quality_orchestrator.py       # 质量编排
└── models.py                     # 验证模型
```

**功能**: 5层防御级联、幻觉检测、引用完整性检查

##### 7. **shared/** - 共享组件 (9个文件)
```
app/agents/shared/
├── __init__.py
├── base.py                       # 基础类和异常
├── cache.py                      # 共享缓存
├── config.py                     # 共享配置
├── quality_config.py             # 质量配置
├── quality_models.py             # 质量模型
├── result_schemas.py             # 结果模式
├── unified_config.py             # 统一配置
└── utils.py                      # 工具函数
```

---

#### ⚠️ **旧架构：遗留智能体文件** (14个 *_agent.py)

##### 兼容性包装器（仅重导出，6个）
```
app/agents/
├── router_agent.py              # → router.routing
├── vector_rag_agent.py          # → rag.vector
├── synthesis_agent.py           # → synthesizer.generation
├── graph_rag_agent.py           # → rag.graph
├── answer_validator_agent.py    # → validation.public
└── base_agent.py                # → shared.base
```

**状态**: ✅ 可安全删除（无外部导入）

##### 仍包含逻辑的智能体文件（8个）
```
app/agents/
├── enhanced_router_agent.py     # EnhancedRouterAgent 类
├── enhanced_vector_rag_agent.py # 增强向量检索
├── context_tracker_agent.py     # 上下文跟踪
├── quality_orchestrator_agent.py# 质量编排
├── react_agent.py               # ReAct智能体
├── retrieval_quality_agent.py   # 检索质量
├── route_validator_agent.py     # 路由验证
└── web_research_agent.py        # Web研究
```

**状态**: ⚠️ 需要逐个评估迁移状态

---

#### 🔧 **辅助配置文件** (约40个)

##### 配置文件
```
app/agents/
├── agent_config.py
├── quality_config.py
├── router_config.py
├── graph_rag_config.py
├── unified_config.py
└── ...
```

##### 工具和模式文件
```
app/agents/
├── hallucination_patterns.py    # 幻觉检测模式
├── fact_verification.py         # 事实验证
├── route_accuracy_tracker.py    # 路由准确率
├── degradation_strategies.py    # 降级策略
├── result_schemas.py            # 结果模式
└── ...
```

##### 工作流文件
```
app/agents/
├── enhanced_rag_workflow.py     # 增强RAG工作流
├── synthesis_templates.py       # 合成模板
├── router_examples.py           # 路由示例
└── ...
```

##### 缓存和工具
```
app/agents/
├── shared_cache.py
├── shared_utils.py
├── graph_rag_cache.py
├── web_activity_logger.py
├── web_activity_data_manager.py
└── web_activity_alerts.py
```

---

## 🏛️ 相关架构组件

### app/orchestration/ - 编排引擎
```
app/orchestration/
├── engine.py                     # 核心编排引擎
├── capabilities.py               # 能力注册 (6大服务)
├── policies.py                   # 执行策略
├── finalization.py               # 最终化服务
└── ...
```

### app/pipeline/ - 管道入口
```
app/pipeline/
├── rag_pipeline.py               # RAGPipeline (公共API)
├── contracts.py                  # 管道契约
├── profiles.py                   # 执行配置文件
└── ...
```

### app/graph/ - 旧LangGraph系统 ⚠️
```
app/graph/
├── execution/
│   └── workflow.py               # 旧工作流构建
├── nodes/                        # 旧节点实现
│   ├── router_node.py
│   ├── vector_node.py
│   ├── graph_node.py
│   ├── synthesis_node.py
│   ├── react_node.py
│   └── ...
└── ...
```

**状态**: 仅在 `app/graph/` 内部使用，与主系统隔离

---

## 📈 架构对比

### 旧架构调用链
```
API请求
  ↓
app/graph/execution/workflow.py
  ↓
LangGraph StateGraph
  ↓
app/graph/nodes/*.py (router_node, vector_node, etc.)
  ↓
app/agents/*_agent.py (router_agent, vector_rag_agent, etc.)
```

### 新架构调用链
```
API请求
  ↓
app/pipeline/rag_pipeline.RAGPipeline.execute()
  ↓
app/orchestration/engine.OrchestrationEngine
  ↓
app/orchestration/capabilities.CoreCapabilities
  ↓
app/agents/{router,rag,synthesizer,tool,validation}/service.py
```

---

## 🎯 六大核心服务

根据 `app/orchestration/capabilities.py` 的 `CoreCapabilities`:

1. **Router** (`router/service.py`)
   - 查询路由和意图分类
   - 置信度校准
   - 动态澄清

2. **Planner** (`planner/service.py`)
   - 任务分解
   - 执行策略决策

3. **Retriever** (`rag/service.py`)
   - 混合检索（向量+BM25+重排序）
   - 图检索 (Neo4j)
   - Web搜索

4. **Tool Runner** (`tool/service.py`)
   - ReAct多跳推理
   - 工具调用管理

5. **Synthesizer** (`synthesizer/service.py`)
   - 引用式答案生成
   - 证据融合

6. **Finalizer** (`orchestration/finalization.py`)
   - 5层验证级联
   - 幻觉检测
   - 质量评分

---

## 📝 文件统计

| 类别 | 数量 | 说明 |
|-----|------|------|
| **新服务模块** | 7个目录 | router, planner, rag, synthesizer, tool, validation, shared |
| **服务文件** | 43个 | service.py 及相关实现 |
| **旧智能体** | 14个 | *_agent.py 文件 |
| **配置/工具** | 42个 | 配置、模式、工具等 |
| **总计** | 99个 | app/agents/ 下所有Python文件 |

---

## 🔍 迁移状态评估

### ✅ 已完成迁移
- API层 → 使用 RAGPipeline
- 核心功能 → 服务化
- 路由、检索、合成、验证 → 独立服务

### ⚠️ 待清理
- 兼容性包装器（6个）
- LangGraph系统（app/graph/）
- 部分遗留智能体文件

### 🎯 清理优先级

**P0 - 立即可删除**:
```
router_agent.py
vector_rag_agent.py
synthesis_agent.py
graph_rag_agent.py
```

**P1 - 评估后删除**:
```
enhanced_router_agent.py
enhanced_vector_rag_agent.py
quality_orchestrator_agent.py
```

**P2 - 评估LangGraph系统**:
```
app/graph/execution/
app/graph/nodes/
```

---

## 🚀 使用建议

### 新功能开发
**必须使用**: 服务化架构
```python
# ✅ 正确
from app.agents.router.service import RouterService
from app.agents.rag.service import RetrieverService

# ❌ 错误
from app.agents.router_agent import RouterAgent
```

### 现有代码维护
**逐步迁移**: 从旧智能体 → 服务
- 保持兼容性包装器直到确认无外部依赖
- 逐个迁移功能到服务模块
- 添加废弃警告

---

## 📚 相关文档

- **架构说明**: `CLAUDE.md` - Architecture Overview
- **服务契约**: `app/domain/contracts.py`
- **编排逻辑**: `app/orchestration/engine.py`
- **管道接口**: `app/pipeline/rag_pipeline.py`
