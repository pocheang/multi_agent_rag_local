# UI 优化：思考状态显示

## 优化目标

将 AI 回答执行过程 UI 从开发日志风格改为 ChatGPT 风格的简洁展示：

- ✅ 用户发送问题后，显示简洁的「正在思考…」状态
- ✅ 添加轻量动态效果（呼吸动画的圆圈图标）
- ✅ 执行过程默认隐藏，通过「已思考 N 秒 ▾」按钮折叠展开
- ✅ 过滤掉技术字段（execution started、trace、STATUS）
- ✅ AI 开始输出答案后，「正在思考…」自动消失
- ✅ 思考状态和最终答案在同一个助手消息区域
- ✅ 保持流式响应逻辑，只修改前端展示

## 实现的文件

### 1. 新建组件 - ThinkingIndicator.tsx

**路径**: `frontend/src/pages/chat/components/ThinkingIndicator.tsx`

**功能**:
- 显示「◌ 正在思考」指示器
- 使用 CSS 动画实现呼吸效果
- 简洁轻量，不依赖复杂的 JavaScript 动画

```tsx
export function ThinkingIndicator({ elapsedSeconds }: ThinkingIndicatorProps) {
  return (
    <div className="thinking-indicator">
      <span className="thinking-dots" aria-hidden="true"></span>
      <span className="thinking-text">正在思考</span>
    </div>
  );
}
```

### 2. 新建样式 - thinking-indicator.css

**路径**: `frontend/src/styles/components/thinking-indicator.css`

**功能**:
- 思考指示器样式（呼吸动画）
- 可折叠的执行过程按钮样式
- 深色和浅色主题支持

**关键样式**:
```css
.thinking-dots::before {
  content: "◌";
  animation: thinking-pulse 1.4s ease-in-out infinite;
}

@keyframes thinking-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.95); }
  50% { opacity: 1; transform: scale(1.05); }
}

.process-summary-toggle {
  /* 轻量透明按钮，默认折叠 */
  background: transparent;
  border: 1px solid rgba(111, 132, 189, 0.15);
}
```

### 3. 修改 MessageCard.tsx

**路径**: `frontend/src/pages/chat/components/MessageCard.tsx`

**关键修改**:

1. **添加思考状态检测**:
```tsx
const isStreaming = message.message_id === "local-assistant-stream";
const isThinking = isStreaming && !message.content;
```

2. **条件渲染思考指示器或内容**:
```tsx
{isThinking ? (
  <ThinkingIndicator elapsedSeconds={getElapsedSeconds()} />
) : (
  <div className="markdown">
    <MarkdownBlock text={message.content || ""} />
  </div>
)}
```

3. **添加可折叠的执行过程按钮**:
```tsx
{hasExecutionSteps && (
  <>
    <button
      className={`process-summary-toggle ${processExpanded ? "expanded" : ""}`}
      onClick={() => setProcessExpanded(!processExpanded)}
    >
      <span>已思考 {getElapsedSeconds()} 秒</span>
      <span className="toggle-arrow">▾</span>
    </button>

    {processExpanded && (
      <CollapsibleSection open={true} ...>
        {/* 执行步骤详情 */}
      </CollapsibleSection>
    )}
  </>
)}
```

4. **过滤技术字段**:
```tsx
const shouldShow = !["execution started", "trace", "STATUS"].some(
  (tech) => step.label?.toLowerCase().includes(tech.toLowerCase())
);

if (!shouldShow) return null;
```

### 4. 修改 streamEventHandlers.ts

**路径**: `frontend/src/pages/chat/hooks/streamEventHandlers.ts`

**关键修改**:

在 `pushExecutionStep` 函数中添加技术字段过滤：

```tsx
function pushExecutionStep(ctx: StreamEventContext, kind: string, label: string, detail = ""): StreamEventContext {
  // 过滤掉技术/调试标签
  const technicalKeywords = ["execution started", "trace", "STATUS", "execution_started"];
  const shouldFilter = technicalKeywords.some((keyword) =>
    label.toLowerCase().includes(keyword.toLowerCase())
  );

  if (shouldFilter) {
    // 更新 current_status 但不添加到 execution_steps
    return {
      ...ctx,
      meta: {
        ...ctx.meta,
        current_status: label,
      },
    };
  }

  // 正常处理其他步骤
  const step: ExecutionStep = { kind, label, detail, at: new Date().toISOString() };
  const updatedSteps = [...ctx.executionSteps, step].slice(-24);
  return {
    ...ctx,
    executionSteps: updatedSteps,
    meta: {
      ...ctx.meta,
      current_status: label,
      execution_steps: updatedSteps,
    },
  };
}
```

### 5. 修改 main.css

**路径**: `frontend/src/styles/main.css`

添加思考指示器样式导入：

```css
@import "./components/thinking-indicator.css";
```

## 用户体验流程

### Before（优化前）:
```
用户消息: 设计RAG系统

助手消息:
┌─────────────────────────────┐
│ 执行过程                    │
│ ┌─────────────────────────┐ │
│ │ STATUS execution started │ │
│ │ trace                    │ │
│ │ 建立通路                 │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘

正在思考

（大卡片占据聊天区域）
```

### After（优化后）:
```
用户消息: 设计RAG系统

助手消息:
◌ 正在思考

（流式输出开始后自动替换为）

助手消息:
RAG 系统可以按照以下方式设计……

已思考 4 秒 ▾  ← 点击展开查看详细过程
```

## 技术要点

1. **状态判断**: 使用 `message.message_id === "local-assistant-stream" && !message.content` 判断思考状态
2. **无缝切换**: 思考指示器和答案内容在同一个 `<div>` 内条件渲染，避免页面跳动
3. **过滤机制**: 
   - 前端组件层：MessageCard 过滤显示
   - 数据层：streamEventHandlers 过滤存储
4. **性能优化**: 使用 CSS 动画而非 JavaScript 定时器
5. **可访问性**: 添加 `aria-label` 和 `aria-expanded` 属性

## 保留的后端逻辑

✅ **不影响后端**：
- Router、Planner、RAG、Tool Calling、Web Search 等执行状态仍然正常收集
- SSE 流式响应逻辑完全保留
- execution_steps 数据结构不变
- Agent 实际执行流程不变

只修改了前端展示方式，后端完全无感知。

## 测试要点

1. ✅ 发送问题后显示「正在思考」
2. ✅ 开始流式输出答案后，「正在思考」消失
3. ✅ 答案完成后，显示「已思考 N 秒 ▾」按钮
4. ✅ 点击按钮展开/折叠执行过程
5. ✅ 执行过程中不显示 "execution started"、"trace"、"STATUS"
6. ✅ 深色和浅色主题下样式正常
7. ✅ 移动端响应式布局正常

## 国际化支持

当前硬编码为中文，后续可以添加 i18n 支持：

```tsx
// 在 i18n 文件中添加
{
  "components.messages.thinking": "正在思考",
  "components.messages.thoughtFor": "已思考 {seconds} 秒",
  "components.messages.showProcess": "查看执行过程",
  "components.messages.hideProcess": "隐藏执行过程"
}
```

## 相关文件

- `frontend/src/pages/chat/components/ThinkingIndicator.tsx` (新建)
- `frontend/src/pages/chat/components/MessageCard.tsx` (修改)
- `frontend/src/pages/chat/hooks/streamEventHandlers.ts` (修改)
- `frontend/src/styles/components/thinking-indicator.css` (新建)
- `frontend/src/styles/main.css` (修改)

## 完成时间

2026-08-17 17:07
