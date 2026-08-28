# app/graph/

图数据库和流式传输工具目录

## 📋 目录说明

本目录包含与**图数据库**（Neo4j）和**流式传输**（SSE）相关的工具模块。

**注意**: 本目录不再包含 LangGraph 工作流系统。所有工作流逻辑已迁移到服务化架构（`app/pipeline/` + `app/orchestration/`）。

---

## 📁 目录结构

```
app/graph/
├── knowledge/              # Neo4j 知识图谱
│   ├── client.py          # Neo4j 客户端（单例模式）
│   ├── cypher_validation.py # Cypher 查询验证
│   └── entity_extraction.py # 实体提取
│
└── streaming/             # 流式传输工具
    └── sse_encoder.py     # Server-Sent Events 编码器
```

---

## 🔧 模块说明

### knowledge/ - Neo4j 知识图谱

**用途**: 提供 Neo4j 图数据库的连接和操作能力

**主要组件**:

#### `client.py` - Neo4jClient
- 单例模式的 Neo4j 驱动管理
- 线程安全的连接池
- 自动 schema 初始化
- 用于知识图谱查询和存储

**使用示例**:
```python
from app.graph.knowledge.client import Neo4jClient

client = Neo4jClient()
# 使用 client 进行图查询
```

**被使用的位置** (8处):
- `app/api/application/lifespan.py` - 应用启动/关闭
- `app/api/routes/admin/graph_rag.py` - 管理端点
- `app/api/routes/admin/settings.py` - 设置管理
- `app/services/documents/index_manager.py` - 文档索引
- `app/services/documents/ingest.py` - 文档摄取

---

#### `cypher_validation.py`
- Cypher 查询语法验证
- 查询安全检查
- 查询模板管理

---

#### `entity_extraction.py`
- 从文本中提取实体
- 实体关系识别
- 用于构建知识图谱

---

### streaming/ - 流式传输工具

**用途**: 提供 Server-Sent Events (SSE) 格式化工具

#### `sse_encoder.py` - encode_sse()
- 将数据编码为 SSE 格式
- 用于实时流式响应

**使用示例**:
```python
from app.graph.streaming.sse_encoder import encode_sse

data = {"type": "status", "message": "Processing..."}
sse_message = encode_sse(data)
# 返回: "data: {\"type\":\"status\",\"message\":\"Processing...\"}\n\n"
```

**被使用的位置** (3处):
- `app/api/query/streaming/cache.py` - 流式缓存
- `app/api/query/streaming/execution.py` - 流式执行
- `app/api/routes/public/query_stream.py` - 查询流端点

---

## 🚫 不再包含的内容

以下模块已在架构迁移中删除：

- ❌ `execution/` - LangGraph 工作流构建器
- ❌ `nodes/` - LangGraph 节点实现
- ❌ `routing/` - 路由决策逻辑
- ❌ `state.py` - LangGraph 状态定义
- ❌ `workflow.py` - 旧工作流入口
- ❌ `studio_entry.py` - LangGraph Studio 入口

**替代方案**: 使用新的服务化架构
```python
# 旧方式（已废弃）
from app.graph.execution.workflow import build_workflow

# 新方式（推荐）
from app.pipeline.rag_pipeline import RAGPipeline
from app.orchestration.engine import OrchestrationEngine
```

---

## 📊 使用统计

| 模块 | 导入位置数量 | 主要用途 |
|-----|------------|---------|
| `knowledge.client` | 8处 | Neo4j 客户端 |
| `streaming.sse_encoder` | 3处 | SSE 编码 |

---

## 🔗 相关文档

- [架构说明](../../CLAUDE.md)

---

## 🛠️ 开发指南

### 添加新的图查询

新的图查询功能应该添加到 `knowledge/` 目录：

```python
# app/graph/knowledge/custom_queries.py
from app.graph.knowledge.client import Neo4jClient


def get_related_entities(entity_id: str):
    client = Neo4jClient()
    # 实现查询逻辑
    ...
```

### 扩展流式传输

流式传输工具应保持简单和通用：

```python
# app/graph/streaming/custom_encoder.py
def encode_custom_format(data: dict) -> str:
    # 实现自定义编码
    ...
```

---

## ⚠️ 注意事项

1. **Neo4j 是可选的**: 如果未配置 Neo4j，系统会回退到纯向量检索
2. **线程安全**: `Neo4jClient` 使用单例模式，确保线程安全
3. **SSE 格式**: 严格遵循 [SSE 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)

---

**最后更新**: 2026-08-18  
**维护者**: RAG System Team
