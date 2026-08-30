# 2026-08-30 完成总结 / Summary

## 一句话

Admin ops 的基准（benchmark）和回放（replay）跑批从来就没成功过——调用管道时没带用户身份，
每一条查询都在工作流第一个节点 `privacy_permission` 上 fail-closed 报错。已修复并补上回归测试。

## 完成的工作

| 项 | 内容 |
|---|---|
| 定位 | `_execute_standard_profile` 不传 `user` → `PipelineRequest.user=None` → `OrchestrationRequest.actor=None` → `AccessScopeResolver.resolve()` 抛 `AccessScopeError` |
| 影响面 | `POST /admin/ops/benchmark/run`、`POST /admin/ops/replay/run` 两个入口的**全部**查询 |
| 修复 | `app/api/routes/admin/ops.py`：给 `_execute_standard_profile` 加上必填的 `user` 形参并构造 `PipelineUser`；两处 `queue.submit` 改用 `partial(..., user=user)` 把管理员身份带进后台队列 |
| 测试 | 新增 `tests/api/test_admin_ops_benchmark_identity.py`（4 条），跑真实 orchestration 图，只对调模型的叶子节点打桩 |
| 决策 | 跑批语料 = 发起管理员的可见范围，不额外收窄；理由与被否方案见 `decisions.md` |
| 文档 | `CLAUDE.md` 新增一条说明（放在 Important Notes 的 Circuit breaker 之后） |

## 验证结果

- 修复前：`_execute_standard_profile('smoke')` → `StageExecutionError: ... authenticated user identity is required`（已实测复现）
- 4 条新测试在 `HEAD` 上全部失败、修复后全部通过（已实测）
- `pytest -q` → **66 passed**（此前 62）
- `ruff check .` / `ruff format --check .` → 通过
- OpenAPI 端点普查 → **149**，与基线一致（未改动任何路由）

## 未完成 / 遗留

1. **趋势记录不含跑批者身份**。`GET /admin/ops/benchmark/trends` 的历史条目里没有 `user_id`，
   而现在不同管理员跑出来的数字未必可比。要么在 `run_benchmark` 写入的 entry 里补记身份，
   要么建专用基准用户（见 `decisions.md` 末尾），目前两者都没做。
2. **`PipelineUser` 构造逻辑第三次重复**。`public/query.py:249`、`public/sessions.py:209`
   和现在的 `admin/ops.py` 各写了一遍同样的 5 行。本次刻意保持与既有写法一致而没有抽公共函数，
   避免把改动面扩散到不相关文件；如果出现第四处，值得抽到 `pipeline_contract.py`。
3. **未核对 `docs/superpowers/plans/2026-08-29-user-data-isolation.md`**。该计划文档在本 worktree
   中不存在（应在另一分支），所以无法对照其"阶段 1 暴露的两个既有问题"逐条确认，
   本次只处理了报告中明确描述的这一个问题。

## 经验教训

- **fail-closed 的守卫会把"没人调用过"的代码路径直接照出来。** 这个 bug 不是回归——
  `resolve()` 那一行早于用户数据隔离的工作。是访问控制收紧之后，一条本来就没人验证过的
  内部路径立刻暴露了。补身份的时候顺带确认了：全项目只有 `admin/ops.py` 这一处调用方漏传。
- **回归测试要跑真图，不能只断言"参数传进去了"。** 最初想写成"检查 `PipelineRequest.user`
  不为 None"，但那只覆盖了 wiring，证明不了 resolver 会接受这个 actor。改成注入桩
  capabilities、保留真实 `PrivacyService` 和 `AccessScopeResolver` 之后，测试才真正复刻了
  线上的失败方式——也才在 `HEAD` 上如期失败。
- **给跑批补身份不是纯粹的 bug 修复，它改变了被测量的东西。** 修好之后基准衡量的语料
  从"全部"变成"该管理员可见的"。这类语义变化必须写进文档，否则下一个看趋势曲线的人
  会把语料差异误读成检索质量波动。
