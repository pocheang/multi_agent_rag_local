# Full Project Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成前端、后端、Agent、检索和 Web MCP 的整体重构，并在稳定后删除所有被替代的实现。

**Architecture:** `RAGPipeline` 是唯一生产入口，调用 Router → Planner → RAG → Tool → Synthesizer。浏览器只与 FastAPI REST/SSE 通信；后端通过 Streamable HTTP MCP Gateway 调用内置能力和第三方连接器。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、LangGraph、FastMCP、React、TypeScript、Ant Design、pytest、ruff、Vite。

## Global Constraints

- 跨层只传递不可变 Pydantic 契约，禁止新增无约束共享字典。
- 生产文件单一职责，通常不超过 300 行；API、策略、适配器和 UI 组件按职责拆分。
- 新路径稳定后必须删除旧路径：禁止永久双实现、死代码、注释代码、永久 feature flag 和无引用配置。
- 网页不直接访问 MCP 或密钥；MCP 写工具必须拥有 scope 和一次性网页审批令牌；`dev_*` 首期只读。
- 每个任务均按失败测试 → 最小实现 → 回归验证 → 独立提交执行。

---

### Task 0: 代码清单与删除门禁

**Files:** Create `scripts/inventory_refactor_targets.py`, `config/refactor_cleanup_allowlist.json`, `docs/development/refactor-removal-register.md`; modify `Makefile`; test `tests/scripts/test_inventory_refactor_targets.py`.

**Produces:** `collect_inventory(repo: Path, allowlist: set[str]) -> dict[str, list[str]]` 和 `make refactor-inventory`。

- [ ] 写失败测试：未引用 `app/legacy/unused.py` 必须出现在 `unreferenced_modules`。
- [ ] 运行 `conda run -n rag-local pytest tests/scripts/test_inventory_refactor_targets.py -v`，确认 `collect_inventory` 尚不存在。
- [ ] 实现模块/导入/超大文件/过期 allowlist 扫描；allowlist 必须包含 `owner`、`replacement`、`remove_when`、`expires_in_release`。
- [ ] 运行测试和 `conda run -n rag-local python scripts/inventory_refactor_targets.py --json audit_output/refactor-inventory.json`。
- [ ] 提交：`git add scripts config/refactor_cleanup_allowlist.json docs/development/refactor-removal-register.md Makefile tests/scripts && git commit -m "chore: add refactor cleanup gate"`。

### Task 1: 领域契约与统一编排

**Files:** Create `app/domain/{contracts,events,errors}.py`, `app/orchestration/{request,engine,policies,event_publisher}.py`; modify `app/pipeline/rag_pipeline.py`; test `tests/domain/test_contracts.py`, `tests/orchestration/test_engine.py`。

**Produces:** `RouteDecision`, `TaskPlan`, `EvidenceBundle`, `ToolResult`, `FinalAnswer`, `ExecutionEvent` 和 `OrchestrationEngine.execute()`。

- [ ] 写失败测试：空来源 `EvidenceItem` 抛出 `ValidationError`；简单问题不 await Planner/Tool。
- [ ] 运行 `conda run -n rag-local pytest tests/domain tests/orchestration -v`，确认模块缺失。
- [ ] 实现 frozen Pydantic 模型与 `route → optional plan → rag → optional tool → synthesize` 编排；`RAGPipeline` 委托 Engine。
- [ ] 运行 `conda run -n rag-local pytest tests/domain tests/orchestration tests/pipeline -v`。
- [ ] 提交：`git add app/domain app/orchestration app/pipeline tests/domain tests/orchestration tests/pipeline && git commit -m "feat: add unified RAG orchestration"`。

### Task 2: Agent、检索与答案适配器

**Files:** Create `app/agents/{router,planner,rag,tool,synthesizer}/service.py`, `app/agents/rag/fusion.py`; modify `app/pipeline/adapters.py`; test `tests/agents/rag/test_fusion.py`。

**Produces:** 并发 Vector/BM25/Graph/Web 检索后的 `EvidenceBundle`，以及带引用的 `FinalAnswer`。

- [ ] 写失败测试：同文档同页的重复证据只保留最高分，且来源和引用不丢失。
- [ ] 运行 `conda run -n rag-local pytest tests/agents/rag/test_fusion.py -v`，确认 `fuse_evidence` 缺失。
- [ ] 用 `asyncio.gather` 执行受 Route/Plan 允许的检索器，归一化、融合、重排；失败转为降级事件。
- [ ] 运行 `conda run -n rag-local pytest tests/agents tests/retrievers tests/test_citation_grounding.py -v`。
- [ ] 提交：`git add app/agents app/pipeline/adapters.py tests/agents tests/retrievers && git commit -m "feat: adapt agents to typed orchestration"`。

### Task 3: MCP Gateway 与第三方连接器

**Files:** Create `app/mcp/{gateway,registry,contracts,authorization,approvals,audit}.py`, `app/mcp/connectors/{base,rest}.py`, `app/services/connectors/{repository,service}.py`; modify `app/mcp/server.py`; test `tests/mcp/test_approvals.py`。

**Produces:** `ToolRegistry.invoke(call, actor) -> ToolResult`、加密连接器凭据和 Streamable HTTP `querymind_mcp`。

- [ ] 写失败测试：未审批的 write call 返回 `approval_required` 且 connector 未执行。
- [ ] 运行 `conda run -n rag-local pytest tests/mcp/test_approvals.py -v`，确认 Registry 缺失。
- [ ] 实现 Pydantic Schema、scope、脱敏凭据、URL allowlist、审批令牌和审计；保留 RAG 为只读 `querymind_rag_*` 工具。
- [ ] 运行 `conda run -n rag-local pytest tests/mcp tests/services/connectors tests/security -v`。
- [ ] 提交：`git add app/mcp app/services/connectors tests/mcp tests/services/connectors tests/security && git commit -m "feat: add governed MCP gateway"`。

### Task 4: API/SSE 与网页功能重构

**Files:** Create `app/api/routes/{orchestration,connectors}.py`, `frontend/src/features/{execution-trace,integrations,tool-approval}/`; modify `app/api/routes/enhanced_query.py`, `frontend/src/App.tsx`, chat hooks; test `tests/api/test_orchestration_stream.py`。

**Produces:** 版本化执行事件、执行追踪、连接器管理和高风险工具确认界面。

- [ ] 写失败测试：`tool_approval` 事件进入前端状态，未知事件不改变状态。
- [ ] 运行前端对应测试，若无 Vitest 先添加 `test` 脚本和配置。
- [ ] SSE 只序列化 `ExecutionEvent`；页面不显示密钥、不拼 MCP 请求，确认后调用审批 API。
- [ ] 运行 `conda run -n rag-local pytest tests/api -v; cd frontend; npm run build`。
- [ ] 提交：`git add app/api frontend/src tests/api frontend/package.json && git commit -m "feat: add execution trace and connector UI"`。

### Task 5: 拆分超大文件并清理旧前后端逻辑

**Files:** Split `app/api/routes/query.py` into `query_request.py`, `query_response.py`, `query_stream.py`; split validation into `app/agents/validation/{rules,citations,nli}.py`; delete superseded frontend/event/config modules.

**Produces:** 只有 router 装配留在 `query.py`，只有 `ValidationCascade.validate()` 作为验证入口，前端只消费版本化事件。

- [ ] 写 API 响应契约测试，断言 `answer`、`citations`、`route` 始终存在。
- [ ] 运行契约测试保存基线：`conda run -n rag-local pytest tests/api/test_query_profile_compatibility.py -v`。
- [ ] 迁移代码后立即删除已移动实现，不能复制保留；在删除登记册记录替代物和观察期。
- [ ] 运行 `conda run -n rag-local pytest tests/api tests/agents -v; conda run -n rag-local ruff check app tests`。
- [ ] 提交：`git add app tests docs/development/refactor-removal-register.md && git add -u && git commit -m "refactor: split responsibilities and remove old code"`。

### Task 6: 影子迁移、全面下线与发布验收

**Files:** Create `app/orchestration/shadow.py`, `config/orchestration_rollout.json`, `scripts/compare_orchestration_results.py`; modify all query routes and documentation; delete无生产引用的 legacy adapters。

**Produces:** 所有 endpoint 唯一走 `RAGPipeline → OrchestrationEngine`，且旧实现不再保留。

- [ ] 写失败测试：shadow 模式返回 primary 答案但记录 candidate 差异；路由源代码不再直接调用 `run_query`。
- [ ] 运行 `conda run -n rag-local pytest tests/orchestration/test_shadow.py tests/api/test_query_profile_compatibility.py -v`。
- [ ] 按 rollout 配置实施 shadow → new；观察期结束后，对每个 legacy adapter 运行 `rg -n "<adapter_name>" app tests`，无生产导入才删除。
- [ ] 运行 `make refactor-inventory; conda run -n rag-local pytest -q; conda run -n rag-local ruff check .; cd frontend; npm run build`，再运行既有 retrieval quality gate。
- [ ] 提交：`git add app config scripts docs tests frontend && git add -u && git commit -m "refactor: complete unified RAG migration"`。

## Completion Gate

仅当清单无过期 allowlist、旧路径无生产引用、全量测试/ruff/前端构建/检索质量门禁通过，且不存在多余代码、配置、文档和部署项时，本重构才算完成。
