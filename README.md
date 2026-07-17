<div align="center">

# QueryMind（智询）

### 企业私有知识库 Agentic RAG 系统

[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB.svg)](https://react.dev/)
[![Version](https://img.shields.io/badge/version-v0.6.2-blue.svg)](./CHANGELOG.md)

**智能路由 · 混合检索 · 知识图谱 · 质量保证 · 执行追踪**

[功能特性](#-核心特性) · [快速开始](#-快速开始) · [系统架构](#-系统架构) · [文档](#-文档) · [更新日志](./CHANGELOG.md)

</div>

---

## 📖 项目简介

**QueryMind（智询）** 是一个**生产级企业知识库 RAG 系统**，采用多智能体架构，提供高精度、可解释、可追踪的企业级知识问答服务。

### 🎯 核心特性

- 🧠 **智能路由系统** - LLM驱动的意图识别，准确率>95%
- 🔍 **混合检索引擎** - 向量检索 + BM25 + 重排序，Precision@5 >0.90
- 🛡️ **质量保证体系** - 5层验证流水线，幻觉率<10%
- 🕸️ **知识图谱推理** - GraphRAG支持多跳推理
- 📎 **精确引用溯源** - 文档/段落/字符三层追溯
- 🔬 **实时执行追踪** - SSE流式状态推送
- 🔐 **企业级安全** - JWT认证 + RBAC权限
- 🤖 **多智能体协作** - 11个专业Agent协同工作

### ✨ v0.6.2 新特性

**项目重命名与监控系统完善** (2026-07-06)

- 🏷️ **项目重命名**: 从"Multi-Agent RAG Local v4"更名为"QueryMind（智询）"
- 📊 **监控系统完善**: Prometheus + Grafana + Alertmanager完整监控栈
- 🔍 **健康检查增强**: 8个服务依赖的综合健康检查
- 📈 **业务指标**: Agent执行、检索质量、LLM成本、缓存命中率追踪
- 🔧 **熔断器集成**: LLM API、向量库、图数据库全面熔断保护
- 📝 **结构化日志**: Structlog配置，JSON输出，动态日志级别
- 🚨 **告警规则**: 30+预定义告警规则，覆盖Critical/Warning/Info
- 📚 **监控文档**: 完整的部署指南、使用手册、实施路线图

📖 [v0.6.2 发布说明](./docs/releases/RELEASE_NOTES_v0.6.2.md) | [v0.6.1 发布说明](./docs/releases/RELEASE_NOTES_v0.6.1.md)

---

## 🧭 企业化配置与一键部署

新的配置与部署入口已集中到 config/ 和 deploy/，运行时生成文件统一放在 .runtime/（不会提交 Git）。完整说明见 [配置与部署指南](./docs/zh-CN/guides/configuration-governance.md)。

`ash
export OPENAI_API_KEY="your-api-key"
./deploy/scripts/deploy.sh production balanced
`

PowerShell 使用：$env:OPENAI_API_KEY = "your-api-key"; .\deploy\scripts\deploy.ps1 -Environment production -Profile balanced。
## 🚀 快速开始

### 方法1: Docker部署（兼容入口）

**一键启动完整服务栈**

```bash
# 1. 克隆仓库
git clone https://github.com/pocheang/querymind.git
cd querymind

# 2. 配置环境变量
cp .env.docker.example .env
nano .env  # 设置密码和API密钥

# 3. 启动所有服务
docker-compose up -d

# 4. 初始化数据库
docker-compose exec backend python scripts/init_db.py
```

**访问应用**
- 🌐 前端界面: http://localhost
- 🔧 后端API: http://localhost:8000
- 📊 API文档: http://localhost:8000/docs
- 🕸️ Neo4j: http://localhost:7474

📖 [完整Docker部署指南](./DOCKER_DEPLOYMENT.md)

---

### 方法2: 本地开发环境

**前置要求**
- Python 3.11+
- Node.js 16+
- PostgreSQL 14+ (可选)
- Neo4j 5+ (可选)

**安装步骤**

1. **克隆仓库**

```bash
git clone https://github.com/pocheang/querymind.git
cd querymind
```

2. **创建环境**

```bash
conda env create -f environment.yml
conda activate rag-local
```

3. **配置环境变量**

```bash
cp .env.example .env
# 编辑 .env 文件，配置API密钥等
```

4. **初始化数据库**

```bash
python scripts/init_db.py
```

5. **启动后端服务**

```bash
uvicorn app.main:app --reload --port 8000
```

6. **启动前端服务**

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 开始使用！

### 基本使用

```python
from app.main import query_system

# 简单查询
result = query_system("什么是机器学习？")
print(result["answer"])

# 带引用的查询
result = query_system(
    "解释深度学习的原理",
    include_sources=True
)
print(result["answer"])
print(result["sources"])
```

---

## 🏗️ 系统架构

### 整体架构

QueryMind 采用**分层解耦 + 多智能体协作**的现代化架构，结合 LangGraph 状态机实现高可靠、可追溯的企业级 RAG 系统。

---

## 🏛️ 架构视图 1：分层逻辑架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          🌐 表现层 (Presentation Layer)                       │
│  ┌──────────────────────┐        ┌─────────────────────────────────────┐   │
│  │   Web Frontend       │        │     API Gateway (FastAPI)          │   │
│  │  React 18 + Vite     │◄──────►│   RESTful API + WebSocket/SSE      │   │
│  │  TypeScript + Axios  │        │   CORS + Rate Limiting + Auth      │   │
│  └──────────────────────┘        └─────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                       🧠 编排层 (Orchestration Layer)                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │            Enhanced RAG Workflow (质量保证编排器)                       │   │
│  │  • 5个质量检查点  • 智能重试  • 熔断器  • 超时保护  • 降级策略           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │            LangGraph StateGraph (状态机编排)                            │   │
│  │  • 9个处理节点  • 条件路由边  • 共享状态  • 执行追踪  • 错误恢复         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        🤖 智能体层 (Agent Layer) - 11个Agent                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ 路由决策层 (2个) │  │ 检索执行层 (4个) │  │  质量保证层 (3个)         │   │
│  │ • Router Agent │  │ • Vector RAG    │  │  • Retrieval Quality    │   │
│  │ • Route Valid. │  │ • Graph RAG     │  │  • Answer Validator     │   │
│  │   99% 准确率    │  │ • React Agent   │  │  • Context Tracker      │   │
│  └─────────────────┘  │ • Web Research  │  │   4层验证级联            │   │
│                       └─────────────────┘  └──────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                编排合成层 (2个)                                      │     │
│  │  • Quality Orchestrator (5维分数融合)  • Synthesis Agent (引用优先)  │     │
│  └───────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         🔧 服务层 (Service Layer)                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ 基础服务         │  │ 安全服务         │  │  监控服务                 │   │
│  │ • Bulkhead      │  │ • Auth Service  │  │  • Agent Tracker        │   │
│  │ • Circuit Break │  │ • RBAC          │  │  • Log Buffer           │   │
│  │ • Shadow Queue  │  │ • JWT Verify    │  │  • Metrics Collector    │   │
│  └─────────────────┘  └─────────────────┘  └──────────────────────────┘   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ 智能服务         │  │ 查询服务         │  │  内容服务                 │   │
│  │ • Language Det. │  │ • Query Decomp. │  │  • Document Processor   │   │
│  │ • Intent Recog. │  │ • Query Expand. │  │  • Chunker              │   │
│  │ • Query Rewrite │  │ • Entity Extract│  │  • Graph Extractor      │   │
│  └─────────────────┘  └─────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        📊 数据访问层 (Data Access Layer)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ 检索器           │  │ 客户端           │  │  缓存                     │   │
│  │ • Vector Retr.  │  │ • Neo4j Client  │  │  • Router Cache         │   │
│  │ • BM25 Retr.    │  │ • ChromaDB CLI  │  │  • Graph Cache          │   │
│  │ • Hybrid Retr.  │  │ • LLM Client    │  │  • Shared Cache         │   │
│  │ • Reranker      │  │ • Embedding CLI │  │  • Redis Cache (可选)    │   │
│  └─────────────────┘  └─────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        💾 数据存储层 (Data Storage Layer)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ 向量存储         │  │ 图数据库         │  │  关系数据库               │   │
│  │ ChromaDB        │  │ Neo4j           │  │  PostgreSQL              │   │
│  │ • 语义检索      │  │ • 知识图谱       │  │  • 用户管理               │   │
│  │ • 3M+ 向量      │  │ • 实体/关系      │  │  • 会话历史               │   │
│  └─────────────────┘  └─────────────────┘  │  • 审计日志               │   │
│  ┌─────────────────┐  ┌─────────────────┐  │  • 权限配置               │   │
│  │ 文档存储         │  │ 缓存/队列        │  └──────────────────────────┘   │
│  │ 本地文件系统     │  │ Redis (可选)     │                                  │
│  │ • PDF/DOCX/TXT │  │ • 会话缓存       │                                  │
│  └─────────────────┘  └─────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 架构视图 2：LangGraph 状态机工作流

```
                            ┌─────────────┐
                            │  用户查询    │
                            └──────┬──────┘
                                   ↓
                        ┌──────────────────────┐
                        │   Router Node        │ ← Few-shot (6 examples)
                        │  (路由决策节点)        │ ← Confidence Calibration
                        └──────────┬───────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Entry Decider Node   │ ← 条件路由
                        │  (路由分发节点)        │ ← 置信度 < 0.6 → Web
                        └──────────┬───────────┘
                                   ↓
                 ┌─────────────────┼─────────────────┐
                 ↓                 ↓                 ↓
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │  Vector Node   │ │  Graph Node    │ │   Web Node     │
        │  (向量检索)     │ │  (图谱查询)     │ │  (Web搜索)      │
        └────────┬───────┘ └────────┬───────┘ └────────┬───────┘
                 │                  │                  │
                 │  ← Vector Retriever + BM25 + Rerank │
                 │  ← Cypher Query + Entity Matching   │
                 │  ← Search Engine + Content Filter   │
                 └─────────────────┼─────────────────┘
                                   ↓
                        ┌──────────────────────┐
                        │ Vector Decider Node  │ ← 检索质量评估
                        │  (检索质量检查)       │ ← Quality < 0.6 → Retry
                        └──────────┬───────────┘
                                   ↓
                    ┌──────────────────────────┐
                    │ Adaptive Planner Node    │ ← 动态规划
                    │  (自适应任务规划)         │ ← 决定是否需要推理
                    └──────────┬───────────────┘
                               ↓
                    ┌──────────────────────────┐
                    │     React Node           │ ← 多跳推理 (可选)
                    │  (ReAct推理节点)          │ ← Thought-Action-Obs
                    └──────────┬───────────────┘
                               ↓
                    ┌──────────────────────────┐
                    │   Synthesis Node         │ ← Citation-First
                    │  (答案合成节点)           │ ← Query Type Templates
                    └──────────┬───────────────┘
                               ↓
                    ┌──────────────────────────┐
                    │  Graph Decider Node      │ ← 4层验证级联
                    │  (答案质量检查)           │ ← Valid? → Output : Retry
                    └──────────┬───────────────┘
                               ↓
                    ┌──────────────────────────┐
                    │   Quality Report Node    │ ← 5维分数融合
                    │  (质量报告生成)           │ ← Quality Score + Breakdown
                    └──────────┬───────────────┘
                               ↓
                            ┌──────────┐
                            │ 最终答案  │ ← 答案 + 引用 + 质量报告
                            └──────────┘

【状态共享】StateGraph 在所有节点间共享:
• query: 原始查询
• resolved_query: 消解后查询
• route_decision: 路由决策
• retrieval_results: 检索结果
• retrieval_quality: 检索质量
• answer: 生成答案
• citations: 引用列表
• validation_result: 验证结果
• quality_report: 质量报告
• context: 上下文历史
• retry_count: 重试计数
• execution_metadata: 执行元数据
```

---

## 📡 架构视图 3：数据流与交互

```
┌─────────────┐                                              ┌─────────────┐
│   用户界面   │                                              │  管理界面   │
└──────┬──────┘                                              └──────┬──────┘
       │ HTTP/WebSocket                                             │ HTTP
       ↓                                                            ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Gateway                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────────┐  │
│  │ Auth Mid.  │→ │ Rate Limit │→ │ CORS Mid.  │→ │ Req. Timing Mid.│  │
│  └────────────┘  └────────────┘  └────────────┘  └─────────────────┘  │
└──────────────────────────────┬───────────────────────────────────────────┘
                               ↓
       ┌───────────────────────┴────────────────────────┐
       ↓                                                 ↓
┌─────────────────┐                            ┌─────────────────┐
│  Query Pipeline │                            │  Admin Pipeline │
└────────┬────────┘                            └────────┬────────┘
         ↓                                              ↓
┌──────────────────────┐                      ┌──────────────────────┐
│ Enhanced RAG Workflow│                      │  Admin Operations    │
│  • Context Resolve   │                      │  • User Management   │
│  • Route Decision    │                      │  • Config Update     │
│  • Retrieval Execute │                      │  • Analytics Query   │
│  • Quality Check     │                      │  • Log Analysis      │
│  • Answer Synthesis  │                      └──────────────────────┘
│  • Score Fusion      │
└────────┬─────────────┘
         ↓
    ┌────┴────┐
    ↓         ↓         ↓         ↓
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Vector  │ │ Graph  │ │  Web   │ │ LLM    │
│Retriever│ │Neo4j CLI│ │Search  │ │Client  │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
    ↓          ↓          ↓          ↓
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ChromaDB│ │ Neo4j  │ │Google  │ │OpenAI  │
│ (本地)  │ │(本地/云)│ │Search  │ │Claude  │
└────────┘ └────────┘ │API     │ │Haiku   │
                      └────────┘ └────────┘
```

---

## 🛡️ 架构视图 4：质量保证体系

```
┌─────────────────────────────────────────────────────────────────┐
│                    质量保证 5 层防线                              │
└─────────────────────────────────────────────────────────────────┘

【Layer 1: 路由质量保证】 <50ms
┌──────────────────────────────────────────┐
│ Route Validator Agent                    │
│ • 路由决策一致性检查                       │
│ • 置信度阈值验证 (>0.6)                   │
│ • 边缘case检测                            │
│ → 失败触发 Web Fallback                   │
└──────────────────────────────────────────┘

【Layer 2: 检索质量保证】 200-500ms
┌──────────────────────────────────────────┐
│ Retrieval Quality Agent                  │
│ • LLM批量相关性打分 (Claude Haiku)        │
│ • 3级相关性评估 (高/中/低)                 │
│ • 低质量文档过滤                          │
│ → 平均相关性 <0.5 触发重试                │
└──────────────────────────────────────────┘

【Layer 3: 答案质量保证】 200-400ms
┌──────────────────────────────────────────┐
│ Answer Validator Agent (4层级联)          │
│ L1: 规则检查 (5ms) - 长度/格式/结构       │
│ L2: NLI验证 (150ms) - 事实一致性 [核心]   │
│ L3: 引用完整性 (10ms) - Citation检查      │
│ L4: 深度LLM分析 (1-2s) - 幻觉检测 [可选]  │
│ → NLI分数 <0.85 触发答案重生成            │
└──────────────────────────────────────────┘

【Layer 4: 质量分数融合】 <5ms
┌──────────────────────────────────────────┐
│ Quality Orchestrator Agent               │
│ • 5维加权融合 (路由10% + 检索30% +        │
│   事实45% + 质量10% + 引用5%)            │
│ • 惩罚规则 (幻觉风险×0.7, 低置信度×0.8)   │
│ → 综合分数 <0.6 触发降级策略              │
└──────────────────────────────────────────┘

【Layer 5: 上下文质量保证】 20-50ms
┌──────────────────────────────────────────┐
│ Context Tracker Agent                    │
│ • 指代消解准确性检查                       │
│ • 会话上下文一致性验证                     │
│ • 多轮对话逻辑连贯性                       │
│ → 上下文冲突触发重新路由                   │
└──────────────────────────────────────────┘

【容错机制】
• 智能重试: 最多2次路由重试 + 2次答案重试
• 熔断器: 连续失败5次 → 30秒熔断 → 降级模式
• 超时保护: 总请求10秒超时 → 快速失败
• 降级策略: 高质量失败 → Web搜索 → 缓存答案
```

---

## 🏗️ 架构设计原则

### 1. **分层解耦** (Layered Decoupling)
- 表现层、编排层、智能体层、服务层、数据层职责分离
- 每层独立演化，降低耦合度
- 层间通过接口通信，支持独立测试

### 2. **专业化智能体** (Specialized Agents)
- 每个 Agent 专注单一职责（Single Responsibility）
- 11 个 Agent 协作 > 1 个通用 Agent
- 便于独立优化、测试、替换

### 3. **状态机编排** (StateGraph Orchestration)
- LangGraph 管理复杂工作流
- 节点 = 处理单元，边 = 条件路由
- 共享状态 + 事件驱动 = 可追溯执行

### 4. **质量优先** (Quality-First)
- 5 层质量防线，覆盖路由→检索→生成→验证→融合
- Citation-First 生成纪律，每个声明必须有引用
- 4 层验证级联，幻觉率从 27.5% 降至 8%

### 5. **容错韧性** (Fault Tolerance & Resilience)
- 智能重试 + 熔断器 + 降级策略
- 超时保护 + 资源隔离 (Bulkhead)
- 失败快速恢复，系统可用性 >99.5%

### 6. **可观测性** (Observability)
- Agent 执行追踪 + 结构化日志
- 性能指标采集 (延迟、准确率、错误率)
- SSE 实时流式状态推送

### 7. **水平扩展** (Horizontal Scalability)
- 无状态服务 + 有状态数据分离
- 支持多实例部署 + 负载均衡
- Redis 缓存层支持分布式扩展

### 核心框架组件

#### 1. **LangGraph 状态机** (app/graph/)
- **StateGraph**: 定义查询处理的有向无环图 (DAG)
- **Node**: 处理节点（router_node, vector_node, graph_node, synthesis_node等）
- **Edge**: 条件路由边（decider_nodes: entry_decider, vector_decider, graph_decider）
- **State**: 共享状态对象（查询、上下文、检索结果、答案等）

#### 2. **增强型 RAG 工作流** (app/agents/enhanced_rag_workflow.py)
- `EnhancedRAGWorkflow`: 生产级质量保证编排器
- 5个质量检查点: 路由验证 → 检索质量 → 答案验证 → 分数融合 → 上下文追踪
- 智能重试策略: 最多2次路由重试 + 2次答案重试
- 熔断器模式: 连续失败5次触发降级

#### 3. **多层缓存系统**
- **Router Cache** (app/agents/router_calibration.py): 路由决策缓存
- **Graph RAG Cache** (app/agents/graph_rag_cache.py): Cypher查询结果缓存
- **Shared Cache** (app/agents/shared_cache.py): 跨Agent共享缓存
- **Redis Cache** (可选): 分布式缓存层

#### 4. **服务层** (app/services/)
- **Bulkhead**: 资源隔离与过载保护
- **Circuit Breaker**: 熔断器实现
- **Agent Execution Tracker**: Agent执行追踪与监控
- **Language Analytics**: 多语言检测与处理
- **Query Decomposer**: 复杂查询分解
- **Shadow Queue**: 后台任务队列

### 核心 Agent 架构详解

QueryMind 采用**专业化 + 协作**的多智能体设计，共 11 个核心 Agent，分为 4 层架构。

---

## 📍 第一层：路由决策层 (Routing Layer)

### 1️⃣ **Enhanced Router Agent** - 智能路由与查询分解
**文件**: `app/agents/enhanced_router_agent.py` + `app/agents/router_agent.py`

**核心职责**:
- 分析查询意图，选择最优执行路径 (Vector/Graph/Web/React)
- 可选查询分解：将复杂查询拆解为多个子查询

**关键特性**:
- **Few-shot Learning**: 基于 6 个精选示例的上下文学习 (router_examples.py)
- **历史校准**: 根据历史准确率动态调整置信度 (router_calibration.py)
- **置信度区间**: 5 个校准档位 (0.5-0.6: ×0.85, ..., 0.9-1.0: ×1.05)
- **查询分解**: 支持将 "对比A和B的优缺点" 拆解为多个子问题
- **路由缓存**: 相同查询复用历史决策

**决策流程**:
```python
1. 查询预处理 (语言检测、意图识别)
2. Few-shot 推理 (6个示例 + 当前查询)
3. 置信度计算 (LLM输出 → 历史校准)
4. 路由选择 (vector/graph/web/react)
5. 缓存决策 (避免重复推理)
```

**性能指标**:
- 准确率: **99%** (v0.6.0, +4.2% vs v0.5.0)
- 平均延迟: 100-200ms
- 低置信度阈值: <0.6 触发 fallback

---

### 2️⃣ **Route Validator Agent** - 路由验证
**文件**: `app/agents/route_validator_agent.py`

**核心职责**:
- 验证 Router Agent 的决策合理性
- 检测边缘 case 和低置信度路由

**关键特性**:
- **一致性检查**: 路由类型与查询特征是否匹配
- **置信度验证**: 置信度 <0.6 → 标记为 "needs_review"
- **Fallback 触发**: 验证失败 → 触发 Web 搜索降级
- **执行时间**: <50ms (纯规则 + 轻量 LLM 调用)

**验证规则**:
```python
- Vector路径: 查询需包含概念词/定义词
- Graph路径: 查询需包含实体/关系词
- 置信度<0.6: 自动标记需要人工审核
```

---

## 📍 第二层：信息检索层 (Retrieval Layer)

### 3️⃣ **Enhanced Vector RAG Agent** - 混合向量检索
**文件**: `app/agents/enhanced_vector_rag_agent.py` + `app/agents/vector_rag_agent.py`

**核心职责**:
- 基于语义相似度的文档检索
- Vector + BM25 混合检索 + 重排序

**关键特性**:
- **查询扩展**: 
  - 实体提取 (NER)
  - 同义词扩展
  - 查询改写
- **混合检索**:
  - 向量检索 (Sentence-Transformers BGE-M3)
  - BM25 关键词检索 (Rank-BM25)
  - RRF 融合 (Reciprocal Rank Fusion)
- **动态 Top-K**:
  - 简单查询: top_k=15
  - 中等查询: top_k=20
  - 复杂查询: top_k=30
- **重排序**: BGE-Reranker-V2-M3 (top 5)

**检索流程**:
```
查询 → 查询扩展 → 并行检索 (Vector + BM25) 
→ RRF融合 → 重排序 → Top 5文档
```

**性能指标**:
- Precision@5: **0.927**
- Recall@10: >0.85
- 平均延迟: 500-800ms

---

### 4️⃣ **Graph RAG Agent** - 知识图谱推理
**文件**: `app/agents/graph_rag_agent_enhanced.py` + `app/agents/graph_rag_agent.py`

**核心职责**:
- 基于 Neo4j 知识图谱的关系推理
- 实体识别 + Cypher 查询生成

**关键特性**:
- **多阶段实体提取**:
  - **Stage 1**: 规则匹配 (正则表达式)
  - **Stage 2**: LLM 提取 (GPT-4)
  - **Stage 3**: 模糊匹配 (Levenshtein ≤2)
- **Cypher 查询生成**: 
  - 自动生成 Cypher 语句
  - 查询验证 (防止注入)
  - 查询缓存 (graph_rag_cache.py)
- **关系遍历**: 
  - 1-hop: 直接关系
  - 2-hop: 二阶关系
  - 3-hop: 多跳推理
- **结果过滤**: 
  - 相关性阈值过滤
  - 去重与排序

**查询示例**:
```cypher
// 查询实体关系
MATCH (e:Entity {name: "Transformer"})-[r]-(related)
RETURN e, r, related
LIMIT 10

// 多跳推理
MATCH path = (a:Entity)-[*1..3]-(b:Entity)
WHERE a.name = "深度学习"
RETURN path
```

**性能指标**:
- 查询成功率: **95%**
- 平均延迟: 800-1500ms
- 缓存命中率: 60-70%

---

### 5️⃣ **React Agent** - 多跳推理与工具调用
**文件**: `app/agents/react_agent.py`

**核心职责**:
- 处理需要多步推理的复杂查询
- 工具调用编排 (Reasoning + Acting)

**关键特性**:
- **ReAct 范式**: 
  - Thought: 思考下一步做什么
  - Action: 调用工具 (Search/Calculate/Query)
  - Observation: 观察结果
  - Repeat: 循环直至得出答案
- **工具集成**:
  - Vector Search Tool
  - Graph Query Tool
  - Web Search Tool
  - Calculator Tool
- **Chain-of-Thought**: 
  - 显式推理步骤
  - 中间结果验证
  - 推理路径可解释

**推理示例**:
```
Query: "比较 Transformer 和 LSTM 的优缺点"

Step 1 - Thought: 需要分别查询两个模型的信息
Step 2 - Action: VectorSearch("Transformer 架构")
Step 3 - Observation: 获得 Transformer 的自注意力机制描述
Step 4 - Action: VectorSearch("LSTM 循环神经网络")
Step 5 - Observation: 获得 LSTM 的门控机制描述
Step 6 - Thought: 整合信息进行对比
Step 7 - Answer: [生成对比表格]
```

**性能指标**:
- 推理准确率: **87%**
- 平均步数: 3-5 steps
- 平均延迟: 2000-4000ms

---

### 6️⃣ **Web Research Agent** - Web 补充搜索
**文件**: `app/agents/web_research_agent.py`

**核心职责**:
- 知识库缺失时的 Web Fallback
- 搜索引擎集成与结果过滤

**关键特性**:
- **搜索引擎集成**: 
  - Google Search API
  - Bing Search API
  - DuckDuckGo (可选)
- **结果过滤**:
  - 来源可信度评分
  - 广告与垃圾内容过滤
  - 时效性检查
- **内容提取**:
  - HTML → Markdown 转换
  - 关键段落提取
  - 引用格式化
- **降级策略**: 
  - 仅在本地检索失败时触发
  - 优先级: 本地 > Web

**性能指标**:
- 触发率: 5-10% (大部分查询本地满足)
- 平均延迟: 1500-2500ms
- 准确率: 75-80%

---

## 📍 第三层：质量保证层 (Quality Assurance Layer)

### 7️⃣ **Retrieval Quality Agent** - 检索质量评估
**文件**: `app/agents/retrieval_quality_agent.py` + `app/agents/relevance_scoring.py`

**核心职责**:
- 评估检索文档与查询的相关性
- 批量相关性打分

**关键特性**:
- **批量打分**: 
  - 使用 Claude Haiku (高性价比)
  - 并行评估多个文档 (批大小=10)
  - 平均延迟 <100ms/文档
- **3级相关性**:
  - **高相关** (0.8-1.0): 直接回答查询
  - **中相关** (0.5-0.8): 部分相关
  - **低相关** (0.0-0.5): 不相关，过滤
- **质量指标**:
  - 平均相关性分数
  - 高相关文档比例
  - 上下文覆盖度
- **异步并行**: 
  - asyncio 并发评估
  - 平均总延迟: 200-500ms

**评分示例**:
```python
Query: "什么是 Transformer？"
Doc1: "Transformer 是 Google 提出的..." → Score: 0.95 (高相关)
Doc2: "深度学习包括 CNN、RNN..." → Score: 0.60 (中相关)
Doc3: "Python 编程基础..." → Score: 0.15 (低相关, 过滤)
```

**性能指标**:
- 相关性准确率: **92%**
- 平均延迟: 200-500ms
- 并发度: 10 文档/批次

---

### 8️⃣ **Answer Validator Agent** - 4层答案验证
**文件**: `app/agents/answer_validator_agent.py` + `app/agents/answer_validator_batch.py`

**核心职责**:
- 4层验证级联 (Validation Cascade)
- 幻觉检测 + 事实一致性验证

**4层验证架构**:

**L1: 规则检查** (~5ms)
```python
- 长度检查: 50 < len(answer) < 2000
- 结构检查: 是否包含引用标记 [doc_id:page]
- 格式检查: 是否回答了问题
- 禁用词检查: 不含"我不知道"等
```

**L2: NLI 验证** (50-150ms) - **核心层**
```python
- 模型: cross-encoder/nli-deberta-v3-base
- 任务: 判断答案是否与上下文矛盾
- 批处理: 句子级批量推理 (batch_size=32)
- 阈值: entailment_score > 0.85 通过
```

**L3: 引用完整性** (~10ms)
```python
- 引用计数: 每个事实性陈述是否有引用
- 引用真实性: 答案中的引用是否在上下文中存在
- 引用格式: [doc_id:page] 格式正确性
- 最低要求: 每个声明至少 1 个引用
```

**L4: 深度 LLM 分析** (1000-2000ms) - **可选层**
```python
- 模型: GPT-4 或 Claude Opus
- 任务: 深度幻觉检测、逻辑一致性检查
- 触发条件: L2 NLI 分数 0.75-0.85 (灰色区域)
- 输出: 详细问题列表 + 改进建议
```

**幻觉检测** (app/agents/hallucination_patterns.py):
```python
- 日期幻觉: "2025年发生..." 但上下文是2023
- 数字幻觉: "准确率99%" 但上下文说"约90%"
- 实体幻觉: 捏造不存在的人名/地名
- 否定幻觉: 上下文"不支持X" 答案说"支持X"
```

**性能指标**:
- NLI 准确率: **95.5%**
- 幻觉检测率: **92%** (v0.6.0: 幻觉率从27.5%降至8%)
- 平均延迟: 200-400ms (L1-L3), +1000ms (L4)
- 假阳性率: <5%

---

### 9️⃣ **Context Tracker Agent** - 多轮对话管理
**文件**: `app/agents/context_tracker_agent.py`

**核心职责**:
- 多轮对话的上下文跟踪
- 会话状态管理与指代消解

**关键特性**:
- **会话存储**: 
  - 内存存储 (短期)
  - PostgreSQL 存储 (长期)
  - 自动过期清理 (30分钟)
- **上下文窗口**: 
  - 滑动窗口: 最近 5 轮对话
  - 摘要压缩: 超过 5 轮自动摘要
- **指代消解**:
  - "它" → 上一轮提到的实体
  - "这个" → 上下文中的概念
  - "继续" → 延续上一个主题
- **路由提示**: 
  - 基于历史决策提供路由建议
  - 避免重复检索

**对话示例**:
```
Turn 1: "什么是 Transformer？"
  → Context: {entity: "Transformer", topic: "架构"}

Turn 2: "它有什么优点？"
  → Resolve: "它" = "Transformer"
  → Query: "Transformer 有什么优点？"
```

**性能指标**:
- 指代消解准确率: **88%**
- 平均延迟: 20-50ms
- 会话存储: 内存 + PostgreSQL

---

## 📍 第四层：编排与合成层 (Orchestration & Synthesis Layer)

### 🔟 **Quality Orchestrator Agent** - 质量分数融合
**文件**: `app/agents/quality_orchestrator_agent.py`

**核心职责**:
- 融合所有质量信号，计算最终质量分数
- 综合评估与降级决策

**加权融合公式** (A/B 测试优化):
```python
Overall_Score = 
  Route_Confidence    × 10%  (路由置信度)
+ Retrieval_Quality   × 30%  (检索质量)
+ Factual_Consistency × 45%  (事实一致性) ← 最重要
+ Answer_Quality      × 10%  (答案质量)
+ Citation_Complete   × 5%   (引用完整性)
```

**惩罚规则**:
```python
if hallucination_risk > 0.3:
    score *= 0.7  # 幻觉风险惩罚
if route_confidence < 0.5:
    score *= 0.8  # 低置信路由惩罚
```

**质量等级**:
```python
score >= 0.85: 高质量 (无警告)
0.70 <= score < 0.85: 中等质量 (建议验证)
0.55 <= score < 0.70: 低质量 (谨慎参考)
score < 0.55: 极低质量 (强烈建议人工审核)
```

**性能指标**:
- 质量分数相关性: **0.88** (与人工评分)
- 执行时间: <5ms (纯计算)
- 降级触发率: 8-12%

---

### 1️⃣1️⃣ **Synthesis Agent** - Citation-First 答案生成
**文件**: `app/agents/synthesis_agent.py` + `app/agents/synthesis_templates.py`

**核心职责**:
- 基于检索结果生成最终答案
- Citation-First 生成纪律

**Citation-First 原则** (Task 13):
```
❌ 错误: 先写答案再补引用
✅ 正确: 每个声明必须同步标注引用

示例:
输入上下文: "[doc1:p3] Transformer uses self-attention"
输出答案: "Transformer uses self-attention [doc1:p3]"

强制规则:
1. 每个事实性陈述必须有引用 [doc_id:page]
2. 无引用 = 不能声明为事实
3. 禁止编造或推测
4. 引用必须在上下文中真实存在
```

**查询类型模板**:
```python
- 概念查询: "定义 + 核心特征 + 应用场景"
- 对比查询: "对比表格 + 优缺点 + 适用场景"
- 关系查询: "实体关系图 + 关系描述"
- 步骤查询: "分步指南 + 注意事项"
```

**Chain-of-Thought 推理**:
```
1. 问题分析: 用户真正想知道什么？
2. 上下文评估: 哪些事实可以提取？每个对应哪个引用？
3. 引用规划: 每个声明对应哪个 [doc_id:page]？
4. 答案结构: 如何组织答案？引用如何嵌入？
```

**后生成验证** (Fact Verifier):
```python
1. 引用真实性: 答案中的引用是否在上下文中存在？
2. 事实一致性: 答案是否与上下文矛盾？
3. 引用完整性: 是否所有声明都有引用？
4. 自动修正: 发现问题 → 重新生成 (最多1次)
```

**语言适配**:
```python
[Language: zh] → 100% 中文回答
[Language: en] → 100% 英文回答
严禁混用中英文
```

**性能指标**:
- 引用完整性: **96%** (v0.6.0, +13% vs v0.5.0)
- 幻觉率: **8%** (v0.6.0, -71% vs v0.5.0)
- 平均延迟: 1000-2000ms
- 事实准确率: **94%**

---

## 🔄 Agent 协作流程

### 完整查询处理流程:

```
1. 用户查询 → Context Tracker (指代消解)
2. Enhanced Router Agent (路由决策)
3. Route Validator Agent (验证路由)
4. ↓ 分支执行 (3选1)
   - Vector RAG Agent (向量检索)
   - Graph RAG Agent (图谱推理)
   - React Agent (多跳推理)
   - Web Research Agent (Web补充)
5. Retrieval Quality Agent (评估检索质量)
6. Synthesis Agent (生成答案)
7. Answer Validator Agent (4层验证)
8. Quality Orchestrator Agent (分数融合)
9. Context Tracker Agent (更新上下文)
10. 返回结果 (答案 + 引用 + 质量报告)
```

### 容错机制:

```python
# 智能重试
if quality_score < 0.6:
    if retry_count < 2:
        # 策略1: 增加 top_k
        # 策略2: 尝试替代路由
        # 策略3: 使用推理模型 (o1-mini)
        retry_with_variation()
    else:
        # 降级策略
        fallback_to_web_search()

# 熔断器
if consecutive_failures > 5:
    open_circuit_breaker()
    use_cached_response()
```

### 技术栈

#### 后端框架
- **FastAPI** - 高性能异步Web框架
- **LangGraph** - 多智能体编排与状态管理
- **LangChain** - LLM应用开发框架
- **Pydantic** - 数据验证与序列化

#### 数据存储
- **ChromaDB** - 向量数据库（语义检索）
- **Neo4j** - 知识图谱数据库（关系推理）
- **PostgreSQL** - 关系数据库（元数据、用户管理）
- **Redis** - 缓存层（可选）

#### AI/ML模型
- **OpenAI GPT-4** - 主LLM（路由、生成、推理）
- **OpenAI GPT-4-mini** - 快速验证任务
- **Claude Haiku** - 批量相关性评分（<100ms）
- **Sentence-Transformers** - 向量嵌入（BGE-M3）
- **BGE-Reranker** - 重排序模型
- **NLI模型** - 自然语言推理验证

#### 检索与NLP
- **Rank-BM25** - 关键词检索
- **Jieba** - 中文分词
- **Levenshtein** - 模糊匹配
- **SpaCy** - 实体提取（可选）

#### 前端技术
- **React 18** - UI框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **TailwindCSS** - 样式框架
- **Axios** - HTTP客户端
- **Server-Sent Events (SSE)** - 实时流式输出

#### 部署与容器化 🆕
- **Docker** - 容器化部署
- **Docker Compose** - 服务编排
- **Nginx** - 反向代理与静态文件服务
- **Multi-stage builds** - 优化镜像大小

#### 开发工具
- **Pytest** - 测试框架
- **Black** - 代码格式化
- **Pylint** - 代码检查
- **MyPy** - 类型检查
- **Pre-commit** - Git钩子

---

## 🔄 查询处理流程

### 标准查询工作流

```mermaid
graph TD
    A[用户查询] --> B[Router Agent]
    B --> C{路由决策}
    C -->|向量检索| D[Vector RAG Agent]
    C -->|图谱推理| E[Graph RAG Agent]
    C -->|复杂推理| F[React Agent]
    C -->|低置信度| G[Web Research Agent]
    
    D --> H[Retrieval Quality Agent]
    E --> H
    F --> H
    G --> H
    
    H --> I[Synthesis Agent]
    I --> J[Answer Validator Agent]
    J --> K{验证通过?}
    K -->|是| L[Quality Orchestrator]
    K -->|否| M[重试/降级]
    M --> B
    
    L --> N[最终答案+引用]
    N --> O[Context Tracker Agent]
    O --> P[返回用户]
```

### 处理阶段详解

#### 阶段1: 路由决策 (100-200ms)
1. **查询分析**: 提取意图、实体、复杂度
2. **Few-shot推理**: 基于6个示例样本
3. **置信度计算**: 历史准确率校准
4. **路由选择**: Vector/Graph/React/Web
5. **验证检查**: Route Validator确认合理性

#### 阶段2: 信息检索 (500-1500ms)
- **Vector路径**:
  - 查询扩展（实体+同义词）
  - 向量检索 + BM25检索
  - RRF融合
  - 重排序（top 5）
  
- **Graph路径**:
  - 实体提取（规则+LLM）
  - 模糊匹配实体
  - Cypher查询生成
  - 关系遍历
  
- **React路径**:
  - 问题分解
  - 多步推理
  - 工具调用链
  - 结果聚合

#### 阶段3: 质量评估 (200-500ms)
1. **相关性评分**: LLM批量打分
2. **文档过滤**: 低质量文档剔除
3. **上下文构建**: 组织检索结果

#### 阶段4: 答案生成 (1000-2000ms)
1. **模板选择**: 概念/比较/关系查询
2. **Citation-first**: 每个声明标注来源
3. **答案生成**: GPT-4合成答案
4. **事实验证**: 后生成检查

#### 阶段5: 多层验证 (200-400ms)
1. **L1 规则检查**: 长度、格式、结构
2. **L2 NLI验证**: 句子级事实检查
3. **L3 引用检查**: 完整性验证
4. **L4 深度分析**: LLM质量评估

#### 阶段6: 质量编排 (50-100ms)
- 融合所有质量分数
- 计算最终质量得分
- 决定是否需要重试

### 容错与降级策略

```python
# 智能重试策略
if quality_score < threshold:
    if retry_count < 2:
        # 策略1: 增加top-k
        # 策略2: 尝试替代路由
        # 策略3: 使用推理模型(o1-mini)
        retry_with_variation()
    else:
        # 降级策略
        fallback_to_simpler_route()

# 熔断器模式
if consecutive_failures > 5:
    open_circuit_breaker()
    use_fallback_route()
```

---

## 📊 性能指标

### 检索性能

- **Precision@5**: >0.90
- **Recall@10**: >0.85
- **MRR (Mean Reciprocal Rank)**: >0.91

### 生成质量

- **路由准确率**: 99%
- **NLI验证准确率**: 95.5%
- **幻觉率**: <10%
- **引用完整性**: 96%

### 系统性能

- **P95响应时间**: <4秒
- **并发能力**: 50+用户
- **系统可用性**: >99.5%
- **错误率**: <1%

> 💡 以上数据基于测试环境，实际性能可能因配置和数据量而异

---

## 📚 文档

### 部署文档

- [Docker部署指南](./DOCKER_DEPLOYMENT.md) - 容器化部署完整指南
- [部署指南](./docs/guides/deployment.md) - 传统部署方式

### 用户文档

- [快速开始指南](./docs/guides/getting-started.md)
- [配置说明](./docs/guides/configuration.md)
- [API参考](./docs/guides/api-reference.md)
- [常见问题](./docs/guides/faq.md)

### 开发文档

- [架构设计](./docs/architecture/README.md)
- [Agent系统](./docs/features/agents/README.md)
- [贡献指南](./CONTRIBUTING.md)

### 发布说明

- [v0.6.1 - 架构增强与Docker支持](./docs/releases/RELEASE_NOTES_v0.6.1.md)
- [v0.6.0 - 质量优化](./docs/releases/RELEASE_NOTES_v0.6.0.md)
- [v0.5.0 - 权限系统](./docs/releases/RELEASE_NOTES_v0.5.0.md)
- [完整历史](./docs/history/VERSION_HISTORY.md)

## 🛠️ 配置选项

### 核心配置文件

#### 1. 环境变量配置 (`.env`)

```bash
# LLM配置
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=2000

# 向量数据库
CHROMA_PERSIST_DIR=./data/chroma
EMBEDDING_MODEL=sentence-transformers/bge-m3

# 图数据库
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# 关系数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/querymind

# 系统配置
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

#### 2. 路由器配置 (`config/router_calibration.json`)

```json
{
  "calibration_buckets": {
    "0.5-0.6": {"multiplier": 0.85, "description": "低置信度"},
    "0.6-0.7": {"multiplier": 0.90, "description": "中低置信度"},
    "0.7-0.8": {"multiplier": 0.95, "description": "中等置信度"},
    "0.8-0.9": {"multiplier": 1.00, "description": "高置信度"},
    "0.9-1.0": {"multiplier": 1.05, "description": "极高置信度"}
  },
  "fallback_threshold": 0.6,
  "enable_few_shot": true,
  "num_examples": 6
}
```

#### 3. 检索配置 (`config/retrieval_config.json`)

```json
{
  "vector_search": {
    "top_k": 20,
    "similarity_threshold": 0.7,
    "enable_query_expansion": true
  },
  "bm25_search": {
    "top_k": 20,
    "k1": 1.5,
    "b": 0.75
  },
  "reranking": {
    "enabled": true,
    "model": "BAAI/bge-reranker-v2-m3",
    "top_n": 5
  },
  "dynamic_top_k": {
    "simple_query": 15,
    "medium_query": 20,
    "complex_query": 30
  }
}
```

#### 4. 质量验证配置 (`config/fact_verification.json`)

```json
{
  "nli_validation": {
    "enabled": true,
    "model": "cross-encoder/nli-deberta-v3-base",
    "threshold": 0.85,
    "batch_size": 32
  },
  "hallucination_detection": {
    "enabled": true,
    "check_dates": true,
    "check_numbers": true,
    "check_entities": true,
    "check_negations": true
  },
  "citation_requirements": {
    "require_citations": true,
    "min_citations_per_claim": 1,
    "citation_format": "[doc_id:page]"
  },
  "verification_threshold": 0.85
}
```

#### 5. 重试与熔断配置 (`config/retry_policy.json`)

```json
{
  "retry": {
    "max_retries": 2,
    "backoff_ms": [100, 500],
    "strategies": [
      "increase_top_k",
      "try_alternative_route",
      "use_reasoning_model"
    ]
  },
  "circuit_breaker": {
    "failure_threshold": 5,
    "timeout_seconds": 30,
    "half_open_after_seconds": 60,
    "success_threshold_to_close": 3
  }
}
```

### 性能调优指南

#### 提高检索精度
```python
# config/retrieval_config.json
{
  "vector_search": {
    "top_k": 30,  # 增加召回
    "similarity_threshold": 0.75  # 提高阈值
  },
  "reranking": {
    "top_n": 10  # 增加重排序数量
  }
}
```

#### 降低延迟
```python
# config/retrieval_config.json
{
  "vector_search": {
    "top_k": 15  # 减少检索量
  },
  "reranking": {
    "top_n": 3  # 减少重排序
  }
}

# config/fact_verification.json
{
  "nli_validation": {
    "batch_size": 64  # 增加批量大小
  }
}
```

#### 降低幻觉率
```python
# config/fact_verification.json
{
  "verification_threshold": 0.90,  # 提高验证阈值
  "citation_requirements": {
    "min_citations_per_claim": 2  # 要求更多引用
  }
}
```

---

## 🔧 开发

### 项目结构

```
querymind/
├── app/                          # 后端应用
│   ├── agents/                   # 11个核心Agent实现
│   │   ├── enhanced_router_agent.py        # 增强路由Agent (查询分解)
│   │   ├── router_agent.py                 # 基础路由Agent (Few-shot)
│   │   ├── router_calibration.py           # 路由置信度校准
│   │   ├── router_examples.py              # Few-shot示例库
│   │   ├── router_config.py                # 路由配置
│   │   ├── route_validator_agent.py        # 路由验证Agent
│   │   ├── route_accuracy_tracker.py       # 路由准确率追踪
│   │   ├── enhanced_vector_rag_agent.py    # 增强向量RAG Agent
│   │   ├── vector_rag_agent.py             # 基础向量RAG Agent
│   │   ├── graph_rag_agent_enhanced.py     # 增强图谱RAG Agent
│   │   ├── graph_rag_agent.py              # 基础图谱RAG Agent
│   │   ├── graph_rag_config.py             # 图谱配置
│   │   ├── graph_rag_cache.py              # 图谱查询缓存
│   │   ├── react_agent.py                  # ReAct推理Agent
│   │   ├── web_research_agent.py           # Web研究Agent
│   │   ├── retrieval_quality_agent.py      # 检索质量Agent
│   │   ├── relevance_scoring.py            # 相关性评分
│   │   ├── answer_validator_agent.py       # 答案验证Agent
│   │   ├── answer_validator_batch.py       # 批量验证
│   │   ├── validation_cascade.py           # 4层验证级联
│   │   ├── hallucination_patterns.py       # 幻觉检测模式
│   │   ├── fact_verification.py            # 事实验证
│   │   ├── context_tracker_agent.py        # 上下文追踪Agent
│   │   ├── quality_orchestrator_agent.py   # 质量编排Agent
│   │   ├── quality_models.py               # 质量数据模型
│   │   ├── quality_config.py               # 质量配置
│   │   ├── quality_logging.py              # 质量日志
│   │   ├── quality_thread_safety.py        # 线程安全
│   │   ├── synthesis_agent.py              # 答案合成Agent
│   │   ├── synthesis_templates.py          # 答案模板
│   │   ├── enhanced_rag_workflow.py        # 增强RAG工作流
│   │   ├── degradation_strategies.py       # 降级策略
│   │   ├── agent_config.py                 # Agent配置
│   │   └── shared_cache.py                 # 共享缓存
│   ├── api/                     # API路由
│   │   ├── main.py              # FastAPI应用入口
│   │   ├── dependencies.py      # 依赖注入
│   │   ├── middleware.py        # 中间件
│   │   └── routes/              # API路由模块
│   │       ├── query.py         # 查询API
│   │       ├── enhanced_query.py # 增强查询API
│   │       ├── advanced_rag.py  # 高级RAG API
│   │       ├── documents.py     # 文档管理
│   │       ├── sessions.py      # 会话管理
│   │       ├── auth.py          # 认证API
│   │       ├── health.py        # 健康检查
│   │       ├── evaluation.py    # 评估API
│   │       ├── analytics.py     # 分析API
│   │       ├── agent_tracking.py # Agent追踪
│   │       ├── admin_*.py       # 管理员API
│   │       └── prompts.py       # 提示词管理
│   ├── core/                    # 核心功能
│   │   ├── config.py            # 配置管理
│   │   ├── models.py            # LLM模型客户端
│   │   ├── embeddings.py        # 向量嵌入
│   │   ├── llm.py               # LLM封装
│   │   └── exceptions.py        # 异常定义
│   ├── graph/                   # 图谱操作
│   │   ├── neo4j_client.py      # Neo4j客户端
│   │   ├── entity_extraction.py # 实体提取
│   │   ├── cypher_validation.py # Cypher验证
│   │   ├── nodes/               # LangGraph节点
│   │   │   ├── router_node.py           # 路由节点
│   │   │   ├── vector_node.py           # 向量检索节点
│   │   │   ├── graph_node.py            # 图谱查询节点
│   │   │   ├── web_node.py              # Web搜索节点
│   │   │   ├── react_node.py            # ReAct推理节点
│   │   │   ├── synthesis_node.py        # 答案合成节点
│   │   │   ├── adaptive_planner_node.py # 自适应规划节点
│   │   │   ├── decider_nodes.py         # 决策节点
│   │   │   └── safe_wrappers.py         # 安全包装
│   │   └── routing/             # 路由逻辑
│   │       └── route_logic.py   # 路由决策逻辑
│   ├── services/                # 业务服务
│   │   ├── agent_execution_tracker.py  # Agent执行追踪
│   │   ├── auth_service.py             # 认证服务
│   │   ├── bulkhead.py                 # 资源隔离
│   │   ├── circuit_breaker.py          # 熔断器
│   │   ├── language_analytics.py       # 语言分析
│   │   ├── language_detector.py        # 语言检测
│   │   ├── query_decomposer.py         # 查询分解
│   │   ├── query_intent.py             # 意图识别
│   │   ├── shadow_queue.py             # 后台队列
│   │   ├── request_context.py          # 请求上下文
│   │   ├── answer_safety.py            # 答案安全
│   │   ├── explainability.py           # 可解释性
│   │   └── log_buffer.py               # 日志缓冲
│   ├── retrievers/              # 检索器
│   │   ├── vector_retriever.py  # 向量检索器
│   │   ├── bm25_retriever.py    # BM25检索器
│   │   ├── hybrid_retriever.py  # 混合检索器
│   │   └── reranker.py          # 重排序器
│   ├── ingestion/               # 数据导入
│   │   ├── document_processor.py # 文档处理
│   │   ├── chunker.py           # 文档分块
│   │   ├── metadata_extractor.py # 元数据提取
│   │   └── graph_extractor.py   # 图谱提取
│   ├── models/                  # 数据模型 (Pydantic)
│   │   ├── query_models.py      # 查询模型
│   │   ├── document_models.py   # 文档模型
│   │   ├── user_models.py       # 用户模型
│   │   └── response_models.py   # 响应模型
│   ├── evaluation/              # 评估模块
│   │   ├── metrics.py           # 评估指标
│   │   ├── benchmarks.py        # 基准测试
│   │   └── ab_testing.py        # A/B测试
│   ├── tools/                   # 工具集
│   │   └── web_search.py        # Web搜索工具
│   └── workflow/                # 工作流
│       └── langgraph_workflow.py # LangGraph工作流
│
├── frontend/                    # 前端应用 (React + TypeScript)
│   ├── src/
│   │   ├── components/         # React组件
│   │   │   ├── QueryInterface.tsx      # 查询界面
│   │   │   ├── AnswerDisplay.tsx       # 答案展示
│   │   │   ├── CitationViewer.tsx      # 引用查看器
│   │   │   ├── QualityIndicator.tsx    # 质量指示器
│   │   │   ├── SessionManager.tsx      # 会话管理
│   │   │   └── AdminDashboard.tsx      # 管理面板
│   │   ├── hooks/              # 自定义Hooks
│   │   │   ├── useQuery.ts     # 查询Hook
│   │   │   ├── useSSE.ts       # SSE流Hook
│   │   │   └── useAuth.ts      # 认证Hook
│   │   ├── pages/              # 页面
│   │   │   ├── HomePage.tsx    # 首页
│   │   │   ├── QueryPage.tsx   # 查询页
│   │   │   ├── HistoryPage.tsx # 历史页
│   │   │   └── AdminPage.tsx   # 管理页
│   │   ├── services/           # API服务
│   │   │   ├── api.ts          # API封装
│   │   │   └── sse.ts          # SSE服务
│   │   ├── utils/              # 工具函数
│   │   │   ├── formatting.ts   # 格式化
│   │   │   └── validation.ts   # 验证
│   │   ├── types/              # TypeScript类型
│   │   ├── App.tsx             # 应用根组件
│   │   └── main.tsx            # 入口文件
│   ├── public/                 # 静态资源
│   ├── package.json            # 依赖配置
│   ├── tsconfig.json           # TS配置
│   └── vite.config.ts          # Vite配置
│
├── config/                      # 配置文件
│   ├── router_calibration.json          # 路由校准配置
│   ├── retrieval_config.json            # 检索配置
│   ├── fact_verification.json           # 事实验证配置
│   ├── retry_policy.json                # 重试策略
│   └── circuit_breaker.json             # 熔断器配置
│
├── tests/                       # 测试
│   ├── agents/                 # Agent测试
│   │   ├── test_router_agent.py
│   │   ├── test_vector_rag_agent.py
│   │   ├── test_graph_rag_agent.py
│   │   ├── test_answer_validator.py
│   │   └── test_quality_orchestrator.py
│   ├── api/                    # API测试
│   │   ├── test_query_api.py
│   │   └── test_auth_api.py
│   ├── integration/            # 集成测试
│   │   ├── test_end_to_end.py
│   │   └── test_workflow.py
│   ├── test_agent_classifier.py         # Agent分类器测试
│   ├── test_pdf_agent_guard.py          # PDF Agent守护测试
│   ├── test_history_store.py            # 历史存储测试
│   ├── test_auth_service.py             # 认证服务测试
│   ├── test_prompt_checker.py           # 提示检查器测试
│   ├── test_pdf_query_logic.py          # PDF查询逻辑测试
│   ├── test_memory_store.py             # 内存存储测试
│   ├── test_rbac.py                     # RBAC测试
│   ├── test_input_normalizer.py         # 输入规范化测试
│   ├── test_graph_tools_enhancement.py  # 图谱工具增强测试
│   ├── test_citation_grounding.py       # 引用基础测试
│   ├── test_resilience.py               # 韧性测试
│   ├── test_answer_safety.py            # 答案安全测试
│   ├── test_consistency_guard.py        # 一致性守护测试
│   ├── test_web_research_filtering.py   # Web研究过滤测试
│   ├── test_evidence_conflict.py        # 证据冲突测试
│   ├── test_runtime_ops.py              # 运行时操作测试
│   ├── test_chunker_parent_child.py     # 分块器测试
│   ├── test_history_session_security.py # 历史会话安全测试
│   └── test_security_hardening.py       # 安全加固测试
│
├── scripts/                     # 工具脚本
│   ├── ingest.py               # 数据导入脚本
│   ├── query_cli.py            # CLI查询工具
│   ├── benchmark_pipeline.py   # 基准测试
│   ├── eval_retrieval.py       # 检索评估
│   ├── ab_comparison.py        # A/B对比 (已废弃，见docs/)
│   ├── load_test_query.py      # 负载测试
│   ├── perf_gate.py            # 性能门控
│   ├── chaos_probe.py          # 混沌测试
│   ├── apply_rollback_profile.py # 回滚配置
│   ├── migrate_*.py            # 数据迁移脚本
│   └── init_db.py              # 数据库初始化
│
├── docs/                        # 文档
│   ├── guides/                 # 用户指南
│   │   ├── getting-started.md
│   │   ├── configuration.md
│   │   ├── api-reference.md
│   │   └── faq.md
│   ├── releases/               # 发布说明
│   │   ├── RELEASE_NOTES_v0.6.0.md
│   │   └── RELEASE_NOTES_v0.5.0.md
│   ├── history/                # 历史文档
│   │   └── VERSION_HISTORY.md
│   ├── architecture/           # 架构文档
│   │   ├── README.md
│   │   ├── agent-system.md
│   │   └── quality-assurance.md
│   ├── features/               # 功能文档
│   │   ├── agents/
│   │   │   └── README.md
│   │   └── routing.md
│   └── DEPLOYMENT_GUIDE_v0.6.0.md # 部署指南
│
├── data/                        # 数据目录
│   ├── chroma/                 # ChromaDB向量数据库
│   ├── documents/              # 原始文档
│   └── cache/                  # 缓存数据
│
├── logs/                        # 日志目录
│   ├── app.log                 # 应用日志
│   ├── agents.log              # Agent日志
│   ├── performance.log         # 性能日志
│   └── error.log               # 错误日志
│
├── .env                         # 环境变量 (不提交)
├── .env.example                 # 环境变量示例
├── environment.yml              # Conda环境配置
├── requirements.txt             # Python依赖 (可选)
├── docker-compose.yml           # Docker配置
├── Dockerfile                   # Docker镜像
├── .gitignore                   # Git忽略文件
├── CLAUDE.md                    # Claude项目配置
├── README.md                    # 本文件
├── CHANGELOG.md                 # 变更日志
├── CONTRIBUTING.md              # 贡献指南
├── CODE_OF_CONDUCT.md           # 行为准则
├── LICENSE                      # MIT许可证
└── SECURITY.md                  # 安全政策
```

**项目统计**:
- Python文件: **274个** (不含依赖库)
- 核心Agent: **11个**
- LangGraph节点: **9个**
- API端点: **30+**
- 测试用例: **50+**
- 配置文件: **5个**

### 运行测试

```bash
# 后端测试
pytest tests/ -v

# 前端测试
cd frontend && npm test

# 覆盖率报告
pytest --cov=app tests/
```

### 代码质量

```bash
# Python代码检查
black app/
pylint app/
mypy app/

# TypeScript代码检查
cd frontend
npm run lint
npm run type-check
```

---

## 🚀 部署

### 生产环境部署

#### 方式1: Docker部署（推荐）

```bash
# 1. 构建镜像
docker-compose build

# 2. 启动服务
docker-compose up -d

# 3. 检查状态
docker-compose ps
docker-compose logs -f
```

#### 方式2: 传统部署

```bash
# 1. 激活环境
conda activate rag-local

# 2. 使用Gunicorn启动
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log

# 3. 使用Nginx反向代理
# 配置见 docs/deployment/nginx.conf
```

#### 方式3: 云平台部署

支持部署到：
- AWS (ECS + RDS + ElastiCache)
- Azure (App Service + Cosmos DB)
- Google Cloud (Cloud Run + Cloud SQL)
- 阿里云 (ECS + RDS + Redis)

详见 [部署指南](./docs/DEPLOYMENT_GUIDE_v0.6.0.md)

### 渐进式发布策略

```bash
# Phase 1: 金丝雀部署 (10% 流量)
# 监控 24-48 小时

# Phase 2: 部分部署 (50% 流量)
# 监控 24-48 小时

# Phase 3: 全量部署 (100% 流量)
# 持续监控
```

---

## 📈 监控与可观测性

### 关键指标监控

#### 1. 业务指标
```sql
-- Router准确率
SELECT 
  route_type,
  COUNT(*) as total,
  SUM(CASE WHEN validated = true THEN 1 ELSE 0 END) as correct,
  ROUND(100.0 * SUM(CASE WHEN validated = true THEN 1 ELSE 0 END) / COUNT(*), 2) as accuracy
FROM route_decisions
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY route_type;

-- 幻觉率
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total_answers,
  SUM(CASE WHEN hallucination_detected = true THEN 1 ELSE 0 END) as hallucinations,
  ROUND(100.0 * SUM(CASE WHEN hallucination_detected = true THEN 1 ELSE 0 END) / COUNT(*), 2) as rate
FROM answer_validations
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

#### 2. 性能指标
```sql
-- P50/P95/P99延迟
SELECT 
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) as p50,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99
FROM query_logs
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Agent性能分析
SELECT 
  agent_name,
  COUNT(*) as executions,
  AVG(execution_time_ms) as avg_time,
  MAX(execution_time_ms) as max_time
FROM agent_executions
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_name
ORDER BY avg_time DESC;
```

#### 3. 质量指标
```sql
-- 引用完整性
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN citation_count > 0 THEN 1 ELSE 0 END) as with_citations,
  ROUND(100.0 * SUM(CASE WHEN citation_count > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as completeness
FROM generated_answers
WHERE created_at > NOW() - INTERVAL '24 hours';

-- 质量分数分布
SELECT 
  CASE 
    WHEN quality_score >= 0.9 THEN 'Excellent'
    WHEN quality_score >= 0.8 THEN 'Good'
    WHEN quality_score >= 0.7 THEN 'Fair'
    ELSE 'Poor'
  END as quality_tier,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage
FROM quality_scores
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY quality_tier;
```

### 告警配置

```yaml
# alerts.yml
alerts:
  - name: high_error_rate
    condition: error_rate > 1%
    duration: 5m
    severity: critical
    
  - name: slow_response
    condition: p95_latency > 5000ms
    duration: 10m
    severity: warning
    
  - name: high_hallucination_rate
    condition: hallucination_rate > 15%
    duration: 15m
    severity: critical
    
  - name: router_accuracy_drop
    condition: router_accuracy < 90%
    duration: 30m
    severity: warning
```

### 日志查询

```bash
# 查看错误日志
tail -f logs/error.log | grep "ERROR"

# 查看特定Agent日志
tail -f logs/agents.log | grep "RouterAgent"

# 查看性能日志
tail -f logs/performance.log | jq '.response_time_ms > 5000'
```

---

## 🔍 故障排查

### 常见问题

#### 问题1: 向量检索返回空结果
**症状**: Vector RAG返回空文档列表  
**解决方案**: 确保文档已正确导入，检查embedding模型路径，调低similarity_threshold

#### 问题2: Neo4j连接失败
**症状**: `Neo4jConnectionError`  
**解决方案**:
```bash
# 重启Neo4j
docker restart neo4j
```

#### 问题3: 响应时间过长 (>10s)
**解决方案**: 减少top_k，禁用NLI验证（临时），使用更快的模型

#### 问题4: 幻觉率过高 (>15%)
**解决方案**: 提高verification_threshold至0.90，要求更多引用(min_citations_per_claim: 2)

### 性能优化检查清单

- [ ] 启用Redis缓存
- [ ] 配置数据库连接池  
- [ ] 优化数据库索引
- [ ] 使用异步任务队列
- [ ] 配置负载均衡
- [ ] 启用API限流

### 调试模式

```bash
export LOG_LEVEL=DEBUG
export DEBUG=true
export ENABLE_AGENT_TRACING=true
python -m app.main
```

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

### 如何贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

详见 [贡献指南](./CONTRIBUTING.md)

### 行为准则

请阅读并遵守我们的 [行为准则](./CODE_OF_CONDUCT.md)

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](./LICENSE) 文件

---

## 🙏 致谢

### 技术栈

- [LangChain](https://github.com/langchain-ai/langchain) - LLM应用框架
- [FastAPI](https://fastapi.tiangolo.com/) - Web框架
- [React](https://react.dev/) - UI框架
- [ChromaDB](https://www.trychroma.com/) - 向量数据库
- [Neo4j](https://neo4j.com/) - 图数据库

### 灵感来源

本项目受到以下工作的启发：
- [GraphRAG](https://github.com/microsoft/graphrag) - Microsoft的图谱RAG
- [LangGraph](https://github.com/langchain-ai/langgraph) - 多智能体编排
- [Ragas](https://github.com/explodinggradients/ragas) - RAG评估框架

---

## 📧 联系方式

- **问题反馈**: [GitHub Issues](https://github.com/pocheang/querymind/issues)
- **功能建议**: [GitHub Discussions](https://github.com/pocheang/querymind/discussions)
- **安全问题**: 请查看 [SECURITY.md](./SECURITY.md)

---

## 🗺️ 路线图

### v0.7.0 (计划中)

- [ ] 多模态支持 (图片、表格理解)
- [ ] 增强的实时学习能力
- [ ] 更多LLM提供商支持
- [ ] 性能优化和扩展性改进

### 长期计划

- 联邦学习支持
- 更多语言支持
- 移动端应用
- 企业级部署解决方案

---

<div align="center">

**⭐ 如果觉得有用，请给个星标支持一下！**

Made with ❤️ by the QueryMind Team

</div>
