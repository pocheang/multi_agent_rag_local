# 2026-08-30 实现记录 / Implementation

## Admin ops 基准与回放跑批的身份缺失修复

### 问题 (Problem)

`app/api/routes/admin/ops.py::_execute_standard_profile` 调用
`execute_standard_compatibility(...)` 时没有传 `user`，于是：

```
PipelineRequest.user = None
  → OrchestrationRequest.actor = None
    → AccessScopeResolver.resolve(None, ...) 抛 AccessScopeError
```

复现（修复前）：

```
python -c "from app.api.routes.admin.ops import _execute_standard_profile; _execute_standard_profile('smoke')"
StageExecutionError: orchestration stage 'privacy_permission' failed: authenticated user identity is required
```

`privacy_permission` 是 LangGraph 工作流的第一个节点（`app/orchestration/langgraph/workflow.py:43`），
所以 **每一条** 基准/回放查询都在到达 router 之前就失败了。两个入口都受影响：

- `POST /admin/ops/benchmark/run` (`ops.py`, `queue.submit(run_benchmark, ...)`)
- `POST /admin/ops/replay/run` (`ops.py`, `queue.submit(run_replay, ...)`)

这不是回归：`resolve()` 这一行早于 2026-08-30 的用户数据隔离工作，`git diff` 确认未被改动。

### 改动 (Changes)

`app/api/routes/admin/ops.py`

1. `_execute_standard_profile(question)` → `_execute_standard_profile(question, *, user)`，
   由 `user` dict 构造 `PipelineUser`，与 `public/query.py` 和 `public/sessions.py`
   中已有的写法保持一致（`user_id` / `username` / `role` / `permissions`，不传 `tenant_id`，
   由 `to_orchestration_request` 回落到 `tenant_id = user_id`）。
2. 两个 `queue.submit(...)` 改用 `functools.partial(_execute_standard_profile, user=user)`，
   把发起请求的管理员身份带进后台队列。`run_benchmark` / `run_replay` 的
   `execute_query: Callable[[str], dict]` 契约不变。

`allowed_sources` 仍然不传（`None`）：`AccessScopeResolver._intersect_requested(None, visible)`
会直接返回该管理员可见的全部来源，与显式传 `_allowed_sources_for_user(user)` 等价，但少一次
文档元数据查询。

### 测试 (Tests)

新增 `tests/api/test_admin_ops_benchmark_identity.py`（4 条）。测试跑的是**真实**的
orchestration 图——真实 `PrivacyService`、真实 `AccessScopeResolver`——只把 router /
retriever / synthesizer 等调用模型的叶子节点打桩，因此它们会以和线上完全相同的方式
在缺少 actor 时失败：

- `test_benchmark_query_completes_under_an_admin_identity` — 核心回归
- `test_missing_identity_still_fails_closed` — 守住 fail-closed 行为
- `test_benchmark_endpoint_hands_the_queue_an_identified_executor`
- `test_replay_endpoint_hands_the_queue_an_identified_executor`

已验证这 4 条在修复前全部失败、修复后全部通过。

全量：`pytest -q` → 66 passed。`ruff check .` / `ruff format --check .` 通过。

---

## 第二部分:基准查询集缺失

修好身份之后 `POST /admin/ops/benchmark/run` 仍然出不了数——`run_benchmark` 只读
`data/eval/benchmark_queries.txt`,而 `data/` 是 gitignored 的运行时目录,本机根本没有
`data/eval/`。查询集为空时函数抛 `ValueError("benchmark query set is empty")`,而且这个
异常死在后台队列的 worker 里,HTTP 调用方只拿到 202,完全看不到。

### 改动

`app/services/runtime/runtime_ops.py`

1. 新增 `_BENCHMARK_QUERY_PATHS`,按序取第一个存在的:
   - `data/eval/benchmark_queries.txt` —— 部署环境专属覆盖,不入库
   - `config/eval/benchmark_queries.txt` —— 随仓库发布的默认集,新检出即可用
2. 解析时跳过 `#` 开头的注释行。此前只过滤空行,查询集文件里任何说明性文字都会被
   当成一条基准查询真的跑出去。

`config/eval/benchmark_queries.txt`(新增,已入库)

12 条中英文查询。**刻意写成与语料无关的通用问法**:它衡量的是管道延迟和各路由分支的
开销,不是检索质量。`grounding_support_ratio` 和 `citations` 要有意义,查询必须与
`data/docs/` 里的真实文档对得上——本机 `data/docs/` 为空,所以这两个指标现在跑出来是 0。

### 为什么放 `config/` 而不是 `data/`

先试过在 `.gitignore` 里给 `data/eval/` 开白名单,不成立:git 不会descend进被排除的父目录,
`!data/eval/` 对 `data/` 已被忽略的情况无效。而且基准查询集本来就是评测夹具、属于配置,
不是运行时数据。`config/` 已跟版本,放这里既不用改 `.gitignore` 语义,又保留了
`data/eval/` 作为部署覆盖点。

### 测试

新增 `tests/services/test_benchmark_query_set.py`(5 条):默认集存在且被登记、注释与空行
不被当查询、部署覆盖优先于默认集、新检出场景下默认集能跑通、查询集彻底缺失时仍然报错。

全量:`pytest -q` → **71 passed**。ruff 通过。
