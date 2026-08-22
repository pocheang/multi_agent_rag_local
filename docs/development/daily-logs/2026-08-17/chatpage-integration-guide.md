# ChatPage 集成指南

## 概述

本文档说明如何将 `ClarificationPrompt` 组件集成到 ChatPage 中。

## 集成步骤

### 1. 导入组件和类型

在 `frontend/src/pages/ChatPage.tsx` 顶部添加：

```tsx
import { ClarificationPrompt } from "@/pages/chat/components/ClarificationPrompt";
import { clarificationApi } from "@/services/api/chat";
import type { ClarificationResponse, ClarificationQuestion, ClarificationContext } from "@/types/api";
```

### 2. 添加状态管理

在 `useChatPageState` 或 `ChatPage` 组件中添加状态：

```tsx
const [clarification, setClarification] = useState<ClarificationResponse | null>(null);
const [isClarifying, setIsClarifying] = useState(false);
```

### 3. 修改查询逻辑

将原来的 `handleSend` 或查询函数改为先检查澄清：

```tsx
const handleSendWithClarification = async (questionText: string) => {
  if (!currentSessionId || !questionText.trim()) return;

  setIsSending(true);
  setRunStatus("preparing");

  try {
    // 调用澄清检查API
    const response = await clarificationApi.checkClarification({
      question: questionText,
      session_id: currentSessionId,
    });

    if (response.action === "NEED_CLARIFICATION") {
      // 显示澄清提示
      setClarification(response);
      setIsSending(false);
      setRunStatus(null);
      return;
    }

    // 信息充足，执行实际查询
    await executeQuery(questionText);
  } catch (error) {
    console.error("Clarification check failed:", error);
    setError("Failed to check clarification");
    setIsSending(false);
    setRunStatus(null);
  }
};
```

### 4. 处理澄清回答

添加处理用户澄清回答的函数：

```tsx
const handleClarificationAnswer = async (fieldName: string, answer: string) => {
  if (!clarification || !currentSessionId) return;

  setIsClarifying(true);

  try {
    // 提交澄清答案并重新检查
    const response = await clarificationApi.checkClarification({
      question: question,  // 原始问题
      session_id: currentSessionId,
      field_name: fieldName,
      answer: answer,
    });

    if (response.action === "NEED_CLARIFICATION") {
      // 还需要继续澄清
      setClarification(response);
    } else {
      // 信息充足，执行查询
      setClarification(null);
      await executeQuery(question);
    }
  } catch (error) {
    console.error("Clarification answer failed:", error);
    setError("Failed to submit clarification");
  } finally {
    setIsClarifying(false);
  }
};
```

### 5. 处理跳过澄清

添加跳过澄清的函数：

```tsx
const handleClarificationSkip = async () => {
  if (!currentSessionId) return;

  try {
    // 重置澄清上下文
    await clarificationApi.resetClarification(currentSessionId);
    
    // 清除澄清状态
    setClarification(null);
    
    // 执行查询（使用已收集的信息）
    await executeQuery(question);
  } catch (error) {
    console.error("Skip clarification failed:", error);
    setError("Failed to skip clarification");
  }
};
```

### 6. 在 JSX 中渲染组件

在消息列表和输入框之间插入澄清提示：

```tsx
<div className="chat-container">
  {/* 顶部栏 */}
  <ChatTopbar {...topbarProps} />

  {/* 侧边栏 */}
  <ChatSidebar {...sidebarProps} />

  {/* 主内容区 */}
  <div className="chat-main">
    {/* 消息列表 */}
    <ChatMessages messages={messages} />

    {/* 澄清提示（如果需要）*/}
    {clarification && clarification.action === "NEED_CLARIFICATION" && (
      <ClarificationPrompt
        question={clarification.clarification!}
        context={clarification.context}
        onAnswer={handleClarificationAnswer}
        onSkip={handleClarificationSkip}
        isSubmitting={isClarifying}
      />
    )}

    {/* 输入框 */}
    <ChatComposer
      value={question}
      onChange={setQuestion}
      onSubmit={handleSendWithClarification}
      disabled={isSending || !!clarification}  // 澄清时禁用输入
    />
  </div>
</div>
```

### 7. 导入样式

在 `frontend/src/styles/main.css` 中添加：

```css
@import './components/clarification-prompt.css';
```

## 完整示例

```tsx
// ChatPage.tsx 关键部分

import { ClarificationPrompt } from "@/pages/chat/components/ClarificationPrompt";
import { clarificationApi } from "@/services/api/chat";

export function ChatPage(props: Props) {
  // ... 现有状态 ...
  
  // 新增澄清状态
  const [clarification, setClarification] = useState<ClarificationResponse | null>(null);
  const [isClarifying, setIsClarifying] = useState(false);

  // 修改后的发送函数
  const handleSendWithClarification = async (questionText: string) => {
    if (!currentSessionId || !questionText.trim()) return;

    setIsSending(true);
    setRunStatus("preparing");

    try {
      const response = await clarificationApi.checkClarification({
        question: questionText,
        session_id: currentSessionId,
      });

      if (response.action === "NEED_CLARIFICATION") {
        setClarification(response);
        setIsSending(false);
        setRunStatus(null);
        return;
      }

      await executeQuery(questionText);
    } catch (error) {
      console.error("Clarification check failed:", error);
      setError("Failed to check clarification");
      setIsSending(false);
      setRunStatus(null);
    }
  };

  // 处理澄清回答
  const handleClarificationAnswer = async (fieldName: string, answer: string) => {
    if (!clarification || !currentSessionId) return;

    setIsClarifying(true);

    try {
      const response = await clarificationApi.checkClarification({
        question: question,
        session_id: currentSessionId,
        field_name: fieldName,
        answer: answer,
      });

      if (response.action === "NEED_CLARIFICATION") {
        setClarification(response);
      } else {
        setClarification(null);
        await executeQuery(question);
      }
    } catch (error) {
      console.error("Clarification answer failed:", error);
      setError("Failed to submit clarification");
    } finally {
      setIsClarifying(false);
    }
  };

  // 处理跳过
  const handleClarificationSkip = async () => {
    if (!currentSessionId) return;

    try {
      await clarificationApi.resetClarification(currentSessionId);
      setClarification(null);
      await executeQuery(question);
    } catch (error) {
      console.error("Skip clarification failed:", error);
      setError("Failed to skip clarification");
    }
  };

  return (
    <div className="chat-page">
      {/* ... 现有 UI ... */}
      
      <div className="chat-main">
        <ChatMessages messages={messages} />
        
        {/* 澄清提示 */}
        {clarification && clarification.action === "NEED_CLARIFICATION" && (
          <ClarificationPrompt
            question={clarification.clarification!}
            context={clarification.context}
            onAnswer={handleClarificationAnswer}
            onSkip={handleClarificationSkip}
            isSubmitting={isClarifying}
          />
        )}
        
        <ChatComposer
          value={question}
          onChange={setQuestion}
          onSubmit={handleSendWithClarification}
          disabled={isSending || !!clarification}
        />
      </div>
    </div>
  );
}
```

## 测试检查清单

- [ ] 简单问题不触发澄清（直接执行）
- [ ] 复杂问题触发澄清提示
- [ ] 可以选择预定义选项
- [ ] 可以输入自定义答案
- [ ] 提交后继续下一轮澄清或执行查询
- [ ] "跳过剩余问题"按钮工作正常
- [ ] 进度显示正确（第 X/Y 轮）
- [ ] 已收集信息正确显示
- [ ] 澄清时输入框被禁用
- [ ] 样式在深色/浅色主题下正常
- [ ] 移动端响应式布局正常

## 注意事项

1. **保存原始问题**: 在澄清过程中需要保持原始问题不变
2. **禁用输入**: 澄清期间禁用消息输入框，避免混淆
3. **错误处理**: 澄清API调用失败时应有友好提示
4. **会话恢复**: 刷新页面后不会保留澄清状态（正常行为）
5. **并发控制**: 确保不会同时触发多个澄清流程

## API端点

- `POST /api/v1/clarification/check` - 检查是否需要澄清
- `POST /api/v1/clarification/reset/{session_id}` - 重置澄清
- `GET /api/v1/clarification/context/{session_id}` - 获取澄清上下文

## 相关文件

- 组件: `frontend/src/pages/chat/components/ClarificationPrompt.tsx`
- 样式: `frontend/src/styles/components/clarification-prompt.css`
- API: `frontend/src/services/api/chat.ts` (clarificationApi)
- 类型: `frontend/src/types/api.ts`
- 翻译: `frontend/src/i18n/locales/{en,zh}.json`
