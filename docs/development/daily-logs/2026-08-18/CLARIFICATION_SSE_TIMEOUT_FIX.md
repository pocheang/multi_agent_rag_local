# 澄清流程中 SSE 超时问题修复

## 问题描述

在多轮澄清功能中，当用户提供补充信息后继续执行查询时，前端会出现 SSE（Server-Sent Events）请求超时错误：

```
Uncaught (in promise) ApiError: Request timed out
  at client.ts:162
  at fetchWithTimeout
  at authFetch
  at streamExecutionEvents
```

网络请求显示 `/api/v1/orchestration/executions/{execution_id}/events` 端点在 30 秒后超时，状态为 `NS_BINDING_ABORTED`。

## 根本原因

### 问题流程

1. 用户在澄清阶段提供补充信息
2. 前端调用 `/api/v1/clarification/check` 检查是否需要继续澄清
3. 如果返回 `CONTINUE`，前端调用 `messageActions.ask()` 发起正常查询
4. 查询流开始，后端发送 `execution_started` 事件（包含 `execution_id`）
5. 前端收到 `execution_id` 后立即订阅 SSE 流：`/api/v1/orchestration/executions/{execution_id}/events`
6. **问题**：SSE 请求使用默认的 30 秒超时（`client.ts:147`）
7. 如果执行时间超过 30 秒，或者连接建立时有延迟，SSE 请求会超时

### 代码位置

**前端**：
- `frontend/src/services/http/client.ts:147` - `fetchWithTimeout` 默认超时 30 秒
- `frontend/src/services/execution/execution-api.ts:10-13` - 订阅执行事件的 SSE 流

**SSE 的特性**：
- SSE（Server-Sent Events）是**长连接**，设计用于持续推送事件
- 它应该保持连接直到：
  1. 执行完成（服务器发送终止事件）
  2. 客户端主动取消（通过 AbortSignal）
  3. 连接断开
- **不应该有固定的超时限制**

## 修复方案

修改 `frontend/src/services/execution/execution-api.ts`，在订阅执行事件时禁用超时：

```typescript
export async function streamExecutionEvents(
  executionId: string,
  signal: AbortSignal,
  onEvent: (event: ExecutionEvent) => void,
): Promise<void> {
  const response = await authFetch(
    `/api/v1/orchestration/executions/${encodeURIComponent(executionId)}/events`,
    { signal },
    { timeoutMs: 0 }, // ✅ SSE 流应该没有超时 - 它们是长连接
  );
  if (!response.ok) return;
  await consumeExecutionEventStream(response, onEvent, signal);
}
```

### 为什么 `timeoutMs: 0` 可以工作

在 `client.ts:130`：

```typescript
const timeoutId = timeoutMs && timeoutMs > 0
  ? globalThis.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs)
  : undefined;
```

当 `timeoutMs` 为 `0` 时，条件 `timeoutMs && timeoutMs > 0` 为 `false`，因此不会设置超时定时器。

## 测试步骤

1. 启动后端和前端服务
2. 发起一个需要澄清的查询（例如：复杂的 RAG 设计问题）
3. 在澄清对话框中提供补充信息
4. 观察查询执行过程
5. 验证：
   - SSE 流不会在 30 秒后超时
   - 执行跟踪面板正常显示执行步骤
   - 查询能够正常完成，即使执行时间超过 30 秒

## 影响范围

- **修改的文件**：`frontend/src/services/execution/execution-api.ts`
- **影响的功能**：所有使用执行跟踪的查询（不仅限于澄清流程）
- **向后兼容性**：✅ 完全兼容，只是移除了不必要的超时限制
- **性能影响**：✅ 无负面影响，实际上改善了用户体验

## 相关文件

- `frontend/src/services/http/client.ts` - HTTP 客户端和超时逻辑
- `frontend/src/services/execution/execution-api.ts` - 执行事件流订阅
- `frontend/src/features/execution-trace/useExecutionTrace.ts` - 执行跟踪 Hook
- `app/api/routes/compatibility/orchestration.py` - SSE 端点实现
- `app/api/routes/public/query_stream.py` - 查询流端点和 execution_id 生成

## 日期

2026-08-18
