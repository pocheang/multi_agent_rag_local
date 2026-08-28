# Frontend Organization Implementation Plan

> 本计划以已确认的 2026-08-11-frontend-organization-design.md 为依据。执行期间按复选框更新状态。

**目标：** 在不改变路由、API 协议、认证、权限、消息流、上传、主题或语言行为的前提下，收敛前端 feature、service、类型和样式边界。

**架构：** 保留 pages/chat、pages/admin 和应用路由。通过兼容导出保护现有 HTTP 调用；execution trace、tool approval 和 integrations 拥有各自的公开类型、service、state 与 Panel。聊天流先兼容旧 SSE 和新的 execution-event 包络，再进行任何收敛。

**技术栈：** React 18、TypeScript、Vite、React Router、i18next/react-i18next、Ant Design、现有 CSS 分层。

## 1. 执行原则

- 小步修改：每次只处理一个逻辑模块，完成后重读涉及文件并更新本计划。
- 不修改 app、backend、server、database、migrations、scripts、tests、任何测试或 spec 文件、.env 与生产配置。
- 不新增、修改、补充或设计测试；只运行 TypeScript、构建、导入、CSS、路由和 Git 范围检查。
- 不改变 API URL、HTTP 方法、请求和响应字段、路由、认证、权限、消息流、上传、主题或语言。
- 当前 features、ChatPage、useMessageActions、package 及 Vitest 相关未提交改动是已确认的用户基线：保留且不回滚。
- 不删除任何文件。AIEditPanel、ReportEditor 与已删除的 agent tracking 文件均不在本计划的删除范围。
- 不全项目格式化、不引入依赖、不创建无意义 barrel export，也不提交用户未提交改动。

## 2. 执行顺序

1. 确认目录边界和导入基线。
2. 统一认证、权限和 execution event 类型。
3. 建立 HTTP 兼容入口及 execution/tool approval service。
4. 建立聊天流双协议适配器。
5. 收紧 ChatPage 的 runtime feature 挂载职责。
6. 整理 runtime feature 的 i18n、状态反馈和隔离样式。
7. 仅处理触及 select 样式中的优先级问题。
8. 完成静态验证和范围审查。

## 3. 文件变更表

| 文件 | 操作 | 原因 | 风险 |
|---|---|---|---|
| frontend/src/types/auth.ts | 新增 | 集中已知角色与前端身份类型 | 低 |
| frontend/src/types/api.ts | 修改 | 复用认证类型且保留 API 字段 | 中 |
| frontend/src/hooks/usePermissions.tsx | 修改 | 分离纯权限计算与 React Hook | 低 |
| frontend/src/features/execution-trace/types.ts | 新增 | 公开 execution event 契约 | 低 |
| frontend/src/features/execution-trace/sse.ts | 修改 | parser 只负责 SSE 解析/消费 | 中 |
| frontend/src/features/tool-approval/state.ts | 修改 | 从公开 event 类型导入 | 低 |
| frontend/src/services/http/client.ts | 新增 | 承接现有 HTTP client 实现 | 中 |
| frontend/src/lib/api-client.ts | 修改 | 保留无行为变化的兼容再导出 | 中 |
| frontend/src/services/execution/execution-api.ts | 新增 | 集中 execution event 流请求 | 中 |
| frontend/src/features/execution-trace/useExecutionTrace.ts | 修改 | 经 service 加载事件流 | 中 |
| frontend/src/features/tool-approval/toolApprovalApi.ts | 新增 | 集中审批确认请求 | 低 |
| frontend/src/features/tool-approval/ToolApprovalPanel.tsx | 修改 | Panel 不再拼接审批协议 | 低 |
| frontend/src/pages/chat/hooks/chatStreamAdapter.ts | 新增 | 同时处理 legacy SSE 与 execution envelope | 高 |
| frontend/src/pages/chat/hooks/useMessageActions.ts | 修改 | 通过适配器保留旧事件分发 | 高 |
| frontend/src/pages/chat/hooks/streamEventHandlers.ts | 修改 | 用明确类型替换触及路径的 any | 中 |
| frontend/src/pages/chat/components/ChatRuntimePanels.tsx | 新增 | 集中 runtime feature 挂载 | 低 |
| frontend/src/pages/ChatPage.tsx | 修改 | 保留页面组合，移除 runtime feature 细节 | 中 |
| frontend/src/features/execution-trace/ExecutionTracePanel.tsx | 修改 | i18n、语义状态和 feature 根类 | 低 |
| frontend/src/features/integrations/IntegrationsPanel.tsx | 修改 | i18n、空状态和 feature 根类 | 低 |
| frontend/src/styles/features/runtime-panels.css | 新增 | 隔离 runtime feature 样式 | 低 |
| frontend/src/styles/pages/chat-entry.css | 修改 | 引入 runtime feature 样式 | 低 |
| frontend/src/styles/components/forms/selects.css | 修改 | 消除可证明不需要的 !important | 中 |
| frontend/src/i18n/locales/en.json | 修改 | 新增 runtime feature 英文 key | 低 |
| frontend/src/i18n/locales/zh.json | 修改 | 新增 runtime feature 中文 key | 低 |
| docs/superpowers/plans/2026-08-11-frontend-organization-plan.md | 修改 | 记录步骤状态和实际验证 | 低 |

没有删除操作。未列出的 Admin、Landing、Report、AI Edit 与历史大主题文件均不在首轮修改范围。

## 4. 实施步骤

### 步骤 1：锁定目录边界与导入基线

**目标：** 确认用户基线和入口依赖，避免覆盖已有前端工作。

**涉及文件：**
- 修改：docs/superpowers/plans/2026-08-11-frontend-organization-plan.md
- 检查：frontend/src/main.tsx、frontend/src/App.tsx、frontend/src/styles/main.css、frontend/src/styles/pages/chat-entry.css、frontend/src/lib/api-client.ts、frontend/src/features

**修改内容：**
- 在本计划记录执行日期及 git status 的前端摘要。
- 记录 api-client 的现有导入方；后续移动必须由兼容再导出保护。
- 确认 App 路由和 route CSS entry，不创建 app 目录或移动页面入口。

**不修改的内容：** 路由、Vite、package、Vitest、测试和后端。

**依赖前置步骤：** 无。

**行为风险：** 低。

**完成标准：** 用户基线仍保留；路由、CSS entry、HTTP client 导入方均有记录。

**回滚方式：** 仅撤销本计划的执行状态记录。

**执行记录（2026-08-11）：**

- 前端基线保留：`frontend/package.json`、`frontend/package-lock.json`、`frontend/src/pages/ChatPage.tsx`、`frontend/src/pages/chat/hooks/useMessageActions.ts`、已删除的 agent tracking 文件、`frontend/src/features/**` 与 `frontend/vitest.config.ts`。
- `lib/api-client` 当前导入方：`features/execution-trace/useExecutionTrace.ts`、`features/tool-approval/ToolApprovalPanel.tsx`、`features/integrations/api.ts`、`pages/admin/AdminAgentQualityDashboard.tsx`、`pages/admin/AdminWebActivityDashboard.tsx`；后续迁移必须保留兼容再导出。
- `App.tsx` 路由入口与路径保持不变；`ChatPage.tsx` 继续按页面入口导入 `styles/pages/chat-entry.css`，不创建 app 目录或移动页面入口。
- `frontend/src/services` 当前尚未建立；本步骤不提前创建，留待步骤 3。

- [x] 运行 git status --short -- frontend docs/superpowers。
- [x] 检查所有 api-client 导入方、App 路由和 chat CSS entry。
- [x] 更新并勾选本步骤。

### 步骤 2：统一认证、权限与 execution event 类型

**目标：** 消除重复用户类型和 Hook 误用，并使 execution event 成为公开 feature 契约。

**涉及文件：**
- 新增：frontend/src/types/auth.ts、frontend/src/features/execution-trace/types.ts
- 修改：frontend/src/types/api.ts、frontend/src/hooks/usePermissions.tsx、frontend/src/features/execution-trace/sse.ts、frontend/src/features/tool-approval/state.ts
- 检查：frontend/src/pages/ChatPage.tsx、frontend/src/pages/chat/components/ChatTopbar.tsx、frontend/src/pages/chat/components/SessionList.tsx

**修改内容：**
- 定义 KnownUserRole、UserIdentity 和 toKnownUserRole；未知角色映射为 viewer，保持当前默认权限。
- AuthUser 复用身份类型，同时保持 user_id、username、display_name、role、status 字段名。
- 导出不依赖 React 的 getPermissionCheck；usePermissions 仅用 useMemo 包装该纯函数；hasPermission 直接调用纯函数。
- RoleBadge 使用 role-badge 和 role-badge--角色 的语义类名。
- 让 ExecutionEvent、stage、status、metadata 类型位于 execution-trace/types.ts；sse.ts 只解析和消费流；tool approval state 只从 types.ts 导入事件类型。

**不修改的内容：** 后端 RBAC、权限矩阵、用户 API 字段和 execution URL。

**依赖前置步骤：** 步骤 1。

**行为风险：** 中；错误的角色回退会改变 UI 权限。

**完成标准：** hasPermission 不调用 Hook；ChatPage 不使用角色断言；execution event 只有一个共享定义。

**回滚方式：** 仅回退本步骤的类型和权限变更，恢复基线导入。

**执行记录（2026-08-11）：**

- 新增 `frontend/src/types/auth.ts` 与 `frontend/src/features/execution-trace/types.ts`；`AuthUser` 复用 `UserIdentity`，未知角色统一映射为 `viewer`。
- `usePermissions` 的纯权限计算已拆为 `getPermissionCheck`；`hasPermission` 不再调用 Hook，ChatPage、ChatTopbar 与 SessionList 改用共享 `UserIdentity`，移除 `as UserRole`。
- execution event 的 DTO 与运行时守卫位于 `execution-trace/types.ts`；`sse.ts` 保留兼容导出并只负责 SSE 解析/消费，tool approval state 改从共享类型导入。
- `rg` 未发现新增 `any`、`as UserRole` 或普通函数中的 Hook 调用；`conda run -n rag-local npm run build` 通过（首次沙箱运行因 Vite 配置读取权限阻断，授权重跑成功）。

- [x] 新增两个共享类型文件并替换触及调用点。
- [x] 用 rg 检查触及文件没有新增 any、as UserRole 或普通函数中的 Hook 调用。
- [x] 运行 conda run -n rag-local npm run build。
- [x] 更新并勾选本步骤。

### 步骤 3：建立 HTTP 兼容入口与新增 feature service

**目标：** 让 HTTP 请求有清晰入口，并将 execution/approval 协议从 UI 中移出。

**涉及文件：**
- 新增：frontend/src/services/http/client.ts、frontend/src/services/execution/execution-api.ts、frontend/src/features/tool-approval/toolApprovalApi.ts
- 修改：frontend/src/lib/api-client.ts、frontend/src/features/execution-trace/useExecutionTrace.ts、frontend/src/features/tool-approval/ToolApprovalPanel.tsx
- 检查：所有引用 frontend/src/lib/api-client.ts 的文件

**修改内容：**
- 将现有 HTTP client 实现原样移到 services/http/client.ts，包括 URL、credentials、retry、ApiError、authFetch、authRequest 和解析逻辑。
- lib/api-client.ts 仅命名再导出 services/http/client.ts 的现有公共符号，禁止批量改动调用方。
- streamExecutionEvents 必须继续使用现有 execution event URL 和 authFetch，接收 executionId 与 AbortSignal。
- confirmToolApproval 必须继续 POST 到当前审批 URL，发送完全相同的 confirmed true 请求体；Panel 只调用该函数。
- useExecutionTrace 保留 AbortController 和 effect cleanup，只把直接 URL 请求改为 service 调用。

**不修改的内容：** appApi、其他领域 API、URL、HTTP 方法、认证和测试。

**依赖前置步骤：** 步骤 2。

**行为风险：** 中；HTTP client 兼容导出缺失会影响现有请求。

**完成标准：** 原 api-client 导入可解析；两个新增协议 URL 只出现在领域 service；构建通过。

**回滚方式：** 恢复 lib/api-client.ts 的完整实现并回退两个 service 与调用点。

**执行记录（2026-08-11）：**

- HTTP client 已移至 `frontend/src/services/http/client.ts`，`frontend/src/lib/api-client.ts` 保留原公共符号的兼容再导出，现有 lib/admin/feature 调用方未批量迁移。
- 新增 `services/execution/execution-api.ts` 与 `features/tool-approval/toolApprovalApi.ts`；execution URL 与 approval URL 各自只出现在对应 service，审批请求体仍为完全相同的 `{ confirmed: true }`。
- `useExecutionTrace` 保留 AbortController/effect cleanup，Panel 只调用 `confirmToolApproval`；导入检查与构建通过。

- [x] 移动 HTTP 实现并写入兼容再导出。
- [x] 新增 execution 和 tool approval service。
- [x] 替换 Hook/Panel 的直接协议调用。
- [x] 检查两个 URL 字符串只位于 service。
- [x] 运行构建，更新并勾选本步骤。

### 步骤 4：建立聊天流双协议适配器

**目标：** 保护现有流式回答、引用、图谱、错误、停止和 fallback，同时消费 execution-event 包络。

**涉及文件：**
- 新增：frontend/src/pages/chat/hooks/chatStreamAdapter.ts
- 修改：frontend/src/pages/chat/hooks/useMessageActions.ts、frontend/src/pages/chat/hooks/streamEventHandlers.ts
- 检查：frontend/src/features/execution-trace/sse.ts、frontend/src/pages/chat/hooks/streamMessageUpdater.ts、frontend/src/lib/app-api.ts

**修改内容：**
- 定义 ChatStreamEvent 联合：LegacyChatStreamEvent 与 ExecutionEnvelopeEvent。
- parseChatStreamFrame 先解析现有 data JSON legacy 事件，再识别 event: execution_event 并使用 execution parser；所有外部内容从 unknown 经类型守卫进入。
- legacy 分支必须继续分发 status、route、thought、error、vector_result、graph_result、web_result、answer_chunk、answer_reset、done 到现有 handler。
- execution envelope 仅更新 execution id、可映射状态以及 metadata 中明确包含的 content/answer mode；只有 failed 状态才触发错误。
- 保留 abort、session detail 刷新、网络断连非流 fallback、toast 与结束清理。

**不修改的内容：** query endpoint、后端事件格式、session API、测试。

**依赖前置步骤：** 步骤 2、步骤 3。

**行为风险：** 高；这是聊天主消息流。

**完成标准：** 所有 legacy handler 仍可达；execution event 可更新 trace；未知帧安全忽略；构建通过。

**回滚方式：** 单独回退适配器、message actions 和 handler 类型变更，恢复当前消息流基线。

**执行记录（2026-08-11）：**

- 新增 `pages/chat/hooks/chatStreamAdapter.ts`，定义 `LegacyChatStreamEvent`、`ExecutionEnvelopeEvent` 与联合事件；先解析 legacy `data` JSON，再解析 `event: execution_event`，未知帧安全忽略。
- `useMessageActions` 已恢复 status、route、thought、error、vector_result、graph_result、web_result、answer_chunk、answer_reset、done 的 legacy 分发，并保留 execution id、状态、content/answer mode 处理。
- execution envelope 仅在 `failed` 时抛错；legacy execution_started、stream_end、abort、session detail 刷新、非流 fallback、toast 与结束清理均保留。
- `streamEventHandlers.ts` 触及路径已移除 `any`，通过显式 unknown 守卫转换 citation、graph 与结果字段；所有 handler 仍有调用点，构建通过。

- [x] 新增联合事件类型和 frame parser。
- [x] 在 useMessageActions 中恢复 legacy 分发并新增 execution 分发。
- [x] 检查全部 handler 名称仍存在调用点。
- [x] 运行构建并逐行审阅消息流 diff。
- [x] 更新并勾选本步骤。

### 步骤 5：收紧 ChatPage 的 runtime feature 组合职责

**目标：** 使 ChatPage 保持页面组合根，把 trace、审批和 integrations 的组合挂载移至专用组件。

**涉及文件：**
- 新增：frontend/src/pages/chat/components/ChatRuntimePanels.tsx
- 修改：frontend/src/pages/ChatPage.tsx
- 检查：三个 runtime feature Panel

**修改内容：**
- ChatRuntimePanels 接收 executionId，在内部调用 useExecutionTrace，并依照当前顺序渲染 ExecutionTracePanel、ToolApprovalPanel、IntegrationsPanel。
- ChatPage 保留 executionId/setExecutionId 和对 useMessageActions 的 onExecutionId；移除三个 Panel import 与 trace Hook。
- 新组件仍放在主内容之后、ToastStack、ApiSettings、KeyboardHelp 之前。

**不修改的内容：** 会话、上传、消息、提示词、sidebar、composer、route props。

**依赖前置步骤：** 步骤 3、步骤 4。

**行为风险：** 中；Hook 生命周期和挂载顺序必须一致。

**完成标准：** ChatPage 不直接导入三个 runtime Panel 或 useExecutionTrace；新组件是唯一组合点；构建通过。

**回滚方式：** 删除新组件并恢复 ChatPage 当前三项 import、Hook 和 JSX。

**执行记录（2026-08-11）：**

- 新增 `pages/chat/components/ChatRuntimePanels.tsx`，仅接收 `executionId: string | null`，内部调用 `useExecutionTrace`。
- ChatPage 保留 `executionId` 与 `onExecutionId`，runtime 三个 Panel 的 JSX 改由新组件按原顺序统一挂载。
- 检查确认 trace、approval、integrations 只有 `ChatRuntimePanels` 一个组合点；构建通过。

- [x] 新增明确 Props 的 ChatRuntimePanels。
- [x] 替换 ChatPage 中对应 JSX。
- [x] 检查 trace/approval/integrations 的唯一组合点。
- [x] 运行构建，更新并勾选本步骤。

### 步骤 6：整理 runtime feature 的 i18n、反馈和隔离样式

**目标：** 为触及 feature 提供中英文一致的文案、loading/error/empty 状态、可访问语义和独立样式根。

**涉及文件：**
- 新增：frontend/src/styles/features/runtime-panels.css
- 修改：frontend/src/features/execution-trace/ExecutionTracePanel.tsx、frontend/src/features/tool-approval/ToolApprovalPanel.tsx、frontend/src/features/integrations/IntegrationsPanel.tsx、frontend/src/styles/pages/chat-entry.css、frontend/src/i18n/locales/en.json、frontend/src/i18n/locales/zh.json、frontend/src/hooks/usePermissions.tsx
- 条件修改：现有共享 badge 样式文件，仅在 role-badge 没有现成样式时

**修改内容：**
- 添加 features.executionTrace、features.toolApproval、features.integrations 两侧对称 key，覆盖标题、aria label、loading、空状态、确认、失败、连接、启用、停用和测试状态。
- 三个 Panel 使用 useTranslation；服务端错误保留详情但有本地化兜底。审批失败使用可见 role alert 且允许再次提交。
- integrations 保留 busyId、loading、列表和排序逻辑，并在空列表时渲染本地化空状态。
- runtime-panels.css 只定义 execution-trace-panel、tool-approval-panel、integrations-panel 及其子元素，不使用全局选择器或 !important。
- chat-entry.css 只增加一个 runtime panel 样式入口。
- RoleBadge 使用 token 驱动的语义样式，不改变角色文本或权限。

**不修改的内容：** 历史 Landing/Admin 硬编码、已有 locale key、tokens 和主题切换。

**依赖前置步骤：** 步骤 2、步骤 5。

**行为风险：** 低；主要风险是漏 key 或主题下不可读。

**完成标准：** 触及 feature 没有新增硬编码可见文案；en/zh key 集合一致；每个 feature 有 loading/error/empty 覆盖；构建通过。

**回滚方式：** 以 feature 为单位同时回退组件、locale 与样式。

**执行记录（2026-08-11）：**

- 三个 runtime feature 已使用 i18next key，补充中英文对称 key；locale 叶子 key 均为 814 个，未发现差异。
- trace 增加空状态，tool approval 增加可见失败详情和重新提交能力，integrations 保留 loading/busy/list/sort 并增加 loading/error/empty 反馈。
- 新增 `styles/features/runtime-panels.css`，仅使用三个 feature 根类及子元素；`chat-entry.css` 已引入，`role-badge` 仅在共享 badges.css 中补充 token 驱动样式。
- runtime 样式不含 `!important`；构建通过。

- [x] 添加对称 locale key 并替换 feature 文案/aria label。
- [x] 补齐审批失败、integrations 空状态、trace 空状态。
- [x] 新增隔离样式并引入 chat entry。
- [x] 比较 en/zh 叶子 key 集合。
- [x] 运行构建，更新并勾选本步骤。

### 步骤 7：收敛触及的 select CSS 优先级

**目标：** 只处理 forms/selects.css 的四处 !important，不扩展为 chat 主题重写。

**涉及文件：**
- 修改：frontend/src/styles/components/forms/selects.css
- 检查：frontend/src/styles/core/tokens.css、frontend/src/styles/themes/dark/colors.css、frontend/src/styles/pages/chat-entry.css

**修改内容：**
- 先定位竞争 select 选择器。
- 在保留 surface、text-primary、accent 和白色文本视觉结果的前提下，以正确的组件选择器特异性替代四处 !important。
- 不修改 themes/light/chat.css、sidebar/modules.css 或其他大型历史样式文件。

**不修改的内容：** tokens、主题色值、响应式断点、页面布局。

**依赖前置步骤：** 步骤 6。

**行为风险：** 中；原生 select 在浅深色主题下可能回归。

**完成标准：** selects.css 不再包含 !important；构建通过；diff 仅涉及必要优先级调整。

**回滚方式：** 单独回退 selects.css。

**执行记录（2026-08-11）：**

- 已检查 dark chat 中 `.option-agent select` 与 `.chat-options-bar select` 的竞争选择器；未改动主题文件、tokens 或布局。
- `selects.css` 的四处 `!important` 已替换为 `:root[data-theme] select option` 及状态选择器，保留 surface、text-primary、accent 和白色选中项文本视觉结果。
- `selects.css` 不再含 `!important`；构建通过。

- [x] 阅读 select 竞争选择器。
- [x] 最小化替换四处 !important。
- [x] 检查该文件不再含 !important。
- [x] 运行构建，更新并勾选本步骤。

### 步骤 8：前端静态验证与范围审查

**目标：** 用实际 diff 验证类型、构建、导入、CSS、路由、i18n 和范围；不运行测试。

**涉及文件：**
- 修改：docs/superpowers/plans/2026-08-11-frontend-organization-plan.md
- 检查：本计划实际变更的全部 frontend/src 文件与 docs/superpowers 文件

**修改内容：**
- 在本计划记录每个已完成任务的实际文件、构建结果和未处理风险。
- 读取完整 Git diff，确认无后端、数据库、脚本、测试或生产配置修改。

**不修改的内容：** 产品功能、测试、后端和生产配置。

**依赖前置步骤：** 步骤 1 至步骤 7。

**行为风险：** 低。

**完成标准：** 构建退出码 0；导入路径解析；CSS entry 明确；App 路由未改；en/zh 对称；变更只在 frontend/src 与 docs/superpowers。

**回滚方式：** 各功能任务按其独立回滚方式回退；验证记录可直接撤销。

- [x] 运行 conda run -n rag-local npm run build。
- [x] 检查 services、兼容 api-client、chatStreamAdapter、ChatRuntimePanels 的导入。
- [x] 检查 chat-entry.css import 图。
- [x] 比较 locale key 集合。
- [x] 运行 git diff --check 和 git status --short -- frontend docs/superpowers。
- [x] 阅读 App.tsx，确认 route path 未变。
- [x] 记录输出、遗留风险并勾选本步骤。

**执行记录（2026-08-11）：**
- `conda run -n rag-local npm run build` 退出码为 0；TypeScript 编译成功，Vite 转换 1228 个模块并完成生产构建。
- 已确认 `services/http/client`、execution service、tool approval service、`chatStreamAdapter`、`ChatRuntimePanels` 及其调用方导入关系；旧 `lib/api-client` 保留兼容 re-export。
- `ChatPage.tsx` 仍通过 `chat-entry.css` 进入聊天样式，且该入口引入 `runtime-panels.css`。
- App 路由路径仍为 `/app/login`、`/app/forgot-password`、`/app`、`/app/admin`、`/app/analytics`、`/app/change-password`、`/app/profile`、`/app/architecture`、`/` 与 `*`。
- en/zh locale 均为 814 个叶子 key，集合完全对称；`selects.css` 已无 `!important`；前端范围 `git diff --check` 通过；tracked diff 未包含测试/spec 文件。
- 未运行测试（按任务约束）；未修改 Vitest、后端、数据库、脚本、测试或生产配置。工作区中的其他未提交改动保持原样。
- 遗留风险：尚未进行浏览器端手工运行验证；双协议适配保持 execution event v1 精确 schema，同时继续保留旧 SSE fallback。

## 5. 实施前暂停条件

- 双协议 SSE 适配需要修改后端事件格式、API URL、请求体或响应字段。
- 发现 runtime feature 存在无法确认的动态导入或外部调用方。
- 修改会影响登录、权限、消息流、上传、路由、主题或语言行为。
- 用户在即将修改的相同文件上新增无法安全合并的未提交变更。
- 继续工作需要改测试、Vitest、后端、脚本、数据库或生产配置。

## 6. 允许的前端验证

- conda run -n rag-local npm run build
- 导入搜索：services、lib/api-client、chatStreamAdapter、ChatRuntimePanels
- CSS entry 搜索：chat-entry.css 的 import
- en/zh locale 叶子 key 集合比较
- git diff --check
- git status --short -- frontend docs/superpowers

预期：构建成功；导入和 CSS 入口存在；locale 比较无差异；diff 无空白错误；本次新增 diff 不包含测试和后端文件。
