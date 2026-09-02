# 执行跟踪 SSE 连接中止问题修复

## 问题描述

在多轮澄清功能中，当用户提供补充信息后继续执行查询时，控制台出现错误：

```
Uncaught (in promise) DOMException: The operation was aborted.
  at onAbort (client.ts:125)
  at useExecutionTrace (useExecutionTrace.ts:14)
```

## 根本原因

### 问题流程

1. 用户发起查询，系统要求澄清
2. 用户提供补充信息
3. 前端调用 `messageActions.ask()` 开始新查询
4. **在 `ask()` 开始时**（`useMessageActions.ts:150`）：
   ```typescript
   onExecutionId?.(null);  // ❌ 设置 executionId 为 null
   ```
5. 这触发 `useExecutionTrace` 的 effect 清理函数
6. 清理函数调用 `controller.abort()`
7. 现有的 SSE 连接被中止
8. 控制台显示 "The operation was aborted" 错误

### 时序问题

```
旧查询执行中 → executionId = "abc-123" → SSE 连接活跃
                     ↓
新查询开始 → onExecutionId(null) → useEffect 清理 → controller.abort()
                     ↓
            SSE 连接被中止 ❌
                     ↓
新的 execution_started 事件到达 → executionId = "xyz-456"
                     ↓
            启动新的 SSE 连接
```

**问题**：在新的 executionId 到达之前，将 executionId 设为 null 会立即中止任何现有连接。

## 修复方案

修改 `frontend/src/features/execution-trace/useExecutionTrace.ts`，只在 executionId 有值时才启动连接：

```typescript
export function useExecutionTrace(executionId: string | null) {
  const [state, dispatch] = useReducer(reduceExecutionTrace, initialExecutionTraceState);

  useEffect(() => {
    // ✅ 只在 executionId 有值时重置状态
    if (executionId) {
      dispatch({ type: "execution_started" });
    }
    // ✅ 如果是 null，直接返回，不做任何操作
    if (!executionId) return;
    const controller = new AbortController();
    void streamExecutionEvents(executionId, controller.signal, (event) => dispatch({ type: "event_received", event }));
    return () => controller.abort();
  }, [executionId]);
  
  return {
    ...state,
    resolveApproval: () => dispatch({ type: "approval_resolved" }),
  };
}
```

### 修复后的行为

```
旧查询执行中 → executionId = "abc-123" → SSE 连接活跃
                     ↓
新查询开始 → onExecutionId(null) → useEffect: 什么都不做 ✅
                     ↓
            SSE 连接继续活跃
                     ↓
新的 execution_started 事件到达 → executionId = "xyz-456"
                     ↓
            旧连接被清理 → 新连接启动 ✅
```

## 与第一个修复的关系

这是**第二个独立的修复**，与之前的 SSE 超时修复配合使用：

### 修复 #1: SSE 超时问题
- **文件**：`frontend/src/services/execution/execution-api.ts`
- **问题**：SSE 流有 30 秒超时限制
- **修复**：设置 `timeoutMs: 0` 禁用超时
- **Commit**: `4d12b09f`

### 修复 #2: SSE 连接中止问题（当前）
- **文件**：`frontend/src/features/execution-trace/useExecutionTrace.ts`
- **问题**：executionId 重置为 null 时中止连接
- **修复**：忽略 null 值，只在有实际 ID 时启动/切换连接
- **Commit**: `af036b67`

## 测试步骤

1. 启动前端和后端
2. 发起需要澄清的查询
3. 提供补充信息
4. 观察：
   - ✅ 不应该出现 "The operation was aborted" 错误
   - ✅ 执行跟踪面板应该正常显示步骤
   - ✅ 查询应该能够完成，即使执行时间超过 30 秒

## 影响范围

- **修改的文件**：`frontend/src/features/execution-trace/useExecutionTrace.ts`
- **影响的功能**：所有使用执行跟踪的查询
- **向后兼容性**：✅ 完全兼容
- **副作用**：✅ 无负面影响

## 相关文件

- `frontend/src/features/execution-trace/useExecutionTrace.ts` - 修复位置
- `frontend/src/pages/chat/hooks/useMessageActions.ts` - onExecutionId(null) 调用位置
- `frontend/src/pages/ChatPage.tsx` - executionId 状态管理

## 日期

2026-08-18
