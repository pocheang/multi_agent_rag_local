# Multi-Agent Local RAG System

一个可本地运行的多智能体 RAG 项目，基于：

- **LangGraph**：工作流与多 Agent 编排
- **LangChain**：模型、文档处理、检索接口
- **Chroma**：本地持久化向量数据库
- **Neo4j**：图谱与关系检索
- **FastAPI**：本地 API 服务
- **Ollama / OpenAI-compatible**：可切换的 LLM 与 Embedding
- **DuckDuckGo**：当 RAG 证据不足时的联网检索回退
- **BM25 + Dense + Reranker**：混合检索
- **原生 Chat UI**：本地浏览器直接使用

## 新增能力

- **Chat UI**：访问 `http://127.0.0.1:8000/` 即可聊天
- **更强图谱抽取**：默认使用 LLM 抽取三元组，失败时自动回退规则抽取
- **混合检索**：向量检索 + BM25 + RRF 融合 + CrossEncoder reranker

## 目录结构

```text
multi_agent_rag_local/
├── app/
│   ├── agents/
│   ├── api/
│   ├── core/
│   ├── graph/
│   ├── ingestion/
│   ├── retrievers/
│   ├── skills/
│   ├── static/
│   └── tools/
├── data/
│   └── docs/
├── scripts/
├── tests/
├── docker-compose.yml
├── .env.example
├── pyproject.toml
└── README.md
```

## 运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
cp .env.example .env
docker compose up -d neo4j
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
python scripts/ingest.py
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

然后打开（统一 React 前端入口）：

```text
http://127.0.0.1:8000/app
```

## React 前端迁移骨架（v4）

项目新增了独立前端工程：`frontend/`（React 18 + TypeScript + Vite）。

### 开发模式

```bash
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173/app
```

默认已通过 Vite 代理把 `/auth`、`/sessions`、`/query` 等 API 转发到 `127.0.0.1:8000`。  
如果前后端不在同域，可在 `frontend/.env.development` 配置：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 构建并由 FastAPI 托管

```bash
cd frontend
npm install
npm run build
```

构建后 FastAPI 会在 `/app` 路径下提供 SPA（并且 `/`、`/auth`、`/admin`、`/architecture` 都会重定向到 React 路由）：

```text
http://127.0.0.1:8000/app
```

## 环境变量

`.env.example` 已扩展支持：

- `CORPUS_STORE_PATH`：本地 chunks JSONL，用于 BM25
- `BM25_TOP_K`
- `VECTOR_TOP_K`
- `HYBRID_RRF_K`
- `ENABLE_RERANKER`
- `RERANKER_MODEL_NAME`
- `RERANKER_TOP_N`
- `GRAPH_EXTRACTION_MODE=llm|rules`

## 图谱抽取

默认：

- 优先 LLM 抽三元组
- 若模型未就绪或 JSON 不合规，则自动回退规则抽取

## 混合检索策略

1. Dense 向量检索（Chroma）
2. Sparse BM25 检索（本地 JSONL 语料）
3. Reciprocal Rank Fusion 融合
4. CrossEncoder reranker 精排

## Chat UI

- 多轮查看回答
- 显示 route、是否用网、graph entities
- 可展开 citations

## 建议本地拉取 reranker 模型

为了首次更稳定：

```bash
python - <<'PY'
from sentence_transformers import CrossEncoder
CrossEncoder('BAAI/bge-reranker-v2-m3', trust_remote_code=True)
print('ok')
PY
```

## 备注

这里的前端是轻量静态页，目标是本地调试与演示优先。若需要，我可以继续补成 React/Vue 前端。


## 新增能力（v3）

- 流式输出：`POST /query/stream`，前端按 SSE 事件流渲染回答
- 会话历史：本地保存到 `data/sessions/*.json`
- 文件上传入口：`POST /upload`，上传后自动增量入库到 Chroma / BM25 / Neo4j

### 关键接口

- `GET /sessions`：列出会话
- `POST /sessions`：创建会话
- `GET /sessions/{session_id}`：读取会话详情
- `POST /upload`：上传 `.md/.txt/.pdf`
- `POST /query/stream`：流式问答

### 说明

- 上传采用增量入库，不会重建整个向量库
- 会话历史默认仅本地保存，不依赖数据库
- 流式接口返回 `text/event-stream`

### 自动入库（可选）

可开启“目录监听自动入库”，把文件直接丢进目录后，系统会自动增量索引：

- `AUTO_INGEST_ENABLED=true`
- `AUTO_INGEST_INTERVAL_SECONDS=3`
- `AUTO_INGEST_WATCH_DOCS=true`
- `AUTO_INGEST_WATCH_UPLOADS=true`
- `AUTO_INGEST_RECURSIVE=true`

默认监听 `DATA_DIR` 与 `UPLOADS_DIR`，支持 `.md/.txt/.pdf` 以及图片文件（如 `.png/.jpg`）。  
为避免文件尚未写完就入库，监听器会在文件元数据连续两轮稳定后再执行索引。
