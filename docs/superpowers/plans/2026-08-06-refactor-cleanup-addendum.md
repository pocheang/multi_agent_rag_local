# Refactor Cleanup Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“完整重构后不保留无必要代码”变为可验证的交付门禁，而不是主观约定。

**Architecture:** 所有删除先由静态清单和生产引用搜索证明候选项可替代，再由契约、集成和构建测试证明行为不变。短期兼容代码只允许作为有截止版本的 allowlist 项存在，观察期结束后必须删除。

**Tech Stack:** Python 3.11、pytest、ruff、TypeScript、Vite、PowerShell、Git。

## Global Constraints

- 禁止保留重复 Agent、永久 feature flag、死导入、注释代码、无生产引用的配置、过期测试夹具、过期部署项和过期文档。
- 任何删除前必须记录替代物、静态引用证据、测试命令、观察期和删除提交。
- 重构结束后，每个公开能力只能存在一个生产实现；兼容层只允许是带截止版本的薄适配器。
- 生产文件通常不超过约 300 行；拆分按职责边界进行，不能只移动代码来规避行数。

---

### Task 1: 创建全仓库清单和临时兼容代码登记册

**Files:**
- Create: `scripts/inventory_refactor_targets.py`
- Create: `config/refactor_cleanup_allowlist.json`
- Create: `docs/development/refactor-removal-register.md`
- Modify: `Makefile`
- Test: `tests/scripts/test_inventory_refactor_targets.py`

**Interfaces:**
- Produces: `collect_inventory(repo: Path, allowlist: set[str]) -> dict[str, list[str]]`.
- Consumed by: 每个 Agent、API、MCP、前端和部署删除任务。

- [ ] **Step 1: 写出未引用旧模块没有 allowlist 时被报告的测试。**

```python
def test_inventory_reports_unreferenced_legacy_module(tmp_path: Path) -> None:
    report = collect_inventory(tmp_path, allowlist=set())
    assert "app/legacy/unused.py" in report["unreferenced_modules"]
```

- [ ] **Step 2: 运行测试确认失败。**

Run: `conda run -n rag-local pytest tests/scripts/test_inventory_refactor_targets.py -v`

Expected: FAIL because `collect_inventory` does not exist.

- [ ] **Step 3: 实现扫描和过期 allowlist 门禁。**

```python
def collect_inventory(repo: Path, allowlist: set[str]) -> dict[str, list[str]]:
    modules = find_python_and_typescript_modules(repo)
    unused = [path for path in modules if path not in allowlist and not has_repo_reference(path, repo)]
    return {"unreferenced_modules": sorted(unused)}
```

每个 allowlist 条目必须包含 `owner`、`replacement`、`remove_when` 和 `expires_in_release`；缺少字段或版本已过期时命令返回非零状态。`Makefile` 增加 `refactor-inventory` 目标。

- [ ] **Step 4: 运行测试与仓库扫描。**

Run: `conda run -n rag-local pytest tests/scripts/test_inventory_refactor_targets.py -v; conda run -n rag-local python scripts/inventory_refactor_targets.py --json audit_output/refactor-inventory.json`

Expected: PASS; 清单只报告候选项，不自动删除文件。

- [ ] **Step 5: 提交本任务。**

```bash
git add scripts/inventory_refactor_targets.py config/refactor_cleanup_allowlist.json docs/development/refactor-removal-register.md Makefile tests/scripts/test_inventory_refactor_targets.py
git commit -m "chore: add refactor cleanup inventory gate"
```

### Task 2: 按领域边界拆分超大生产文件

**Files:**
- Modify: `app/api/routes/query.py`
- Modify: `app/agents/enhanced_rag_workflow.py`
- Modify: `app/core/models.py`
- Modify: `app/graph/streaming/stream_processor.py`
- Create: `app/api/routes/query_request.py`
- Create: `app/api/routes/query_response.py`
- Create: `app/api/routes/query_stream.py`
- Create: `app/agents/validation/rules.py`
- Create: `app/agents/validation/citations.py`
- Create: `app/agents/validation/nli.py`
- Test: `tests/api/test_query_profile_compatibility.py`
- Test: `tests/agents/test_validation_cascade.py`

**Interfaces:**
- Consumes: 现有公开 API Schema 和新编排契约。
- Produces: 不改变公开 API 的小型路由处理器和拆分后的验证策略模块。

- [ ] **Step 1: 写出旧路由与拆分后路由返回同一响应 Schema 的测试。**

```python
def test_query_response_contract_is_stable(client) -> None:
    response = client.post("/api/v1/query", json={"question": "test"})
    assert {"answer", "citations", "route"} <= response.json().keys()
```

- [ ] **Step 2: 运行测试确认现有契约。**

Run: `conda run -n rag-local pytest tests/api/test_query_profile_compatibility.py -v`

Expected: PASS before the split; save the response shape as the refactor contract.

- [ ] **Step 3: 逐个提取单一职责模块。**

```python
# query.py only registers routes
router.post("/query")(execute_query)
router.post("/query/stream")(stream_query)
```

提取后 `query.py` 仅保留 router 装配；请求转换进入 `query_request.py`，结果转换进入 `query_response.py`，SSE 进入 `query_stream.py`。验证逻辑按规则、引用和 NLI 拆分，调用入口保持一个 `ValidationCascade.validate(...)`。

- [ ] **Step 4: 运行契约、Agent 与静态检查。**

Run: `conda run -n rag-local pytest tests/api/test_query_profile_compatibility.py tests/agents/test_validation_cascade.py -v; conda run -n rag-local ruff check app tests`

Expected: PASS; 被拆分文件不再包含已迁走实现。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/api/routes app/agents/validation app/agents/enhanced_rag_workflow.py app/core/models.py app/graph/streaming tests/api tests/agents
git commit -m "refactor: split query and validation responsibilities"
```

### Task 3: 删除已经被统一编排器取代的旧路径

**Files:**
- Modify: `app/pipeline/rag_pipeline.py`
- Modify: `app/pipeline/adapters.py`
- Modify: `app/api/routes/query.py`
- Modify: `app/api/routes/enhanced_query.py`
- Modify: `app/api/routes/advanced_rag.py`
- Delete: 仅在引用搜索、影子观察和回归均通过后确认无生产导入的 legacy adapter 文件
- Test: `tests/pipeline/test_rag_pipeline_orchestration.py`
- Test: `tests/api/test_query_profile_compatibility.py`

**Interfaces:**
- Consumes: 新 `OrchestrationEngine` 和影子流量比较报告。
- Produces: 所有公开入口仅通过一个 `RAGPipeline → OrchestrationEngine` 路径。

- [ ] **Step 1: 写出所有公开 endpoint 只调用管道入口的测试。**

```python
def test_query_routes_delegate_to_rag_pipeline(source: str) -> None:
    assert "RAGPipeline" in source
    assert "run_query(" not in source
```

- [ ] **Step 2: 运行测试确认旧直接调用被检出。**

Run: `conda run -n rag-local pytest tests/api/test_query_profile_compatibility.py::test_query_routes_delegate_to_rag_pipeline -v`

Expected: FAIL until each endpoint no longer直接调用 legacy workflow.

- [ ] **Step 3: 删除而非注释旧路径。**

```bash
rg -n "EnhancedRAGWorkflow|AdvancedRAGWorkflow|run_query\(" app tests
```

对每个候选：在登记册记录替代实现与观察期，删除文件或分支，执行上述引用搜索，确保只剩迁移 allowlist 中的临时适配器。不得用注释或永久 feature flag 保存旧实现。

- [ ] **Step 4: 运行 API、管道、全量测试与构建。**

Run: `conda run -n rag-local pytest tests/pipeline tests/api -v; conda run -n rag-local pytest -q; cd frontend; npm run build`

Expected: PASS; 影子比较在观察期内无阻断差异，删除后不再有对应生产导入。

- [ ] **Step 5: 提交本任务。**

```bash
git add app/pipeline app/api tests/pipeline tests/api docs/development/refactor-removal-register.md
git add -u
git commit -m "refactor: remove superseded RAG execution paths"
```

### Task 4: 清理前端、配置、部署与文档中的遗留内容

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/chat/hooks/useMessageActions.ts`
- Modify: `frontend/src/pages/chat/hooks/streamEventHandlers.ts`
- Modify: `config/router_calibration.json`
- Modify: `config/retrieval_config.json`
- Modify: `deploy/compose/compose.yaml`
- Modify: `docs/development/mcp.md`
- Modify: `README.md`
- Delete: 已由 `features/execution-trace`、`features/integrations` 和统一 API 替代的前端组件、环境键和部署项
- Test: `tests/test_config_generation.py`
- Test: `frontend/scripts/webapp-smoke.mjs`

**Interfaces:**
- Consumes: 最终 API/SSE 事件和 Gateway 配置。
- Produces: 不引用旧事件名称、旧 Profile 选择器或旧环境变量的网页、配置、部署与文档。

- [ ] **Step 1: 写出配置不含废弃键、前端不含旧事件分支的测试。**

```python
def test_runtime_config_has_no_legacy_workflow_keys(settings) -> None:
    assert "ENABLE_LEGACY_ADVANCED_WORKFLOW" not in settings.model_dump()
```

```javascript
test("compiled web app has no legacy event names", () => {
  expect(bundleText).not.toContain("vector_result");
});
```

- [ ] **Step 2: 运行测试确认当前遗留项被发现。**

Run: `conda run -n rag-local pytest tests/test_config_generation.py -v; node frontend/scripts/webapp-smoke.mjs`

Expected: FAIL until old keys and event handlers are removed or migrated.

- [ ] **Step 3: 删除遗留状态与文档，保留一份迁移说明。**

```typescript
const nextState = reduceExecutionEvent(state, event); // only versioned ExecutionEvent types
```

删除旧状态和已废弃 Profile UI；配置只保留新编排开关与有过期日期的 rollout 开关；部署只暴露 FastAPI 与受控 MCP Gateway；README 和 MCP 文档只描述最终架构及迁移版本。

- [ ] **Step 4: 运行配置、网页 smoke、构建和文档检查。**

Run: `conda run -n rag-local pytest tests/test_config_generation.py -v; node frontend/scripts/webapp-smoke.mjs; cd frontend; npm run build; conda run -n rag-local python scripts/check_docs.py`

Expected: PASS; 搜索结果中没有被删除功能的用户文档或环境变量。

- [ ] **Step 5: 提交本任务。**

```bash
git add frontend/src config deploy docs README.md tests frontend/scripts
git add -u
git commit -m "chore: remove obsolete frontend config and deployment paths"
```

## 完成门禁

执行 `make refactor-inventory`、`conda run -n rag-local pytest -q`、`conda run -n rag-local ruff check .` 与 `cd frontend; npm run build`。只有四项通过、登记册无过期项、生产引用搜索无旧路径且质量门禁达标时，重构才可宣告完成。
