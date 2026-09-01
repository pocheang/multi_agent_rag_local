# 2026-08-31 完成总结 / Summary

## 一句话

Package D 六项全部完成，22 项审计清单归零。本日修的都是「实现在、接线断」的问题——每一项接
上之后，都还额外暴露出一个只有走到那段代码才会显形的真 bug。

## 完成的工作

| 项 | 内容 | 新增测试 |
|---|---|---|
| #14b | token 流式回答 + 流式脱敏 + 前端草稿气泡 | 22 + 7(前端) |
| #12 | 两段式检索，`enhanced_graph.py`（495 行）从不可达变可达 | 15 |
| #4′ | `max_retrievals` → 源数量；查询复杂度 → `top_k`/`rerank_top_n` | 18 |
| #3′ | `deadline_at` 零读者 → `ExecutionBudget` + HTTP `timeout_ms` | 12 |
| #10 | 九个技能全线空转 → 六段新模板 + 一处映射 + 三个沿用 | 27 |
| #9c | 多轮跟随问句用会话历史补全后再检索 | 16 |

## 顺带修掉的（接线之后才显形）

| 问题 | 位置 | 之前为什么没人发现 |
|---|---|---|
| 事件循环误用 | `app/agents/rag/cache.py` | 从 `asyncio.to_thread` 进来时 `get_event_loop()` 会抛，兜底给每个池线程装一个永不关闭的私有 loop；跨多 loop 的 `asyncio.Lock` 不串行化任何东西。没人走到这段代码 |
| `QUERY_REWRITE_WITH_LLM` 是死开关 | `rule_rewrite.py:76` | `remaining_seconds()` 永远返回 None（请求路径上没人设 `request_context`），而 `_llm_rewrite` 把 None 当成「没时间」 |
| 增强图查找不可达 | `graph.py` + `orchestrator.py` | 两个独立原因，只修一个都没用 |
| `_render_conversation` 的 12 轮上限是死的 | `synthesizer/service.py` | API 把整个会话压成一条 turn，永远只有 1 条 |

## 验证结果

- **后端 `pytest -q` → 430 passed**（本日开始时 342）
- **前端 `npx vitest run`（在 `frontend/` 下）→ 26 passed / 4 files**
- `ruff check .` / `ruff format --check .` → 通过
- OpenAPI 操作普查 → **151**，与基线一致（`timeout_ms` 是字段不是端点）
- 端到端实测：
  - 流式草稿含密钥/邮箱/内部标记时，前端拼出的是 `……运维密钥是 [REDACTED]，联系人 <EMAIL_1>……`
  - `timeout_ms=2500` → 有效剩余 2499ms，knowledge 阶段上限 15000→2499，`output_filter` 保持 8000
  - `"成本呢？"` + 会话 → 检索 query 变成 `("成本呢？", "比亚迪刀片电池的成本")`
  - 同一问题在 6 个技能下产生 6 种不同的答案模板

## 代码规模

`77 files changed, 3495 insertions(+), 1354 deletions(-)`，另有 20 个新增测试文件与 6 个新增
实现模块（`skills.py` / `width.py` / `streaming.py` / `answer_stream.py` / `runtime.py` /
`selector.py`）。

## 教训

**「零实现」和「实现在但没接线」是两回事，判断错了会给出错的建议。** 我在 #9c 上说过
「`enable_context_tracking` 零实现」，实际上 `app/services/context_management.py` 有 642 行
在做这件事。更糟的是随后的补救：我推荐接上它，而没有先读它的判定逻辑——读完才发现它对中文
零指代结构性失效。两次都是**没把已有代码读完就下结论**。

**接线本身会暴露 bug，所以「接上」不等于「小改动」。** 本日六项里有四项在接线之后立刻显形
了一个新问题（见上表）。一段从没被执行过的代码，它「看起来对」和「跑得对」之间没有关系。

**开关坏掉和开关关掉要分开记。** `GRAPH_RAG_ENHANCED` 和 `QUERY_REWRITE_WITH_LLM` 都默认
false，但前者是条件写错导致永远进不去，后者是依赖的 ContextVar 从没被设置。CLAUDE.md 的
「Dormant by design」清单只有在里面每一项都**确实能打开**时才有意义，所以修好之后要显式写明
「现在它真的能用了，开不开是成本决定」。

## 遗留

审计清单已清零。以下是本日新产生的、需要真实语料才能推进的：

- **`GRAPH_RAG_ENHANCED` 与 `QUERY_REWRITE_WITH_LLM` 的开启决定**——两者都从「坏的」变成
  「可用但默认关」，开不开取决于部署的 Neo4j 规模和每轮多一次 LLM 调用的成本预算
- **六段技能模板需要真实语料验证**——它们只在路由器选中对应技能时生效，互不影响，可以逐个观察
- **跟随问句改写影响路由**（原计划第 2 步）——目前改写只进检索，让它也影响路由收益是
  `"它们的区别呢"` 能拿到 comparison 路由和 graph 源，风险是一次错误补全把整条路由带偏。
  值得等第 1 步的线上数据
