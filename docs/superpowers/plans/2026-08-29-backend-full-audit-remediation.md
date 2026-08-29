# 后端全量审计修复计划（2026-08-29）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-08-29 后端全量审计发现的功能断链、并发隐患与配置漂移，删除 13,115 行零引用死代码，并建立最低限度的 CI/lint 门禁，使 CLAUDE.md 的描述与实际运行的系统一致。

**Architecture:** 不改变整体架构。LangGraph 拓扑（`privacy_permission → router → [clarification] → [planner] → knowledge → synthesizer → verifier → output_filter`）保持不变，`app/domain/` 的类型契约保持不变。改动集中在三类：(1) 已有模块内的局部修复；(2) 已验证零调用点的模块删除；(3) 目录归位（把生产路由从 `compatibility/` 移出）。唯一的新增 HTTP 契约是 `AdvancedRAGRequest` 增加两个可选字段与响应 metadata 增加 `execution_id`，均向后兼容。

**Tech Stack:** Python 3.11+ / FastAPI / LangGraph / Pydantic v2 / ruff。前端 React 18 + TypeScript + Vite。当前仓库**没有测试套件**（`tests/` 已在 v0.7 重写前清空），本计划在 Phase 1 创建第一批回归测试。

---

## Global Constraints

- 每一条命令都必须在 conda 环境 `rag-local` 中执行（`conda activate rag-local`）。
- **不改变任何 settings/env 标志的默认值。** 本计划修 bug、删死代码、清理无效配置，**不启用任何当前处于休眠状态的功能**（例如 `enable_fact_verification`、`knowledge_orchestrator_enabled`、`CASCADE_ENABLE_LEVEL2`）。启用休眠功能是一个独立的产品决策，用户尚未做出。
- 每个删除任务必须以一次验证性 grep 开始（写计划时已各跑过一次，执行时需重跑，防止树已变化），确认被删文件之外零引用。
- 遵循现有代码风格：`from __future__ import annotations`、Pydantic-first 类型契约、不引入新依赖。
- 每次提交前对改动文件运行 `ruff check <files>` 与 `ruff format <files>`。
- 每个 Phase 结束时必须做一次**端点普查**，端点数不得意外减少。
  **不要用 `len(app.routes)`** —— FastAPI 0.138+ 的 `include_router` 在 `app.routes` 里只留一个 `_IncludedRouter`
  包装对象而不再展平子路由，该计数随 FastAPI 版本变化（本机 rag-local 装的是 0.138.2，得 30；
  某些环境的 0.135.3 得 156）。用 OpenAPI 操作数，它跨版本一致：

  ```bash
  conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
  ```

  **当前基线 = 151 个操作**（2026-08-29 在 fastapi 0.138.2 与 0.135.3 上校验一致）。
- Phase 之间可以停下来交付；Phase 内的任务有顺序依赖，不要跳步。

---

## Scope

### 本计划覆盖（32 项审计发现）

| Phase | 主题 | 任务 | 审计项 |
|---|---|---|---|
| 1 | 功能断链修复 | Task 1–5 | #1 #2 #3 #4 #5 #6 |
| 2 | 并发与运行时风险 | Task 6–10 | #7 #8 #9 #10 #11 |
| 3 | 配置漂移与假功能 | Task 11–15 | #12 #13 #14 #15 #16 #17 |
| 4 | 死代码与结构清理 | Task 16–20 | #18 #19 #20 #21 #22 #23 #26 |
| 5 | 工程基线与文档 | Task 21–23 | #24 #25 #27 #28–#32 |

### 明确不在本计划范围内（需要用户单独决策）

以下每一项都是**补齐未接线的功能**，而非修 bug，因此不在此计划内。它们在 Task 23 中会被写入 CLAUDE.md 作为"已知未接线"，而不是被静默启用：

1. **启用事实核查与自审**（`enable_fact_verification` / `enable_self_review`）——涉及每次查询额外 1–2 次 LLM 调用，是成本/延迟决策。
2. **启用 KnowledgeOrchestrator 路径**（`KNOWLEDGE_ORCHESTRATOR_ENABLED=true`）——两条检索装配路径的切换，需要 A/B 验证。
3. **把动态 top-K 接进主检索路径**——`app/retrievers/hybrid/adaptive_params.py` 存在但主路径硬编码 `top_k=6`，接线会改变检索召回特征，需要重跑评测基线。
4. **实现真正的 PostgreSQL 支持**——当前所有存储走裸 `sqlite3`，迁移到 async SQLAlchemy 是一个独立的存储层重构。Task 13 只负责**停止声称支持它**。
5. **重建多跳工具推理（ReAct 的替代品）**——`react.py` 已于 2026-08-29 删除，替代方案是新功能。
6. **重建测试套件**——本计划只为自己修改的代码创建回归测试，不承担 v0.7 全量测试重建。

---

## File Structure

**Phase 1（功能修复）**
- Modify: `app/api/routes/compatibility/advanced_rag.py` — 接受 `session_id`/`conversation`，落库消息，返回 `execution_id`。
- Modify: `app/domain/advanced_rag.py` — `AdvancedRAGResult.metadata` 增加 `execution_id`（无需改模型，写入 metadata 字典）。
- Modify: `app/agents/synthesizer/service.py` — 把 `request.conversation` 渲染进 `memory_context` 并传给 `synthesize_answer`。
- Modify: `app/agents/rag/service.py` — 修复 `graph` 路由不触发图检索。
- Modify: `app/orchestration/langgraph/nodes.py` — `clarification` 的 `action=="ask"` 不再抛异常。
- Modify: `app/agents/clarification/rules.py` — 澄清问题双语化。
- Modify: `frontend/src/services/api/chat.ts`、`frontend/src/pages/chat/hooks/useMessageActions.ts`、`frontend/src/pages/ChatPage.tsx`、`frontend/src/types/api.ts` — 传 `session_id`、接 `execution_id`。
- Create: `tests/api/test_advanced_rag_session.py`、`tests/agents/test_rag_graph_route.py`、`tests/agents/test_clarification_bilingual.py`。

**Phase 2（并发）**
- Modify: `app/retrievers/hybrid/retriever.py` — 删除两处模块级 monkeypatch。
- Modify: `app/services/query/guard.py`、`app/api/routes/compatibility/advanced_rag.py` — 负载守卫改为不阻塞事件循环。
- Modify: `app/api/middleware/rate_limit.py`、`app/services/auth/redis_rate_limit.py` — 改用 `redis.asyncio`，`print` 改 `logging`。
- Modify: `app/pipeline/rag_pipeline.py` — 缓存 `OrchestrationEngine`。
- Modify: `app/api/routes/admin/ops.py` — benchmark/replay 改后台任务。

**Phase 3（配置）**
- Modify: `app/core/config.py` — 删除 33 个无读取方的字段（保留有替代实现的语义）。
- Delete: `app/database/` — 整个包零业务调用方，随 Task 13 删除。
- Modify: `app/api/routes/operations/health.py` — 修 `/ready`：删假 postgres 检查、并发化、加鉴权。
- Modify: `app/services/answer_safety.py` — 尊重 `answer_safety_scan_enabled`。
- Modify: `app/pipeline/profiles.py`、`app/orchestration/policies.py` — 删死配置。

**Phase 4（清理）**
- Delete: 184 个零引用模块（含 78 个 alias shim、`app/prompts/` 24/25 模块、4 个 import 即失败的模块、2 个 `.original` 备份）。
- Modify: `app/api/main.py`、`app/api/application/router_registry.py` — 删除为已删测试保留的 monkeypatch 桥。
- Rename: `app/api/routes/compatibility/` → 按实际角色归位。

**Phase 5（基线）**
- Create: `.github/workflows/ci.yml`。
- Modify: `.pre-commit-config.yaml`、`Makefile`、`CLAUDE.md`。

---

# Phase 1 — 功能断链修复

> 这一阶段修复的是"核心功能实际是断的"。完成后聊天才具备持久化与多轮能力。Task 1–3 有强耦合，必须连续完成才有意义。

### Task 1: 让主查询端点接受会话、落库消息、返回 execution_id

**Files:**
- Modify: `app/api/routes/compatibility/advanced_rag.py`
- Test: `tests/api/test_advanced_rag_session.py`

**Interfaces:**
- Consumes（均已存在，不改签名）：`app.api.dependencies` 的 `_history_store_for_user`、`_build_memory_context_for_session`、`_promote_long_term_memory`、`_require_valid_session_id`；`app.pipeline.contracts.ConversationMessage`。
- Produces：`AdvancedRAGRequest.session_id`（可选字段，向后兼容）；`AdvancedRAGResult.metadata` 增加 `execution_id` 与 `session_id`。

**Context:** 审计 #1/#3。当前 `app/api/routes/compatibility/advanced_rag.py:174` 调用 `RAGPipeline().execute()` 时不传 `session_id`，也不写任何历史。全仓库 `HistoryStore.append_message` 只有一个调用点（`app/api/routes/sessions/export.py:267`，会话*导入*功能），且路由表中不存在 `POST /sessions/{id}/messages`。因此**聊天记录只存在于 React 内存里，刷新即丢**；同时 `PATCH /sessions/{id}/messages/{id}?rerun=true` 依赖消息已在 store 中，这条路径当前永远找不到消息。

`execution_id` 在第 154 行被创建但从不返回，导致 `/api/v1/orchestration/executions/{id}/events` 这条 SSE 链路无法被订阅。

本任务采用「扩展现有端点」而非「新增 `POST /sessions/{id}/messages` 路由」，理由：重跑路径（`app/api/routes/public/sessions.py:197-232`）已经完整实现了"记忆上下文 → 执行 → 落库 → 提升长期记忆"的全套逻辑，复用同一批 helper 可保证两条路径行为一致；新增路由会产生第三套需要同步的实现。

- [x] **Step 1: 写失败的回归测试**

创建 `tests/api/test_advanced_rag_session.py`：

```python
"""Regression tests: the advanced-rag endpoint must persist the exchange."""

from __future__ import annotations

from typing import Any

import pytest

from app.api.routes.compatibility import advanced_rag


class _FakeHistoryStore:
    def __init__(self) -> None:
        self.appended: list[tuple[str, str, str, dict[str, Any]]] = []

    def get_session(self, session_id: str) -> dict[str, Any]:
        return {"session_id": session_id, "messages": []}

    def append_message(self, session_id: str, role: str, content: str, metadata=None):
        self.appended.append((session_id, role, content, metadata or {}))
        return {"session_id": session_id, "messages": []}


@pytest.mark.asyncio
async def test_query_persists_user_and_assistant_messages(monkeypatch):
    """A query carrying session_id must write exactly one user message and
    one assistant message into the session history store."""
    store = _FakeHistoryStore()
    monkeypatch.setattr(advanced_rag, "_history_store_for_user", lambda user: store)
    monkeypatch.setattr(advanced_rag, "_promote_long_term_memory", lambda **_: None)

    await advanced_rag._persist_exchange(
        user={"user_id": "u1"},
        session_id="s1",
        question="What is RAG?",
        answer="Retrieval-augmented generation. [E1]",
        metadata={"route": "vector"},
    )

    roles = [role for _sid, role, _content, _meta in store.appended]
    assert roles == ["user", "assistant"]
    assert store.appended[0][2] == "What is RAG?"
    assert store.appended[1][3]["route"] == "vector"


@pytest.mark.asyncio
async def test_persist_is_a_noop_without_session_id(monkeypatch):
    """Omitting session_id must keep today's stateless behaviour."""
    store = _FakeHistoryStore()
    monkeypatch.setattr(advanced_rag, "_history_store_for_user", lambda user: store)

    await advanced_rag._persist_exchange(
        user={"user_id": "u1"}, session_id=None, question="q", answer="a", metadata={}
    )

    assert store.appended == []


def test_execution_id_is_returned_in_metadata():
    """The tracker execution id must reach the client, otherwise the SSE
    execution-trace endpoint can never be subscribed to."""
    metadata = advanced_rag._response_metadata(
        pipeline_result_metadata={},
        route="vector",
        citations=[],
        execution_id="exec-123",
        session_id="s1",
    )
    assert metadata["execution_id"] == "exec-123"
    assert metadata["session_id"] == "s1"
```

运行确认失败（`_persist_exchange` / `_response_metadata` 尚不存在）：

```bash
conda run -n rag-local python -m pytest tests/api/test_advanced_rag_session.py -x -q
```

- [x] **Step 2: 扩展请求模型**

在 `AdvancedRAGRequest` 中，于 `query` 之后、`enable_decomposition` 之前插入一个字段：

```python
class AdvancedRAGRequest(BaseModel):
    """Request model for advanced RAG query."""

    query: str = Field(..., description="User query")
    session_id: str | None = Field(
        default=None,
        description="Session to persist this exchange into and to draw memory context from",
    )
    enable_decomposition: bool = Field(
        default=False,
        description="Enable query decomposition",
    )
```

其余字段保持不变。`session_id` 为可选，省略时行为与今天完全一致（不落库、无记忆上下文），因此对任何现有调用方向后兼容。

- [x] **Step 3: 补充 import**

把文件顶部的 dependencies import 改为：

```python
from app.api.dependencies import (
    _build_memory_context_for_session,
    _history_store_for_user,
    _promote_long_term_memory,
    _require_permission,
    _require_user,
    _require_valid_session_id,
    _reserve_chat_credit,
)
```

并在 `app.pipeline.contracts` 的 import 中加入 `ConversationMessage`：

```python
from app.pipeline.contracts import (
    ConversationMessage,
    PipelineContext,
    PipelineRequest,
    PipelineResult,
    PipelineUser,
    SourceScope,
)
```

- [x] **Step 4: 新增两个 helper**

在 `_context_docs` 函数之后插入：

```python
def _response_metadata(
    *,
    pipeline_result_metadata: dict[str, Any],
    route: str,
    citations: list[dict[str, Any]],
    execution_id: str,
    session_id: str | None,
) -> dict[str, Any]:
    """Assemble the client-facing metadata block.

    ``execution_id`` is required by the SSE trace endpoint
    (``GET /api/v1/orchestration/executions/{execution_id}/events``); without it
    the client has no way to subscribe to the run it just started.
    """
    return {
        "route": route,
        "citations": citations,
        "validation": pipeline_result_metadata.get("validation", {}),
        "execution_id": execution_id,
        "session_id": session_id,
    }


async def _persist_exchange(
    *,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    answer: str,
    metadata: dict[str, Any],
) -> None:
    """Write the user turn and the assistant turn into the session history.

    Mirrors the message-rerun path in ``app/api/routes/public/sessions.py`` so
    both entry points produce identically shaped history rows.  A persistence
    failure must never fail the request: the answer was already produced and
    returning it is strictly better than a 500.
    """
    if not session_id:
        return
    try:
        history_store = _history_store_for_user(user)
        history_store.append_message(session_id=session_id, role="user", content=question)
        history_store.append_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            metadata=metadata,
        )
        _promote_long_term_memory(
            user=user,
            session_id=session_id,
            question=question,
            result={"answer": answer, **metadata},
        )
    except Exception:
        logger.exception("Failed to persist chat exchange for session %s", session_id)
```

- [x] **Step 5: 改写 `_process_advanced_rag_query_impl`**

把 `_require_permission(...)` 起至 `return result` 止的函数体替换为：

```python
    _require_permission(user, "query:run", request, "advanced-rag")

    session_id = _require_valid_session_id(request_data.session_id) if request_data.session_id else None

    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution(
        request_data.query,
        user_id=str(user.get("user_id", "") or "") or None,
        profile="advanced",
    )
    try:
        allowed_sources = _resolve_advanced_allowed_sources(user, request_data.allowed_sources)
        memory_context = _build_memory_context_for_session(user, session_id, request_data.query)
        conversation = (
            (ConversationMessage(role="system", content=memory_context),) if memory_context else ()
        )
        pipeline_request = PipelineRequest(
            question=request_data.query,
            profile=PipelineProfile.ADVANCED,
            session_id=session_id,
            conversation=conversation,
            user=PipelineUser(
                user_id=str(user.get("user_id", "") or "") or None,
                username=str(user.get("username", "") or "") or None,
                role=str(user.get("role", "") or "") or None,
                permissions=frozenset(user.get("permissions") or []),
            ),
            source_scope=SourceScope(allowed_sources=frozenset(allowed_sources)),
            enable_decomposition=request_data.enable_decomposition,
            enable_self_rag=request_data.enable_self_rag,
        )
        pipeline_result = await RAGPipeline().execute(pipeline_request)
        plan_data = pipeline_result.execution_metadata.get("plan")

        decomposed_query = (
            _decomposed_query_from_plan(request_data.query, plan_data) if request_data.enable_decomposition else None
        )

        answer_quality = None
        sub_query_results: list[SubQueryResult] = []
        if request_data.enable_self_rag:
            answer_quality, sub_query_results = await _run_self_rag_evaluation(
                query=request_data.query,
                pipeline_result=pipeline_result,
                plan_data=plan_data,
            )

        metadata = _response_metadata(
            pipeline_result_metadata=dict(pipeline_result.execution_metadata),
            route=pipeline_result.route.route,
            citations=[citation.model_dump(mode="json") for citation in pipeline_result.citations],
            execution_id=execution_id,
            session_id=session_id,
        )
        await _persist_exchange(
            user=user,
            session_id=session_id,
            question=request_data.query,
            answer=pipeline_result.answer,
            metadata=metadata,
        )

        result = AdvancedRAGResult(
            query=request_data.query,
            decomposed_query=decomposed_query,
            sub_query_results=sub_query_results,
            final_answer=pipeline_result.answer,
            answer_quality=answer_quality,
            metadata=metadata,
        )
        tracker.complete_execution(execution_id, result.model_dump())
        return result
    except Exception as e:
        tracker.fail_execution(execution_id, str(e))
        logger.exception("Error processing advanced RAG query")
        raise internal_error("Unable to process advanced query")
```

**注意**：`tracker.start_execution` 必须保留在 `try` 之前（与现状一致），否则 `except` 分支引用的 `execution_id` 会未定义。

- [x] **Step 6: 跑测试并验证应用仍能启动**

```bash
conda run -n rag-local python -m pytest tests/api/test_advanced_rag_session.py -x -q
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
```

端点数应仍为 151。

- [x] **Step 7: Lint 并提交**

```bash
conda run -n rag-local ruff check app/api/routes/compatibility/advanced_rag.py tests/
conda run -n rag-local ruff format app/api/routes/compatibility/advanced_rag.py tests/
git add app/api/routes/compatibility/advanced_rag.py tests/api/test_advanced_rag_session.py
git commit -m "fix(api): persist chat exchanges and return execution_id from the query endpoint"
```

---

### Task 2: 前端传 session_id 并消费 execution_id

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/services/api/chat.ts`
- Modify: `frontend/src/pages/chat/hooks/useMessageActions.ts`

**Interfaces:**
- Consumes: Task 1 新增的 `session_id` 请求字段与 `metadata.execution_id` 响应字段。
- Produces: `NormalizedQueryResult.executionId`。

**Context:** 审计 #1/#3 的前端一半。`frontend/src/pages/chat/hooks/useMessageActions.ts:113` 的 `onExecutionId?.(null)` 是全前端唯一调用点——`executionId` 永远是 `null`，于是 `ChatRuntimePanels` / `useExecutionTrace` / `consumeExecutionEventStream` 整条链路永不触发。同一函数第 137 行调用 `appApi.advanced()` 时也没有把已经拿到的 `sid` 传下去。

- [x] **Step 1: 扩展类型**

在 `frontend/src/types/api.ts` 中：

```typescript
export type NormalizedQueryResult = {
  answer: string;
  citations: Citation[];
  route?: string;
  executionId?: string;
  qualityReport?: Record<string, unknown>;
  executionMetadata?: Record<string, unknown>;
};
```

`AdvancedQueryResponse` 无需修改——其 `metadata` 已是 `Record<string, unknown>`。

- [x] **Step 2: 传 session_id、解析 execution_id**

在 `frontend/src/services/api/chat.ts` 中把 `AdvancedQueryInput` 与 `queryApi.advanced` 改为：

```typescript
type AdvancedQueryInput = {
  query: string;
  sessionId?: string;
  enableDecomposition: boolean;
  enableSelfRag: boolean;
  signal?: AbortSignal;
};

export const queryApi = {
  async advanced(input: AdvancedQueryInput): Promise<NormalizedQueryResult> {
    const res = await authFetch("/api/advanced-rag/query", {
      method: "POST",
      signal: input.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: input.query,
        ...(input.sessionId ? { session_id: input.sessionId } : {}),
        enable_decomposition: input.enableDecomposition,
        enable_self_rag: input.enableSelfRag,
      }),
    });
    const payload = await parseOrThrow<AdvancedQueryResponse>(res);
    const metadata = recordOrUndefined(payload.metadata) ?? {};
    return {
      answer: typeof payload.final_answer === "string" ? payload.final_answer : "",
      citations: citationList(metadata.citations),
      route: typeof metadata.route === "string" ? metadata.route : undefined,
      executionId: typeof metadata.execution_id === "string" ? metadata.execution_id : undefined,
      qualityReport: recordOrUndefined(payload.answer_quality),
      executionMetadata: metadata,
    };
  },
};
```

- [x] **Step 3: 在 `ask()` 中传 sid、上报 executionId、与服务端历史对账**

在 `useMessageActions.ts` 的 `ask()` 内，把 `appApi.advanced({...})` 调用及其后的 `await onCreditsChanged?.();` 一段改为：

```typescript
      const result = await appApi.advanced({
        query: q,
        sessionId: sid,
        enableDecomposition: true,
        enableSelfRag: true,
        signal: runAbort.signal,
      });
      if (!isRunActive()) return;
      if (result.executionId) onExecutionId?.(result.executionId);
      setMessages((prev) => prev.map((message) => (
        message.message_id === "local-assistant-stream"
          ? {
              ...message,
              content: result.answer,
              metadata: {
                ...EMPTY_METADATA,
                route: result.route || "",
                citations: result.citations,
                quality_report: result.qualityReport,
              },
            }
          : message
      )));
      await actions.refreshSessions(true, true);
      await onCreditsChanged?.();
```

**说明**：`execution_id` 在响应返回时该次执行已经结束，因此 SSE 流会立即读到终态并关闭——这对"回看本次执行各阶段耗时"有效（`ExecutionTrace` 保留 1 小时）。要做**实时**进度推送需要端点先返回 id 再流式产出，那是独立改动，不在本计划范围。本步骤修的是"id 从不返回导致整条链路死掉"这个 bug。

- [x] **Step 4: 构建验证并提交**

```bash
cd frontend && npm run build && cd ..
git add frontend/src/types/api.ts frontend/src/services/api/chat.ts frontend/src/pages/chat/hooks/useMessageActions.ts
git commit -m "fix(frontend): send session_id with chat queries and consume execution_id"
```

---

### Task 3: 让合成器真正使用对话历史

**Files:**
- Modify: `app/agents/synthesizer/service.py`
- Test: `tests/agents/synthesizer/test_conversation_context.py`

**Interfaces:**
- Consumes: `OrchestrationRequest.conversation`（已存在，`app/pipeline/contracts.py:107` 已填充）。
- Produces: 无新接口——`synthesize_answer` 已有 `memory_context: str = ""` 参数（`app/agents/synthesizer/generation.py:321`），本任务只是开始传它。

**Context:** 审计 #2。`OrchestrationRequest.conversation` 被 `to_orchestration_request` 填充后**全仓库无任何读取方**。`app/agents/synthesizer/service.py:46-54` 调用 `synthesize_answer` 时只传 `question`、`vector_context`、`force_language`、`session_id`，把已有的 `memory_context` 参数留空。因此即使 Task 1 把记忆上下文放进了 `conversation`，它仍会在这一步被丢弃——**Task 1 与 Task 3 必须都完成，多轮能力才真正打通**。

- [x] **Step 1: 写失败的测试**

创建 `tests/agents/synthesizer/test_conversation_context.py`。**先阅读** `app/domain/knowledge.py` 与 `app/domain/workflow.py` 确认 `EvidenceItem` / `ContextBundle` 的真实必填字段，按实际签名构造夹具——不要为了让测试通过而修改被测代码：

```python
"""Regression test: conversation turns must reach the generator."""

from __future__ import annotations

import pytest

from app.agents.synthesizer.service import SynthesizerAgentService, _render_conversation
from app.orchestration.request import ConversationTurn, OrchestrationRequest


def test_render_conversation_includes_both_roles():
    rendered = _render_conversation((
        ConversationTurn(role="user", content="Tell me about doc A."),
        ConversationTurn(role="assistant", content="Doc A covers X."),
    ))
    assert "Tell me about doc A." in rendered
    assert "Doc A covers X." in rendered


def test_render_conversation_is_empty_for_no_turns():
    assert _render_conversation(()) == ""


def test_render_conversation_is_bounded():
    turns = tuple(
        ConversationTurn(role="user", content="x" * 500) for _ in range(40)
    )
    rendered = _render_conversation(turns)
    assert len(rendered) <= 4000


@pytest.mark.asyncio
async def test_conversation_is_passed_as_memory_context(evidence_context):
    """`evidence_context` fixture must build a ContextBundle with one evidence
    item; see app/domain/workflow.py for its real field names."""
    captured: dict = {}

    def fake_generate(question, skill_name, **kwargs):
        captured.update(kwargs)
        return {"answer": "ok [E1]"}

    service = SynthesizerAgentService(generate=fake_generate)
    request = OrchestrationRequest(
        question="And what about the second one?",
        profile="advanced",
        conversation=(ConversationTurn(role="assistant", content="Doc A covers X."),),
    )

    await service.synthesize_candidate(request, evidence_context, ())

    assert "Doc A covers X." in captured["memory_context"]
```

```bash
conda run -n rag-local python -m pytest tests/agents/synthesizer/test_conversation_context.py -x -q
```

- [x] **Step 2: 新增渲染函数**

在 `app/agents/synthesizer/service.py` 中、`_answer_text` 之前插入：

```python
def _render_conversation(turns: tuple, *, max_turns: int = 12, max_chars: int = 4000) -> str:
    """Render recent conversation turns into the generator's memory_context slot.

    Bounded on both axes so a long session cannot crowd retrieved evidence out
    of the model's context window.  The newest turns are the ones kept.
    """
    if not turns:
        return ""
    recent = list(turns)[-max_turns:]
    lines = [
        f"{str(turn.role).strip() or 'user'}: {str(turn.content).strip()}"
        for turn in recent
        if str(getattr(turn, "content", "") or "").strip()
    ]
    if not lines:
        return ""
    rendered = "\n".join(lines)
    return rendered[-max_chars:] if len(rendered) > max_chars else rendered
```

- [x] **Step 3: 传给生成器**

在 `synthesize_candidate` 中把 `asyncio.to_thread(...)` 调用改为：

```python
        generated = await asyncio.to_thread(
            self._generate,
            request.question,
            "answer_with_citations",
            memory_context=_render_conversation(request.conversation),
            vector_context=generation_context,
            force_language=request.force_language,
            session_id=request.session_id or "",
            enable_fact_verification=False,
            enable_self_review=False,
        )
```

`enable_fact_verification` / `enable_self_review` 维持 `False`（见 Global Constraints——启用它们是独立决策，Task 23 会把这一现状写进文档）。

- [x] **Step 4: 跑测试、Lint、提交**

```bash
conda run -n rag-local python -m pytest tests/agents/synthesizer/ -x -q
conda run -n rag-local ruff check app/agents/synthesizer/service.py tests/
conda run -n rag-local ruff format app/agents/synthesizer/service.py tests/
git add app/agents/synthesizer/service.py tests/agents/synthesizer/test_conversation_context.py
git commit -m "fix(synthesizer): pass conversation history into generation as memory_context"
```

---

### Task 4: 修复 graph 路由不触发图检索

**Files:**
- Modify: `app/agents/rag/service.py:306-307`
- Test: `tests/agents/test_rag_graph_route.py`

**Interfaces:**
- Consumes: `RouteDecision.effective_route`（已存在的 property，`app/domain/contracts.py:47`）。
- Produces: 无新接口。

**Context:** 审计 #4。`app/agents/router/service.py::_to_domain_route` 对 `route == "graph"` 返回 `RouteDecision(intent="knowledge_retrieval", route="graph", ...)`；而 `RAGAgentService.retrieve` 只在 `route.intent == "hybrid"` 时把图检索器加入 `enabled`。于是**路由到 graph 的查询静默退化成 vector+BM25，Neo4j 只有 hybrid 路由能碰到**。`effective_route` 是执行面的正确判据（对 graph 返回 `"graph"`，对 hybrid 返回 `"hybrid"`）。

- [x] **Step 1: 写失败的测试**

创建 `tests/agents/test_rag_graph_route.py`：

```python
"""Regression test: a graph route must actually query the graph retriever."""

from __future__ import annotations

import pytest

from app.agents.rag.service import RAGAgentService
from app.domain.contracts import EvidenceBundle, RouteDecision
from app.orchestration.request import OrchestrationRequest


def _route(intent: str, route: str | None) -> RouteDecision:
    return RouteDecision(
        intent=intent,
        route=route,
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test",
    )


def _recorder(name: str, called: list[str]):
    async def retriever(request, decision, plan):
        called.append(name)
        return EvidenceBundle()

    return retriever


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "route", "graph_expected"),
    [
        ("knowledge_retrieval", "graph", True),
        ("hybrid", None, True),
        ("knowledge_retrieval", "vector", False),
    ],
)
async def test_graph_retriever_selected_for_graph_and_hybrid(intent, route, graph_expected):
    called: list[str] = []
    service = RAGAgentService(
        vector=_recorder("vector", called),
        bm25=_recorder("bm25", called),
        graph=_recorder("graph", called),
        web=_recorder("web", called),
    )

    await service.retrieve(
        OrchestrationRequest(question="q", profile="advanced"), _route(intent, route), None
    )

    assert ("graph" in called) is graph_expected
```

- [x] **Step 2: 改判据**

在 `app/agents/rag/service.py` 中把：

```python
        if route.intent == "hybrid":
            enabled.append(("graph", self._graph))
```

改为：

```python
        if route.effective_route in {"graph", "hybrid"}:
            enabled.append(("graph", self._graph))
```

- [x] **Step 3: 跑测试、Lint、提交**

```bash
conda run -n rag-local python -m pytest tests/agents/test_rag_graph_route.py -x -q
conda run -n rag-local ruff check app/agents/rag/service.py tests/
conda run -n rag-local ruff format app/agents/rag/service.py tests/
git add app/agents/rag/service.py tests/agents/test_rag_graph_route.py
git commit -m "fix(rag): run graph retrieval for the graph route, not only for hybrid"
```

---

### Task 5: 澄清流程 —— 不再 500，且支持双语

**Files:**
- Modify: `app/orchestration/langgraph/nodes.py:166-172`
- Modify: `app/agents/clarification/rules.py`
- Modify: `app/agents/clarification/service.py`
- Test: `tests/agents/test_clarification_bilingual.py`

**Interfaces:**
- Produces: `rules.question_for(intent, field_name, language="zh")` 增加第三个可选参数（默认 `"zh"`，向后兼容）；新增模块级 `_QUESTIONS_EN`。
- Consumes: 无新依赖（语言判定用内联的 CJK 字符检测，避免为一个分支引入 `language_analytics` 的单例）。

**Context:** 审计 #5/#6。两个独立缺陷：

1. `app/orchestration/langgraph/nodes.py:167` 在 `result.action == "ask"` 时 `raise StageExecutionError`。而 pipeline 调用 `clarifier(request, route_decision)` 时 `context=None`，`collected_info` 恒为 `{}` → 对 `rag_design`/对比类查询**必然**返回 `ask` → 必然 500。前端靠先调 `/api/v1/clarification/check` 挡住了，但 `useClarification.ts:98` 的 catch 分支写着 "fallback to direct query"——澄清服务一抖动用户就吃 500。
2. `rules.py:24` 的 `_QUESTIONS` 全部硬编码中文，英文用户会收到中文追问，违反双语承诺。

- [x] **Step 1: 写失败的测试**

创建 `tests/agents/test_clarification_bilingual.py`：

```python
"""Regression tests for clarification language and non-fatal degradation."""

from __future__ import annotations

from app.agents.clarification.rules import question_for

_CJK = lambda text: any("一" <= ch <= "鿿" for ch in text)  # noqa: E731


def test_chinese_question_is_the_default():
    q = question_for("rag_design", "scenario")
    assert q is not None and _CJK(q.question)


def test_english_question_is_available():
    q = question_for("rag_design", "scenario", language="en")
    assert q is not None
    assert not _CJK(q.question)
    assert q.field_name == "scenario"
    assert q.options


def test_both_languages_agree_on_field_names_and_option_counts():
    catalogue = {
        "rag_design": ("scenario", "data_source", "scale", "performance_requirement"),
        "document_comparison": ("doc_ids", "comparison_aspect", "output_format"),
    }
    for intent, fields in catalogue.items():
        for field_name in fields:
            zh = question_for(intent, field_name)
            en = question_for(intent, field_name, language="en")
            assert zh is not None and en is not None, f"{intent}.{field_name}"
            assert zh.field_name == en.field_name
            assert len(zh.options) == len(en.options)


def test_unknown_language_falls_back_to_chinese():
    q = question_for("rag_design", "scenario", language="fr")
    assert q is not None and _CJK(q.question)
```

- [x] **Step 2: 让 clarification 节点降级而不是抛异常**

在 `app/orchestration/langgraph/nodes.py` 的 `clarification` 方法中，把：

```python
        if result.action == "ask":
            raise StageExecutionError(
                "clarification",
                RuntimeError(
                    "interactive clarification is required; use the clarification API with the returned thread"
                ),
            )
        complete_query = result.complete_query or request.question
```

替换为：

```python
        if result.action == "ask":
            # Interactive clarification belongs to the HTTP clarification API
            # (POST /api/v1/clarification/check), which owns the multi-round
            # state.  Inside the pipeline nobody can answer the question, so
            # continue with the original query instead of failing the request.
            logger.info("clarification requested but not interactively resolvable; continuing with original query")
            complete_query = request.question
        else:
            complete_query = result.complete_query or request.question
```

确认该模块顶部已有 `import logging` 与 `logger = logging.getLogger(__name__)`；若无则补上。

- [x] **Step 3: 为澄清问题增加英文版本**

在 `app/agents/clarification/rules.py` 中把现有 `_QUESTIONS` 重命名为 `_QUESTIONS_ZH`（内容一字不改），并在其后新增：

```python
_QUESTIONS_EN: dict[str, dict[str, ClarificationQuestion]] = {
    "rag_design": {
        "scenario": ClarificationQuestion(
            question="What is this RAG system mainly for?",
            options=["Enterprise knowledge base", "Customer support Q&A", "Code knowledge base", "Data analysis"],
            allow_custom_input=True,
            field_name="scenario",
        ),
        "data_source": ClarificationQuestion(
            question="What are the main data sources?",
            options=["PDF / Office documents", "Databases", "APIs", "Web pages"],
            allow_custom_input=True,
            field_name="data_source",
        ),
        "scale": ClarificationQuestion(
            question="Roughly how much data do you expect?",
            options=["Small (<1GB)", "Medium (1-10GB)", "Large (10-100GB)", "Very large (>100GB)"],
            allow_custom_input=True,
            field_name="scale",
        ),
        "performance_requirement": ClarificationQuestion(
            question="What response-time requirement do you have?",
            options=["Real-time (<1s)", "Fast (1-3s)", "Normal (3-5s)", "No strict requirement"],
            allow_custom_input=True,
            field_name="performance_requirement",
        ),
    },
    "document_comparison": {
        "doc_ids": ClarificationQuestion(
            question="Which documents or subjects should be compared?",
            options=[],
            allow_custom_input=True,
            field_name="doc_ids",
        ),
        "comparison_aspect": ClarificationQuestion(
            question="Which aspects matter most for the comparison?",
            options=["Features", "Performance", "Cost", "Changes over time or versions"],
            allow_custom_input=True,
            field_name="comparison_aspect",
        ),
        "output_format": ClarificationQuestion(
            question="What output format would you like?",
            options=["Comparison table", "Detailed report", "Brief summary"],
            allow_custom_input=True,
            field_name="output_format",
        ),
    },
}

_QUESTIONS_BY_LANGUAGE = {"zh": _QUESTIONS_ZH, "en": _QUESTIONS_EN}
```

- [x] **Step 4: 让 `question_for` 接受语言**

```python
def question_for(intent: str, field_name: str, language: str = "zh") -> ClarificationQuestion | None:
    """Return a fresh structured question so request state cannot mutate templates."""

    catalog = _QUESTIONS_BY_LANGUAGE.get(str(language or "zh").lower(), _QUESTIONS_ZH)
    template = catalog.get(intent, {}).get(field_name)
    return template.model_copy(deep=True) if template is not None else None
```

同时把 `_structured_fields` 中的 `supported` 集合显式指向中文表（两套字段名相同，显式指定避免歧义）：

```python
    supported = {field_name for questions in _QUESTIONS_ZH.values() for field_name in questions}
```

- [x] **Step 5: 在澄清服务中按查询语言选择问题**

在 `app/agents/clarification/service.py` 的 `clarify()` 中把 `question = question_for(assessment.intent, next_field or "")` 改为：

```python
        question = question_for(
            assessment.intent,
            next_field or "",
            language=_question_language(request),
        )
```

并在模块底部（`__all__` 之前）新增：

```python
def _question_language(request: OrchestrationRequest) -> str:
    """Pick the clarification language from the explicit override, then the query text."""
    forced = str(getattr(request, "force_language", "") or "").strip().lower()
    if forced in {"zh", "en"}:
        return forced
    return "zh" if any("一" <= ch <= "鿿" for ch in str(request.question or "")) else "en"
```

- [x] **Step 6: 跑测试、验证启动、Lint、提交**

```bash
conda run -n rag-local python -m pytest tests/agents/test_clarification_bilingual.py -x -q
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
conda run -n rag-local ruff check app/agents/clarification/ app/orchestration/langgraph/nodes.py tests/
conda run -n rag-local ruff format app/agents/clarification/ app/orchestration/langgraph/nodes.py tests/
git add app/agents/clarification/ app/orchestration/langgraph/nodes.py tests/agents/test_clarification_bilingual.py
git commit -m "fix(clarification): degrade instead of failing in-pipeline, and localize questions"
```

### Phase 1 验收

已用自动化替代验证（2026-08-29，36 个测试全绿）：`tests/api/test_advanced_rag_roundtrip.py` 以真实 `HistoryStore` + 桩 pipeline 跑完整两轮对话，断言四条消息按序落库、第二轮携带第一轮上下文进入 pipeline、两轮返回不同的 `execution_id`；双语澄清用直接调用 `ClarificationAgentService.clarify()` 验证（英文问句得英文追问）。**浏览器层的刷新保持与真实模型的多轮质量仍需人工确认。**

- [~] 端到端手测：登录 → 新建会话 → 提问 → **刷新页面** → 历史仍在。  ← **待人工验证**（需要运行中的服务与真实模型）
- [~] 端到端手测：连续提两个相关问题，第二个问题的回答体现出第一轮上下文。  ← **待人工验证**（需要运行中的服务与真实模型）
- [~] 端到端手测：提一个"设计一个 RAG 系统"类问题，收到澄清追问；用英文提同类问题，收到**英文**追问。  ← **待人工验证**（需要运行中的服务与真实模型）
- [x] `conda run -n rag-local python -m pytest tests/ -q` 全绿。

---

# Phase 2 — 并发与运行时风险

> 这一阶段修的是"平时看不出来、上量就出事"的问题。Task 6 与 Task 9 都涉及共享状态，必须严格按步骤走。

### Task 6: 删除混合检索器的模块级 monkeypatch

**Files:**
- Modify: `app/retrievers/hybrid/candidate_collection.py`
- Modify: `app/retrievers/hybrid/parent_expansion.py`
- Modify: `app/retrievers/hybrid/retriever.py:142-183`
- Test: `tests/retrievers/test_no_module_patching.py`

**Interfaces:**
- Produces: `collect_candidates(..., *, rewrite_fn=None, vector_fn=None, bm25_fn=None)` 三个仅关键字、默认 `None` 的可选参数；`expand_to_parent_context(candidates, *, parent_text_map_fn=None)` 同理。全部默认回退到各自模块的现有实现，因此对既有调用方零影响。
- 移除：`retriever.py` 对 `candidate_collection.build_rewrite_queries` / `.safe_similarity_search` / `.bm25_search` 与 `parent_expansion.get_parent_text_map` 的赋值。

**Context:** 审计 #7 —— **本计划中风险最高的一处**。`app/retrievers/hybrid/retriever.py:152-183` 在调用前改写 `candidate_collection` 的三个模块级全局函数，在 `finally` 中恢复；`retriever.py:142-150` 对 `parent_expansion.get_parent_text_map` 做同样的事。

这条路径是活的：`app/agents/rag/vector.py:22` → `hybrid_search_with_diagnostics`（`retriever.py:18`）→ 第 54/88/105 行。而 `RAGAgentService` 通过 `asyncio.gather` 并发发起多个查询变体，底层还有一个 50 线程的 `ThreadPoolExecutor`。两个并发调用交错时，B 会把 A 已经打好的补丁当作"原值"保存，A 恢复后 B 再恢复，最终把补丁值永久写回模块全局。

两处 monkeypatch 的注释都写着 *"for pre-refactor tests and scripts"* —— **那些测试和脚本已在 2026-08-28 随 `tests/` 与 `scripts/` 一起被清空**。这个机制现在没有任何服务对象，只剩风险。

- [ ] **Step 1: 写守卫测试**

创建 `tests/retrievers/test_no_module_patching.py`：

```python
"""Guard test: hybrid retrieval must not mutate module-level globals.

Two concurrent retrievals used to race on candidate_collection's module
globals; this test fails if that pattern is reintroduced.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from app.retrievers.hybrid import candidate_collection, retriever


def test_retriever_source_has_no_global_assignment():
    source = inspect.getsource(retriever)
    for attr in ("build_rewrite_queries", "safe_similarity_search", "bm25_search"):
        assert f"candidate_collection.{attr} =" not in source, (
            f"retriever.py must not reassign candidate_collection.{attr}"
        )
    assert "parent_expansion.get_parent_text_map =" not in source


def test_collect_candidates_accepts_injected_callables():
    params = inspect.signature(candidate_collection.collect_candidates).parameters
    for name in ("rewrite_fn", "vector_fn", "bm25_fn"):
        assert name in params, f"collect_candidates must accept {name}"
        assert params[name].default is None


@pytest.mark.asyncio
async def test_concurrent_searches_leave_globals_untouched():
    before = (
        candidate_collection.build_rewrite_queries,
        candidate_collection.safe_similarity_search,
        candidate_collection.bm25_search,
    )

    async def run():
        await asyncio.to_thread(retriever.hybrid_search, "concurrency probe")

    await asyncio.gather(*(run() for _ in range(4)), return_exceptions=True)

    after = (
        candidate_collection.build_rewrite_queries,
        candidate_collection.safe_similarity_search,
        candidate_collection.bm25_search,
    )
    assert before == after
```

```bash
conda run -n rag-local python -m pytest tests/retrievers/test_no_module_patching.py -x -q
```

- [ ] **Step 2: 给 `collect_candidates` 增加注入点**

在 `app/retrievers/hybrid/candidate_collection.py` 中把签名改为：

```python
def collect_candidates(
    query: str,
    allowed_sources: list[str] | None,
    vector_threshold: float,
    settings,
    precomputed_vector_results: dict[str, list] | None = None,
    precomputed_raw_vector_results: dict[str, list] | None = None,
    dynamic_top_k: int | None = None,
    dynamic_vector_weight: float | None = None,
    dynamic_bm25_weight: float | None = None,
    *,
    rewrite_fn=None,
    vector_fn=None,
    bm25_fn=None,
) -> tuple[list[dict], dict]:
    """Collect and fuse candidates from vector and BM25 retrieval.

    ``rewrite_fn`` / ``vector_fn`` / ``bm25_fn`` let a caller substitute the
    retrieval primitives for one call.  They default to this module's own
    implementations; previously callers achieved the same effect by reassigning
    module globals, which raced across concurrent requests.
    """
    _rewrite = rewrite_fn or build_rewrite_queries
    _vector = vector_fn or safe_similarity_search
    _bm25 = bm25_fn or bm25_search
    rrf_k = int(getattr(settings, "hybrid_rrf_k", 60) or 60)
```

然后把函数体内的三处调用改为使用局部别名：
- 第 73 行 `variants = build_rewrite_queries(` → `variants = _rewrite(`
- 第 120 行 `vector_results = safe_similarity_search(` → `vector_results = _vector(`
- 第 144 行 `sparse = bm25_search(` → `sparse = _bm25(`

**执行时用 grep 复核**，确保没有遗漏的调用点：

```bash
grep -n "build_rewrite_queries(\|safe_similarity_search(\|bm25_search(" app/retrievers/hybrid/candidate_collection.py
```

- [ ] **Step 3: 给 `expand_to_parent_context` 增加同样的注入点**

先读 `app/retrievers/hybrid/parent_expansion.py`，确认 `expand_to_parent_context` 的签名与它内部调用 `get_parent_text_map` 的位置，然后按 Step 2 完全相同的模式添加 `*, parent_text_map_fn=None` 并在函数体开头写 `_parent_text_map = parent_text_map_fn or get_parent_text_map`。

- [ ] **Step 4: 改写 retriever.py 的两个 wrapper**

把 `_expand_to_parent_context` 替换为：

```python
def _expand_to_parent_context(candidates: list[dict]) -> list[dict]:
    """Expand candidates to parent context using this module's text-map source."""
    return expand_to_parent_context(candidates, parent_text_map_fn=get_parent_text_map)
```

把 `_collect_candidates_for_current_module` 替换为：

```python
def _collect_candidates_for_current_module(
    query: str,
    allowed_sources: list[str] | None,
    vector_threshold: float,
    settings,
    precomputed_raw_vector_results: dict[str, list] | None = None,
    dynamic_top_k: int | None = None,
    dynamic_vector_weight: float | None = None,
    dynamic_bm25_weight: float | None = None,
) -> tuple[list[dict], dict]:
    """Collect candidates using this module's retrieval primitives.

    The primitives are injected explicitly.  They used to be installed by
    reassigning candidate_collection's module globals, which raced whenever two
    retrievals overlapped.
    """
    return candidate_collection.collect_candidates(
        query,
        allowed_sources=allowed_sources,
        vector_threshold=vector_threshold,
        settings=settings,
        precomputed_raw_vector_results=precomputed_raw_vector_results,
        dynamic_top_k=dynamic_top_k,
        dynamic_vector_weight=dynamic_vector_weight,
        dynamic_bm25_weight=dynamic_bm25_weight,
        rewrite_fn=build_rewrite_queries,
        vector_fn=_safe_similarity_search,
        bm25_fn=bm25_search,
    )
```

原实现中用 `getattr(module, "...", fallback)` 从 `sys.modules[__name__]` 取函数，是为了让测试能 monkeypatch 本模块的符号；测试已不存在，直接引用即可。随之可删除 `retriever.py` 顶部不再使用的 `import sys`（若无其他用途）。

- [ ] **Step 5: 验证并提交**

```bash
conda run -n rag-local python -m pytest tests/retrievers/ -x -q
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
conda run -n rag-local ruff check app/retrievers/hybrid/ tests/
conda run -n rag-local ruff format app/retrievers/hybrid/ tests/
git add app/retrievers/hybrid/ tests/retrievers/test_no_module_patching.py
git commit -m "fix(retrievers): inject retrieval primitives instead of patching module globals"
```

---

### Task 7: 负载守卫不再阻塞事件循环

**Files:**
- Modify: `app/services/query/guard.py`
- Modify: `app/api/dependencies.py`
- Modify: `app/api/routes/compatibility/advanced_rag.py`
- Test: `tests/services/test_query_guard_async.py`

**Interfaces:**
- Produces: `QueryLoadGuard.acquire_async(user_key)`（异步上下文管理器）；`app.api.dependencies._reserve_chat_credit_async(request, user, resource_type)`。
- 保留：同步的 `acquire` / `_reserve_chat_credit` 原样不动——`app/api/routes/public/sessions.py` 的重跑路径是同步 `def` 处理器（跑在线程池里），继续用同步版本是正确的。

**Context:** 审计 #8。`app/services/query/guard.py:172` 使用 `threading.BoundedSemaphore.acquire(timeout=3.0)`（阻塞调用），而它经由同步上下文管理器 `_reserve_chat_credit` 在 **async 路由** `process_advanced_rag_query` 中执行。并发达到 `query_max_concurrent`（默认 24）时，后续请求会把整个事件循环阻塞最多 `query_acquire_timeout_ms`（默认 3 秒）——恰好在服务最需要保持响应的过载时刻。同一上下文里 `auth_service.chat_credit_reservation` 走的是同步 `sqlite3`，同样在循环上。

- [ ] **Step 1: 写测试**

创建 `tests/services/test_query_guard_async.py`：

```python
"""The async guard must not block the event loop while waiting for a slot."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.query.guard import QueryLoadGuard, QueryOverloadedError


def _guard(**overrides):
    kwargs = dict(
        per_user_max_requests=1000,
        per_user_window_seconds=60,
        max_concurrent=1,
        max_waiting=4,
        acquire_timeout_ms=1000,
        backend="memory",
    )
    kwargs.update(overrides)
    return QueryLoadGuard(**kwargs)


@pytest.mark.asyncio
async def test_event_loop_stays_responsive_while_a_slot_is_held():
    guard = _guard()
    ticks = 0

    async def heartbeat():
        nonlocal ticks
        for _ in range(20):
            await asyncio.sleep(0.01)
            ticks += 1

    async def holder():
        async with guard.acquire_async("u1"):
            await asyncio.sleep(0.15)

    async def waiter():
        async with guard.acquire_async("u2"):
            pass

    beat = asyncio.create_task(heartbeat())
    await asyncio.gather(holder(), waiter())
    await beat
    # A blocking acquire would have frozen the heartbeat for the whole wait.
    assert ticks >= 10


@pytest.mark.asyncio
async def test_queue_full_still_raises():
    guard = _guard(max_waiting=0, acquire_timeout_ms=1000)

    async def holder():
        async with guard.acquire_async("u1"):
            await asyncio.sleep(0.2)

    task = asyncio.create_task(holder())
    await asyncio.sleep(0.05)
    with pytest.raises(QueryOverloadedError):
        async with guard.acquire_async("u2"):
            pass
    await task
```

- [ ] **Step 2: 给 `QueryLoadGuard` 增加异步入口**

在 `app/services/query/guard.py` 顶部把 import 改为：

```python
import asyncio
import logging
import sys
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
```

在 `QueryLoadGuard.acquire` 之后新增：

```python
    @asynccontextmanager
    async def acquire_async(self, user_key: str) -> AsyncIterator[dict[str, int | str]]:
        """Acquire a slot without blocking the event loop.

        ``acquire`` waits on a threading primitive for up to
        ``acquire_timeout_ms``.  Running that wait inline in an async handler
        freezes every other task on the loop precisely when the server is
        overloaded, so the blocking enter and exit are moved to worker threads.
        """
        manager = self.acquire(user_key)
        stats = await asyncio.to_thread(manager.__enter__)
        exc_info: tuple = (None, None, None)
        try:
            yield stats
        except BaseException:
            exc_info = sys.exc_info()
            raise
        finally:
            await asyncio.to_thread(manager.__exit__, *exc_info)
```

- [ ] **Step 3: 给 `_reserve_chat_credit` 增加异步孪生体**

**先确认** `auth_service.chat_credit_reservation` 的 `__exit__` 语义：`credit.commit()` 是显式调用，未提交时退出应当是回滚/释放。用以下命令核对，再决定是否需要向 `__exit__` 传递异常信息：

```bash
grep -n "def chat_credit_reservation" -A 30 app/services/auth/user_manager.py
```

在 `app/api/dependencies.py` 中，紧接现有 `_reserve_chat_credit` 之后新增：

```python
@asynccontextmanager
async def _reserve_chat_credit_async(request: Request, user: dict[str, Any], resource_type: str):
    """Async twin of ``_reserve_chat_credit`` for async route handlers.

    ``_reserve_chat_credit`` waits on a threading semaphore and touches SQLite;
    both must stay off the event loop.  Sync handlers (e.g. the message-rerun
    path) keep using the sync version, which already runs in a threadpool.
    """
    manager = _reserve_chat_credit(request, user, resource_type)
    credit = await asyncio.to_thread(manager.__enter__)
    exc_info: tuple = (None, None, None)
    try:
        yield credit
    except BaseException:
        exc_info = sys.exc_info()
        raise
    finally:
        await asyncio.to_thread(manager.__exit__, *exc_info)
```

并把该模块顶部的 import 补齐：`import asyncio`、`import sys`，以及 `from contextlib import asynccontextmanager, contextmanager`。

- [ ] **Step 4: 在异步路由中改用异步版本**

在 `app/api/routes/compatibility/advanced_rag.py` 中：

```python
from app.api.dependencies import (
    _build_memory_context_for_session,
    _history_store_for_user,
    _promote_long_term_memory,
    _require_permission,
    _require_user,
    _require_valid_session_id,
    _reserve_chat_credit_async,
)
```

并把 `process_advanced_rag_query` 改为：

```python
@router.post("/query", response_model=AdvancedRAGResult)
async def process_advanced_rag_query(
    request_data: AdvancedRAGRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    async with _reserve_chat_credit_async(request, user, "advanced_query") as credit:
        response = await _process_advanced_rag_query_impl(request_data, request, user)
        credit.commit()
        return response
```

- [ ] **Step 5: 验证并提交**

```bash
conda run -n rag-local python -m pytest tests/services/test_query_guard_async.py tests/api/ -x -q
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
conda run -n rag-local ruff check app/services/query/guard.py app/api/dependencies.py app/api/routes/compatibility/advanced_rag.py tests/
conda run -n rag-local ruff format app/services/query/guard.py app/api/dependencies.py app/api/routes/compatibility/advanced_rag.py tests/
git add app/services/query/guard.py app/api/dependencies.py app/api/routes/compatibility/advanced_rag.py tests/services/test_query_guard_async.py
git commit -m "fix(api): keep the query load guard and credit reservation off the event loop"
```

---

### Task 8: 限流中间件改用异步 Redis

**Files:**
- Modify: `app/services/auth/redis_rate_limit.py`
- Modify: `app/api/middleware/rate_limit.py`

**Interfaces:**
- Produces: `RedisRateLimiter.check_rate_limit_async(key, max_requests, window_seconds)`。
- 保留：同步 `check_rate_limit` 不动（若有同步调用方）；执行前用 grep 确认调用方集合。

**Context:** 审计 #9。`app/api/middleware/rate_limit.py:51` 在 `async def dispatch` 中调用同步 `redis` 客户端的 `pipe.execute()`——这是一次阻塞网络往返，跑在事件循环上；`RedisRateLimiter.__init__` 里的 `redis.from_url(...).ping()` 同理。项目已依赖 `redis>=5.0.0`，其自带 `redis.asyncio`，改造无需新依赖。该文件还用 `print()` 而非 `logging` 输出运行状态。

- [ ] **Step 1: 确认调用方集合**

```bash
grep -rn "check_rate_limit\|get_rate_limiter\|RedisRateLimiter" app --include=*.py
```

记录所有同步调用点；只有全部迁移完毕才可以删除同步版本（本任务不删）。

- [ ] **Step 2: 把 `print` 换成 logging**

在 `app/services/auth/redis_rate_limit.py` 顶部加入：

```python
import logging

logger = logging.getLogger(__name__)
```

把文件中全部 4 处 `print(f"INFO: ...")` / `print(f"WARNING: ...")` 改为对应的 `logger.info(...)` / `logger.warning(...)`，去掉字符串里的 `INFO: ` / `WARNING: ` 前缀。

- [ ] **Step 3: 增加异步实现**

在 `RedisRateLimiter` 中新增一个惰性初始化的异步客户端与异步检查方法，与现有同步实现并列（滑动窗口算法逻辑与 `_check_redis` 保持一致，内存回退直接复用现有的 `_check_memory`，它是纯 CPU 操作，无需线程）：

```python
    async def _get_async_client(self):
        """Lazily create the asyncio Redis client, or None when unavailable."""
        if self._async_client is not None:
            return self._async_client
        if not (REDIS_AVAILABLE and self._redis_url):
            return None
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, decode_responses=False)
            await client.ping()
            self._async_client = client
        except Exception as exc:
            logger.warning("RedisRateLimiter: async Redis unavailable (%s), using in-memory storage", exc)
            self._async_client = None
        return self._async_client

    async def check_rate_limit_async(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int | None]:
        """Async sliding-window check; never blocks the event loop."""
        client = await self._get_async_client()
        if client is None:
            return self._check_memory(key, max_requests, window_seconds)
        try:
            current_time = time.time()
            window_start = current_time - window_seconds
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, window_seconds + 1)
            results = await pipe.execute()
            if results[1] >= max_requests:
                oldest = await client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    return False, int(window_seconds - (current_time - oldest[0][1])) + 1
                return False, window_seconds
            return True, None
        except Exception as exc:
            logger.warning("Redis rate limit check failed (%s); falling back to memory", exc)
            return self._check_memory(key, max_requests, window_seconds)
```

在 `__init__` 中记录 `self._redis_url = redis_url` 与 `self._async_client = None`（同步客户端的建立逻辑保持不变）。

- [ ] **Step 4: 中间件改调异步方法**

在 `app/api/middleware/rate_limit.py` 的 `dispatch` 中：

```python
        is_allowed, retry_after = await self.rate_limiter.check_rate_limit_async(
            rate_key, endpoint_config["max_requests"], endpoint_config["window_seconds"]
        )
```

- [ ] **Step 5: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
conda run -n rag-local ruff check app/services/auth/redis_rate_limit.py app/api/middleware/rate_limit.py
conda run -n rag-local ruff format app/services/auth/redis_rate_limit.py app/api/middleware/rate_limit.py
git add app/services/auth/redis_rate_limit.py app/api/middleware/rate_limit.py
git commit -m "fix(middleware): use asyncio Redis for rate limiting and log instead of print"
```

---

### Task 9: 缓存 OrchestrationEngine（必须先把事件上报改成请求隔离）

**Files:**
- Modify: `app/orchestration/engine.py`
- Modify: `app/pipeline/rag_pipeline.py`
- Test: `tests/orchestration/test_engine_reuse.py`

**Interfaces:**
- 改变：`OrchestrationServices` 的事件上报器从实例属性改为 `ContextVar`，与 `RAGAgentService._current_degradation_reporter`（`app/agents/rag/service.py:34`）已采用的模式一致。
- Produces: `RAGPipeline` 内的按 profile 缓存的引擎。

**Context:** 审计 #10。`app/pipeline/rag_pipeline.py:69` 每次请求都新建 `OrchestrationEngine`，其 `__init__` 会调用 `build_workflow()` 编译 StateGraph。实测**每请求约 21ms 纯构造开销**，且是事件循环上的同步 CPU 工作。系统只有一个 profile、一个 policy，完全可以复用。

**但不能直接缓存。** `OrchestrationEngine._execute` 会调用 `self._services.bind_event_reporter(reporter)`，而 `OrchestrationServices._event_reporter` 是**实例属性**。今天没出问题，纯粹是因为每个请求都有自己的引擎实例。一旦共享引擎，请求 B 的 `bind_event_reporter` 会覆盖请求 A 的上报器——**A 的执行事件会流进 B 的 SSE 流**。因此 Step 1 是这个任务的前提，不是可选优化。

- [ ] **Step 1: 把事件上报器改成 ContextVar**

在 `app/orchestration/engine.py` 顶部加入：

```python
from contextvars import ContextVar
```

在 `_discard_event` 定义之后（或模块级常量区）加入：

```python
# Per-request event reporter, installed by the engine for the current async
# task.  A ContextVar (not instance state) so one OrchestrationServices object
# can be shared across concurrent requests without leaking one request's
# execution events into another request's stream.  Mirrors the pattern already
# used by RAGAgentService for degradation reporting.
_current_event_reporter: ContextVar[Callable[[ExecutionEvent], Awaitable[None]] | None] = ContextVar(
    "orchestration_current_event_reporter", default=None
)
```

把 `OrchestrationServices` 的三处相关代码改为：

```python
    def bind_event_reporter(self, reporter: Callable[[ExecutionEvent], Awaitable[None]]) -> None:
        _current_event_reporter.set(reporter)
        if self._event_reporter_binder is not None:
            self._event_reporter_binder(reporter)

    async def report_event(self, event: ExecutionEvent) -> None:
        reporter = _current_event_reporter.get() or _discard_event
        await reporter(event)
```

并从 `__init__` 中删除 `self._event_reporter: Callable[...] = _discard_event` 这一行（`_event_reporter_binder` 保留）。

**注意**：`_event_reporter_binder` 指向 `RAGAgentService.set_degradation_reporter`，后者本身已经写 ContextVar，因此这条链路天然是请求隔离的。

- [ ] **Step 2: 写并发隔离测试**

创建 `tests/orchestration/test_engine_reuse.py`：

```python
"""A shared engine must keep each request's events in its own stream."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.events import ExecutionEvent
from app.orchestration.engine import OrchestrationServices


def _services() -> OrchestrationServices:
    async def unused(*args, **kwargs):
        raise AssertionError("not called in this test")

    return OrchestrationServices(
        router=unused, planner=unused, retriever=unused, tool_runner=unused, synthesizer=unused
    )


@pytest.mark.asyncio
async def test_concurrent_tasks_do_not_share_the_event_reporter():
    services = _services()
    seen: dict[str, list[str]] = {"a": [], "b": []}

    async def run(name: str) -> None:
        async def reporter(event: ExecutionEvent) -> None:
            seen[name].append(event.stage)

        services.bind_event_reporter(reporter)
        await asyncio.sleep(0)  # force interleaving with the other task
        await services.report_event(ExecutionEvent(stage="route", status="completed"))

    await asyncio.gather(run("a"), run("b"))

    assert seen["a"] == ["route"]
    assert seen["b"] == ["route"]
```

在 Step 1 之前这个测试必须失败（两个事件都会落到最后一次 bind 的那个上报器）。

- [ ] **Step 3: 缓存引擎**

在 `app/pipeline/rag_pipeline.py` 中把 `_engine_for` 改为：

```python
    def _engine_for(self, profile: PipelineProfile) -> PipelineExecutionEngine:
        if self._injected_engine is not None:
            return self._injected_engine
        engine = _ENGINE_CACHE.get(profile)
        if engine is None:
            engine = OrchestrationEngine(
                services=self.capabilities.orchestration_services(),
                policy=ExecutionPolicy.for_profile(profile),
            )
            _ENGINE_CACHE[profile] = engine
        return engine
```

并在模块级（`class RAGPipeline` 之前）加入：

```python
# One compiled LangGraph workflow per profile.  Building it costs ~20ms of
# synchronous CPU work, which would otherwise run on the event loop for every
# request.  Safe to share only because OrchestrationServices scopes its event
# reporter with a ContextVar (see app/orchestration/engine.py).
_ENGINE_CACHE: dict[PipelineProfile, PipelineExecutionEngine] = {}
```

**注意**：只有当 `RAGPipeline` 使用默认的 `capabilities`（即 `capabilities` 参数为 `None`）时才可以走缓存。若调用方注入了自定义 `capabilities`，必须绕过缓存。在 `__init__` 中记录 `self._uses_default_capabilities = capabilities is None`，并把 `_engine_for` 的缓存分支加上这个条件。

- [ ] **Step 4: 测量收益并提交**

```bash
conda run -n rag-local python -m pytest tests/orchestration/test_engine_reuse.py -x -q
conda run -n rag-local python -c "
import time
from app.pipeline.rag_pipeline import RAGPipeline
from app.pipeline.profiles import PipelineProfile
for i in range(4):
    t=time.perf_counter(); RAGPipeline()._engine_for(PipelineProfile.ADVANCED)
    print('%.2f ms' % ((time.perf_counter()-t)*1000))
"
```

第一次约 20ms，之后应降到 1ms 以内。

```bash
conda run -n rag-local ruff check app/orchestration/engine.py app/pipeline/rag_pipeline.py tests/
conda run -n rag-local ruff format app/orchestration/engine.py app/pipeline/rag_pipeline.py tests/
git add app/orchestration/engine.py app/pipeline/rag_pipeline.py tests/orchestration/test_engine_reuse.py
git commit -m "perf(pipeline): reuse the compiled workflow and scope event reporting per request"
```

---

### Task 10: 管理端基准测试改为后台任务

**Files:**
- Modify: `app/api/routes/admin/ops.py`

**Interfaces:**
- 改变：`POST /admin/ops/benchmark/run` 与 `POST /admin/ops/replay/run` 由同步执行改为投递到 `BackgroundTaskQueue` 并立即返回 `202` + `job_id`。
- Consumes: `api_dependencies.get_query_runtime().shadow_queue`（`BackgroundTaskQueue`，已在 lifespan 中 `start()`）。

**Context:** 审计 #11。`app/api/routes/admin/ops.py:271` 与 `:385` 在单个 HTTP 请求内同步执行最多 20（benchmark）/ 50（replay）次完整 RAG 查询，每次查询内部还各起一次 `asyncio.run()`。按每次 3–5 秒计，单请求耗时 1–4 分钟，必然撞上反向代理超时，并长期占用 FastAPI 线程池的一个 worker。

- [ ] **Step 1: 确认后台队列的投递 API**

```bash
grep -n "def submit\|def enqueue\|def stats\|def start\|def stop" app/services/runtime/background_queue.py
```

按其实际方法名编写 Step 2；若队列不支持返回结果，则把结果写入现有的 benchmark 结果文件（`run_benchmark` 已有落盘逻辑，读取端点 `/admin/ops/benchmark/trends` 已存在），端点只需返回"已受理"。

- [ ] **Step 2: 改造两个端点**

以 benchmark 为例（replay 同构）：

```python
@router.post("/benchmark/run", status_code=202)
def admin_ops_benchmark_run(
    request: Request,
    max_queries: int = 20,
    user: dict[str, Any] = Depends(_require_user),
):
    """Accept a benchmark run and execute it off the request path.

    A run executes up to ``max_queries`` full RAG queries; doing that inline
    kept one HTTP request open for minutes and occupied a threadpool worker.
    Results land in the existing benchmark history read by /benchmark/trends.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    if max_queries < 1:
        raise bad_request("max_queries must be >= 1")
    queue = api_dependencies.get_query_runtime().shadow_queue
    queue.submit(lambda: run_benchmark(max_queries=max_queries, execute_query=_execute_standard_profile))
    _audit(
        request,
        action="admin.ops.benchmark.run",
        resource_type="admin",
        result="accepted",
        user=user,
        detail=f"queries={max_queries}",
    )
    return {"ok": True, "status": "accepted", "max_queries": max_queries}
```

- [ ] **Step 3: 前端适配**

`frontend/src/pages/admin/actions/opsActions.ts` 中触发 benchmark/replay 的调用方需要改为"提交后提示已受理，稍后刷新 trends"，而不是等待结果。执行时先读该文件确认现有交互。

- [ ] **Step 4: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
cd frontend && npm run build && cd ..
git add app/api/routes/admin/ops.py frontend/src/pages/admin/
git commit -m "perf(admin): run ops benchmark and replay in the background queue"
```

### Phase 2 验收

- [ ] `tests/retrievers/test_no_module_patching.py`、`tests/services/test_query_guard_async.py`、`tests/orchestration/test_engine_reuse.py` 全绿。
- [ ] 并发压测：`query_max_concurrent` 设为 2，同时发 10 个查询，期间 `GET /health` 仍能在 100ms 内返回。
- [ ] `POST /admin/ops/benchmark/run` 在 1 秒内返回 202。

---

# Phase 3 — 配置漂移与假功能

> 这一阶段不改变任何运行行为，只让"配置面"与"实现面"重新对齐：删掉无人读取的开关，修掉永远说谎的健康检查。

### Task 11: 删除 33 个无读取方的 Settings 字段

**Files:**
- Modify: `app/core/config.py`
- Modify: `config/env/*.env.example`、`config/profiles/*.env.example`（同步删除对应条目）
- Test: `tests/core/test_settings_have_readers.py`

**Context:** 审计 #12。261 个 Settings 字段中有 33 个在 `app/` 内**零读取**（已排除通过 property 间接使用的字段）。它们让运维以为某些开关有效，实际上不然。危害最大的几个：

| 字段 | 实际后果 |
|---|---|
| `query_rate_limit_admin` / `_premium` / `_user` | **角色限流不存在**（`app/services/security/role_based_rate_limiter.py` 也是零引用孤儿，Phase 4 删除） |
| `query_request_timeout_ms`、`query_overload_inflight_threshold`、`query_overload_waiting_threshold` | 过载保护阈值不生效 |
| `query_retry_enabled` / `_max_attempts` / `_base_delay_ms` | 实现已于 2026-08-29 删除，配置遗留 |
| `clarification_max_rounds`、`clarification_min_confidence` | 澄清轮数硬编码在 `rules.py::_MAX_ROUNDS`，env 无效 |
| `answer_safety_scan_enabled` | 见 Task 14 |
| `db_pool_size`/`_max_overflow`/`_timeout`/`_recycle` | 见 Task 13 |
| `enable_llm_intent_classification`、`enable_query_rewrite` | 与 `query_rewrite_enabled` 等重复 |
| `tool_runner_max_iterations`、`tavily_api_key` | ReAct 已删除 |
| `perf_gate_max_p95_ms`、`perf_gate_max_error_rate_percent` | 质量门禁随 `scripts/` 一起清空 |

- [ ] **Step 1: 重新生成待删清单（树可能已变化）**

```bash
conda run -n rag-local python - <<'PY'
import ast, re, os
src = open("app/core/config.py", encoding="utf-8").read()
fields = [
    st.target.id
    for node in ast.walk(ast.parse(src))
    if isinstance(node, ast.ClassDef) and node.name == "Settings"
    for st in node.body
    if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)
]
cfg_body = "\n".join(
    l for l in src.splitlines()
    if not re.match(r"\s*\w+\s*:\s*[\w\[\]| ]+\s*=\s*Field\(", l)
)
texts = [cfg_body]
for dp, _dn, fn in os.walk("app"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        p = os.path.join(dp, f)
        if f.endswith(".py") and p != os.path.join("app", "core", "config.py"):
            texts.append(open(p, encoding="utf-8", errors="ignore").read())
blob = "\n".join(texts)
unused = [f for f in fields if not re.search(r"\b" + re.escape(f) + r"\b", blob)]
print(f"{len(unused)} / {len(fields)} unread:")
for u in unused:
    print(" ", u)
PY
```

- [ ] **Step 2: 逐个删除，并同步删除 env 模板中的条目**

对清单中的每个字段，删除 `app/core/config.py` 里的声明行，并 grep 其 env 别名（例如 `QUERY_RATE_LIMIT_ADMIN`）在 `config/` 与 `deploy/` 下的出现，一并删除：

```bash
grep -rn "QUERY_RATE_LIMIT_ADMIN\|QUERY_RETRY_ENABLED\|PERF_GATE_MAX_P95_MS" config/ deploy/
```

**例外**：`admin_create_approval_token` 虽然零读取，但它与仍在使用的 `admin_create_approval_token_hash` 是一对（明文/哈希两种配置方式）。删除前先 grep 确认哈希路径能独立工作；若不能，保留并加注释说明它只在 `reload_settings` 后由哈希路径消费。

- [ ] **Step 3: 顺手修掉重复注释**

`app/core/config.py` 中 `# Query Analysis & Clarification` 连续出现两次，删掉其中一行。

- [ ] **Step 4: 增加防回归测试**

创建 `tests/core/test_settings_have_readers.py`，把 Step 1 的脚本逻辑固化为一个断言"未读字段数为 0"的测试，防止以后再堆积死配置。

- [ ] **Step 5: 验证并提交**

```bash
conda run -n rag-local python -m pytest tests/core/test_settings_have_readers.py -x -q
conda run -n rag-local python -c "from app.core.config import get_settings; get_settings(); print('settings ok')"
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
git add app/core/config.py config/ tests/core/test_settings_have_readers.py
git commit -m "chore(config): drop settings fields that no code reads"
```

---

### Task 12: 修复 /ready 探针

**Files:**
- Modify: `app/api/routes/operations/health.py`

**Context:** 审计 #14，三个独立问题：

1. `_check_postgres_ready`（第 130 行）import 的 `app.core.database` **模块不存在**（`app/core/` 下只有 config/exceptions/logging_config/models/schemas/shared_config），于是永远返回 `ok: True, status: "not_configured"` —— 一个永远说谎的健康检查。
2. 8 项检查**串行执行**，各带 3–5 秒超时，最坏约 30 秒，K8s / Docker 的 readiness probe 必然超时。
3. 端点**未鉴权**，且会真实调用 OpenAI `/models`、Anthropic、Ollama、Neo4j、Redis。任何人可以反复请求 `/ready` 放大对外部服务的请求与成本。

- [ ] **Step 1: 删除假的 postgres 检查**

删除 `_check_postgres_ready` 函数，并从 `ready()` 的 `checks` 字典中移除 `"postgres"` 条目。理由：所有真实存储走裸 `sqlite3`（见 Task 13），不存在需要探测的 PostgreSQL 连接。`sqlite` 的可用性已由 `chroma`/文件系统检查间接覆盖。

- [ ] **Step 2: 并发执行剩余检查**

把 `ready()` 改为 `async def` 并用线程池并发跑同步检查：

```python
@router.get("/ready")
async def ready():
    """Readiness probe — all dependency checks run concurrently.

    Each check carries its own 3-5s timeout; running them serially made the
    worst case ~30s, longer than a typical readiness-probe deadline.
    """
    names = ("redis", "ollama", "openai", "anthropic", "neo4j", "chroma", "embedding_model")
    fns = (
        _check_redis_ready,
        _check_ollama_ready,
        _check_openai_api_ready,
        _check_anthropic_api_ready,
        _check_neo4j_ready,
        _check_chroma_ready,
        _check_embedding_model_ready,
    )
    results = await asyncio.gather(*(asyncio.to_thread(fn) for fn in fns), return_exceptions=True)
    checks: dict[str, dict[str, Any]] = {"api": {"ok": True, "required": True, "latency_ms": 0}}
    for name, result in zip(names, results, strict=True):
        checks[name] = (
            {"ok": False, "required": False, "latency_ms": 0, "error": "dependency check failed"}
            if isinstance(result, BaseException)
            else result
        )
```

其余（`blocking_failures` 计算、状态码判定、payload 组装）保持不变。在模块顶部补 `import asyncio`。

- [ ] **Step 3: 把昂贵的外部探测收敛到鉴权端点**

`/ready` 保留为**廉价**探针：只做本地检查（chroma 目录、embedding 模型是否已加载、api 自身）。把会发起外部网络调用的 4 项（ollama / openai / anthropic / neo4j）移到一个新的管理员端点：

```python
@router.get("/ready/dependencies", dependencies=[Depends(require_admin)])
async def ready_dependencies():
    """Full external-dependency probe.  Admin-only: it makes real outbound
    calls to the configured model providers and to Neo4j, so it must not be
    reachable by unauthenticated callers."""
```

把 Step 2 的完整实现放进这个端点，`/ready` 只保留本地检查子集。

- [ ] **Step 4: 移除 query_runtime 明细**

`ready()` 的 payload 中 `query_runtime.guard.stats()` 与 `shadow_queue.stats()` 暴露了内部并发状态，且未经 `_public_readiness_detail` 清洗。把这两项一并移到 `/ready/dependencies`。

- [ ] **Step 5: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
```

端点数应 **+1**（新增 `/ready/dependencies`）。**新基线 = 152**。

```bash
conda run -n rag-local ruff check app/api/routes/operations/health.py
conda run -n rag-local ruff format app/api/routes/operations/health.py
git add app/api/routes/operations/health.py
git commit -m "fix(health): drop the fake postgres probe, parallelize checks, gate outbound probes"
```

---

### Task 13: 删除未被使用的数据库连接池

**Files:**
- Delete: `app/database/connection_pool.py`
- Delete: `app/database/query_optimizer.py`
- Delete: `app/database/` 整个包（若删空）
- Modify: `app/api/application/lifespan.py`
- Modify: `app/api/routes/optimization/performance.py`

**Context:** 审计 #13。`DatabaseConnectionPool` 在 `get_connection_pool()`（第 203 行）中以**全部默认值**构造，`DB_POOL_SIZE` 等 4 个 env 完全被忽略；而 lifespan 却打印 `size=%d` 并传入 `settings.db_pool_size`（默认值恰好也是 20，掩盖了这个 bug）。

更关键的是：**这个 async 引擎从未被任何业务代码使用过**。全仓库对它的引用只有 lifespan 的初始化/关闭，以及 `/optimization/*` 读取它的统计。真实存储全部走裸 `sqlite3.connect()`：`app/services/auth/auth_service.py:116`、`app/services/sessions/history.py:487`、`app/services/sessions/metadata_db.py:113`、`app/services/prompts/store.py:24`、`app/wiki/store.py:33`、`app/retrievers/stores/vector.py:24`。

因此 CLAUDE.md 声称的 "PostgreSQL (`asyncpg`) supported for production" **不成立**。

**2026-08-29 执行 Task 21 时取得的佐证**：`aiosqlite` 与 `asyncpg` 虽然写在 `pyproject.toml` 的**硬依赖**里，但在 `rag-local` 环境中**根本没有安装**，而应用一切正常。也就是说 `initialize_pool()` 每次启动都以 `ModuleNotFoundError` 失败，被 lifespan 的 `except Exception: logger.warning(... non-critical)` 吞掉——没有任何人注意到，因为没有任何东西使用这个池。删除时记得一并从 `dependencies` 中移除这两个包。本任务的选择是**删除误导性的死代码**，而不是把 6 个存储迁移到 async SQLAlchemy —— 后者是独立的存储层重构，已在 Scope 中明确排除。

`query_optimizer.py` 一并删除：它唯一的公开方法 `explain_query` 已被硬编码为 `raise NotImplementedError`，其余部分只被 `/optimization/database/*` 引用。

- [ ] **Step 1: 复核引用**

```bash
grep -rn "connection_pool\|query_optimizer\|initialize_pool\|close_pool\|get_connection_pool\|optimize_database" app --include=*.py
```

预期只出现在：`app/database/`、`app/api/application/lifespan.py`、`app/api/routes/optimization/performance.py`。若出现其他调用方，**停止并复核**。

- [ ] **Step 2: 从 lifespan 中移除**

删除 `app/api/application/lifespan.py` 中的：
- 全局标志 `_pool_initialized`（含 `global` 声明中的引用）
- 启动块 `try: from app.database.connection_pool import initialize_pool ... except`
- 关闭块 `if _pool_initialized: ... close_pool()`

`_cache_initialized` 与缓存管理器保持不变（那是活的）。

- [ ] **Step 3: 从 optimization 路由中移除相关端点**

删除 `app/api/routes/optimization/performance.py` 中的三个端点：`/database/stats`、`/database/optimize`、`/database/slow-queries`；从 `/stats` 的聚合 payload 中移除 `"database": connection_pool.get_pool_stats()` 一项；删除对应的两行 import。

- [ ] **Step 4: 删除包并从依赖中移除 asyncpg**

```bash
git rm -r app/database/
```

在 `pyproject.toml` 的 `dependencies` 中删除 `"asyncpg>=0.29.0,<1.0"`。**保留** `sqlalchemy[asyncio]` 与 `aiosqlite`，除非 grep 确认它们也无人使用：

```bash
grep -rn "sqlalchemy\|aiosqlite" app --include=*.py
```

- [ ] **Step 5: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
```

端点数应 **−3**（删除 `/optimization/database/{stats,optimize,slow-queries}`）。**新基线 = 149**。

```bash
git add -A app/database app/api/application/lifespan.py app/api/routes/optimization/performance.py pyproject.toml
git commit -m "chore(db): remove the unused async connection pool and query optimizer"
```

---

### Task 14: 让答案安全扫描尊重它的开关

**Files:**
- Modify: `app/services/answer_safety.py`
- Test: `tests/services/test_answer_safety.py`

**Context:** 审计 #15/#17。`sanitize_answer` 硬返回 `{"enabled": True, ...}` 且从不读取 `settings.answer_safety_scan_enabled` —— 该开关完全无效（Task 11 会把它从"待删清单"里移出来，因为本任务给了它读取方）。

另外 CLAUDE.md 声称安全层覆盖 "API keys, private keys, SSNs, credit card numbers, passwords, emails, phone numbers"，但 `answer_safety.py` 只有 4 条模式（`sk-*`、`AKIA*`、私钥头、`password/token=`）。SSN / 信用卡 / 邮箱 / 电话 的模式在**另一条路径** `app/agents/validation/rules.py:117-121` 上。本任务不合并这两套（合并会改变输出行为），只让开关生效；文档由 Task 23 修正。

- [ ] **Step 1: 写测试**

创建 `tests/services/test_answer_safety.py`：

```python
"""The answer safety scan must honour its settings flag."""

from __future__ import annotations

from app.services import answer_safety


def test_secrets_are_redacted_when_enabled():
    text, meta = answer_safety.sanitize_answer("key is sk-abcdefghijklmnop1234")
    assert "sk-abcdefghijklmnop1234" not in text
    assert meta["enabled"] is True
    assert meta["redactions"] == 1


def test_scan_can_be_disabled(monkeypatch):
    class _Settings:
        answer_safety_scan_enabled = False

    monkeypatch.setattr(answer_safety, "get_settings", lambda: _Settings())
    original = "key is sk-abcdefghijklmnop1234"
    text, meta = answer_safety.sanitize_answer(original)
    assert text == original
    assert meta == {"enabled": False, "redactions": 0}
```

- [ ] **Step 2: 实现**

```python
import re

from app.core.config import get_settings

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    re.compile(r"\b(?:password|passwd|token|secret)\s*[:=]\s*\S{4,}", flags=re.IGNORECASE),
]


def sanitize_answer(text: str) -> tuple[str, dict]:
    """Redact credential-shaped strings from an answer.

    Returns the sanitized text plus a report.  ``ANSWER_SAFETY_SCAN_ENABLED=false``
    disables the scan entirely; the report then says so rather than claiming a
    scan ran.
    """
    raw = str(text or "")
    if not bool(getattr(get_settings(), "answer_safety_scan_enabled", True)):
        return raw, {"enabled": False, "redactions": 0}
    redactions = 0
    sanitized = raw
    for pattern in _PATTERNS:
        sanitized, n = pattern.subn("[REDACTED]", sanitized)
        redactions += int(n)
    return sanitized, {"enabled": True, "redactions": redactions}
```

- [ ] **Step 3: 验证并提交**

```bash
conda run -n rag-local python -m pytest tests/services/test_answer_safety.py -x -q
conda run -n rag-local ruff check app/services/answer_safety.py tests/
conda run -n rag-local ruff format app/services/answer_safety.py tests/
git add app/services/answer_safety.py tests/services/test_answer_safety.py
git commit -m "fix(safety): honour ANSWER_SAFETY_SCAN_ENABLED instead of hardcoding enabled"
```

---

### Task 15: 删除 profile / policy 的死配置

**Files:**
- Modify: `app/pipeline/profiles.py`
- Modify: `app/orchestration/policies.py`
- Modify: `app/pipeline/rag_pipeline.py`

**Context:** 审计 #16。`ProfileCapabilities`（17 个字段）、`CapabilityBudget`（4 个字段）、`ENDPOINT_PROFILES`、`profile_for_endpoint` **全部零读取** —— `get_profile_definition(selected)` 在 `rag_pipeline.py:93/110` 只被当作"未知 profile 抛错"的校验使用，返回值从不使用。更糟的是两套配置互相矛盾：`ProfileCapabilities(answer_validation=False, quality_reporting=False)`，而 `ExecutionPolicy.for_profile` 硬编码 `require_answer_validation=True, require_quality_report=True`（后者才是生效的那个）。

`ExecutionPolicy` 的 `enable_route_validation` 与 `enable_retrieval_quality` 两个字段也无任何读取方。

- [ ] **Step 1: 复核零读取**

```bash
grep -rn "ProfileCapabilities\|CapabilityBudget\|ENDPOINT_PROFILES\|profile_for_endpoint\|\.capabilities\b\|\.budget\b" app --include=*.py | grep -v "app/pipeline/profiles.py"
grep -rn "enable_route_validation\|enable_retrieval_quality" app --include=*.py
```

- [ ] **Step 2: 精简 `profiles.py`**

删除 `ProfileCapabilities`、`CapabilityBudget`、`ProfileDefinition`、`PROFILE_DEFINITIONS`、`ENDPOINT_PROFILES`、`profile_for_endpoint`、`get_profile_definition`，只保留 `PipelineProfile` 枚举。加一段模块 docstring 说明为什么只剩枚举：

```python
"""The pipeline profile enum.

The system runs a single profile.  The capability/budget descriptors that used
to live here were never read — ``ExecutionPolicy.for_profile`` is the single
source of truth for what a profile enables — and they had drifted into
contradicting it, so they were removed rather than kept as decoration.
"""
```

- [ ] **Step 3: 更新 `rag_pipeline.py`**

删除 `get_profile_definition` 的 import 与两处调用。`execute()` 中原有的 profile 一致性校验保留：

```python
        selected = request.profile if profile is None else PipelineProfile(profile)
        if selected != request.profile:
            raise ValueError("Pipeline profile must match PipelineRequest.profile")
```

`PipelineProfile(profile)` 本身就会对未知值抛 `ValueError`，校验语义不丢失。

- [ ] **Step 4: 精简 `ExecutionPolicy`**

删除 `enable_route_validation` 与 `enable_retrieval_quality` 两个字段，以及 `for_profile` 中对 `enable_retrieval_quality` 的赋值。

- [ ] **Step 5: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
conda run -n rag-local python -m pytest tests/ -q
git add app/pipeline/profiles.py app/pipeline/rag_pipeline.py app/orchestration/policies.py
git commit -m "chore(pipeline): remove profile and policy fields that nothing reads"
```

### Phase 3 验收

- [ ] `tests/core/test_settings_have_readers.py` 断言未读字段为 0。
- [ ] `GET /ready` 在 2 秒内返回，且不发起任何外部网络调用。
- [ ] `GET /ready/dependencies` 未鉴权时返回 401/403。
- [ ] `ANSWER_SAFETY_SCAN_ENABLED=false` 时答案中的 `sk-` 串不再被替换。

---

# Phase 4 — 死代码与结构清理

> 184 个模块 / 13,115 行（约占后端 20%）零引用。**这一阶段必须在 Phase 5 建立 CI 之后再做，或者至少与 Task 21 并行** —— 没有门禁的大规模删除是最容易引入回归的操作。若时间紧张，可先做 Phase 5 的 Task 21/22，再回来做 Phase 4。

每个删除任务共用同一套安全流程：**复核 grep → 删除 → 验证应用仍能启动且端点数不变 → 提交**。端点基线在 Phase 3 结束后为 **149**（151 + Task 12 的 1 − Task 13 的 3）。

### Task 16: 删除四个连 import 都失败的模块与两个备份文件

**Files:**
- Delete: `app/api/routes/public/query_status.py`
- Delete: `app/evaluation/services/evaluation_service.py`（以及若因此删空的 `app/evaluation/services/`）
- Delete: `app/retrievers/optimized_retriever.py`
- Delete: `app/services/multimodal/processor.py`
- Delete: `app/agents/rag/cache.py.original`、`app/agents/shared/cache.py.original`

**Context:** 审计 #18/#21。对全部 184 个零引用模块逐个执行 `importlib.import_module` 后，有 4 个**连导入都会失败**：

| 模块 | 错误 |
|---|---|
| `app/api/routes/public/query_status.py` | `ModuleNotFoundError: No module named 'app.api.query.response'` |
| `app/evaluation/services/evaluation_service.py` | `ImportError: cannot import name 'GroundTruth' from 'app.evaluation.models'` |
| `app/retrievers/optimized_retriever.py` | `ImportError: cannot import name 'HybridRetriever' from 'app.retrievers.hybrid.retriever'` |
| `app/services/multimodal/processor.py` | `ModuleNotFoundError: No module named 'fitz'`（可选 extra `multimodal`） |

前三个是彻底损坏的死代码。第四个（`processor.py`）依赖可选 extra，但它同样零引用 —— 活的多模态入口是 `app/services/multimodal/image_processor.py` 与 `table_extractor.py`。

`query_status.py` 还牵出另一件事：它是 `QueryResultCache` 的**唯一读取方**，而这个缓存**从没有任何写入方**（审计 #15）。它也从未被注册进 `ROUTER_MODULES`，所以路由表里根本没有这个端点。删除后 `QueryResultCache` 变成完全零引用，在 Task 19 中一并删除。

`.original` 是被 git 跟踪的备份文件，与现行版本分别相差 486 行和 190 行。

- [ ] **Step 1: 复核引用**

```bash
grep -rn "query_status\|optimized_retriever\|evaluation_service\|multimodal.processor\|multimodal import processor" app --include=*.py
grep -rn "cache.py.original" app deploy config --include=* 2>/dev/null
```

预期无输出（`app/evaluation/services/__init__.py` 若 re-export 了 `EvaluationService`，需一并处理）。

- [ ] **Step 2: 删除**

```bash
git rm app/api/routes/public/query_status.py
git rm app/retrievers/optimized_retriever.py
git rm app/services/multimodal/processor.py
git rm -r app/evaluation/services/
git rm app/agents/rag/cache.py.original app/agents/shared/cache.py.original
```

- [ ] **Step 3: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"   # 期望 149
git commit -m "chore: delete four modules that fail to import and two stale .original backups"
```

---

### Task 17: 拆除为已删测试保留的兼容层

**Files:**
- Modify: 所有仍在 import shim 路径的模块（由 Step 1 的脚本枚举）
- Modify: `app/api/main.py`
- Modify: `app/api/application/router_registry.py`
- Modify: `app/pipeline/rag_pipeline.py`
- Delete: 全部 alias shim 模块（约 78 个）

**Context:** 审计 #20。仓库中约有 78 个纯转发模块，形如：

```python
"""Compatibility alias for the canonical service owner."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("app.services.observability.alerting")
```

同源产物还有：
- `app/api/main.py` 的 `_CompatMainModule.__setattr__` monkeypatch 桥与 `__getattr__` 转发（第 71–95 行），注释明确写着 "for backward-compatible monkeypatching"；
- `router_registry.py` 的 `_ROUTE_MODULES` 元组，注释写着 "Keep this collection in the exact order used by app.api.main's compatibility monkeypatch bridge"，且 `pipeline_compat` "is intentionally included even though it is not itself registered as a router"；
- `RAGPipeline._execute_compatibility`（直接 `raise RuntimeError("compatibility execution is retired")`）与 `__init__` 的 `**deprecated` 吞参。

这些机制的唯一服务对象是 monkeypatch 式的测试，而 `tests/` 已于 2026-08-28 清空。保留它们的代价是：每个模块有两个可用路径，静态分析和重构工具都会被误导。

**注意：并非所有 shim 都是孤儿。** 例如 `app/retrievers/hybrid_retriever.py` 被 `app/agents/rag/vector.py:22` 使用，`app/services/query_guard.py` 被 `app/api/dependencies.py:41` 使用。必须先改写导入方，再删除。

- [ ] **Step 1: 枚举 shim 及其导入方**

```bash
conda run -n rag-local python - <<'PY'
import ast, os, re, collections

shims = {}
for dp, _dn, fn in os.walk("app"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f).replace("\\", "/")
        src = open(p, encoding="utf-8").read()
        m = re.search(r'_sys\.modules\[__name__\] = _?import_module\("([^"]+)"\)', src)
        if m:
            shims[p[:-3].replace("/", ".")] = m.group(1)

importers = collections.defaultdict(list)
for dp, _dn, fn in os.walk("app"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f).replace("\\", "/")
        if p[:-3].replace("/", ".") in shims:
            continue
        try:
            tree = ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            mod = n.module if isinstance(n, ast.ImportFrom) and not n.level else None
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else []
            for candidate in ([mod] if mod else []) + names:
                if candidate in shims:
                    importers[candidate].append(p)

print(f"{len(shims)} shims found; {sum(1 for s in shims if importers[s])} still imported\n")
for shim, target in sorted(shims.items()):
    where = importers[shim]
    print(f"{shim}\n    -> {target}")
    for w in where:
        print(f"       imported by {w}")
PY
```

把输出保存下来，它就是 Step 2 的工作清单。

- [ ] **Step 2: 把每个导入方改写到规范路径**

对脚本列出的每一个 "imported by"，把 `from app.services.alerting import X` 改为 `from app.services.observability.alerting import X`（即改成脚本输出的 `->` 目标）。逐文件改，改完立刻跑：

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
```

重跑 Step 1 的脚本，直到 "still imported" 为 0。

- [ ] **Step 3: 拆除 `app/api/main.py` 的兼容外壳**

把整个文件替换为：

```python
"""Stable FastAPI entry point."""

import logging

from app.api.application.factory import create_app
from app.api.dependencies import auth_service, settings
from app.api.utils import auth_dependencies, auth_helpers

logger = logging.getLogger(__name__)

auth_dependencies.auth_service = auth_service
auth_helpers.auth_service = auth_service

_STATIC_PATHS = resolve_static_file_paths()
_serve_react_index, serve_react_app_root, serve_react_app = build_frontend_handlers(_STATIC_PATHS)

app = create_app(
    settings,
    static_paths=_STATIC_PATHS,
    static_handlers=(_serve_react_index, serve_react_app_root, serve_react_app),
)

__all__ = ["app", "create_app"]
```

并补上 `from app.api.application.static_files import build_frontend_handlers, resolve_static_file_paths`。**删除**：`__getattr__`、`_CompatMainModule`、`sys.modules[__name__].__class__ = _CompatMainModule`、`_ROUTE_MODULES`、`_APPLICATION_COMPAT_MODULES`，以及所有仅为门面存在的 `# noqa: F401` 转发 import。

`auth_dependencies` / `auth_helpers` 的两行赋值**必须保留** —— 那是真实的运行时注入，不是兼容层。执行前用 grep 确认这两个模块确实读取模块级 `auth_service`。

- [ ] **Step 4: 精简 `router_registry.py`**

删除 `_ROUTE_MODULES` / `ROUTE_MODULES` 元组与相关注释，以及仅为它存在的 import（`api_dependencies`、`admin_helpers`、`document_helpers`、`memory_helpers`、`session_helpers`、`pipeline_compat`、`auth_dependencies`、`auth_helpers`）。保留 `ROUTER_MODULES` 与 `register_routers`。`__all__` 相应缩减为 `["ROUTER_MODULES", "register_routers"]`。

同步检查 `app/api/application/factory.py` 是否引用了 `ROUTE_MODULES`：

```bash
grep -rn "ROUTE_MODULES\|_ROUTE_MODULES" app --include=*.py
```

- [ ] **Step 5: 清理 `RAGPipeline` 的测试残留**

在 `app/pipeline/rag_pipeline.py` 中删除 `_execute_compatibility` 方法，并把 `__init__` 的 `**deprecated: Any` 参数及 `del deprecated` 一并删除（同时删掉那两行说明注释）。

- [ ] **Step 6: 删除全部 shim**

```bash
conda run -n rag-local python - <<'PY'
import os, re, subprocess
targets = []
for dp, _dn, fn in os.walk("app"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        if re.search(r'_sys\.modules\[__name__\] = _?import_module\("', open(p, encoding="utf-8").read()):
            targets.append(p.replace("\\", "/"))
print(f"deleting {len(targets)} shims")
subprocess.run(["git", "rm", *targets], check=True)
PY
```

- [ ] **Step 7: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"   # 期望 149
conda run -n rag-local python -m pytest tests/ -q
conda run -n rag-local ruff check app
git add -A app
git commit -m "chore(api): remove the compatibility shim layer left over from the deleted test suite"
```

---

### Task 18: 删除死掉的 prompts 包

**Files:**
- Delete: `app/prompts/` 下除 `core/canonical_agent_prompts.py` 与必要 `__init__.py` 之外的全部模块

**Context:** 审计 #19。`app/prompts/` 共 25 个模块约 3,400 行，其中**只有 `core/canonical_agent_prompts.py` 有一个导入方**（`app/agents/synthesizer/generation.py:19`）。零引用的包括：468 行的 `PromptManager`、4 套 skills 提示词库（`cybersecurity_skills_prompts.py` 397 行、`pdf_web_prompts.py` 319 行、`comparison_timeline_prompts.py` 302 行、`ai_knowledge_prompts.py` 209 行）、`retrieval/rag_quick_retrieval_prompts.py`（585 行）、`retrieval/self_rag_prompts.py`、以及 `core/` 下的 `intent_prompts.py` / `react_prompts.py` / `review_prompts.py` / `router_prompts.py` / `synthesis_prompts.py`。

活的提示词分别住在 `app/agents/synthesizer/templates.py`、`app/agents/router/examples.py`、`app/agents/planner/prompts.py`、`app/agents/knowledge/prompts.py`。

**注意**：Task 17 会先删掉 `app/prompts/` 根目录下那批 5–37 行的 shim；本任务处理剩下的实体模块。

- [ ] **Step 1: 复核**

```bash
conda run -n rag-local python - <<'PY'
import ast, os, collections
mods = {}
for dp, _dn, fn in os.walk("app/prompts"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if f.endswith(".py"):
            p = os.path.join(dp, f).replace("\\", "/")
            m = p[:-3].replace("/", ".")
            mods[m[:-9] if m.endswith(".__init__") else m] = p
ref = collections.Counter()
for dp, _dn, fn in os.walk("app"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f).replace("\\", "/")
        if p.startswith("app/prompts/"):
            continue
        try:
            tree = ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and not n.level and n.module:
                ref[n.module] += 1
            elif isinstance(n, ast.Import):
                for a in n.names:
                    ref[a.name] += 1
for m, p in sorted(mods.items()):
    print(f"{ref[m]:3d} external importers  {p}")
PY
```

只有 `app/prompts/core/canonical_agent_prompts.py` 应当 > 0。**任何其他非零结果都要停下来复核。**

- [ ] **Step 2: 删除**

保留 `app/prompts/__init__.py`、`app/prompts/core/__init__.py`、`app/prompts/core/canonical_agent_prompts.py`，删除其余全部。若 `__init__.py` 中 re-export 了被删模块，同步清理其内容。

```bash
git rm app/prompts/manager.py
git rm -r app/prompts/skills/ app/prompts/retrieval/
git rm app/prompts/core/intent_prompts.py app/prompts/core/react_prompts.py \
       app/prompts/core/review_prompts.py app/prompts/core/router_prompts.py \
       app/prompts/core/synthesis_prompts.py
```

- [ ] **Step 3: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"   # 期望 149
conda run -n rag-local python -c "from app.agents.synthesizer import generation; print('synthesis prompts ok')"
git add -A app/prompts
git commit -m "chore(prompts): delete the unused prompt library, keep the one live module"
```

---

### Task 19: 删除剩余零引用模块

**Files:** 由 Step 1 的脚本枚举（Task 16–18 完成后剩余部分）

**Context:** 审计 #18 的余量。Task 16–18 之后，仍有大量零引用模块，主要分布在：

| 包 | 代表模块 |
|---|---|
| `app/domain/` | `user_experience.py`(601)、`exceptions.py`(353) |
| `app/orchestration/` | `degradation_strategies.py`(488)、`error_handling.py`(174) |
| `app/tools/graph/` | `config.py`(196)（`core.py`/`enhanced.py` 经 shim 存活，Task 17 后改为直连） |
| `app/ingestion/processing/` | `performance.py`(390)、`structure_columns.py`(154)、`streaming.py`(127)、`monitoring.py`(116) |
| `app/services/` 各子包 | `security/role_based_rate_limiter.py`(205)、`runtime/query_result_cache.py`、`retrieval/context_compressor.py`(218)、`language/chinese_*.py`、`query/llm_rewriter.py` 等 |
| `app/agents/` | `rag/retrieval_quality.py`(347)、`shared/utils.py`(205)、`shared/result_schemas.py`(111) |
| `app/mcp/` | `server.py`(139)、`connectors/` |
| `app/evaluation/baselines/` | `hybrid.py`、`rerank.py`、`vector_only.py`（与 `chroma/` 下同名文件重复） |
| `app/api/routes/sessions/` | 若 Task 17 后仍零引用则复核 |

`app/orchestration/degradation_strategies.py` 值得单独一提：它是唯一读取 `config/circuit_breaker.json` 的模块，而那个文件**不存在**（导入时会打印 "Circuit breaker config not found... using defaults"）。真正生效的熔断配置是 `settings.circuit_breaker_*`。

**这个任务分批做，每批一个提交**，按上表分包，便于出问题时定位与回滚。

- [ ] **Step 1: 重新生成完整的零引用清单**

```bash
conda run -n rag-local python - <<'PY'
import ast, os, collections
mods = {}
for dp, _dn, fn in os.walk("app"):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if f.endswith(".py"):
            p = os.path.join(dp, f).replace("\\", "/")
            m = p[:-3].replace("/", ".")
            mods[m[:-9] if m.endswith(".__init__") else m] = p
ref = collections.Counter()
for m, p in mods.items():
    try:
        tree = ast.parse(open(p, encoding="utf-8").read())
    except SyntaxError:
        continue
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                ref[a.name] += 1
        elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
            ref[n.module] += 1
            for a in n.names:
                ref[f"{n.module}.{a.name}"] += 1
groups = collections.defaultdict(list)
for m, p in mods.items():
    if m in ("app", "app.main", "app.api.main") or p.endswith("__init__.py"):
        continue
    if ref[m] == 0:
        loc = sum(1 for _ in open(p, encoding="utf-8"))
        groups["/".join(p.split("/")[:3])].append((p, loc))
total = 0
for pkg in sorted(groups, key=lambda k: -sum(l for _, l in groups[k])):
    loc = sum(l for _, l in groups[pkg])
    total += loc
    print(f"\n{pkg}  ({loc} loc, {len(groups[pkg])} files)")
    for p, l in sorted(groups[pkg], key=lambda x: -x[1]):
        print(f"   {l:5d}  {p}")
print(f"\nTOTAL {total} loc")
PY
```

- [ ] **Step 2: 逐包删除**

对每个包重复：

```bash
# 1) 逐文件复核（模块名与 "from <pkg> import <name>" 两种形式都要查）
grep -rn "degradation_strategies\|OrchestrationDegradationPolicy" app --include=*.py

# 2) 删除
git rm app/orchestration/degradation_strategies.py app/orchestration/error_handling.py

# 3) 验证
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"

# 4) 提交
git commit -m "chore(orchestration): delete unreferenced degradation and error-handling modules"
```

**特别注意**：
- `app/domain/exceptions.py` 删除前，确认 `app/domain/__init__.py` 未 re-export 其中的异常类，且没有 `except SomeDomainError` 引用它们。
- `app/agents/shared/result_schemas.py` 与 `utils.py` 可能被 `app/agents/shared/__init__.py` re-export，需一并清理。
- 每删一个包，重跑一次 `conda run -n rag-local python -m pytest tests/ -q`。

- [ ] **Step 3: 清理空包**

删除只剩 `__init__.py`（或完全为空）的目录：`app/api/query/`、`app/api/query/streaming/`、`app/workflow/`、`app/tests/`。

```bash
git rm -r app/api/query app/workflow app/tests
```

`app/graph/__init__.py` 与 `app/agents/__init__.py` 为空但其子包是活的，**保留**。

- [ ] **Step 4: 最终验证**

```bash
conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"   # 期望 149
conda run -n rag-local python -m pytest tests/ -q
conda run -n rag-local ruff check app
```

再跑一次 Step 1 的脚本，确认剩余零引用模块数已降到个位数，并把每个残留项的保留理由写进提交信息。

---

### Task 20: 把生产路由从 compatibility/ 目录移出

**Files:**
- Move: `app/api/routes/compatibility/advanced_rag.py` → `app/api/routes/public/query.py`
- Move: `app/api/routes/compatibility/orchestration.py` → `app/api/routes/public/orchestration.py`
- Move: `app/api/routes/compatibility/pipeline_compat.py` → `app/api/routes/internal/pipeline_contract.py`
- Modify: `app/api/application/router_registry.py`、`app/api/routes/public/sessions.py`、`app/api/routes/admin/ops.py`、`app/mcp/server.py`（若未在 Task 19 删除）

**Context:** 审计 #23。生产聊天入口 `POST /api/advanced-rag/query` 的实现住在 `routes/compatibility/`，前端 SSE 消费的 `/api/v1/orchestration/executions/{id}/events` 也在那里。`pipeline_compat.py` 自己的模块 docstring 就写着 "⚠️ INTERNAL API - Not for external use ... Despite being in the 'compatibility' directory, this is NOT deprecated code"。目录名与实际角色严重不符，会持续误导后续重构（本次审计初期就一度把主查询端点当成遗留代码）。

**HTTP 路径不变** —— 只搬模块位置，`APIRouter(prefix=...)` 一律保持原样，避免破坏前端。

- [ ] **Step 1: 移动文件**

```bash
mkdir -p app/api/routes/internal
git mv app/api/routes/compatibility/advanced_rag.py app/api/routes/public/query.py
git mv app/api/routes/compatibility/orchestration.py app/api/routes/public/orchestration.py
git mv app/api/routes/compatibility/pipeline_compat.py app/api/routes/internal/pipeline_contract.py
git rm app/api/routes/compatibility/__init__.py
```

创建 `app/api/routes/internal/__init__.py`：

```python
"""Internal shared contracts used by multiple route modules.

Not registered as routers; these modules expose helper contracts (e.g. the
standard RAG pipeline execution contract) consumed by admin and session routes.
"""
```

- [ ] **Step 2: 更新导入方**

```bash
grep -rn "routes.compatibility\|routes import compatibility" app --include=*.py
```

逐个改写：
- `app/api/application/router_registry.py`：`from app.api.routes.compatibility import advanced_rag, orchestration` → 从 `public` 导入；同时更新 `ROUTER_MODULES` 中的符号名。
- `app/api/routes/public/sessions.py:19` 与 `app/api/routes/admin/ops.py:30`：`from app.api.routes.compatibility.pipeline_compat import execute_standard_compatibility` → `from app.api.routes.internal.pipeline_contract import execute_standard_compatibility`。
- Phase 1 新建的 `tests/api/test_advanced_rag_session.py` 中的 `from app.api.routes.compatibility import advanced_rag` → `from app.api.routes.public import query as advanced_rag`。

- [ ] **Step 3: 更新 pipeline_contract 的 docstring**

删除模块 docstring 里"Despite being in the 'compatibility' directory..."一段——它已不再适用。

- [ ] **Step 4: 验证路径未变并提交**

```bash
conda run --no-capture-output -n rag-local python -c "
import app.api.main as m
paths = set(m.app.openapi()['paths'])
assert '/api/advanced-rag/query' in paths, 'chat endpoint moved!'
assert '/api/v1/orchestration/executions/{execution_id}/events' in paths, 'SSE endpoint moved!'
print(len(paths), 'paths')
"
conda run -n rag-local python -m pytest tests/ -q
git add -A app tests
git commit -m "refactor(api): move live routes out of the compatibility directory"
```

### Phase 4 验收

- [ ] 零引用模块数降至个位数，且每个残留项都有书面保留理由。
- [ ] `app/` 的 Python 文件数与总行数记录在提交信息中（对比清理前的 583 文件）。
- [ ] 端点数为 149，`/api/advanced-rag/query` 与 SSE 端点路径未变。
- [ ] 全部测试通过。

---

# Phase 5 — 工程基线与文档

> 建议**先做 Task 21/22 再做 Phase 4** —— 大规模删除需要门禁保护。

### Task 21: 修复当前的 lint 失败并把 ruff 接入 pre-commit

> **执行记录（2026-08-29）**：Step 1–2 按计划完成（2 个 UP038 已修；`ruff format .` 实际重排 23 个文件，不是写计划时统计的 24 个）。**Step 3 有偏离**：`pre-commit` 在 `rag-local` 中并未安装，我没有擅自往环境里装包，改为把 `pre-commit>=3.7.0` 加进 `[project.optional-dependencies].dev`，并只校验了 YAML 可解析。**`pre-commit install` 与 `pre-commit run --all-files` 仍待人工执行。**

**Files:**
- Modify: `app/agents/router/routing.py:146`、`:278`
- Modify: 24 个未格式化文件
- Modify: `.pre-commit-config.yaml`

**Context:** 审计 #28/#29。CLAUDE.md 把 `ruff check .` 与 `ruff format .` 列为标准命令，但**两个当前都是红的**：`ruff check .` 报 2 个 `UP038` 错误，`ruff format --check .` 显示 24 个文件待格式化。`.pre-commit-config.yaml` 只有空白字符类 hook，**不含 ruff**，所以没有任何机制阻止这种漂移。

- [x] **Step 1: 修 UP038**

`app/agents/router/routing.py` 两处：

```python
        if reasoning_confidence is not None and isinstance(reasoning_confidence, int | float):
```

```python
        if llm_confidence is not None and isinstance(llm_confidence, int | float):
```

- [x] **Step 2: 格式化全仓库**

```bash
conda run -n rag-local ruff format .
conda run -n rag-local ruff check .
```

两条都必须干净退出。**这一步会触碰 24 个文件，单独提交**，不要和逻辑改动混在一起。

- [x] **Step 3: 把 ruff 加进 pre-commit**

`.pre-commit-config.yaml`：

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
      - id: check-json
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: mixed-line-ending
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

```bash
conda run -n rag-local pre-commit install
conda run -n rag-local pre-commit run --all-files
```

- [x] **Step 4: 提交**

```bash
git add app/agents/router/routing.py
git commit -m "style: fix the two UP038 lint errors"
git add -A
git commit -m "style: apply ruff format across the tree"
git add .pre-commit-config.yaml
git commit -m "build: run ruff and ruff-format in pre-commit"
```

---

### Task 22: 增加 CI

> **执行记录（2026-08-29）**：三处偏离，均已在 CI 文件内注释说明。
> 1. **加了 `npm run type-check`**（计划里没有）——本地验证干净，值得设为门禁。
> 2. **没有加 `npm run lint`**——干净检出下报 **151 errors / 29 warnings**，绝大多数是 `Blob`/`URL` 等浏览器全局的 `no-undef`，属 ESLint env 配置不全。开箱即红的门禁只会训练所有人忽略 CI，这应当作为独立的前端任务处理。
> 3. **`asyncio_mode` 用 `strict` 而非计划里的 `auto`**——现有测试全部显式带 `@pytest.mark.asyncio`，`auto` 会改变既有行为；`strict` 保持现状且同样满足 CI 需要。
> CI 的每一步都已在本地按 YAML 折叠后的原样执行验证：ruff 干净、census 151、36 测试绿、type-check 绿、build 绿。

**Files:**
- Create: `.github/workflows/ci.yml`

**Context:** 审计 #28。仓库**完全没有 CI** —— 没有 `.github/` 目录。没有门禁的情况下，Phase 4 的大规模删除风险显著更高，因此这个任务应当在 Phase 4 之前完成。

- [x] **Step 1: 创建 workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install ruff
        run: pip install "ruff>=0.6.0"
      - name: Lint
        run: ruff check .
      - name: Format check
        run: ruff format --check .
      - name: Install package
        run: pip install -e ".[dev]"
      - name: Endpoint census
        run: |
          python - <<'EOF'
          import app.api.main as m
          d = m.app.openapi()["paths"]
          n = sum(1 for i in d.values() for k in i if k in {"get","post","put","patch","delete"})
          print(f"{n} operations")
          assert n >= 140, f"endpoint count collapsed to {n}"
          EOF
      - name: Tests
        run: pytest tests/ -q

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run build
```

**注意**：`Endpoint census` 这一步会加载全部路由模块（本地实测约 31 秒），但不会触发 lifespan 的模型预热（那只在 uvicorn 启动时发生）。用 OpenAPI 操作数而非 `len(app.routes)`，因为后者随 FastAPI 版本变化（见 Global Constraints）。若该步骤因缺少可选 extra 而失败，退化为只导入 `app.api.application.router_registry` 并断言 `ROUTER_MODULES` 非空。

- [x] **Step 2: 恢复 pytest 配置**

`pyproject.toml` 的 pytest/coverage 配置已于 2026-08-28 移除。加回最小配置，使 `pytest tests/ -q` 在 CI 中能正确发现异步测试：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [x] **Step 3: 验证并提交**

```bash
conda run -n rag-local python -m pytest tests/ -q
git add .github/workflows/ci.yml pyproject.toml
git commit -m "build: add CI running ruff, an import check, tests, and the frontend build"
```

---

### Task 23: 修正 CLAUDE.md 与 Makefile

**Files:**
- Modify: `CLAUDE.md`
- Modify: `Makefile`

**Context:** 审计 #27/#30/#31/#32 与全部文档漂移项。

- [ ] **Step 1: 修正 SSE 描述**

`## Important Notes` 中：

```markdown
- **SSE streaming**: Real-time status updates use Server-Sent Events (see `app/api/routes/enhanced_query.py`)
```

`enhanced_query.py` 已于 2026-08-29 删除。改为：

```markdown
- **SSE streaming**: Execution-trace events are served by
  `app/api/routes/public/orchestration.py`
  (`GET /api/v1/orchestration/executions/{execution_id}/events`). The query endpoint
  returns `metadata.execution_id`, which the client uses to subscribe. The stream
  replays a finished run's stage events; it is not a token-level answer stream.
```

- [ ] **Step 2: 修正数据库描述**

```markdown
**Database**: SQLite (default, `DATABASE_URL`), with PostgreSQL (`asyncpg`) supported for production
```

改为：

```markdown
**Database**: SQLite only. Every store opens its own `sqlite3` connection
(`app/services/auth/auth_service.py`, `app/services/sessions/history.py`,
`app/services/sessions/metadata_db.py`, `app/services/prompts/store.py`,
`app/wiki/store.py`, `app/retrievers/stores/vector.py`). There is no shared
connection pool and no PostgreSQL support; an unused async SQLAlchemy pool was
removed on 2026-08-29.
```

- [ ] **Step 3: 修正安全描述**

把 `Safety checks` 一条改为准确描述两条独立路径：

```markdown
4. **Safety checks**: Two independent redaction paths.
   `app/services/answer_safety.py` runs on every finalized answer and covers
   OpenAI-style keys, AWS access key ids, private-key headers, and
   `password=`/`token=` assignments; it is gated by `ANSWER_SAFETY_SCAN_ENABLED`.
   `app/agents/validation/rules.py` additionally matches SSN, credit-card,
   email, and phone patterns, and runs inside the validation cascade reached
   through the verifier. There is no content-moderation/toxicity filter and no
   bias-detection implementation.
```

- [ ] **Step 4: 修正检索与路由描述**

- **Dynamic Top-K**：明确说明主检索路径硬编码 `top_k=6`（`app/agents/rag/service.py`），`app/retrievers/hybrid/adaptive_params.py` 只在 `candidate_collection.py` 内生效，因此 `DYNAMIC_RETRIEVAL_ENABLED` 与 `DYNAMIC_*_CAP` 对默认聊天路径无影响。
- **Graph retrieval**：记录 Task 4 的修复——`graph` 与 `hybrid` 两个路由都会查询知识图谱。

- [ ] **Step 5: 记录休眠功能**

在 `## Quality Assurance` 下新增一段，把 Scope 中"明确不在范围内"的项写成显式的已知状态，避免下一次审计再次把它们当成 bug：

```markdown
**Dormant by design (2026-08-29)**: the following exist and are tested but are
switched off on the live request path. Turning any of them on is a cost/latency
decision, not a bug fix.
- Fact verification and self-review: `app/agents/synthesizer/service.py` calls
  `synthesize_answer(..., enable_fact_verification=False, enable_self_review=False)`.
- `KnowledgeOrchestrator` as the top-level retrieval assembler:
  `KNOWLEDGE_ORCHESTRATOR_ENABLED` defaults to false; retrieval instead goes
  through `RAGAgentService`, which delegates to the same orchestrator internally.
- Router confidence calibration: `ENABLE_CALIBRATION` defaults to false, so
  `config/router_calibration.json` is not read.
```

- [ ] **Step 6: 修正 Makefile 与 conda 约定的冲突**

`make install` 用 `python -m venv .venv`，与 CLAUDE.md 强制的 conda `rag-local` 矛盾（只有 `config-check`/`config-render` 用了 `conda run`）。二选一，建议统一到 conda：

```makefile
install:
	conda run -n rag-local pip install -e ".[dev]"

api:
	conda run -n rag-local uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "artifacts/*" --reload-exclude "frontend/*"
```

- [ ] **Step 7: 记录 `.runtime/` 必须先渲染**

`.runtime/` 当前为空，`resolve_runtime_env_file()` 因此返回 `None`，运行实例跑在全部 261 个（清理后约 228 个）硬编码默认值上。在 `### Runtime config` 段落中加一句：

```markdown
`.runtime/` starts empty. Until `make config-render ENV=development` is run,
`Settings` falls back to its hardcoded defaults for every field — including
`MODEL_BACKEND=local`. Run the render step (or export real environment
variables) before treating any configured value as active.
```

- [ ] **Step 8: 加一条日期注记**

在现有的 `Note (2026-08-29): A backend agent audit found...` 之后追加：

```markdown
Note (2026-08-29, second pass): A full-backend audit found the chat path was not
persisting messages, conversation context was filled but never read, the query
endpoint never returned its execution_id, the `graph` route never queried the
graph, and ~13k lines across 184 modules had zero importers. See
`docs/superpowers/plans/2026-08-29-backend-full-audit-remediation.md` for the
remediation plan and what was deliberately left dormant.
```

- [ ] **Step 9: 提交**

```bash
git add CLAUDE.md Makefile
git commit -m "docs: correct CLAUDE.md and Makefile against the 2026-08-29 full backend audit"
```

### Phase 5 验收

- [x] `ruff check .` 与 `ruff format --check .` 均干净退出。
- [~] `pre-commit run --all-files` 通过。  ← **待人工执行**（pre-commit 未安装）
- [~] CI 在一个测试 PR 上全绿。  ← **待人工验证**（需要推送到 GitHub）
- [ ] CLAUDE.md 中不再有指向已删除文件的引用（`grep -oE '\bapp/[a-z_/]+\.py' CLAUDE.md | sort -u | while read f; do test -f "$f" || echo "MISSING: $f"; done` 无输出）。

---

## Self-Review

**Spec coverage** —— 审计报告的 32 项发现全部有归属：

| 审计项 | 任务 |
|---|---|
| #1 聊天不落库 | Task 1 + Task 2 |
| #2 多轮上下文断链 | Task 1 + Task 3 |
| #3 execution_id 不返回 | Task 1 + Task 2 |
| #4 graph 路由不查图 | Task 4 |
| #5 澄清触发即 500 | Task 5 |
| #6 澄清只有中文 | Task 5 |
| #7 检索器 monkeypatch 竞态 | Task 6 |
| #8 负载守卫阻塞事件循环 | Task 7 |
| #9 同步 Redis 在 async 中间件 | Task 8 |
| #10 每请求重建 LangGraph | Task 9 |
| #11 benchmark 同步跑满分钟 | Task 10 |
| #12 33 个无读取方配置 | Task 11 |
| #13 连接池不读配置 / PostgreSQL 假支持 | Task 13 + Task 23 Step 2 |
| #14 /ready 假健康 / 串行 / 未鉴权 | Task 12 |
| #15 QueryResultCache 无写入方 | Task 16 + Task 19 |
| #16 profile 死配置 | Task 15 |
| #17 PII 模式与文档不符 | Task 14 + Task 23 Step 3 |
| #18 184 模块零引用 | Task 16 / 17 / 18 / 19 |
| #19 prompts 包死掉 | Task 18 |
| #20 78 个 alias shim | Task 17 |
| #21 .original 备份入库 | Task 16 |
| #22 空包与重名模块 | Task 19 Step 3 + Task 17 |
| #23 生产路由在 compatibility/ | Task 20 |
| #24 事实核查硬编码关闭 | Task 23 Step 5（记录为休眠，不启用） |
| #25 finalization 第二条验证路径不可达 | Task 19（随 `app/orchestration/` 清理复核） |
| #26 检索退化策略只用 1/3 | Task 19（删除未实例化的两个策略类） |
| #27 image_processor 硬编码过期模型 | 见下方"已知遗留" |
| #28 无 CI | Task 22 |
| #29 ruff 当前失败 | Task 21 |
| #30 .runtime/ 为空 | Task 23 Step 7 |
| #31 Makefile 与 conda 冲突 | Task 23 Step 6 |
| #32 admin benchmark 阻塞 | Task 10 |

**已知遗留（本计划有意未覆盖）** —— #27 `app/services/multimodal/image_processor.py:276` 硬编码 `model="claude-3-haiku-20240307"`，绕过 `settings.anthropic_chat_model` 与统一的 model runtime / 出站脱敏层。修它需要先确定该走 `get_chat_model()` 的哪条视觉分支，涉及 `app/services/models/runtime.py` 的多模态支持现状，超出"局部修复"的范畴。建议作为独立任务处理，并在 Task 23 中一并记录。

**Placeholder scan** —— 无 "TBD" / "补充错误处理" / 未展示的代码。每处修改都给出了确切的前后文本；每个删除任务都以一条可执行的复核 grep 开始；三处需要先读现有签名再落笔的地方（`parent_expansion.expand_to_parent_context`、`chat_credit_reservation.__exit__`、`BackgroundTaskQueue.submit`）都写明了要跑哪条命令确认，而不是假设签名。

**Type consistency** —— 新增的公开接口只有四个，且都保持默认值向后兼容：`collect_candidates(*, rewrite_fn=None, vector_fn=None, bm25_fn=None)`、`question_for(intent, field_name, language="zh")`、`QueryLoadGuard.acquire_async(user_key)`（与同步 `acquire` 同签名同语义）、`AdvancedRAGRequest.session_id: str | None = None`。`_render_conversation` 与 `_response_metadata` / `_persist_exchange` 均为模块私有。没有引入新的 domain 类型，`app/domain/` 的契约完全未变。

**风险排序** —— Task 6（monkeypatch 移除）与 Task 17（拆兼容层）是本计划风险最高的两项：前者改的是活的检索路径，后者一次性触碰全仓库的 import。两者都应在 Task 22 的 CI 就绪之后执行，并各自独立成一个 PR。
