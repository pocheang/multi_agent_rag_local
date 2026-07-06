# 系统架构 (System Architecture)

本文档详细介绍 QueryMind（智询） 系统的整体架构设计、核心组件和技术选型。

## 目录

- [快速参考](#快速参考)
- [架构概览](#架构概览)
- [技术栈](#技术栈)
- [核心组件](#核心组件)
- [数据流](#数据流)
- [多智能体系统](#多智能体系统)
- [检索系统](#检索系统)
- [安全架构](#安全架构)
- [性能优化](#性能优化)
- [可扩展性设计](#可扩展性设计)

---

## 快速参考

### 架构层次速查

| 层次 | 职责 | 主要技术 | 关键组件 |
|------|------|---------|---------|
| **用户界面** | 交互展示 | React, TypeScript | 聊天界面、文档管理 |
| **API 网关** | 请求路由 | FastAPI | 路由、中间件、认证 |
| **工作流编排** | 智能体协同 | LangGraph | Router、Vector、Graph、Synthesis |
| **业务服务** | 业务逻辑 | Python | 认证、会话、文档管理 |
| **检索系统** | 混合检索 | ChromaDB, BM25 | 向量、稀疏、融合、重排序 |
| **数据存储** | 数据持久化 | ChromaDB, Neo4j, SQLite | 向量库、图数据库、应用DB |
| **外部服务** | LLM 调用 | OpenAI, Anthropic, Ollama | 聊天模型、嵌入模型 |

### 核心组件速查

**智能体系统**:
```
Router Agent         → 分析查询意图，决定路由策略
Adaptive Planner     → 自适应调整检索参数
Vector RAG Agent     → 执行混合检索（向量+BM25）
Graph RAG Agent      → 查询知识图谱
Web Research Agent   → 网络搜索（可选）
Synthesis Agent      → 综合信息生成答案
```

**检索管道**:
```
查询 → [向量检索 + BM25检索] → RRF融合 → 重排序 → 结果
     ↓                        ↓          ↓         ↓
  ChromaDB                rank-bm25   算法   bge-reranker
```

**数据流速查**:
```
文档上传 → 内容提取 → 分块 → 嵌入 → ChromaDB
                          ↓
                    实体抽取 → Neo4j
                          ↓
                    元数据 → SQLite
```

### 技术栈速查

**后端框架**:
- FastAPI - Web 框架
- LangGraph - 工作流编排
- LangChain - LLM 集成

**数据库**:
- ChromaDB - 向量存储
- Neo4j - 知识图谱
- SQLite - 应用数据
- Redis - 缓存（可选）

**检索技术**:
- sentence-transformers - 嵌入和重排序
- rank-bm25 - BM25 算法
- jieba - 中文分词

**前端技术**:
- React 18 - UI 框架
- TypeScript - 类型安全
- Vite - 构建工具
- Axios - HTTP 客户端

### 端口和服务速查

| 服务 | 端口 | 协议 | 用途 |
|------|------|------|------|
| FastAPI | 8000 | HTTP | REST API |
| React Dev | 5173 | HTTP | 前端开发服务器 |
| Neo4j Browser | 7474 | HTTP | Neo4j 管理界面 |
| Neo4j Bolt | 7687 | Bolt | Neo4j 数据库连接 |
| Redis | 6379 | TCP | 缓存服务 |
| Ollama | 11434 | HTTP | 本地 LLM 服务 |

### API 端点速查

| 端点组 | 前缀 | 主要端点 |
|--------|------|---------|
| 认证 | `/api/auth` | `/login`, `/register`, `/logout` |
| 查询 | `/api/query` | `/`, `/stream` |
| 会话 | `/api/sessions` | `/`, `/{id}` |
| 文档 | `/api/documents` | `/upload`, `/list` |
| 管理 | `/api/admin` | `/users`, `/settings` |
| 健康检查 | `/` | `/health`, `/ready` |

### 配置文件速查

```bash
# 最小配置
MODEL_BACKEND=local
NEO4J_PASSWORD=your-password

# 生产配置关键项
APP_ENV=production
MODEL_BACKEND=openai
OPENAI_API_KEY=sk-xxx
NEO4J_URI=bolt://production-neo4j:7687
AUTH_TOKEN_TTL_HOURS=24
RETRIEVAL_CACHE_BACKEND=redis
ENABLE_RERANKER=true
```

### 设计模式速查

**分层架构**:
```
Presentation Layer    (API Routes)
    ↓
Business Logic Layer  (Services)
    ↓
Data Access Layer     (Repositories)
    ↓
Data Storage Layer    (Databases)
```

**依赖注入**:
```python
# FastAPI 依赖注入
@router.get("/items")
async def list_items(
    db: Database = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return db.query("SELECT * FROM items")
```

**事件驱动**:
```python
# 流式响应
async def stream_query():
    async for event in workflow.astream(state):
        yield encode_sse(event)
```

### 安全机制速查

**认证**:
- JWT 令牌（24小时有效）
- bcrypt 密码哈希
- HTTP Bearer 认证

**授权**:
- RBAC（基于角色）
- 用户级数据隔离
- API 密钥加密存储

**数据保护**:
- Fernet 对称加密（API 密钥）
- 出站数据脱敏
- 敏感字段过滤

### 性能优化速查

**缓存策略**:
```
L1: 内存缓存 (LRU, 256 项)
L2: Redis 缓存 (TTL: 60-300秒)
L3: 查询结果缓存
```

**并发优化**:
- 异步 I/O（FastAPI + asyncio）
- 并行检索（向量 + BM25）
- 批处理（文档嵌入、数据库操作）

**资源限制**:
- 查询超时：30-60秒
- 文件大小：20MB/文件
- 批量上传：20文件/次

### 监控指标速查

**系统指标**:
- QPS（每秒查询数）
- P50/P95/P99 延迟
- 错误率
- CPU/内存使用率

**业务指标**:
- 检索召回率
- 检索精确率
- 重排序效果
- 用户满意度

### 扩展点速查

**添加新 LLM 提供商**:
```
1. app/core/models.py - 添加模型配置
2. app/core/config.py - 添加环境变量
3. 实现统一的 LLM 接口
```

**添加新检索器**:
```
1. app/retrievers/ - 创建检索器类
2. 继承 BaseRetriever
3. 实现 retrieve() 方法
4. 集成到 hybrid_retrieve()
```

**添加新智能体**:
```
1. app/agents/ - 创建智能体文件
2. app/graph/nodes/ - 创建节点
3. app/graph/workflow.py - 添加到工作流
4. app/graph/state.py - 更新状态
```

---

## 架构概览

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   React Frontend (Vite + TypeScript)                     │   │
│  │   - 聊天界面  - 文档管理  - 会话管理  - 管理控制台      │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/SSE
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                         API 网关层                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   FastAPI Application                                    │   │
│  │   - 路由管理  - 认证授权  - 参数验证  - 中间件          │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                     工作流编排层 (LangGraph)                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  多智能体协同工作流                                       │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │   │
│  │  │ Router │→ │ Vector │→ │ Graph  │→ │Synthe- │        │   │
│  │  │ Agent  │  │ Agent  │  │ Agent  │  │sis     │        │   │
│  │  └────────┘  └────────┘  └────────┘  └────────┘        │   │
│  │       ↓           ↓           ↓           ↑             │   │
│  │  ┌────────────────────────────────────────┐             │   │
│  │  │     状态管理 (GraphState)              │             │   │
│  │  └────────────────────────────────────────┘             │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                         业务服务层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  认证    │  │  会话    │  │  文档    │  │  提示词  │       │
│  │  服务    │  │  服务    │  │  服务    │  │  服务    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  运行时  │  │  记忆    │  │  韧性    │  │  缓存    │       │
│  │  治理    │  │  管理    │  │  管理    │  │  管理    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                         检索系统层                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  混合检索管道                                             │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │  向量检索  │  │ BM25 检索  │  │  重排序器  │        │   │
│  │  │ (ChromaDB) │  │ (rank-bm25)│  │(bge-rerank)│        │   │
│  │  └────────────┘  └────────────┘  └────────────┘        │   │
│  │         ↓              ↓              ↓                 │   │
│  │  ┌─────────────────────────────────────┐               │   │
│  │  │   倒数排名融合 (RRF)                │               │   │
│  │  └─────────────────────────────────────┘               │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                         数据存储层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ ChromaDB │  │  Neo4j   │  │  SQLite  │  │  Redis   │       │
│  │  向量库  │  │  图数据库│  │  应用DB  │  │  缓存    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                         外部服务层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Ollama  │  │  OpenAI  │  │Anthropic │  │   Web    │       │
│  │  本地LLM │  │   API    │  │   API    │  │  Search  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### 设计原则

1. **模块化**: 每个组件职责单一，可独立测试和部署
2. **分层架构**: 清晰的层次划分，降低耦合
3. **可扩展**: 支持新的模型、检索器、智能体
4. **容错性**: 熔断器、重试、降级策略
5. **性能**: 缓存、异步、并发优化
6. **安全**: RBAC、加密、审计日志

---

## 技术栈

### 后端技术

| 分类 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **Web 框架** | FastAPI | 0.115+ | REST API 和 WebSocket |
| **工作流** | LangGraph | 0.2+ | 多智能体编排 |
| **AI 框架** | LangChain | 0.3+ | LLM 集成和工具链 |
| **向量数据库** | ChromaDB | 0.5+ | 向量存储和检索 |
| **图数据库** | Neo4j | 5.24+ | 知识图谱 |
| **应用数据库** | SQLite | 3.x | 用户、会话、元数据 |
| **缓存** | Redis | 5.0+ | 查询缓存和会话存储 |
| **嵌入模型** | sentence-transformers | 3.0+ | 文本嵌入和重排序 |
| **NLP** | jieba | 0.42+ | 中文分词 |
| **文档解析** | pypdf, docling | - | PDF/DOCX 解析 |
| **OCR** | Tesseract, PaddleOCR | - | 图像文字识别 |

### 前端技术

| 分类 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **框架** | React | 18+ | UI 框架 |
| **构建工具** | Vite | 5+ | 快速构建和热更新 |
| **语言** | TypeScript | 5+ | 类型安全 |
| **路由** | React Router | 6+ | 单页应用路由 |
| **HTTP 客户端** | Axios | 1+ | API 调用 |
| **样式** | CSS Modules | - | 模块化 CSS |

### LLM 提供商支持

- **Ollama**: 本地部署（Qwen、LLaMA、Mistral 等）
- **OpenAI**: GPT-4、GPT-3.5、text-embedding-3
- **Anthropic**: Claude 3/4 系列

---

## 核心组件

### 1. API 网关 (FastAPI)

**职责**：
- 接收和路由 HTTP 请求
- 认证和授权
- 请求验证和响应序列化
- 流式响应（SSE）

**关键特性**：
- 自动生成 OpenAPI 文档
- 异步请求处理
- 依赖注入系统
- 中间件支持（CORS、日志、错误处理）

**核心代码**：
```python
# app/api/main.py
from fastapi import FastAPI
from app.api.routes import auth, query, sessions, documents

app = FastAPI(title="QueryMind（智询）")
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(query.router, prefix="/query", tags=["query"])
# ... 其他路由
```

---

### 2. 工作流编排器 (LangGraph)

**职责**：
- 定义多智能体工作流
- 管理状态传递
- 条件路由
- 并发执行

**工作流结构**：
```python
# app/graph/workflow.py
from langgraph.graph import StateGraph, END

workflow = StateGraph(GraphState)
workflow.add_node("router", router_node)
workflow.add_node("vector", vector_node)
workflow.add_node("graph", graph_node)
workflow.add_node("web", web_node)
workflow.add_node("synthesis", synthesis_node)

workflow.add_edge("router", "vector")
workflow.add_conditional_edges("vector", route_after_vector)
workflow.add_edge("synthesis", END)
```

**状态管理**：
```python
# app/graph/state.py
from typing import TypedDict, List

class GraphState(TypedDict):
    query: str
    context: List[str]
    retrieved_docs: List[Dict]
    graph_results: List[Dict]
    web_results: List[Dict]
    next_step: str
    final_answer: str
    execution_id: str
    tier: str  # fast/balanced/deep
```

---

### 3. 智能体系统

#### Router Agent (路由智能体)

**职责**: 分析查询意图，决定执行策略

**决策因素**：
- 查询复杂度（简单事实 vs 多跳推理）
- 所需资源（仅向量 vs 向量+图 vs 全部）
- 时效性要求（实时信息 vs 历史知识）

**策略选择**：
```python
strategies = {
    "fast": {
        "vector_top_k": 5,
        "enable_graph": False,
        "enable_web": False,
        "max_time_ms": 800
    },
    "balanced": {
        "vector_top_k": 10,
        "enable_graph": True,
        "enable_web": conditional,
        "max_time_ms": 2000
    },
    "deep": {
        "vector_top_k": 20,
        "enable_graph": True,
        "enable_web": True,
        "max_time_ms": 5000
    }
}
```

#### Vector RAG Agent (向量检索智能体)

**职责**: 执行混合检索，获取相关文档

**检索流程**：
1. 查询重写和扩展（同义词、中文分词）
2. 并行执行向量检索和 BM25 检索
3. 倒数排名融合（RRF）
4. 重排序（可选）
5. 去重和过滤

#### Graph RAG Agent (图检索智能体)

**职责**: 查询知识图谱，获取实体关系

**查询类型**：
- 实体属性查询
- 关系查询（一跳、多跳）
- 路径查询
- 子图查询

**Neo4j Cypher 示例**：
```cypher
MATCH (e:Entity {name: $entity_name})
OPTIONAL MATCH (e)-[r]-(related:Entity)
RETURN e, type(r), related
LIMIT 20
```

#### Web Research Agent (网络搜索智能体)

**职责**: 当本地知识不足时，进行网络搜索

**触发条件**：
- 向量检索结果为空或置信度低
- 查询涉及时事或最新信息
- 用户明确要求网络搜索

**安全措施**：
- 域名白名单
- 结果质量评分
- 来源可信度验证

#### Synthesis Agent (合成智能体)

**职责**: 综合所有信息，生成最终答案

**生成流程**：
1. 整合多源信息（文档、图谱、网络）
2. 检查信息一致性
3. 生成答案并标注引用
4. 安全扫描（避免有害内容）
5. 格式化输出

---

### 4. 检索系统

#### 混合检索架构

```
查询
  │
  ├─→ 向量检索 (ChromaDB)
  │     └─→ 语义相似度搜索
  │
  ├─→ BM25 检索 (rank-bm25)
  │     └─→ 关键词精确匹配
  │
  └─→ 倒数排名融合 (RRF)
        └─→ 重排序 (bge-reranker-v2-m3)
              └─→ 最终结果
```

#### 向量检索 (ChromaDB)

**特性**：
- 余弦相似度搜索
- 元数据过滤（来源、日期、标签）
- 持久化存储

**配置参数**：
```python
VECTOR_TOP_K = 10
VECTOR_SIMILARITY_THRESHOLD = 0.2
CHROMA_COLLECTION = "local_rag_collection"
```

**查询示例**：
```python
results = vector_store.similarity_search_with_score(
    query=query,
    k=top_k,
    filter={"user_id": user_id}
)
```

#### BM25 检索

**特性**：
- TF-IDF + BM25 算法
- 中文分词支持（jieba）
- 文档过滤

**配置参数**：
```python
BM25_TOP_K = 10
BM25_K1 = 1.5  # 词频饱和度
BM25_B = 0.75   # 文档长度归一化
```

#### 倒数排名融合 (RRF)

**算法**：
```python
def rrf_score(rank: int, k: int = 60) -> float:
    return 1 / (k + rank)

# 对每个候选文档，累加来自各检索器的 RRF 分数
for doc in candidates:
    score = rrf_score(vector_rank) + rrf_score(bm25_rank)
```

**优势**：
- 不依赖绝对分数，只看排名
- 自然融合不同检索器结果
- 无需手动调整权重

#### 重排序器

**模型**: BAAI/bge-reranker-v2-m3

**用途**: 对融合后的候选文档进行精细排序

**配置**：
```python
ENABLE_RERANKER = True
RERANKER_TOP_N = 5
```

---

### 5. 数据存储

#### ChromaDB (向量存储)

**用途**：
- 存储文档嵌入向量
- 语义搜索
- 元数据管理

**数据模型**：
```python
{
    "id": "doc_123_chunk_5",
    "embedding": [0.1, 0.2, ...],  # 向量
    "metadata": {
        "source": "report.pdf",
        "page": 5,
        "user_id": "user_456",
        "timestamp": "2026-06-19T10:00:00"
    },
    "document": "文档内容..."
}
```

#### Neo4j (知识图谱)

**用途**：
- 存储实体和关系
- 多跳推理
- 路径查询

**数据模型**：
```
(Entity:Person {name: "张三", age: 30})
-[:WORKS_AT {since: 2020}]->
(Entity:Company {name: "某公司"})
```

#### SQLite (应用数据库)

**表结构**：
- `users`: 用户信息、角色、密码哈希
- `sessions`: 会话元数据、策略配置
- `documents`: 文档元数据、摄取状态
- `prompts`: 提示词模板、版本历史
- `audit_logs`: 审计日志

---

## 数据流

### 1. 文档摄取流程

```
上传文档
  │
  ├─→ 文档类型检测 (PDF/DOCX/TXT/图片)
  │
  ├─→ 内容提取
  │     ├─ PDF: pypdf / docling
  │     ├─ 图片: OCR (Tesseract/PaddleOCR)
  │     └─ DOCX: python-docx
  │
  ├─→ 文本分块 (Parent-Child 策略)
  │     ├─ Parent Chunk: 1500 字符
  │     └─ Child Chunk: 600 字符
  │
  ├─→ 向量化 (Embedding)
  │     └─→ 存入 ChromaDB
  │
  ├─→ 实体提取和关系抽取
  │     └─→ 存入 Neo4j
  │
  └─→ 元数据存储
        └─→ 存入 SQLite
```

### 2. 查询处理流程

```
用户查询
  │
  ├─→ 认证和授权检查
  │
  ├─→ 查询预处理
  │     ├─ 语言检测
  │     ├─ 中文分词
  │     └─ 敏感词过滤
  │
  ├─→ Router Agent 分析
  │     └─→ 确定执行策略 (fast/balanced/deep)
  │
  ├─→ Vector RAG Agent
  │     ├─ 向量检索
  │     ├─ BM25 检索
  │     ├─ RRF 融合
  │     └─ 重排序
  │
  ├─→ Graph RAG Agent (条件执行)
  │     └─→ Neo4j 查询
  │
  ├─→ Web Research Agent (条件执行)
  │     └─→ DuckDuckGo 搜索
  │
  ├─→ Synthesis Agent
  │     ├─ 信息整合
  │     ├─ 答案生成
  │     ├─ 引用标注
  │     └─ 安全检查
  │
  └─→ 返回结果
        ├─ 同步响应 (JSON)
        └─ 流式响应 (SSE)
```

### 3. 流式响应流程

```
SSE 连接建立
  │
  ├─→ 工作流开始执行
  │
  ├─→ 智能体状态更新
  │     └─→ 推送事件: {"type": "agent_start", "agent": "vector"}
  │
  ├─→ 中间结果
  │     └─→ 推送事件: {"type": "docs_retrieved", "count": 5}
  │
  ├─→ 答案流式生成
  │     └─→ 推送事件: {"type": "token", "content": "这是"}
  │                   {"type": "token", "content": "答案"}
  │
  └─→ 完成
        └─→ 推送事件: {"type": "done", "total_time_ms": 1234}
```

---

## 多智能体系统

### 智能体协同模式

#### 1. 串行模式

```
Router → Vector → Graph → Synthesis
```

适用于：需要前序结果作为后续输入的场景

#### 2. 并行模式

```
        ┌─ Vector ─┐
Router ─┤          ├→ Synthesis
        └─ Graph ─┘
```

适用于：独立任务，可同时执行

#### 3. 条件路由模式

```
Router → Vector → [结果充分？] ─Yes→ Synthesis
                       │
                       No
                       ↓
                    Graph/Web → Synthesis
```

适用于：动态决策，按需调用

---

## 安全架构

### 认证和授权

**JWT 认证**：
```python
# 令牌结构
{
    "sub": "user_id",
    "role": "user|admin",
    "exp": 1719734400  # 过期时间
}
```

**RBAC 权限**：
- **User**: 查询、会话管理、文档上传
- **Admin**: 用户管理、系统配置、运维操作

### 数据隔离

- **用户级隔离**: 每个用户只能访问自己的文档和会话
- **会话级隔离**: 不同会话的上下文独立
- **元数据过滤**: 查询时自动注入 `user_id` 过滤器

### 加密和脱敏

- **API 密钥加密**: Fernet 对称加密
- **密码哈希**: bcrypt
- **出站数据脱敏**: 自动移除敏感信息（API 密钥、密码）

---

## 性能优化

### 缓存策略

#### 多层缓存

1. **查询缓存**: 缓存检索结果（TTL: 60-300秒）
2. **会话缓存**: 缓存会话上下文
3. **模型缓存**: 缓存嵌入模型和重排序模型

#### 自适应 TTL

```python
cache_ttl = {
    "fast": 300,      # 简单查询，缓存时间长
    "balanced": 120,  # 平衡查询
    "deep": 60        # 复杂查询，缓存时间短
}
```

### 并发优化

**异步执行**：
```python
# 向量和图检索并行
results = await asyncio.gather(
    vector_retriever.retrieve(query),
    graph_retriever.retrieve(query)
)
```

**批处理**：
- 批量文档嵌入
- 批量 Neo4j 查询

---

## 可扩展性设计

### 水平扩展

- **无状态 API**: 可部署多个实例，通过负载均衡分发
- **外部化状态**: 会话存储在 Redis，数据库独立部署

### 插件化架构

**添加新的 LLM 提供商**：
```python
# app/services/llm_factory.py
def get_llm(backend: str):
    if backend == "custom":
        return CustomLLM(...)
```

**添加新的检索器**：
```python
# app/retrievers/custom_retriever.py
class CustomRetriever(BaseRetriever):
    def retrieve(self, query: str) -> List[Document]:
        # 自定义检索逻辑
        pass
```

**添加新的智能体**：
```python
# app/agents/custom_agent.py
def custom_agent(state: GraphState) -> GraphState:
    # 自定义智能体逻辑
    return state
```

---

## 监控和可观测性

### 指标收集

- **请求指标**: QPS、延迟、错误率
- **检索指标**: 召回率、精确率、重排序效果
- **资源指标**: CPU、内存、磁盘 I/O

### 追踪

- **分布式追踪**: OpenTelemetry
- **智能体追踪**: 每个智能体的执行时间和状态
- **查询追踪**: 端到端的查询生命周期

### 日志

- **结构化日志**: JSON 格式
- **日志级别**: DEBUG、INFO、WARNING、ERROR
- **审计日志**: 敏感操作记录

---

## 下一步

了解系统架构后，建议继续阅读：

1. **[多智能体系统](./MULTI_AGENT_SYSTEM.md)** - 深入智能体协同机制
2. **[检索系统](./RETRIEVAL_SYSTEM.md)** - 详解混合检索算法
3. **[API 开发](./API_DEVELOPMENT.md)** - 学习 API 开发规范

---

**更新日期**: 2026-06-19  
**文档版本**: 1.0
