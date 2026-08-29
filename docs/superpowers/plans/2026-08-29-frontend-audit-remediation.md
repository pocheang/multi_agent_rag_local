# 前端审计修复计划（2026-08-29，后端修复后续）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-08-29 后端全量审计修复（`2026-08-29-backend-full-audit-remediation.md`）在前端留下的缺口，以及审计过程中在前端本身发现的问题：执行追踪链路仍未接通、SSE 事件词表不匹配、37 个未定义的 i18n 键、878 行零引用模块，以及让 `npm run lint` 具备进入 CI 的条件。

**Architecture:** 不改前端架构。React 18 + TypeScript + Vite + Zustand + i18next 保持不变，路由与页面结构不变。Task 1 是唯一涉及后端的任务（接通事件发布器），其余全部限于 `frontend/`。

**Tech Stack:** React 18 / TypeScript / Vite / i18next / ESLint 9 flat config。后端侧仅触碰 `app/pipeline/rag_pipeline.py` 与 `app/api/deps/runtime.py`。

---

## Global Constraints

- 后端命令一律在 conda 环境 `rag-local` 中执行；前端命令在 `frontend/` 目录下执行。
- 每个任务结束前必须通过 `npm run type-check` 与 `npm run build`。
- **不改动任何 HTTP 路径或请求/响应字段名**，除非任务明确要求。前端 61 个端点调用当前 100% 命中后端 OpenAPI，这个状态必须保持。
- i18n 修改必须同时更新 `en.json` 与 `zh.json`，且保持两者键集完全一致（当前各 1045 个键，零差异）。
- 每个删除任务以一次验证性检查开始，确认零引用。
- 每个任务单独提交。

---

## 审计结论速览

用当前后端的 OpenAPI 规格逐一比对了前端全部 61 个端点调用：

| 检查项 | 结果 |
|---|---|
| 前端调用指向已删端点 | **0 个** —— Task 12/13 删掉的 `/optimization/database/*` 与改造的 `/ready` 前端从未使用 |
| en/zh 键集差异 | **0** —— 各 1045 键，完全对齐 |
| 端点路径匹配 | **61/61** 命中 |

也就是说后端的删除动作没有打断任何前端调用。真正的问题在别处。

---

## Scope

### 本计划覆盖

| Phase | 主题 | 任务 |
|---|---|---|
| 1 | ESLint 门禁（先做，为后续改动兜底） | Task 1 |
| 2 | 与后端改动相关的缺口 | Task 2–4 |
| 3 | i18n 修复 | Task 5–6 |
| 4 | 死代码清理 | Task 7 |

### 明确不在范围内

1. **补一个 replay 触发 UI**——后端 `POST /admin/ops/replay/run` 已改为 202 后台任务，但前端从来没有调用方。要不要在管理台加这个入口是产品决策，不是修 bug。
2. **UI/视觉改动**——本计划不碰样式与布局。
3. **前端测试套件**——`frontend/package.json` 有 `test` 脚本但仓库中没有测试文件。重建前端测试是独立工作。

---

## File Structure

- Modify: `frontend/eslint.config.js` — 用 `globals.browser` 替换手写清单，为 TS 文件关闭 `no-undef`。
- Modify: `.github/workflows/ci.yml` — 把 `npm run lint` 加为门禁。
- Modify: `app/pipeline/rag_pipeline.py`、`app/api/deps/runtime.py` — 把管线事件接到 `ExecutionEventStore`（Task 2，唯一的后端改动）。
- Modify: `frontend/src/features/execution-trace/types.ts` — 补齐 stage 词表。
- Modify: `frontend/src/features/execution-trace/ExecutionTracePanel.tsx` — 新 stage 的展示标签。
- Modify: `frontend/src/i18n/locales/{en,zh}.json` — 补 37 个缺失键，删 189 个未使用键。
- Modify: `frontend/src/pages/admin/AdminSystemMonitor.tsx` — 修正 i18n 命名空间。
- Delete: 20 个零引用模块（878 行）。

---

# Phase 1 — ESLint 门禁

### Task 1: 修复 ESLint 配置并把 lint 加进 CI

**Files:**
- Modify: `frontend/eslint.config.js`
- Modify: `.github/workflows/ci.yml`

**Context:** `npm run lint` 在干净检出下报 **151 errors / 29 warnings**，因此在 2026-08-29 加 CI 时被排除在门禁之外。归类后：

```
151  no-undef                              ← 全部是浏览器/DOM/TS 全局
 11  react-refresh/only-export-components
  6  react-hooks/exhaustive-deps
  6  @typescript-eslint/no-unused-vars
  3  @typescript-eslint/no-explicit-any
  2  no-console
  1  @typescript-eslint/no-non-null-assertion
```

151 个 `no-undef` 触发在 `HTMLInputElement`(28)、`React`(25)、`HTMLDivElement`(10)、`AbortSignal`(10)、`URL`(9)、`HTMLElement`(9)、`File`/`Blob`(各 6)、`RequestInit`、`Headers`、`Response`、`crypto`、`navigator` 等标识符上。**这些全部不是真实缺陷**，而是两个配置问题：

1. `languageOptions.globals` 手写了 14 个全局（`window`、`document`、`fetch`……），漏掉了其余 749 个浏览器全局。
2. `js.configs.recommended` 的 `no-undef` 对 `.ts/.tsx` 生效。typescript-eslint 官方明确建议在 TS 文件上关闭该规则——TypeScript 编译器本身就会报未定义标识符，而 `tsc -b --noEmit` 已经是干净的且已在 CI 中。

`globals` 包已在 `node_modules` 中可用（763 个 browser 键），无需新增依赖。

- [ ] **Step 1: 记录当前基线**

```bash
cd frontend && npm run lint 2>&1 | tail -3
```

记下 errors/warnings 数量，Step 3 后用于对比。

- [ ] **Step 2: 修配置**

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

- [ ] **Step 3: 确认 error 归零**

```bash
cd frontend && npm run lint 2>&1 | tail -5
```

期望 **0 errors**。剩余 warnings（约 29 个）保持 warning 级别，本任务不处理——它们是真实的代码风格问题，值得单独一轮，但不应阻塞门禁。

若仍有 error，逐条判断是真实缺陷还是配置问题，**不要用 `eslint-disable` 掩盖真实缺陷**。

- [ ] **Step 4: 加进 CI**

在 `.github/workflows/ci.yml` 的 frontend job 中，`Type check` 之前插入：

```yaml
      - name: Lint
        run: npm run lint
```

并删除文件末尾那段说明为什么不做门禁的注释（`# \`npm run lint\` is deliberately not a gate yet...` 整段）。

- [ ] **Step 5: 验证并提交**

```bash
cd frontend && npm run lint && npm run type-check && npm run build && cd ..
git add frontend/eslint.config.js .github/workflows/ci.yml
git commit -m "build(frontend): fix the ESLint globals config and make lint a CI gate"
```

---

# Phase 2 — 与后端改动相关的缺口

### Task 2: 接通执行追踪事件链路

**Files:**
- Modify: `app/pipeline/rag_pipeline.py`
- Modify: `app/api/deps/runtime.py`（或按实际 `ExecutionEventStore` 单例位置调整）
- Test: `tests/orchestration/test_execution_events_reach_store.py`

**⚠️ 这是本计划唯一涉及后端的任务，也是唯一需要你先做决策的任务。**

**Context:** 后端 Task 1/2 让 `execution_id` 到达了前端，`useExecutionTrace` 因此第一次真正开始订阅 SSE。但订阅到的内容几乎是空的——事件链路有**三处独立断裂**：

1. `RAGPipeline._build_engine` 构造 `OrchestrationEngine` 时不传 `publisher`，于是 `engine.py:142` 落到 `NullEventPublisher()`。管线各阶段 `report_event` 出来的 `ExecutionEvent` 直接被丢弃。
2. `ExecutionEventStore.publish` 全仓库只有一个调用方：`app/mcp/registry.py:76`（MCP 工具注册表）。RAG 管线从不写入这个 store，所以 SSE 端点的 `event_store.events_since(...)` 永远返回空。
3. `AgentExecutionTracker.record_agent_step` **零调用方**（只有 `app/services/__init__.py` 的 re-export）。所以 `trace.steps` 恒为空，SSE 端点的 `_trace_event` 循环一次也不执行。

净效果：`GET /api/v1/orchestration/executions/{id}/events` 对一次正常聊天只会吐出一个由 `trace.status` 合成的终态事件。前端的 `ExecutionTracePanel` 因此几乎没有内容，`ToolApprovalPanel` 依赖的 `pendingApproval`（`state.ts:43`，条件是 `stage === "tool" && message === "approval required"`）永远不会触发。

**需要你决策**：

- **选项 A（推荐）：接通链路。** 让 `RAGPipeline` 传入一个把事件写进 `ExecutionEventStore` 的 publisher。管线已经在每个阶段发事件了（`privacy_permission`、`route`、`clarification`、`plan`、`knowledge_strategy`、`knowledge`、`tool`、`synthesize`、`verifier`、`finalize`、`output_filter`、`complete`），基础设施齐备，缺的只是这一根接线。做完前端面板立刻有内容。
- **选项 B：删掉整条链路。** 移除 `execution-trace/` 与 `tool-approval/` 前端特性、SSE 端点、`ExecutionEventStore`、`AgentExecutionTracker` 的 step API，以及后端 Task 1 加的 `metadata.execution_id`。

**在你选定之前不要执行本任务。** 下面的步骤按选项 A 编写。

- [ ] **Step 1: 确认事件存储的单例获取方式**

```bash
grep -n "ExecutionEventStore\|get_execution_event_store\|execution_events" app/api/deps/runtime.py
```

确认 `ExecutionEventStore` 实例的持有位置与获取函数名，Step 3 需要按实际情况引用。

- [ ] **Step 2: 写失败的测试**

创建 `tests/orchestration/test_execution_events_reach_store.py`，断言：一次经过 `RAGPipeline.execute()` 的执行（pipeline 内部可用桩 services）会让对应 `execution_id` 在 `ExecutionEventStore` 中留下 **多于一个** 事件，且其中包含 `knowledge` 与 `synthesize` 阶段。

- [ ] **Step 3: 实现 publisher**

在 `app/orchestration/event_publisher.py` 中新增一个把事件写入 store 的 publisher 实现（与既有 `EventPublisher` 协议一致），并让 `RAGPipeline._build_engine` 在构造 `OrchestrationEngine` 时传入它。

**注意两点**：
- `OrchestrationRequest.execution_id` 已经存在（`execute_stream` 会 `model_copy(update={"execution_id": ...})`），但 `execute()` 路径当前不设置它。publisher 需要知道当前请求的 `execution_id` 才能正确归档——最干净的做法是让 `public/query.py` 把 tracker 的 `execution_id` 写进 `PipelineRequest`，一路传到 `OrchestrationRequest`。
- 引擎现在是**按 profile 缓存的共享实例**（后端 Task 9）。publisher 因此不能持有 per-request 状态；`execution_id` 必须从 `request` 上取，或走 ContextVar，与 `_current_event_reporter` 同样的模式。**这一点如果做错，会重新引入 Task 9 修掉的跨请求事件串流问题。**

- [ ] **Step 4: 加内存上限**

`ExecutionEventStore._events` 是一个无上限的 `defaultdict(list)`，接通之后每次查询都会往里写十来个事件且**永不清理**。必须加入与 `AgentExecutionTracker` 一致的 TTL 清理（后者是 1 小时，见 `_cleanup_loop`），否则这是一个内存泄漏。

- [ ] **Step 5: 验证并提交**

```bash
conda run --no-capture-output -n rag-local python -m pytest -q
conda run --no-capture-output -n rag-local ruff check . && conda run --no-capture-output -n rag-local ruff format --check .
git commit -m "fix(orchestration): publish pipeline execution events into the event store"
```

---

### Task 3: 对齐 SSE 事件的 stage 词表

**Files:**
- Modify: `frontend/src/features/execution-trace/types.ts`
- Modify: `frontend/src/features/execution-trace/ExecutionTracePanel.tsx`

**依赖**：Task 2 选择了选项 A 才有意义；若选了选项 B，本任务随之取消。

**Context:** 后端 `app/domain/events.py::EventStage` 有 **14** 个取值：

```
privacy_permission, route, clarification, plan, knowledge_strategy, knowledge,
rag, tool, synthesize, verifier, finalize, output_filter, complete, failed
```

前端 `ExecutionStage` 只有 **7** 个：`route, plan, rag, tool, synthesize, complete, failed`。

而 `isExecutionEvent()` 用 `stages.includes(...)` 做校验，返回 `false` 时 `parseExecutionEventSse` 直接返回 `null`，事件被**静默丢弃**。也就是说 14 个阶段里有 7 个会被扔掉，**包括 `knowledge`——主检索阶段**。

今天看不出来，是因为管线事件根本到不了前端（Task 2）。Task 2 一接通，这个不匹配立刻变成"面板只显示一半阶段"。

`isExecutionEvent` 还用 `hasExactKeys` 要求字段集完全相等，这意味着后端 `ExecutionEvent` 任何新增字段都会导致前端丢弃全部事件——比 stage 问题更脆。本任务一并放宽为"必需字段齐备"。

- [ ] **Step 1: 补齐 stage 词表**

在 `frontend/src/features/execution-trace/types.ts` 中：

```typescript
// Mirrors EventStage in app/domain/events.py. Keep both lists in sync: an
// unknown stage makes isExecutionEvent reject the event and the UI silently
// drops it.
export type ExecutionStage =
  | "privacy_permission"
  | "route"
  | "clarification"
  | "plan"
  | "knowledge_strategy"
  | "knowledge"
  | "rag"
  | "tool"
  | "synthesize"
  | "verifier"
  | "finalize"
  | "output_filter"
  | "complete"
  | "failed";
```

并把 `isExecutionEvent` 内的 `stages` 数组同步为同一份清单（或直接由类型推导出一个 `const` 数组，避免两处再次漂移）。

- [ ] **Step 2: 放宽字段校验**

把 `hasExactKeys(event, [...])` 改为只检查必需字段存在，允许后端新增字段：

```typescript
function hasKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}
```

`isExecutionEvent` 与 `isExecutionMetadataItem` 都改用它。**不要放宽类型检查本身**——只放宽"不允许有额外字段"这一条。

- [ ] **Step 3: 给新 stage 补展示标签**

读 `ExecutionTracePanel.tsx`，确认它如何把 stage 映射成展示文本。为 7 个新增 stage 补上标签（并按 i18n 现状决定是硬编码还是走 `t()`；若走 `t()`，键必须同时加进 `en.json` 与 `zh.json`）。

- [ ] **Step 4: 验证并提交**

```bash
cd frontend && npm run lint && npm run type-check && npm run build && cd ..
git commit -m "fix(frontend): accept all backend execution stages in the trace event guard"
```

---

### Task 4: 清掉 benchmark 改造留下的孤儿 i18n 键

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh.json`

**Context:** 后端 Task 10 把 `POST /admin/ops/benchmark/run` 改为 202 后台任务，前端相应把提示文案从 `admin.actions.benchmarkComplete` 换成了新增的 `admin.actions.benchmarkQueued`。旧键留在了两个语言文件里，现在无人引用。

这一条本可以并进 Task 6（批量清理未使用键），单独列出是因为它是后端改动的直接残留，应当与那次改动关联记录。

- [ ] **Step 1: 确认零引用**

```bash
grep -rn "benchmarkComplete" frontend/src || echo "confirmed unused"
```

- [ ] **Step 2: 从两个语言文件中删除该键**

- [ ] **Step 3: 验证键集仍然对齐并提交**

```bash
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

**Context:** 全量扫描 `t("...")` 调用后，有 **37 个点分键**在 `en.json` 中不存在。i18next 配置为 `fallbackLng: 'en'` 且未设 `parseMissingKeyHandler`，因此缺失键会**原样渲染成 key 字符串**——用户在界面上看到的是 `pages.admin.monitor.cpu` 而不是 "CPU"。

其中 **22 个集中在 `AdminSystemMonitor.tsx`**，根因是**命名空间写错**：代码用 `pages.admin.monitor.*`，而语言文件里定义的是 `admin.systemMonitor.*`。两边键名也不完全对应（`avgResponseTime` vs `avgResponse`、`activeRequests` vs `activeConnections`），且代码需要的 `cpu`、`provider`、`model`、`baseUrl` 等在任何命名空间下都不存在。

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

注：`useClarification.ts` 的三个键都写成 `t("chat.clarificationError") || "Failed to submit clarification"`，所以英文用户看到的是兜底英文字面量，**中文用户同样看到英文**——这三个键补齐后中文界面才会正确本地化。这也是后端 Task 5 澄清双语化在前端的对应缺口。

- [ ] **Step 1: 重新生成缺失清单（代码可能已变化）**

```bash
cd frontend && node -e "
const fs=require('fs'),path=require('path');
const flat=(o,p='')=>Object.entries(o).reduce((a,[k,v])=>Object.assign(a,typeof v==='object'&&v?flat(v,p?p+'.'+k:k):{[p?p+'.'+k:k]:v}),{});
const en=flat(JSON.parse(fs.readFileSync('src/i18n/locales/en.json','utf8')));
const miss={};
const walk=d=>fs.readdirSync(d,{withFileTypes:true}).forEach(e=>{const f=path.join(d,e.name);
 if(e.isDirectory())return walk(f);
 if(!/\.tsx?$/.test(e.name))return;
 fs.readFileSync(f,'utf8').split('\n').forEach((l,i)=>{
  for(const m of l.matchAll(/\bt\(\s*[\"'\`]([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)[\"'\`]/g))
   if(!(m[1] in en))(miss[m[1]]=miss[m[1]]||[]).push(f+':'+(i+1));});});
walk('src');
console.log(Object.keys(miss).length+' missing');
Object.entries(miss).sort().forEach(([k,v])=>console.log(' ',k,'->',v[0]));
"
```

- [ ] **Step 2: 决定 AdminSystemMonitor 的命名空间归属**

两种做法，**二选一并保持一致**：

- **A（推荐）**：把 `AdminSystemMonitor.tsx` 中的 `t("pages.admin.monitor.X")` 改为 `t("admin.systemMonitor.X")`，复用已有的 16 个键，只为缺的（`cpu`、`provider`、`model`、`baseUrl`、`chatModel`、`reasoningModel`、`embeddingModel`、`enabled`、`last`、`resources`、`services`、`serviceLatency`、`responseTime`、`trafficMetrics`、`systemStatus`、`autoRefresh`、`totalRequests`、`activeRequests`、`avgResponseTime`、`errorRate`、`disk`、`memory`）新增条目。注意 `admin.systemMonitor` 下已有 `avgResponse`/`activeConnections`，与代码需要的 `avgResponseTime`/`activeRequests` 语义相同——**复用旧键名，改代码**，不要两套并存。
- **B**：新建 `pages.admin.monitor` 命名空间，把 `admin.systemMonitor.*` 整体迁过去并删除旧的。改动面更大，但和文件里其他 `pages.*` 页面命名空间更一致。

- [ ] **Step 3: 补齐其余 15 个键**

en/zh 两份都要加。中文翻译要与文件中既有风格一致（参考相邻条目的措辞）。

- [ ] **Step 4: 确认清零并且键集仍然对齐**

重跑 Step 1 的脚本，期望 `0 missing`。再跑一次键集对齐检查：

```bash
cd frontend && node -e "
const fs=require('fs');
const flat=(o,p='')=>Object.entries(o).reduce((a,[k,v])=>Object.assign(a,typeof v==='object'&&v?flat(v,p?p+'.'+k:k):{[p?p+'.'+k:k]:v}),{});
const en=Object.keys(flat(JSON.parse(fs.readFileSync('src/i18n/locales/en.json','utf8'))));
const zh=Object.keys(flat(JSON.parse(fs.readFileSync('src/i18n/locales/zh.json','utf8'))));
console.log('en',en.length,'zh',zh.length);
console.log('only-en',en.filter(k=>!zh.includes(k)));
console.log('only-zh',zh.filter(k=>!en.includes(k)));
"
```

- [ ] **Step 5: 人工确认渲染**

启动前端，打开管理台的系统监控页，确认不再出现 `pages.admin.monitor.*` 这样的原始 key 字符串。

- [ ] **Step 6: 提交**

```bash
git commit -m "fix(i18n): define the 37 referenced-but-missing keys"
```

---

### Task 6: 删除 189 个未使用的 i18n 键

**Files:**
- Modify: `frontend/src/i18n/locales/{en,zh}.json`

**依赖**：必须在 Task 5 之后做。Task 5 会把一部分"未使用"键重新接上（例如 `admin.systemMonitor.*` 若选了方案 A），先删会误伤。

**Context:** 1045 个键中有 189 个从未被 `t()` 引用。

- [ ] **Step 1: Task 5 完成后重新生成未使用清单**

用 Task 5 Step 1 的脚本变体，输出 `defined but never referenced`。

- [ ] **Step 2: 人工复核动态键**

**这一步不能跳过。** 有些键是动态拼接消费的（例如 `t(\`admin.status.${status}\`)`），静态扫描看不到。删除前先搜索模板字面量形式的 `t()` 调用：

```bash
cd frontend && grep -rn 't(`' src --include=*.ts --include=*.tsx
```

把这些模式覆盖到的键前缀从待删清单中排除，并在提交信息里记录排除了哪些前缀及原因。

- [ ] **Step 3: 删除并验证键集对齐**

- [ ] **Step 4: 提交**

```bash
git commit -m "chore(i18n): drop locale keys no code references"
```

---

# Phase 4 — 死代码清理

### Task 7: 删除零引用的前端模块

**Files:** 见下表（20 个文件，878 行）

**Context:** 从 `main.tsx` / `App.tsx` 出发做可达性分析（解析 `@/` 别名与相对路径，覆盖静态 import 与动态 `import()`），188 个模块中有 20 个无任何导入方：

| 行数 | 文件 | 备注 |
|---|---|---|
| 181 | `pages/ForgotPasswordPage.tsx` | 有 `pages.forgotPassword` i18n 命名空间，但页面未接进路由 |
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

**`ForgotPasswordPage.tsx` 需要单独决策**：它不是残留，而是一个**写好了但没接进路由**的功能（181 行 + 完整 i18n）。删掉等于放弃这个功能。执行时请先确认是要删除还是要补上路由；本计划默认删除，若要保留则从清单中移除并单独开任务接线。

- [ ] **Step 1: 重新生成零引用清单**

复用审计时的脚本（解析 `@/` 别名与相对路径，入口为 `main.tsx`/`App.tsx`）。**不要凭本文档的清单直接删**，代码可能已变化。

- [ ] **Step 2: 逐个二次复核**

对每个候选文件，用文件名（不含扩展名）在 `src/` 全文搜索一遍，确认没有动态引用或字符串引用：

```bash
cd frontend && for f in $(cat to_delete.txt); do
  n=$(basename "$f" | sed 's/\.[jt]sx\?$//')
  echo "$(grep -rl "$n" src --include=*.ts --include=*.tsx | grep -v "^$f$" | wc -l)  $f"
done
```

任何非零结果都要停下来查清楚。

- [ ] **Step 3: 分两批删除**

先删 5 个一行 shim（零风险），单独提交；再删其余 15 个，单独提交。每批之后跑 `npm run type-check && npm run build`。

- [ ] **Step 4: 清理随之孤立的 i18n 键**

删掉页面/组件后，它们的 i18n 键会变成未使用（例如 `pages.forgotPassword.*`）。重跑 Task 6 的检测并一并清理。

- [ ] **Step 5: 验证并提交**

```bash
cd frontend && npm run lint && npm run type-check && npm run build && cd ..
```

---

## 验收

- [ ] `cd frontend && npm run lint` → **0 errors**
- [ ] `npm run type-check` → 干净
- [ ] `npm run build` → 成功
- [ ] CI 的 frontend job 包含 lint 且全绿
- [ ] i18n：引用但未定义的键 = 0；en/zh 键集差异 = 0
- [ ] 前端零引用模块 = 0
- [ ] 前端端点调用仍然 100% 命中后端 OpenAPI（用审计时的比对脚本重跑）
- [ ] 人工：管理台系统监控页不再显示原始 i18n key
- [ ] 人工（若做了 Task 2 选项 A）：发起一次聊天，执行追踪面板显示出多个阶段而不只是一个终态事件

---

## Self-Review

**Spec coverage** —— 审计发现的 8 项全部有归属：

| 发现 | 任务 |
|---|---|
| 执行追踪三处断链 | Task 2（需你先决策） |
| SSE stage 词表 14 vs 7 不匹配 | Task 3 |
| `benchmarkComplete` 孤儿键 | Task 4 |
| 37 个未定义 i18n 键（含 22 个命名空间错误） | Task 5 |
| 189 个未使用 i18n 键 | Task 6 |
| 20 个零引用模块 / 878 行 | Task 7 |
| ESLint 151 个 error 全为配置问题 | Task 1 |
| replay 端点无前端调用方 | 明确排除（产品决策） |

**未发现问题的部分**（已核实，无需动作）：前端 61 个端点调用 100% 命中后端 OpenAPI；`/ready` 与 `/optimization/database/*` 前端从未使用，后端 Task 12/13 零影响；en/zh 键集完全对齐；`tsc -b --noEmit` 干净。

**Placeholder scan** —— 无 "TBD"。每个删除任务都以"重新生成清单 + 二次复核"开头而不是照抄本文档的清单；Task 2 的 publisher 实现给出了两个必须注意的约束（execution_id 来源、共享引擎下不能持有 per-request 状态）而不是留白；Task 5 Step 2 给出了两个具体方案并标明推荐项。

**风险排序** —— Task 2 风险最高：它触碰后端共享引擎，做错会重新引入后端 Task 9 修掉的跨请求事件串流，且会打开一个当前无上限的内存 store（Step 4 专门处理）。Task 7 次之，删除面最大。Task 1 风险最低且为后续任务提供门禁，因此排在最前。
