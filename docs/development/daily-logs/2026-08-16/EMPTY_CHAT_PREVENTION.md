# 空聊天防重复创建功能

## 功能说明

当用户点击"新建聊天"按钮时，系统会检查当前聊天是否为空（没有用户消息）。如果当前聊天为空，系统将不会创建新的聊天记录，而是保持在当前空白聊天页面。

## 实现逻辑

### 判断规则

**当前聊天为空的判断条件：**
- 当前聊天中没有任何 `role === "user"` 的消息
- 当前存在 `currentSessionId`（已有会话ID）

**有效用户消息的定义：**
- 只有 `role === "user"` 的消息才算有效内容
- 系统消息、助手回复、欢迎语、占位符等都不算有效内容

### 行为逻辑

| 当前状态 | 用户操作 | 系统行为 |
|---------|---------|---------|
| 当前聊天为空（无用户消息） | 点击"新建聊天" | **不创建**新会话，显示提示信息，保持当前聊天 |
| 当前聊天非空（有用户消息） | 点击"新建聊天" | **正常创建**新会话，切换到新聊天 |
| 没有当前会话（首次进入） | 点击"新建聊天" | **正常创建**新会话 |

### 用户反馈

**英文提示：**
```
Current chat is empty. Continue here instead of creating new chat.
```

**中文提示：**
```
当前聊天为空，将继续在此聊天而不创建新会话。
```

提示类型：`info` toast，自动消失

## 代码修改

### 1. 核心逻辑 - `useSessionActions.ts`

```typescript
const createSession = async (signal?: AbortSignal) => {
  // Check if current chat is empty (no user messages)
  const hasUserMessages = messages.some((msg) => msg.role === "user");

  // If current chat is empty, don't create a new session - reuse current chat
  if (!hasUserMessages && currentSessionId) {
    notify(t("components.chat.emptyChatNotice"), "info");
    closeSidebar();
    return currentSessionId;
  }

  // ... 正常创建会话的逻辑
};
```

### 2. 参数传递链

**ChatPage.tsx** → **useChatActions.ts** → **useSessionActions.ts**

传递 `messages` 状态，用于判断当前聊天是否有用户消息。

### 3. 国际化配置

**en.json:**
```json
"emptyChatNotice": "Current chat is empty. Continue here instead of creating new chat."
```

**zh.json:**
```json
"emptyChatNotice": "当前聊天为空，将继续在此聊天而不创建新会话。"
```

## 使用场景

### 场景 1：首次进入应用
1. 用户首次进入，系统自动创建一个空会话
2. 用户还未输入任何消息
3. 用户点击"新建聊天"
4. **结果**：不创建新会话，显示提示，保持当前空白聊天

### 场景 2：删除所有消息后
1. 用户在聊天中删除了所有用户消息
2. 聊天变为空（只剩系统/助手消息或完全为空）
3. 用户点击"新建聊天"
4. **结果**：不创建新会话，显示提示，保持当前聊天

### 场景 3：正常使用
1. 用户已经发送了至少一条消息
2. 用户点击"新建聊天"
3. **结果**：正常创建新会话，切换到新聊天

## 优点

1. **避免空会话累积**：防止侧边栏充斥大量无意义的空白会话
2. **用户体验优化**：减少不必要的操作和混淆
3. **数据库优化**：减少无效的会话记录
4. **清晰的反馈**：通过 toast 提示告知用户为什么没有创建新会话

## 测试验证

### 手动测试步骤

1. **测试空聊天阻止创建**
   - 启动应用，进入聊天页面
   - 不输入任何消息
   - 点击侧边栏"新建聊天"按钮
   - 验证：应该看到提示信息，不创建新会话

2. **测试非空聊天正常创建**
   - 输入一条消息并发送
   - 点击"新建聊天"按钮
   - 验证：应该正常创建新会话并切换

3. **测试多语言**
   - 切换语言到中文
   - 重复上述测试
   - 验证：提示信息应为中文

## 技术栈

- **React Hooks**: `useSessionActions`
- **i18n**: `react-i18next` 多语言支持
- **TypeScript**: 类型安全
- **Zustand**: 状态管理（通过 `useChatStore`）

## 相关文件

- `frontend/src/pages/chat/hooks/useSessionActions.ts` - 核心逻辑
- `frontend/src/pages/chat/hooks/useChatActions.ts` - 参数传递
- `frontend/src/pages/ChatPage.tsx` - 组件集成
- `frontend/src/i18n/locales/en.json` - 英文翻译
- `frontend/src/i18n/locales/zh.json` - 中文翻译
- `frontend/src/pages/chat/components/SessionList.tsx` - 新建聊天按钮
