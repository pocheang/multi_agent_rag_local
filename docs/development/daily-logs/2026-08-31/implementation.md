# 2026-08-31 实现 / Implementation

## #14b 流式回答

一条 SSE 订阅承载两种事件名。`execution_event` 是既有的阶段事件；`answer_fragment` 是新增
的、正在书写中的答案。

| 文件 | 改动 |
|---|---|
| `app/privacy/streaming.py`（新） | `StreamingRedactor`：只释放脱敏结果不会再变的文本 |
| `app/orchestration/answer_stream.py`（新） | `AnswerStreamStore`，ContextVar 绑定执行 id |
| `app/agents/synthesizer/service.py` | `_generate_streaming`，剥掉 `[E{k}]` 后发布 |
| `app/agents/synthesizer/generation.py` | `_stream_content` + `on_token` 钩子，带 invoke 兜底 |
| `app/api/routes/public/orchestration.py` | `serialize_answer_fragment`，与阶段事件同一访问校验 |
| `app/services/answer_safety.py` / `security/outbound_redaction.py` | `\s*` → `\s{0,8}`、`\s+` → `\s{1,8}` |
| 前端 | `parseAnswerFragmentSse`、`ExecutionTraceState.draft`、`onDraft` 接到 `local-assistant-stream` 气泡 |

`StreamingRedactor` 的释放规则（三个条件同时成立才放行）：

1. 保留一段尾部余量（margin）
2. 只在空白处切
3. 确认 `redact(raw[:b])` 仍是 `redact(raw[:b + margin])` 的前缀

第 3 条是关键。`password = hunter2` 这类秘密**起始于边界之前、跨越边界**，只在尾部留余量
接不住它。已发出内容记录为**字符串**而非长度——脱敏会改变长度，用偏移量算会失步。

## #12 两段式检索

`enhanced_graph.py`（495 行）有**两个独立原因**不可达，只修一个都没用：

1. `_run_graph_rag_impl` 的条件是 `should_enhance and retrieved_docs`，而唯一生产调用方
   （`app/knowledge/adapters.py`）没有文档可传
2. 编排器把所有源塞进一个 `gather`，不存在「文档已就绪而图检索还没开始」的时刻

改动：

- `app/agents/rag/graph.py` —— 去掉 `and retrieved_docs`。增强查找本身不需要文档；文档只精
  化决定结果上限的质量估计
- `app/knowledge/adapters.py` —— 新增 `PriorEvidenceAdapter` 协议 + `GraphKnowledgeAdapter`
- `app/knowledge/orchestrator.py` —— `_retrieve_in_phases`，声明依赖的源进第二阶段

三个约束写进了代码：

- 只在 `GRAPH_RAG_ENHANCED` 打开时才分两阶段（关掉时先验证据没有读者，延后纯亏并发）
- 第二阶段继承 `STAGE_TIMEOUT_RETRIEVAL_MS` 的**剩余**额度，不是各自一份
- 阶段结果**按下标**而非按源名重组：`KnowledgeStrategy.sources` 没有唯一性约束

顺带重写了 `app/agents/rag/cache.py`。它包装一个 async 缓存的方式是
`asyncio.get_event_loop()` + `run_until_complete`；`run_graph_rag` 从 `asyncio.to_thread`
进来，工作线程里 `get_event_loop()` 会抛，兜底给每个池线程装一个永不关闭的私有 loop——而跨
多个 loop 用的 `asyncio.Lock` 什么也没串行化。现在是普通同步 TTL+LRU。

## #4′ 检索宽度

两件被算出来又丢掉的东西：

**`TaskBudget.max_retrievals` → 源数量**（不是宽度）。planner 按 `2 + hybrid?1 + web?1` 推
出它，是**检索调用次数**，正好对应 `_rule_strategy` 构建的源列表。截断按 planner 自己的推
导顺序花：必需本地二元组 → 路由 hint 指定的源 → 关键词猜出来的源。按发现顺序截断会把 web
那一格花在 `multimodal` 上，因为关键词规则把 `web` 追加在最后。

**查询复杂度 → `top_k` / `rerank_top_n`**。复杂度定义搬到 `app/knowledge/width.py`
（Knowledge Agent 不能 import 检索器），一个定义两个基数：Agent 放大 `TOP_K`(4)/
`RERANKER_TOP_N`(5)，遗留 hybrid 路径放大 `VECTOR_TOP_K`/`BM25_TOP_K`(6)。

新增契约字段 `KnowledgeStrategy.rerank_top_n`（None = 用设置）。只加宽 `top_k` 而不动重排，
等于多喂候选然后把多的丢掉。

`_bounded` 的夹取上限从 `TOP_K` 改成 `dynamic_vector_top_k_cap`——它是对 decider 输出的**上
限**而非默认值，夹到 `TOP_K` 会把刚放大的宽度立刻夹回去。

## #3′ 调用方 deadline

`ExecutionBudget(config, deadline_at=…)`，`remaining_ms()` 取 min。偏移量只测一次，之后全
走 `perf_counter`；naive datetime 按 UTC 读。`MANDATORY_STAGES` 照旧豁免。

HTTP 侧新增 `timeout_ms`（`ge=1000, le=120000`）→ `_deadline_from()` → `deadline_at`。线上
格式相对、契约绝对：两边时钟不必一致，但跨阶段消耗的预算不该每阶段重新推导。

同一处改动让引擎在整个 workflow 外面开 `request_context`。这是
`app/services/runtime/request_context.py` 的用途，而请求路径上从来没人设过它。

## #10 技能

`RouteDecision.skill` 每次请求都被赋值、按 `VALID_SKILLS` 校验，然后**零读者**。

`app/agents/synthesizer/skills.py`（新）是决定技能含义的唯一位置，它**选择**模板而不是**追
加**模板——`templates.py` 已经在按问题推断 query type 并把模板塞进提示词，再加一套会在同一
个 prompt 里放两种互相竞争的答案形状。

- 六个技能有自己的形状（新写）
- `compare_entities` 映射到既有的 `COMPARISON_TEMPLATE`
- `answer_with_citations` / `ai_knowledge_assistant` / 未知技能沿用按问题推断

链路：`WorkflowNodeRuntime.synthesizer` 读 `state["route"].skill` →
`synthesize_candidate(..., skill)` → `_build_prompt_with_language` → `skill_answer_template`。

## #9c 多轮跟随

**第 0 步**：`query.py` 送真实轮次。它以前把整个会话压成一条 `system` 消息（已渲染的记忆
块）。合成器能凑合，改写不行。渲染块仍排最前（它带着原始轮次没有的长期记忆），后面接真实
的 user/assistant 轮。新增 `_recent_session_turns`，用与渲染块相同的 `SHORT_TERM_ROUNDS`。

**第 1 步**：`_llm_rewrite(query, conversation)`。有历史切到 standalone 改写提示词，没历史
保持原提示词。`_render_turns` 跳过 `system` 轮——那是同一批轮次的摘要，喂回去等于同一份内容
给模型看两遍。`KnowledgeOrchestrator.retrieve(..., conversation)`，`QueryRewriter` 签名相应
改为 `Callable[[str, Sequence[object]], Sequence[str]]`。

**第 2 步**：`enable_context_tracking` 在两个消费点各强制一次——`RAGAgentService.retrieve`
决定检索能知道什么，`SynthesizerAgentService.synthesize_candidate` 决定生成能知道什么。

原问题永远保留：`_with_queries` 把它并在变体前面，`primary_query`（重排打分用）在合并前读取。
