# 多模态智能知识平台架构改造设计

日期：2026-08-24  
状态：目标架构已由用户给定；本设计用于把目标映射到当前 QueryMind 代码库。

## 1. 目标与边界

本次改造将现有的服务化 RAG 执行链逐步收敛为：6 个核心 Agent、一个 Knowledge Orchestrator、Evidence/Knowledge/Memory 三层知识体系、多模态证据链、确定性的隐私与权限服务，以及统一评测/追踪。

以下内容不在范围内：重写前端、替换 FastAPI/React/Chroma/Neo4j、为目录整齐移动全部旧代码、把 Retriever/脱敏/权限包装成 Agent、增加与知识问答无关的新业务功能。

## 2. 当前事实基线

- `RAGPipeline` 已是 HTTP/SSE 的公开执行门面，`OrchestrationEngine` 顺序调用 Router、Planner、RAG、Tool、Synthesizer、Finalizer。
- 项目依赖 LangGraph 1.2.0，但应用代码没有 `StateGraph`；`langgraph.json` 仍指向已删除的 `app.graph.studio_entry:get_graph`。
- Router、Planner、Synthesizer 和 Validation 已有类型化 Service；Planner 默认只返回单任务，Clarification 是 Router 旁路 API，不属于主编排。
- 现有 typed RAG Service 并发调用 Vector/BM25/Graph/Web 后按分数去重；另一套 `hybrid_retriever` 已包含 Query Rewrite、RRF、BGE rerank 和父块扩展，但没有成为 typed 主链的统一检索实现。
- 多模态模型、PDF 图片/OCR/表格/图表处理和 `MultiModalRetriever` 已存在，但未接入主 ingestion/RAG；其索引代码导入不存在的 `app.retrievers.stores.chroma_store`，且只索引图片描述/OCR 文本，不保存可检索的原图/视觉向量。
- 主 loader 仅支持 PDF、图片和文本；Word/PPT/Excel 未进入统一 ingestion。
- 文档 registry、owner/visibility、allowed_sources、RBAC、输出 secret 清洗、外部 LLM 文本脱敏已有基础；tenant、ACL、字段级过滤、输入 PII/secret 服务、图片 mask 和统一 Output DLP 缺失。
- Session/Long-term Memory 已有本地实现和候选评分，但完成回答后仍自动尝试写入；无 GBrain 适配器、Memory Resolver、过期/冲突/更新语义。
- 无 LLM Wiki 生产代码。
- Recall@K、MRR、NDCG、执行追踪、时延已有基础；评测实现存在重复/Schema 漂移，token 使用当前明确标记为 unavailable，缺少 Router/Planner/Reranker/Faithfulness 的统一记录。

## 3. 方案选择

### 方案 A：增量式 LangGraph 切换（采用）

保留 `RAGPipeline`、现有 Agent Service、Retriever 和 API；新增 LangGraph state/nodes/workflow，节点只调用既有/新增 Service。先以 shadow 模式比较旧 Engine 与新图，再把 `OrchestrationEngine` 收敛为 LangGraph 门面，最后删除旧的顺序编排代码。

优点：API 风险最低，最大化复用现有实现，可分阶段验收和回滚。缺点：迁移期存在短暂双执行路径，需要严格限制 shadow 只观察、不产生持久化副作用。

### 方案 B：一次性重写

一次性新建 agents/knowledge/ingestion/memory/wiki/privacy/permissions 并切换全部 API。目录最整齐，但会重复实现已存在模块，回归面过大，不符合当前 ADR 的渐进式策略。

### 方案 C：保留当前 Engine，仅模拟 Agent 名称

改名和补 Service，不引入 LangGraph。成本低，但无法提供多轮 interrupt/resume、显式条件边和一次受限验证回路，不满足目标架构。

## 4. 目标运行时结构

```text
HTTP / SSE / MCP
        |
        v
RAGPipeline（唯一公开执行门面）
        |
        v
Privacy + Permission preflight（确定性服务）
        |
        v
LangGraph Workflow
  Router -> Clarification? -> Planner? -> Knowledge Agent
                                      -> Knowledge Orchestrator
                                      -> Synthesizer -> Verifier
                                                ^          |
                                                | retry<=1 |
                                                +----------+
        |
        v
Output DLP + API/SSE compatibility projection
```

`app/graph/` 继续只表示 Neo4j/图知识工具，LangGraph 编排放在 `app/orchestration/langgraph/`，避免两个“graph”概念混淆。

## 5. 核心契约

### WorkflowState

State 使用 `TypedDict`，只保存可序列化、可恢复的信息：

- request、privacy、permission_scope
- route_decision、clarification_state、complete_query
- task_plan、knowledge_strategy、retrieval_round
- evidence、knowledge_items、memory_items、context
- candidate_answer、verification、final_answer
- retry_count、errors、trace

所有节点只写自己拥有的字段。`retry_count` 最大值来自配置，默认 1；Verifier 只能回到 Knowledge，不能回到 Router/Clarification/Planner。

### EvidenceItem

统一字段至少包括：`item_id`、`layer`、`modality`、`content`、`source`、`document_id`、`version`、`page`、`chunk_id`、`image_id`、`artifact_uri`、`retriever`、`score`、`acl_tags`、`retrieved_at`。

引用键为稳定结构 `document_id@version:page:chunk_id[:image_id]`，API 继续投影为现有 citation 字段，并通过 metadata 添加新字段。

### KnowledgeStrategy

Knowledge Agent 只产生策略：选择哪些 source、每源 top_k/timeout、是否 rewrite、是否 rerank、是否 visual、是否 web/tool、允许的降级路径。它不能 import Chroma、Neo4j、BM25、WikiStore、MemoryStore 或 HTTP 客户端。

### VerificationDecision

Verifier 返回 `approved | retry_retrieval | rejected | degraded`，并列出 unsupported claims、citation errors、conflicts、missing aspects、retry_query。只有 `retry_retrieval` 且 `retry_count < max_retries` 才允许条件边回到 Knowledge。

## 6. Knowledge Orchestrator

Orchestrator 是普通 Service，按以下流水线执行：

```text
complete_query / subtasks
  -> build_rewrite_queries（只执行一次）
  -> permission-aware parallel adapters
  -> RRF across selected sources
  -> identity/content deduplication
  -> BGE reranker（失败时 lexical fallback）
  -> source-priority conflict annotation
  -> context builder / token budget
```

现有 `build_rewrite_queries`、hybrid candidate collection、RRF、reranker、parent expansion、Vector/BM25/Graph/Web 实现继续复用。迁移后 `RAGAgentService` 只作为兼容代理调用 Orchestrator，不再持有第二套融合逻辑。

Evidence 优先级固定为：授权的原始 Evidence > 同一 Evidence 派生的 Wiki > 当前明确会话事实 > 经 Resolver 接受的长期 Memory > Web/Tool 补充信息。优先级不代替相关性排序，只用于冲突处理和答案断言。

## 7. 三层数据设计

### Evidence Layer

扩展现有 document registry/corpus metadata，不另建重复文档目录。每次 ingestion 产生不可变 `document_id + version`，保存原文件、解析 manifest、chunk、table、image artifact 和索引状态。Chroma/BM25/Neo4j 都携带同一版本与权限元数据。

### Knowledge Layer

新增 `app/wiki/`，Wiki 仅从 Evidence 生成。每个条目保存 evidence refs、生成模型/提示版本、内容版本、diff、状态和时间；update/rollback 产生新版本而不覆盖历史。Context Builder 遇到 Wiki 与 Evidence 冲突时保留冲突说明并使用 Evidence。

### Memory Layer

现有 session history 保留。新增 Memory Resolver，先解析当前显式上下文，再选择长期记忆；仅偏好、稳定用户事实、明确待办和用户要求记住的信息可进入长期记忆。重复项 merge、较新明确值 supersede 旧值、过期项不参与检索、冲突项降权并要求确认。GBrain 通过 `LongTermMemoryPort` 适配；未配置时保留当前本地 store 作为兼容后端，不伪装成 GBrain 已启用。

## 8. 多模态 ingestion

统一 parser dispatch：PDF 复用 Docling/PyMuPDF/OCR；DOCX/PPTX 使用 Docling，必要时使用 python-docx/python-pptx fallback；XLSX 使用 openpyxl/pandas 提取 sheet/table/formula/chart metadata。每个 parser 输出同一 `ParsedDocument`。

图片处理保存原图 artifact、masked derivative、OCR、VLM 描述和视觉 embedding。外部 OCR/VLM/embedding 前必须经过权限检查和图片敏感区域 mask；原始图片不进入外部 provider payload。ColPali 作为可选视觉 embedding provider，未安装/未配置时降级为描述文本 embedding，并在 diagnostics 中标明 visual capability degraded。

## 9. 隐私与权限

隐私和权限是 Workflow 前后以及 Orchestrator 内部的确定性服务：

- 输入：normalize -> PII/secret detect -> text mask；附件/图片先检测并生成 masked derivative。
- 检索：`AccessScope` 同时包含 tenant、actor、role、permissions、document_ids、allowed_sources、ACL tags；每个 adapter 必须 fail closed。
- 上下文：字段级过滤和再次 mask 后才进入模型。
- 输出：引用范围校验 -> PII/secret DLP -> 未授权来源检查 -> 返回。

现有 owner/visibility/allowed_sources 和 outbound redaction 作为实现基础；禁止只依赖最终 citation 过滤，因为模型可能已看到未授权上下文。

## 10. API 与前端兼容

- 保留现有 query、stream、clarification、session、document URL 和 HTTP 方法。
- clarification 响应只增加 `complete_query`、`workflow_thread_id`、`resume_token`；现有字段不删除。
- 前端完成澄清后提交 `complete_query`，不再重新提交原始问题。
- SSE 保留现有事件，并增加可忽略的 `clarification_required`、`knowledge_strategy`、`verification` metadata。
- citation 保留 `source/document_id/page/metadata`，在 metadata 增加 chunk/image/version/artifact 引用。

## 11. 失败、超时与回滚

- 全请求只有一个 deadline 和一个共享 retry budget；每个 retriever 有子 timeout，但不能自行无限重试。
- partial retrieval 只在策略允许时降级，记录 source、exception type、latency、fallback。
- Verifier 二次检索最多一次，新的 retry query 只补缺口，不重复已成功 source。
- shadow workflow 不写 session、memory、wiki、cache 或审计副作用。
- LangGraph 通过配置逐租户/逐比例开启；未达到质量和权限门禁时回退到当前 Engine。最终切换后 Engine 仅代理 LangGraph，不保留第二套节点顺序。

## 12. 验收标准

1. 生产查询只经 `RAGPipeline -> LangGraph`，六个 Agent 边界在 trace 中可见。
2. Router/Knowledge Agent 不执行检索，Retriever/Privacy/Permission 不是 Agent。
3. Clarification 可多轮恢复，完整 Query 包含已收集信息且不重复提问。
4. Vector/BM25/Graph/Wiki/Memory/Multimodal/Web 按策略动态选用；融合、去重、rerank 只执行一次。
5. 引用能定位 document/version/page/chunk/image；图片原件和视觉向量可用。
6. tenant/RBAC/ACL/字段 mask 在检索前生效，OCR/VLM 和输出都经过 DLP。
7. Verifier 最多一次回检，不存在无限环。
8. Recall@K、MRR、NDCG、reranker delta、faithfulness、answer relevance、router accuracy、token、latency、retry/failure reason 可按 execution_id 查询。
9. 现有前端构建、HTTP/SSE contract、MCP contract 和回归测试通过。

