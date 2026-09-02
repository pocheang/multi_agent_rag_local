# 前端审计修复计划（2026-08-29）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本文档为跨会话交接件，自包含。** 执行者无需阅读任何历史对话——所需的背景、基线数字、审计脚本、环境坑与待决策项全部写在下面。

**Goal:** 修复 2026-08-29 后端全量审计修复在前端留下的缺口，以及前端自身的问题：执行追踪链路未接通、SSE 事件词表不匹配、37 个未定义的 i18n 键、878 行零引用模块，并让 `npm run lint` 具备进入 CI 的条件。

**Architecture:** 不改前端架构。React 18 + TypeScript + Vite + Zustand + i18next 保持不变，路由与页面结构不变。Task 2 是唯一涉及后端的任务，其余全部限于 `frontend/`。

**Tech Stack:** React 18 / TypeScript / Vite / i18next / ESLint 9 flat config。后端侧仅触碰 `app/orchestration/event_publisher.py`、`app/pipeline/rag_pipeline.py`、`app/orchestration/execution_events.py`。

---

## 交接背景：这之前发生了什么

2026-08-29 完成了一轮**后端全量审计与修复**，计划见
[`2026-08-29-backend-full-audit-remediation.md`](2026-08-29-backend-full-audit-remediation.md)，23 个任务 / 33 个提交
（`9646ab65..162ac5a8`）。与本计划相关的结论：

- 后端删除了 184 个零引用模块（约 13,000 行）、45 个无读取方的配置字段、3 个端点
  （`/optimization/database/{stats,optimize,slow-queries}`），并新增 1 个（`/ready/dependencies`）。
- **主聊天端点 `POST /api/advanced-rag/query` 现在接受 `session_id`，并在 `metadata` 中返回
  `execution_id` 与 `session_id`。** 前端已相应改造（传 `sessionId`、消费 `executionId`、每轮
  `refreshSessions` 对账）。
- `POST /admin/ops/benchmark/run` 与 `/replay/run` 改为返回 **202**，任务转入后台队列。
- 路由做过一次搬迁：`app/api/routes/compatibility/` 拆为 `public/query.py`、
  `public/orchestration.py`、`internal/pipeline_contract.py`。**所有 HTTP 路径未变。**

随后对前端做了一轮对照审计，产出即本计划。

### 已核实无需处理的部分

| 检查项 | 结果 |
|---|---|
| 前端调用指向已删端点 | **0 个**。`/optimization/database/*` 与 `/ready` 前端从未使用 |
| 端点路径匹配 | **61/61** 命中后端 OpenAPI |
| en/zh 键集差异 | **0**（各 1045 个键） |
| `tsc -b --noEmit` | 干净 |

**后端的删除动作没有打断任何前端调用。** 问题在别处，见下文任务。

### 起始基线（执行前请先确认没有漂移）

| 指标 | 值 |
|---|---|
| git HEAD | `3b2f89c8`（本计划自身的提交之前） |
| 后端端点数（OpenAPI 操作） | 149 |
| 后端测试 | 56 passed |
| 前端模块数 | 188 |
| 前端零引用模块 | 20（878 行） |
| i18n 键数 | en 1045 / zh 1045 |
| i18n 引用但未定义 | 37 |
| i18n 定义但未引用 | 189 |
| `npm run lint` | 151 errors / 29 warnings |

---

## ⚠️ 执行前需要人类决策的两件事

**这两项不确定之前，对应任务不要动手。**

### 决策 1：执行追踪功能——接通还是删除？（影响 Task 2、Task 3）

执行追踪链路当前有三处独立断裂（详见 Task 2 的 Context），结果是 SSE 端点对一次正常聊天
只吐出一个合成的终态事件，前端 `ExecutionTracePanel` 几乎没有内容，`ToolApprovalPanel`
永远不触发。

- **选项 A（推荐）：接通。** 管线已经在 12 个阶段发事件，基础设施齐备，缺的只是一根接线。
  做完前端面板立刻有内容。→ 执行 Task 2 与 Task 3。
- **选项 B：删除整条链路。** 移除 `execution-trace/` 与 `tool-approval/` 前端特性、SSE 端点、
  `ExecutionEventStore`、`AgentExecutionTracker` 的 step API，以及后端返回的 `metadata.execution_id`。
  → 跳过 Task 2/3，另开一个删除任务。

### 决策 2：`ForgotPasswordPage.tsx` 保留还是删除？（影响 Task 7）

它出现在零引用清单里（181 行），但**不是残留**——是一个写好了、有完整 i18n
（`pages.forgotPassword.*`）、却从未接进路由的功能。删掉等于放弃找回密码。

本计划默认**删除**。若要保留，从 Task 7 的清单中移除它并单独开任务补路由。

---

## Global Constraints

- 后端命令一律在 conda 环境 `rag-local` 中执行；前端命令在 `frontend/` 目录下执行。
- 每个任务结束前必须通过 `npm run type-check` 与 `npm run build`。
- **不改动任何 HTTP 路径或请求/响应字段名**，除非任务明确要求。前端 61 个端点调用当前
  100% 命中后端 OpenAPI，这个状态必须保持（用 `scripts/audit/frontend_audit.py` 验证）。
- i18n 修改必须同时更新 `en.json` 与 `zh.json`，且保持两者键集完全一致。
- 每个删除任务以一次验证性检查开始，**不要直接照抄本文档的清单**——代码可能已变化。
- 每个任务单独提交。

---

## 环境须知（踩过的坑，避免重复）

1. **`conda run` 对多行 `-c` 会失败**，且会弹出 conda 的错误上报提示。两个可用写法：
   ```bash
   conda run --no-capture-output -n rag-local python -m pytest -q     # 加 --no-capture-output
   /c/Users/pocheang/anaconda3/envs/rag-local/python.exe script.py     # 或直接用解释器路径
   ```
   多行 Python 用 stdin heredoc（`python - <<'PY' ... PY`）而不是 `-c`。

2. **不要用 `len(app.routes)` 数端点。** 本机 rag-local 装的是 FastAPI 0.138.2，`include_router`
   在 `app.routes` 里只留一个 `_IncludedRouter` 包装对象，得到 30；旧版本得 156。用 OpenAPI 操作数：
   ```bash
   conda run --no-capture-output -n rag-local python -c "import app.api.main as m; d=m.app.openapi()['paths']; print(sum(1 for i in d.values() for k in i if k in {'get','post','put','patch','delete'}))"
   ```

3. **输出中文需要 `PYTHONIOENCODING=utf-8`**，否则 Windows 控制台的 cp1252 会抛 `UnicodeEncodeError`。

4. **pytest 的 `tmp_path` 在本机不可用**：`C:\Users\...\Temp\pytest-of-pocheang` 目录 ACL 拒绝写入
   （`WinError 5`）。需要临时目录时用 `tempfile.mkdtemp()`，参见
   `tests/api/test_advanced_rag_roundtrip.py` 的 `history` fixture。

5. **超长内容不要用 Bash heredoc 写文件**，引号解析会失败。用编辑器工具或分段写入。

---

## Scope

| Phase | 主题 | 任务 |
|---|---|---|
| 1 | ESLint 门禁（先做，为后续改动兜底） | Task 1 |
| 2 | 与后端改动相关的缺口 | Task 2–4 |
| 3 | i18n 修复 | Task 5–6 |
| 4 | 死代码清理 | Task 7 |

### 明确不在范围内

1. **补一个 replay 触发 UI**——后端 `POST /admin/ops/replay/run` 已改为 202 后台任务，但前端
   从来没有调用方。要不要在管理台加这个入口是产品决策，不是修 bug。
2. **UI/视觉改动**——本计划不碰样式与布局。
3. **前端测试套件**——`frontend/package.json` 有 `test` 脚本但仓库中没有测试文件。重建前端测试
   是独立工作。
4. **29 个 ESLint warning**——Task 1 只把 error 清零。那 29 个是真实的代码风格问题
   （`react-hooks/exhaustive-deps` 6、`no-unused-vars` 6、`no-explicit-any` 3 等），值得单独一轮。

---

## 审计工具

`scripts/audit/frontend_audit.py`（已入库）一次性跑完三项检查：端点 vs OpenAPI、零引用模块、
i18n 键。**每个任务的验证步骤都用它**，不要手写一次性脚本。

```bash
cd <repo root>
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
```

当前输出（起始基线）：

```
[endpoints] 61 referenced, 0 not in backend OpenAPI
[orphans] 188 modules, 20 with no importer (878 lines)
[i18n] en=1045 zh=1045 keys
    referenced: 893   missing: 37   unused: 189
    NOTE: template-literal t(`...`) calls in 6 file(s); review before deleting unused keys
```

三项全部归零时脚本退出码为 0。它也会列出使用了模板字面量 ``t(`...`)`` 的文件——Task 6 删除
未使用键之前**必须**先看这个清单。

---

## File Structure

- Modify: `frontend/eslint.config.js` — 用 `globals.browser` 替换手写清单，为 TS 文件关闭 `no-undef`。
- Modify: `.github/workflows/ci.yml` — 把 `npm run lint` 加为门禁。
- Modify: `app/orchestration/event_publisher.py`、`app/pipeline/rag_pipeline.py`、
  `app/orchestration/execution_events.py` — 接通管线事件（Task 2，唯一的后端改动）。
- Modify: `frontend/src/features/execution-trace/types.ts` — 补齐 stage 词表、放宽字段校验。
- Modify: `frontend/src/features/execution-trace/ExecutionTracePanel.tsx` — 新 stage 的展示标签。
- Modify: `frontend/src/i18n/locales/{en,zh}.json` — 补 37 个缺失键，删未使用键。
- Modify: `frontend/src/pages/admin/AdminSystemMonitor.tsx` — 修正 i18n 命名空间。
- Delete: 20 个零引用模块（878 行）。

---

# Phase 1 — ESLint 门禁

### Task 1: 修复 ESLint 配置并把 lint 加进 CI

**Files:**
- Modify: `frontend/eslint.config.js`
- Modify: `.github/workflows/ci.yml`

**Context:** `npm run lint` 在干净检出下报 **151 errors / 29 warnings**，因此 2026-08-29 加 CI 时
被排除在门禁之外（`ci.yml` 末尾有一段注释说明原因）。归类后：

```
151  no-undef                              <- 全部是浏览器/DOM/TS 全局
 11  react-refresh/only-export-components
  6  react-hooks/exhaustive-deps
  6  @typescript-eslint/no-unused-vars
  3  @typescript-eslint/no-explicit-any
  2  no-console
  1  @typescript-eslint/no-non-null-assertion
```

151 个 `no-undef` 触发在 `HTMLInputElement`(28)、`React`(25)、`HTMLDivElement`(10)、
`AbortSignal`(10)、`URL`(9)、`HTMLElement`(9)、`File`/`Blob`(各 6)、`RequestInit`、`Headers`、
`Response`、`crypto`、`navigator` 等标识符上。**这些全部不是真实缺陷**，而是两个配置问题：

1. `languageOptions.globals` 手写了 14 个全局（`window`、`document`、`fetch`……），漏掉了其余
   749 个浏览器全局。
2. `js.configs.recommended` 的 `no-undef` 对 `.ts/.tsx` 生效。typescript-eslint 官方明确建议在
   TS 文件上关闭该规则——TypeScript 编译器本身就会报未定义标识符，而 `tsc -b --noEmit` 已经是
   干净的且已在 CI 中。

`globals` 包已在 `node_modules` 中可用（763 个 browser 键），**无需新增依赖**。

- [x] **Step 1: 记录当前基线**

```bash
cd frontend && npm run lint 2>&1 | tail -3
```

记下 errors/warnings 数量，Step 3 后用于对比。

- [x] **Step 2: 修配置**

在 `frontend/eslint.config.js` 顶部加入 import：

```javascript
import globals from 'globals';
```

把 `languageOptions.globals` 的手写清单整块替换为：

```javascript
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
```

并在 `rules` 中、`'no-unused-vars': 'off'` 那一行旁边加入：

```javascript
      // TypeScript already reports undefined identifiers, and `tsc -b --noEmit`
      // runs in CI. Leaving no-undef on for .ts/.tsx only produced false
      // positives on DOM and TS lib globals (151 of them).
      'no-undef': 'off',
```

- [x] **Step 3: 确认 error 归零**

```bash
cd frontend && npm run lint 2>&1 | tail -5
```

期望 **0 errors**。剩余约 29 个 warning 保持 warning 级别，本任务不处理（见 Scope 排除项）。

若仍有 error，逐条判断是真实缺陷还是配置问题。**不要用 `eslint-disable` 掩盖真实缺陷。**

- [x] **Step 4: 加进 CI**

在 `.github/workflows/ci.yml` 的 frontend job 中，`Type check` 之前插入：

```yaml
      - name: Lint
        run: npm run lint
```

并删除文件末尾那段说明为什么不做门禁的注释（以
`# \`npm run lint\` is deliberately not a gate yet` 开头的整段）。

- [x] **Step 5: 验证并提交**

```bash
cd frontend && npm run lint && npm run type-check && npm run build && cd ..
git add frontend/eslint.config.js .github/workflows/ci.yml
git commit -m "build(frontend): fix the ESLint globals config and make lint a CI gate"
```

---

# Phase 2 — 与后端改动相关的缺口

### Task 2: 接通执行追踪事件链路

> **⚠️ 需要先完成「决策 1」。** 下面按选项 A（接通）编写。

**Files:**
- Modify: `app/orchestration/event_publisher.py`
- Modify: `app/pipeline/rag_pipeline.py`
- Modify: `app/orchestration/execution_events.py`
- Modify: `app/api/routes/public/query.py`
- Test: `tests/orchestration/test_execution_events_reach_store.py`

**Context:** 后端修复让 `execution_id` 到达了前端，`useExecutionTrace` 因此第一次真正开始订阅
SSE。但订阅到的内容几乎是空的——事件链路有**三处独立断裂**：

1. `RAGPipeline._build_engine`（`app/pipeline/rag_pipeline.py`）构造 `OrchestrationEngine` 时
   不传 `publisher`，于是 `app/orchestration/engine.py` 落到 `NullEventPublisher()`。管线各阶段
   `report_event` 出来的 `ExecutionEvent` 直接被丢弃。
2. `ExecutionEventStore.publish` 全仓库只有一个调用方：`app/mcp/registry.py`（MCP 工具注册表）。
   RAG 管线从不写入这个 store，所以 SSE 端点的 `event_store.events_since(...)` 永远返回空。
3. `AgentExecutionTracker.record_agent_step` **零调用方**（只有 `app/services/__init__.py` 的
   re-export）。所以 `trace.steps` 恒为空，SSE 端点里遍历 steps 的循环一次也不执行。

净效果：`GET /api/v1/orchestration/executions/{id}/events` 对一次正常聊天只会吐出一个由
`trace.status` 合成的终态事件。前端 `ExecutionTracePanel` 因此几乎没有内容，`ToolApprovalPanel`
依赖的 `pendingApproval`（`frontend/src/features/tool-approval/state.ts`，条件是
`stage === "tool" && message === "approval required"`）永远不会触发。

管线实际会发出的 12 个阶段（`app/orchestration/langgraph/nodes.py`）：
`privacy_permission`、`route`、`clarification`、`plan`、`knowledge_strategy`、`knowledge`、
`tool`、`synthesize`、`verifier`、`finalize`、`output_filter`，加上 `engine.py` 的 `complete`。

- [x] **Step 1: 确认事件存储的单例获取方式**

```bash
grep -n "ExecutionEventStore\|get_execution_event_store\|execution_events" app/api/deps/runtime.py app/api/routes/public/orchestration.py
```

确认 `ExecutionEventStore` 实例的持有位置与获取函数名，Step 3 需要按实际情况引用。

- [x] **Step 2: 写失败的测试**

创建 `tests/orchestration/test_execution_events_reach_store.py`，断言：一次经过
`RAGPipeline.execute()` 的执行（内部用桩 services）会让对应 `execution_id` 在
`ExecutionEventStore` 中留下**多于一个**事件，且其中包含 `knowledge` 与 `synthesize` 阶段。

```bash
conda run --no-capture-output -n rag-local python -m pytest tests/orchestration/ -x -q
```

- [x] **Step 3: 实现 publisher 并接线**

在 `app/orchestration/event_publisher.py` 中新增一个把事件写入 store 的 publisher 实现
（与既有 `EventPublisher` 协议一致），并让 `RAGPipeline._build_engine` 构造
`OrchestrationEngine` 时传入它。

**两个必须遵守的约束：**

- **`execution_id` 的来源。** `OrchestrationRequest.execution_id` 字段已存在
  （`execute_stream` 会 `model_copy(update={"execution_id": ...})`），但 `execute()` 路径当前
  不设置它。最干净的做法是让 `app/api/routes/public/query.py` 把 tracker 的 `execution_id`
  写进 `PipelineRequest`，一路传到 `OrchestrationRequest`。
- **引擎是按 profile 缓存的共享实例**（后端 Task 9 的改动，`_ENGINE_CACHE`）。publisher
  因此**不能持有 per-request 状态**；`execution_id` 必须从 `request` 上取，或走 ContextVar，
  与 `app/orchestration/engine.py` 里 `_current_event_reporter` 同样的模式。
  **这一点如果做错，会重新引入后端 Task 9 刚修掉的跨请求事件串流问题**（请求 B 的上报器
  覆盖请求 A 的，A 的事件流进 B 的 SSE 流）。

- [x] **Step 4: 给事件存储加内存上限**

`ExecutionEventStore._events` 是一个无上限的 `defaultdict(list)`。接通之后每次查询都会往里写
十来个事件且**永不清理**——这是一个内存泄漏，必须在同一个任务里解决。

加入与 `AgentExecutionTracker` 一致的 TTL 清理（后者是 1 小时，见其 `_cleanup_loop`），或按
execution 数量做 LRU 淘汰。选哪种都行，但要有上限。

- [x] **Step 5: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -m pytest -q
conda run --no-capture-output -n rag-local ruff check . && conda run --no-capture-output -n rag-local ruff format --check .
git commit -m "fix(orchestration): publish pipeline execution events into the event store"
```

---

### Task 3: 对齐 SSE 事件的 stage 词表

> **依赖**：决策 1 选了选项 A 才有意义；选了选项 B 则本任务取消。

**Files:**
- Modify: `frontend/src/features/execution-trace/types.ts`
- Modify: `frontend/src/features/execution-trace/ExecutionTracePanel.tsx`

**Context:** 后端 `app/domain/events.py::EventStage` 有 **14** 个取值：

```
privacy_permission, route, clarification, plan, knowledge_strategy, knowledge,
rag, tool, synthesize, verifier, finalize, output_filter, complete, failed
```

前端 `ExecutionStage` 只有 **7** 个：`route, plan, rag, tool, synthesize, complete, failed`。

而 `isExecutionEvent()` 用 `stages.includes(...)` 做校验，返回 `false` 时
`parseExecutionEventSse` 直接返回 `null`，事件被**静默丢弃**。也就是说 14 个阶段里有 7 个会被
扔掉，**包括 `knowledge`——主检索阶段**。

今天看不出来，是因为管线事件根本到不了前端（Task 2）。Task 2 一接通，这个不匹配立刻变成
"面板只显示一半阶段"。

`isExecutionEvent` 还用 `hasExactKeys` 要求字段集**完全相等**，这意味着后端 `ExecutionEvent`
任何新增字段都会导致前端丢弃全部事件——比 stage 问题更脆。本任务一并放宽为"必需字段齐备"。

- [x] **Step 1: 补齐 stage 词表**

在 `frontend/src/features/execution-trace/types.ts` 中：

```typescript
// Mirrors EventStage in app/domain/events.py. Keep both lists in sync: an
// unknown stage makes isExecutionEvent reject the event and the UI silently
// drops it.
export const EXECUTION_STAGES = [
  "privacy_permission",
  "route",
  "clarification",
  "plan",
  "knowledge_strategy",
  "knowledge",
  "rag",
  "tool",
  "synthesize",
  "verifier",
  "finalize",
  "output_filter",
  "complete",
  "failed",
] as const;

export type ExecutionStage = (typeof EXECUTION_STAGES)[number];
```

并让 `isExecutionEvent` 用 `EXECUTION_STAGES` 做校验，**不要再手写第二份数组**——原本的两处
定义正是漂移的来源。

- [x] **Step 2: 放宽字段校验**

把 `hasExactKeys(event, [...])` 改为只检查必需字段存在，允许后端新增字段：

```typescript
function hasKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}
```

`isExecutionEvent` 与 `isExecutionMetadataItem` 都改用它。**不要放宽类型检查本身**——只放宽
"不允许有额外字段"这一条。

- [x] **Step 3: 给新 stage 补展示标签**

读 `ExecutionTracePanel.tsx`，确认它如何把 stage 映射成展示文本。为 7 个新增 stage 补上标签。
若走 `t()`，键必须**同时**加进 `en.json` 与 `zh.json`。

- [x] **Step 4: 验证并提交**

```bash
cd frontend && npm run lint && npm run type-check && npm run build && cd ..
git commit -m "fix(frontend): accept all backend execution stages in the trace event guard"
```

---

### Task 4: 清掉 benchmark 改造留下的孤儿 i18n 键

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh.json`

**Context:** 后端把 `POST /admin/ops/benchmark/run` 改为 202 后台任务后，前端相应把提示文案从
`admin.actions.benchmarkComplete` 换成了新增的 `admin.actions.benchmarkQueued`。旧键留在了两个
语言文件里，现在无人引用。

单独列出（而不是并进 Task 6）是因为它是后端改动的直接残留，应当与那次改动关联记录。

- [x] **Step 1: 确认零引用**

```bash
grep -rn "benchmarkComplete" frontend/src || echo "confirmed unused"
```

- [x] **Step 2: 从两个语言文件中删除该键**

- [x] **Step 3: 验证并提交**

```bash
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
cd frontend && npm run build && cd ..
git commit -m "chore(i18n): drop benchmarkComplete, orphaned by the 202 benchmark change"
```

---

# Phase 3 — i18n 修复

### Task 5: 修复 37 个引用了但未定义的 i18n 键

**Files:**
- Modify: `frontend/src/pages/admin/AdminSystemMonitor.tsx`
- Modify: `frontend/src/pages/AdminPage.tsx`
- Modify: `frontend/src/i18n/locales/{en,zh}.json`
- 另有 6 个文件各引用 1–2 个缺失键（见下表）

**Context:** 有 **37 个点分键**在 `en.json` 中不存在。i18next 配置为 `fallbackLng: 'en'`
（`frontend/src/i18n/config.ts`）且未设 `parseMissingKeyHandler`，因此缺失键会**原样渲染成 key
字符串**——用户在界面上看到的是 `pages.admin.monitor.cpu` 而不是 "CPU"。

其中 **22 个集中在 `AdminSystemMonitor.tsx`**，根因是**命名空间写错**：代码用
`pages.admin.monitor.*`，而语言文件里定义的是 `admin.systemMonitor.*`。两边键名也不完全对应
（代码要 `avgResponseTime`/`activeRequests`，文件里是 `avgResponse`/`activeConnections`），
且代码需要的 `cpu`、`provider`、`model`、`baseUrl` 等在任何命名空间下都不存在。

完整清单：

| 键 | 引用位置 | 处理方式 |
|---|---|---|
| `pages.admin.monitor.*`（22 个） | `AdminSystemMonitor.tsx` | 见 Step 2 |
| `pages.admin.sections.monitor` | `AdminPage.tsx:146` | 新增 |
| `chat.clarificationError` | `useClarification.ts:49` | 新增 |
| `chat.skipClarificationError` | `useClarification.ts:65` | 新增 |
| `chat.clarificationAuthError` | `useClarification.ts:93` | 新增 |
| `common.retry` | `AdminAgentQualityDashboard.tsx:126`、`AdminSystemMonitor.tsx:64` | 新增 |
| `common.noData` / `common.optional` / `common.required` | `AdminSystemMonitor.tsx` | 新增 |
| `admin.export.csv` / `admin.export.json` | `exportUtils.tsx:87,95` | 新增 |
| `admin.ui.pagination` / `admin.ui.itemsPerPage` | `AdminPagination.tsx:30,40` | 新增 |
| `admin.ui.catalogFallback` | `AdminModelSettings.tsx:122` | 新增 |
| `admin.ui.noServiceData` | `AdminOpsDiagnostics.tsx:125` | 新增 |

**注意 `useClarification.ts` 的三个键**：它们都写成
`t("chat.clarificationError") || "Failed to submit clarification"`，所以英文用户看到的是兜底
英文字面量，**中文用户同样看到英文**。这三个键补齐后中文界面才会正确本地化——这也是后端澄清
双语化改动在前端的对应缺口。

- [x] **Step 1: 重新生成缺失清单（代码可能已变化）**

```bash
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
```

看 `[i18n]` 段落的 `MISSING` 行，每行带引用位置。

- [x] **Step 2: 决定 AdminSystemMonitor 的命名空间归属**

两种做法，**二选一并保持一致**：

- **A（推荐）**：把 `AdminSystemMonitor.tsx` 中的 `t("pages.admin.monitor.X")` 改为
  `t("admin.systemMonitor.X")`，复用已有的 16 个键，只为缺的新增条目。
  `admin.systemMonitor` 下已有 `avgResponse`/`activeConnections`，与代码需要的
  `avgResponseTime`/`activeRequests` 语义相同——**复用旧键名并改代码**，不要两套并存。
- **B**：新建 `pages.admin.monitor` 命名空间，把 `admin.systemMonitor.*` 整体迁过去并删除旧的。
  改动面更大，但与文件里其他 `pages.*` 页面命名空间更一致。

- [x] **Step 3: 补齐其余 15 个键**

en/zh 两份都要加。中文翻译要与文件中既有风格一致（参考相邻条目的措辞）。

- [x] **Step 4: 确认清零且键集仍然对齐**

```bash
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
```

期望 `missing: 0`，且没有 `only-en` / `only-zh` 输出行。

- [x] **Step 5: 人工确认渲染**

启动前端，打开管理台的系统监控页，确认不再出现 `pages.admin.monitor.*` 这样的原始 key 字符串。

- [x] **Step 6: 提交**

```bash
git commit -m "fix(i18n): define the 37 referenced-but-missing keys"
```

---

### Task 6: 删除未使用的 i18n 键

> **依赖**：必须在 Task 5 之后做。Task 5 会把一部分"未使用"键重新接上（例如
> `admin.systemMonitor.*` 若选了方案 A），先删会误伤。

**Files:**
- Modify: `frontend/src/i18n/locales/{en,zh}.json`

**Context:** 1045 个键中有 189 个从未被 `t()` 静态引用（Task 5 完成后这个数字会变小）。

- [x] **Step 1: Task 5 完成后重新生成未使用清单**

```bash
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
```

- [x] **Step 2: 人工复核动态键**

**这一步不能跳过。** 有些键是动态拼接消费的（例如 ``t(`admin.status.${status}`)``），静态扫描
看不到。审计脚本会在 `[i18n]` 段末尾列出使用了模板字面量 ``t(`...`)`` 的文件（当前是 6 个）。

逐个打开这些文件，找出被拼接的键前缀，把这些前缀覆盖到的键**从待删清单中排除**，并在提交
信息里记录排除了哪些前缀及原因。

- [x] **Step 3: 删除并验证键集对齐**

```bash
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
cd frontend && npm run build && cd ..
```

- [x] **Step 4: 提交**

```bash
git commit -m "chore(i18n): drop locale keys no code references"
```

---

# Phase 4 — 死代码清理

### Task 7: 删除零引用的前端模块

> **⚠️ `ForgotPasswordPage.tsx` 需要先完成「决策 2」。**

**Files:** 见下表（20 个文件，878 行）

**Context:** 从 `main.tsx` / `App.tsx` 出发做可达性分析（解析 `@/` 别名与相对路径，覆盖静态
import 与动态 `import()`），188 个模块中有 20 个无任何导入方：

| 行数 | 文件 | 备注 |
|---|---|---|
| 181 | `pages/ForgotPasswordPage.tsx` | **见决策 2**：写好但未接路由的功能，非残留 |
| 161 | `components/ContextResolution.tsx` | 澄清相关，被 `useClarification` 取代 |
| 141 | `components/QueryOptimization.tsx` | 同上 |
| 52 | `pages/chat/hooks/useChatInitialization.ts` | |
| 45 | `components/CodeBlock.tsx` | |
| 41 | `lib/async-utils.ts` | |
| 39 | `hooks/useAsyncState.ts` | |
| 35 | `components/animations/index.ts` | |
| 34 | `hooks/useAsyncAction.ts` | |
| 34 | `pages/chat/hooks/useDocumentState.ts` | |
| 32 | `pages/chat/components/SelectControl.tsx` | |
| 29 | `lib/string-utils.ts` | |
| 28 | `pages/chat/hooks/usePromptState.ts` | |
| 18 | `pages/chat/components/TopbarToggleButton.tsx` | |
| 3 | `components/multimodal/index.ts` | |
| 1×5 | `lib/{document,prompt,query,session,user-settings}-api.ts` | 一行 re-export shim，与后端刚删掉的 106 个 shim 同源 |

- [x] **Step 1: 重新生成零引用清单**

```bash
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
```

看 `[orphans]` 段落。**不要凭本文档的清单直接删**，代码可能已变化。

- [x] **Step 2: 逐个二次复核**

对每个候选文件，用文件名（不含扩展名）在 `src/` 全文搜索一遍，确认没有动态引用或字符串引用：

```bash
cd frontend && for f in $(cat to_delete.txt); do
  n=$(basename "$f" | sed 's/\.[jt]sx\?$//')
  echo "$(grep -rl "$n" src --include=*.ts --include=*.tsx | grep -v "^$f$" | wc -l)  $f"
done
```

任何非零结果都要停下来查清楚。

- [x] **Step 3: 分两批删除**

先删 5 个一行 shim（零风险），单独提交；再删其余（单独提交）。每批之后：

```bash
cd frontend && npm run type-check && npm run build && cd ..
```

- [x] **Step 4: 清理随之孤立的 i18n 键**

删掉页面/组件后，它们的 i18n 键会变成未使用（例如删了 `ForgotPasswordPage.tsx` 之后的
`pages.forgotPassword.*`）。重跑审计脚本并按 Task 6 的流程一并清理。

- [x] **Step 5: 验证并提交**

```bash
cd frontend && npm run lint && npm run type-check && npm run build && cd ..
PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py
```

---

## 验收

自动化：

- [x] `cd frontend && npm run lint` → **0 errors**
- [x] `npm run type-check` → 干净
- [x] `npm run build` → 成功
- [x] `PYTHONIOENCODING=utf-8 conda run --no-capture-output -n rag-local python scripts/audit/frontend_audit.py`
      → **退出码 0**（端点 0 不匹配、孤儿 0、i18n missing 0、en/zh 键集无差异）
- [x] 后端仍然干净：`conda run --no-capture-output -n rag-local python -m pytest -q` 全绿；
      端点数 149（若做了 Task 2 则确认未变）
- [x] CI 的 frontend job 包含 lint 且全绿

人工：

- [x] 管理台系统监控页不再显示原始 i18n key
- [x] 中文界面下触发一次澄清失败，提示文案是中文而不是英文兜底
- [x] （若做了 Task 2 选项 A）发起一次聊天，执行追踪面板显示出多个阶段而不只是一个终态事件

---

## Self-Review

**Spec coverage** —— 审计发现的 8 项全部有归属：

| 发现 | 任务 |
|---|---|
| 执行追踪三处断链 | Task 2（需决策 1） |
| SSE stage 词表 14 vs 7 不匹配 + `hasExactKeys` 过严 | Task 3 |
| `benchmarkComplete` 孤儿键 | Task 4 |
| 37 个未定义 i18n 键（含 22 个命名空间错误） | Task 5 |
| 189 个未使用 i18n 键 | Task 6 |
| 20 个零引用模块 / 878 行 | Task 7（需决策 2） |
| ESLint 151 个 error 全为配置问题 | Task 1 |
| replay 端点无前端调用方 | 明确排除（产品决策） |

**未发现问题的部分**（已核实，无需动作）：前端 61 个端点调用 100% 命中后端 OpenAPI；
`/ready` 与 `/optimization/database/*` 前端从未使用，后端对它们的改动零影响；en/zh 键集完全
对齐；`tsc -b --noEmit` 干净。

**Placeholder scan** —— 无 "TBD"。每个删除/清理任务都以"重跑审计脚本"开头而不是照抄本文档的
清单；审计脚本已入库（`scripts/audit/frontend_audit.py`）并通过 ruff，新会话直接可运行；Task 2
的 publisher 实现给出了两个必须遵守的约束（`execution_id` 来源、共享引擎下不能持有 per-request
状态）而不是留白；Task 5 Step 2 给出两个具体方案并标明推荐项；两个需要人类决策的点提到了文档
最前面而不是藏在任务里。

**风险排序** —— Task 2 风险最高：触碰后端共享引擎，做错会重新引入刚修掉的跨请求事件串流，
且会打开一个当前无上限的内存 store（Step 4 专门处理）。Task 7 次之，删除面最大。Task 1 风险
最低且为后续任务提供门禁，因此排在最前。

---

## 执行结果（2026-08-29 完成）

**决策：** 决策 1 选 **A（接通执行追踪）**；决策 2 选 **删除 ForgotPasswordPage**。

**提交：** `8a8c8f12..db429654`，共 9 个提交（计划的 7 个任务 + 删除任务拆成 3 批）。

### 最终指标

| 指标 | 起始 | 结束 |
|---|---|---|
| 后端端点数（OpenAPI 操作） | 149 | 149（未变） |
| 后端测试 | 56 passed | **62 passed** |
| 前端模块数 | 188 | 160 |
| 前端零引用模块 | 20（878 行） | **0** |
| i18n 键数 | en 1045 / zh 1045 | en 870 / zh 870 |
| i18n 引用但未定义 | 37 | **0** |
| i18n 定义但未引用 | 189 | 27（全部为模板字面量动态键，见下） |
| `npm run lint` | 151 errors / 29 warnings | **0 errors** / 25 warnings |
| 审计脚本退出码 | 1 | **0** |

### 与计划不同的地方

1. **`npm run lint` 原本带 `--max-warnings 0`**，因此 error 清零后仍然非零退出，无法直接进 CI。
   计划要求"lint 进门禁"与"29 个 warning 留待单独一轮"两者冲突。采用棘轮（ratchet）：
   阈值设为当前 warning 数（先 29，删模块后降到 25），新增 warning 一律拦下，数字只降不升。

2. **`globals` 补进了 `devDependencies`。** 计划说它已在 `node_modules` 中、无需新增依赖，但那是
   eslint 的传递依赖；直接 import 一个未声明的包会在 eslint 升级时静默失效，故显式声明。

3. **Task 7 与 Task 6 调换顺序。** 先删模块再做一次 i18n 未使用键清理，而不是清理两遍。
   Task 7 Step 4 本来就要求删完模块后再跑一次 Task 6 的流程。

4. **删除面比计划的 20 个模块大。** 审计脚本报告的是"无导入方"（一层），不是可达性。删掉
   `components/{animations,multimodal}/index.ts` 两个 barrel 后，它们独占的导出模块随之暴露，
   连锁了两轮：animations 的 Framer Motion 变体 4 个（含 CSS）、multimodal 整个目录 3 个、
   以及只被 multimodal 引用的 `types/common.ts`。合计多删 8 个 .tsx/.ts + 4 个 .css。
   **副作用：`framer-motion` 已无任何源码 import，但依赖声明保留未动**——是否移除是单独决策。

5. **37 个缺失键的症状与计划描述不同。** 计划说会渲染成原始 key 字符串；实际取决于写法：
   - `t(key, "English default")`（32 个）→ 渲染英文兜底，**中文用户看到英文**；
   - `t(key) || "English default"`（5 个）→ i18next 对缺失键返回 key 本身（truthy），`||` 从不触发，
     **确实渲染原始 key**。这 5 处已改用 defaultValue 参数。
   修复动作与计划一致，只是记录准确的症状。

6. **三个澄清错误键放进 `clarification.*` 而不是新建 `chat.*` 命名空间**——仓库中没有 `chat`
   顶层命名空间，而 `clarification.*` 已经承载该功能的全部文案（包括这三个错误对应的
   `submit` / `skip` 标签）。为 3 个错误新开一个平行命名空间会把一个功能拆成两处。

7. **`admin.systemMonitor.activeConnections` 重命名为 `activeRequests`**（而非计划建议的"复用旧键名"）：
   它标注的是 `traffic.active_requests`，旧键名与旧文案描述的是这个面板并不展示的数据。
   `avgResponse` 与 `serviceStatus` 则按计划复用（纯同义词）。

### 未做的部分

- **计划明确排除的 4 项**全部未做：replay 触发 UI、UI/视觉改动、前端测试套件、25 个 ESLint warning。
- **人工验收的 3 项无法在本机执行**：`.runtime/` 为空且未配置模型后端，跑不起完整聊天链路。
  改为等价的程序化验证：
  - AdminSystemMonitor 的 31 个键在 en/zh 下全部解析成功（无原始 key 残留）；
  - 澄清错误的 3 个键在 zh 下有中文文案，且调用点已改为会真正触发的 defaultValue 写法；
  - 用桩 services 跑通一次真实 `RAGPipeline.execute()`，事件存储收到 8 个阶段
    （`privacy_permission` / `route` / `knowledge_strategy` / `knowledge` / `synthesize` /
    `verifier` / `output_filter` / `complete`），再把这 8 条经 `serialize_execution_event`
    序列化后的真实载荷喂给前端 `isExecutionEvent` 与 `parseExecutionEventSse`：8/8 通过，
    含新增字段时仍通过（前向兼容）。旧的 7 个 stage 词表会丢弃其中 5 条。

### 仍然开放

- `framer-motion` 依赖已无消费方，是否从 `package.json` 移除。
- 25 个 ESLint warning（棘轮已锁住，不会增加）。
- 前端测试套件仍为空；本轮的前端改动没有自动化回归测试保护，后端侧有
  `tests/orchestration/test_execution_events_reach_store.py`（6 个测试）。
