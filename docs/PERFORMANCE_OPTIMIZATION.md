# RAG 系统性能优化指南

**最后更新**: 2026-04-28


## 🐌 慢的原因分析

根据你的配置，系统慢主要有以下原因：

### 1. **多 Agent 串行执行**
你的系统使用 LangGraph 多 Agent 工作流：
- Router Agent（路由）
- Vector RAG Agent（向量检索）
- Graph RAG Agent（图谱检索）
- Web Research Agent（联网搜索）
- Synthesis Agent（答案合成）

**每个查询都要经过多个步骤，串行执行！**

### 2. **检索过程复杂**
```
向量检索 (TOP_K=6) 
  → BM25 检索 (TOP_K=6)
  → RRF 融合
  → Reranker 重排序 (BAAI/bge-reranker-v2-m3)
  → 动态检索调整
```

### 3. **LLM 调用次数多**
- 查询重写（如果启用）
- 查询分解（如果启用）
- 路由决策
- 图谱提取
- 答案生成
- 答案质检（review）

### 4. **模型选择**
- 当前使用：`claude-sonnet-4-6`（Anthropic）
- 每次 API 调用都有网络延迟

### 5. **Neo4j 图谱查询**
- 图谱遍历可能很慢，特别是数据量大时

---

## ⚡ 优化方案

### 🎯 立即见效的优化（推荐）

#### 1. **切换到更快的检索配置**

编辑 `.env` 文件：

```bash
# 从 advanced 改为 baseline（更快但精度略低）
RETRIEVAL_PROFILE=baseline

# 减少检索数量
TOP_K=3                    # 从 4 改为 3
VECTOR_TOP_K=4             # 从 6 改为 4
BM25_TOP_K=4               # 从 6 改为 4
RERANKER_TOP_N=3           # 从 5 改为 3

# 禁用一些耗时的功能
QUERY_REWRITE_ENABLED=false        # 禁用查询重写
QUERY_DECOMPOSE_ENABLED=false      # 禁用查询分解
DYNAMIC_RETRIEVAL_ENABLED=false    # 禁用动态检索
CONSISTENCY_GUARD_ENABLED=false    # 禁用一致性检查
ANSWER_SAFETY_SCAN_ENABLED=false   # 禁用安全扫描（测试环境）

# 减少超时时间
QUERY_REQUEST_TIMEOUT_MS=30000     # 从 60s 改为 30s
```

**预期提速：40-60%**

#### 2. **使用本地模型（最快）**

如果你有 GPU，使用 Ollama 本地模型：

```bash
# 安装 Ollama
# 下载: https://ollama.com/download

# 拉取模型
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text

# 修改 .env
MODEL_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
```

**预期提速：70-80%（无网络延迟）**

#### 3. **禁用图谱检索（如果不需要）**

修改路由逻辑，跳过 Graph RAG：

```bash
# 在 .env 中添加
GRAPH_RAG_ENABLED=false
```

或者在代码中修改 `app/agents/router_agent.py`，强制返回 `vector_only`。

**预期提速：30-40%**

#### 4. **启用更激进的缓存**

```bash
# 增加缓存时间和容量
RETRIEVAL_CACHE_ENABLED=true
RETRIEVAL_CACHE_TTL_SECONDS=300    # 从 45s 改为 5分钟
RETRIEVAL_CACHE_MAX_ITEMS=1024     # 从 256 改为 1024
```

**预期提速：重复查询快 90%**

---

### 🚀 进阶优化

#### 5. **并行执行检索**

修改 `app/graph/workflow.py`，让向量检索和图谱检索并行：

```python
# 当前是串行
vector_result = run_vector_rag(question)
graph_result = run_graph_rag(question)

# 改为并行
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=2) as executor:
    vector_future = executor.submit(run_vector_rag, question)
    graph_future = executor.submit(run_graph_rag, question)
    
    vector_result = vector_future.result()
    graph_result = graph_future.result()
```

**预期提速：20-30%**

#### 6. **使用更快的 Reranker**

```bash
# 禁用 Reranker（最快但精度降低）
ENABLE_RERANKER=false

# 或使用更小的模型
RERANKER_MODEL_NAME=BAAI/bge-reranker-base
```

**预期提速：15-25%**

#### 7. **减少 LLM Token 数量**

```bash
# 减少上下文长度
MAX_CONTEXT_CHUNKS=4       # 从 6 改为 4
PARENT_CHUNK_SIZE=1000     # 从 1500 改为 1000
```

**预期提速：10-20%**

---

## 📊 性能对比

| 配置 | 预计响应时间 | 精度 |
|------|------------|------|
| **当前配置** (advanced) | 8-15秒 | ⭐⭐⭐⭐⭐ |
| **快速配置** (baseline) | 3-6秒 | ⭐⭐⭐⭐ |
| **本地模型** (Ollama) | 2-4秒 | ⭐⭐⭐⭐ |
| **极速配置** (禁用图谱+Reranker) | 1-3秒 | ⭐⭐⭐ |

---

## 🎯 推荐配置（平衡速度和精度）

创建一个新的 `.env.fast` 文件：

```bash
# 快速配置
MODEL_BACKEND=anthropic
ANTHROPIC_CHAT_MODEL=claude-sonnet-4-6

# 检索优化
RETRIEVAL_PROFILE=baseline
TOP_K=3
VECTOR_TOP_K=4
BM25_TOP_K=4
RERANKER_TOP_N=3
ENABLE_RERANKER=true

# 禁用耗时功能
QUERY_REWRITE_ENABLED=false
QUERY_DECOMPOSE_ENABLED=false
DYNAMIC_RETRIEVAL_ENABLED=false
CONSISTENCY_GUARD_ENABLED=false
ANSWER_SAFETY_SCAN_ENABLED=false

# 缓存优化
RETRIEVAL_CACHE_ENABLED=true
RETRIEVAL_CACHE_TTL_SECONDS=180
RETRIEVAL_CACHE_MAX_ITEMS=512

# 超时设置
QUERY_REQUEST_TIMEOUT_MS=30000

# 上下文优化
MAX_CONTEXT_CHUNKS=4
```

然后：
```bash
cp .env.fast .env
```

**预期：3-6秒响应，精度损失 < 10%**

---

## 🔍 诊断工具

### 查看每个步骤的耗时

在 `app/graph/workflow.py` 中添加计时：

```python
import time

start = time.time()
vector_result = run_vector_rag(question)
print(f"Vector RAG: {time.time() - start:.2f}s")

start = time.time()
graph_result = run_graph_rag(question)
print(f"Graph RAG: {time.time() - start:.2f}s")

start = time.time()
answer = synthesize_answer(...)
print(f"Synthesis: {time.time() - start:.2f}s")
```

### 使用 OpenTelemetry 追踪

系统已集成 OTEL，访问：
```
http://127.0.0.1:8000/metrics
```

---

## 💡 硬件相关

### 如果你有 GPU
- 使用 Ollama 本地模型（最快）
- 使用本地 Embedding 模型

### 如果只有 CPU
- 使用云端 API（Anthropic/OpenAI）
- 禁用 Reranker
- 减少检索数量

### 网络问题
- 如果 Anthropic API 慢，切换到 OpenAI
- 或使用国内代理

---

## 🎬 立即行动

**最简单的优化（1分钟）：**

```bash
# 编辑 .env 文件，修改这几行：
RETRIEVAL_PROFILE=baseline
QUERY_REWRITE_ENABLED=false
QUERY_DECOMPOSE_ENABLED=false
TOP_K=3
RERANKER_TOP_N=3

# 重启后端
# Ctrl+C 停止，然后重新运行
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

**预期提速 40-50%！**

试试看，然后告诉我效果如何！
