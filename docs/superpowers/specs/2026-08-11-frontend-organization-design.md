# Frontend Organization Design

## 1. 背景

当前前端已具备 React 18、TypeScript、Vite、React Router、i18next 和按路由拆分 CSS 的基础能力，且 `npm run build` 能在当前工作区基线上通过。Chat 与 Admin 已经形成部分页面内模块和 Hooks，但 API、权限、类型和样式职责仍跨越多个目录。当前未提交的 execution trace、tool approval、integrations 功能也直接接入 ChatPage，进一步放大了这些边界问题。

本次整理以当前工作区为基线，目标是让页面负责组合、features 负责业务能力、services 负责请求、hooks 负责状态与交互、components 负责展示，并保留已有路由、API 协议、认证、权限、主题、语言、上传和消息流行为。

## 2. 当前问题

### P0：消息流兼容性风险

- `frontend/src/pages/chat/hooks/useMessageActions.ts:164-189` 已将原有 SSE 分支处理改为只接受 `execution_event` 包络；而 `streamEventHandlers.ts:39-48, 94-251` 仍定义并依赖 status、route、thought、vector_result、graph_result、web_result、answer_chunk、answer_reset、done 的旧事件形状。若服务端在任一入口仍发送旧形状事件，聊天增量内容、检索元数据和完成状态会被忽略。
- `frontend/src/features/execution-trace/sse.ts:12-27` 只接受严格的 `event: execution_event` 与 version `"1"` 的完整字段集；这是一处新的协议假设，未提供兼容适配层。

### P1：API 与组件边界混杂

- `frontend/src/lib/api.ts:1-8` 将 app 与 admin API 合并为一个 `appApi`；Chat、Admin 和设置组件由此都依赖一个横跨领域的总入口。
- `frontend/src/components/AIEditPanel.tsx:67`、`ReportEditor.tsx:74,113,150` 直接在展示组件内调用 `fetch`；`ToolApprovalPanel.tsx:16` 也直接构造审批请求。请求、错误处理和协议类型无法集中维护。
- `frontend/src/features/execution-trace/useExecutionTrace.ts:29` 直接拼接编排事件 URL；而 `frontend/src/features/integrations/api.ts` 已开始形成按领域封装的 API 模式，现有两种模式并存。

### P1：类型边界不清且包含宽泛类型

- `frontend/src/types/api.ts:1-8` 的 `AuthUser.role` 和 `status` 都包含 `| string`，实际退化为 `string`；`ChatPage.tsx:39-46` 再用断言转换为更窄的 `UserRole`。
- `frontend/src/hooks/usePermissions.tsx:10-18` 再定义了一份 User/role 模型；`pages/admin/components/WebActivityTables.tsx:4` 还有局部 User 类型。
- `frontend/src/pages/chat/hooks/streamEventHandlers.ts:18-48,247-248`、`pages/admin/actions/types.ts:40-44`、`components/apiSettingsUtils.ts:51`、`lib/api-client.ts:75,92,128` 等处使用 `any`，会掩盖 API 和流事件的结构变化。

### P1：国际化与可访问性覆盖不一致

- `frontend/src/features/execution-trace/ExecutionTracePanel.tsx:7-15`、`features/tool-approval/ToolApprovalPanel.tsx:30-31`、`features/integrations/IntegrationsPanel.tsx:46-127` 存在新增的英文可见文本、aria label、错误反馈和加载文案，但未使用 i18next。
- `frontend/src/pages/LandingPage.tsx:79,123,181,417`、`pages/admin/AdminModelSettings.tsx:141-179`、`pages/chat/components/ChatTopbar.tsx:44` 等已有硬编码可见文本，与项目的 i18next 机制并存。
- `frontend/src/i18n/locales/en.json` 与 `zh.json` 当前各有 777 个叶子 key，键集合一致；问题在于调用侧绕过 key，而不是 locale 文件失配。

### P1：主题样式的职责与覆盖范围过大

- `frontend/src/styles/themes/light/chat.css` 约 766 行，`styles/components/sidebar/modules.css` 约 975 行，均通过 `:root[data-theme] .page-shell ...` 的长选择器覆盖多个组件细节。
- `frontend/src/styles/pages/chat-entry.css:4-15` 同时引入 topbar、sidebar、messages、composer、citations、graph、process 以及浅/深色主题；功能样式、组件样式与主题覆盖在一个入口耦合。
- `frontend/src/styles/components/forms/selects.css:48-57` 使用 4 处 `!important`，说明通用表单样式与主题/浏览器默认行为的优先级关系不够稳定。

### P2：页面与 Hook 的职责仍可进一步收紧

- `frontend/src/pages/ChatPage.tsx` 约 378 行，除页面组合外还负责权限用户转换、用户模型配置同步、execution trace 状态、上传/会话/消息/提示词 Hook 编排和多组回调绑定。
- `frontend/src/pages/AdminPage.tsx` 约 326 行，既负责页面布局，又管理审计/系统日志分页、数据加载 effect、轮询和各管理面板的组合。
- `frontend/src/hooks/usePermissions.tsx:182-189` 的 `hasPermission` 是普通函数却调用 Hook；目前没有调用方，但该导出一旦在普通函数或事件回调中使用会违反 Hooks 规则。`RoleBadge` 还依赖未在项目样式中定义的 Tailwind 风格类名。

### P2：目录边界不完全一致

- API 文件、纯工具和浏览器 Hooks 同处 `frontend/src/lib/`；例如 `lib/hooks/*` 与 `src/hooks/*` 并存。
- `frontend/src/components/` 同时包含通用展示组件、设置业务、报告编辑和 AI 编辑；后两者的请求与状态职责不符合共享组件边界。
- `frontend/src/features/` 的新增 execution-trace、tool-approval、integrations 是合理方向，但 tool approval 状态反向依赖 execution trace 的 SSE 类型，形成 feature 间的实现耦合。

### P3：一致性与可读性

- `frontend/src/utils/exportUtils.tsx` 不含 JSX，却使用 `.tsx` 并广泛使用 `any`。
- 源码中同时存在 `@/`、相对路径以及单双引号混用；这不影响构建，但提高了移动文件和批量检索的成本。
- 当前路由入口、CSS 入口和 i18n locale 文件都存在明确结构，不建议为“整齐”而重排它们。

## 3. 目标

1. 为网络请求建立按领域的服务层入口，统一参数、返回值和错误转换，同时保持 URL、HTTP 方法、请求体和响应协议不变。
2. 保持 `pages/chat` 与 `pages/admin` 的既有局部模块结构；只抽取确有跨页面或跨 feature 价值的类型、服务与纯展示组件。
3. 将新增 execution trace、tool approval、integrations 固化为独立 feature：公开组件、Hook、state 和 service 边界，不让展示组件直接发请求。
4. 以可辨识的领域类型替换重构触及路径中的 `any` 和不安全断言；不对未触及的后端协议做猜测性重写。
5. 让所有新增或修改的可见文本、操作反馈、loading/error/empty 状态经过现有 i18next key；保持中英文 locale 键同步。
6. 维持现有 CSS 分层和路由级代码分割，优先减少 chat 主题文件对组件内部结构的长链覆盖，并消除不必要的 `!important`。

## 4. 非目标

- 后端、数据库、迁移、脚本、测试代码或测试配置的实现。
- API 协议、路由、认证机制、权限规则、业务功能或用户可见交互的变更。
- 新增测试、修改测试、补测或设计测试方案。
- 无依据的状态管理库、CSS 方案、路由框架或 UI 库替换。
- 为统一目录外观而移动合理的页面局部组件、路由入口或全部样式文件。
- 删除 `AIEditPanel`、`ReportEditor` 或任何现有文件，除非后续以实际引用证据确认无使用方；当前没有此证据。

## 5. 目标目录结构

在不重排现有合理局部结构的前提下，采用以下最小调整目标：

```text
frontend/src/
├── App.tsx                         # 保留当前应用入口与路由位置
├── components/                     # 仅共享展示/交互组件，不直接调用业务 API
├── features/
│   ├── execution-trace/            # 事件类型、state、Hook、Panel、service
│   ├── integrations/               # 表单状态、Panel、service、types
│   ├── tool-approval/              # 审批状态、Panel、service、types
│   └── settings/                   # 仅在确认跨页面复用时承接 API 设置业务
├── hooks/                          # 跨领域 UI/浏览器 Hook；不放页面流程
├── lib/                            # 纯工具、格式化、校验、主题、文件工具
├── pages/
│   ├── chat/                       # 保留现有聊天局部 components/hooks/types
│   └── admin/                      # 保留现有管理局部 components/actions/hooks
├── services/                       # api-client 与按领域 API service
├── types/                          # 跨页面共享契约类型
├── i18n/
└── styles/
    ├── core/
    ├── components/
    ├── features/
    ├── pages/
    └── themes/
```

`pages/chat`、`pages/admin`、`styles` 的既有子目录保留。`services/` 仅在迁移已有 API 文件时引入，不创建无内容目录或 barrel export。

## 6. 模块职责

| 目录 | 允许内容 | 不允许内容 |
|---|---|---|
| `pages/` | 路由页面组合、页面级布局、页面局部协调 | 可复用 API 协议、通用展示组件、跨页面状态 |
| `pages/*/hooks` | 仅该页面使用的状态、交互、派生数据 | 其他页面复用的领域服务 |
| `features/*` | 可独立启用的业务能力：UI、state、领域 Hook、service 调用编排 | 依赖具体页面内部实现或直接访问其他 feature 私有文件 |
| `components/` | 无业务 API 的通用展示、输入、布局与反馈组件 | 领域请求、认证/权限决策、特定页面流程 |
| `services/` | `api-client`、按领域请求、响应解析、协议类型映射 | JSX、页面状态、样式 |
| `hooks/` | 跨领域的浏览器能力与 UI 交互 Hook | 页面专属流程、混合多个业务领域的聚合 Hook |
| `lib/` | 无 React 依赖的纯函数、主题、校验、文件与字符串工具 | API client、业务状态、组件 |
| `types/` | 跨页面共享的稳定领域/API 类型 | 单个组件内部 Props、仅一个 feature 使用的临时状态 |
| `styles/` | 核心 tokens、共享组件、feature、页面和主题样式 | 反向表达业务逻辑或跨页面覆写 |

## 7. 依赖方向

```text
pages → features / components / page hooks / services / types / lib
features → feature services / components / hooks / types / lib
components → hooks / types / lib
services → types / lib
hooks → services / types / lib
lib, types, styles → 不依赖 pages、features 或 components
```

具体约束：

- `components` 不直接调用业务 API；现有直接请求先迁移到 feature 或 service 的调用者。
- `pages` 只组合 feature 与页面局部 Hook，不持有协议解析细节。
- feature 之间通过公开类型或 service 接口协作，不互相导入内部实现文件。
- 低层的 `services`、`lib`、`types` 不得导入 `pages`。
- CSS 只通过组件或路由入口加载；主题只覆盖 token 或明确的 feature 根类，避免依赖深层 DOM 结构。

## 8. 组件拆分策略

- 保持 `ChatPage`、`AdminPage` 作为组合根；先提取明确的 feature host/容器，而不按行数机械拆分。
- execution trace、tool approval、integrations 各自公开一个 Panel 与一个可测试之外的状态/动作边界；Panel 通过 Props 接收数据和动作。
- API Settings、Report Editor、AI Edit 只有在确认仍有使用方后再分别归属到 `features/settings`、`features/reports`；不得继续作为带请求的通用 components。
- 每个 Props 类型贴近组件；只在跨 feature 复用时提升到 `types/`。
- 不以多个 boolean 让同一组件承载不相干的界面模式；使用明确的状态对象或拆分后的子组件。

## 9. Hooks 整理策略

- `pages/chat/hooks` 保持会话、消息、文档、提示词、拖拽等页面流程职责；stream parser 与事件适配从消息动作中分离。
- execution trace 使用 feature 内的 reducer/Hook，并由 service 提供事件流；tool approval 不能反向依赖 execution trace 的私有模块。
- `usePermissions` 拆分为纯权限计算函数和 React Hook；普通函数不得调用 Hook。角色类型以共享 `AuthUser`/权限领域类型为唯一来源。
- `lib/hooks` 中真正通用的 React Hook 迁至 `hooks/` 或保留为明确的 `lib/react` 边界，二者二选一；不创建 `useCommon` 等聚合 Hook。

## 10. API 和服务层整理策略

- 将现有 `api-client` 作为唯一的 fetch、base URL、凭据、响应错误解析入口；不改变其请求行为。
- 按 auth、sessions、queries、documents、prompts、admin、analytics、integrations、execution、reports 划分 service 文件；每个函数明确输入与输出类型。
- 用领域 service 替代 `appApi` 的跨域聚合入口，迁移采用一批一个领域的方式，并保留短期兼容导出直到所有引用完成迁移。
- 流式 query 使用显式适配器：先识别已有事件，再识别 execution envelope；仅在协议确认后移除旧分支，保证消息内容、引用、图谱、错误和完成事件不丢失。
- 新增或重构的 service 统一转换网络/非 2xx 错误；页面和 Panel 只消费已定义的领域错误结果。

## 11. TypeScript 规范

- 新增及重构触及的 API、SSE、Props 和 reducer action 不使用 `any`；使用 `unknown` 配合类型守卫或明确的 DTO。
- 用共享的角色、用户、citation、stream metadata 类型替换重复定义；不再将 `string` 与窄字符串联合混用。
- 所有类型断言都必须有可追溯的运行时校验或受控转换函数。
- 单 feature 私有类型留在 feature 内；稳定 API 契约放在 `types/` 或 service 邻近的 contract 文件。

## 12. CSS 规范

- 继续使用现有 tokens 与主题变量，不引入新的设计系统或 CSS 框架。
- theme 文件优先覆盖 tokens 和 feature 根类；减少 `:root[data-theme] .page-shell` 后跟多层组件实现选择器。
- 保留 route entry CSS 的代码分割，但让每个 feature 在明确入口加载自身样式，避免 chat entry 成为所有视觉规则的总汇。
- 移除可由 tokens 和特异性解决的 `!important`，不做视觉改版；改动后保持浅色、深色与现有响应式断点一致。
- 新增 Panel 必须拥有以 feature 名称为前缀的样式根类，避免依赖全局标签选择器。

## 13. 国际化规范

- 所有新增或修改的可见文本、`aria-label`、placeholder、loading/error/empty/success 提示均使用 `useTranslation` 和现有 locale。
- 以 feature/page 命名空间新增 key，同时更新 `en.json` 和 `zh.json`；不改动已使用 key 的语义。
- 保留当前 locale key 对称性（当前两侧各 777 个叶子 key）。
- 机器可读值（角色枚举、指标符号、URL、协议字段）不强制翻译，但展示时必须有本地化 label。

## 14. 行为兼容性

以下内容必须保持不变：

- 路由路径、lazy 页面入口、登录登出、cookie/凭据行为与主题切换。
- 现有 API URL、HTTP 方法、请求参数、响应字段与错误含义。
- Chat 会话、文件上传、流式消息、停止生成、非流 fallback、引用、图谱与执行状态展示。
- 管理页面权限、筛选、分页、轮询、导出与配置操作。
- 中英文切换、浅/深色主题和移动端响应式布局。

对 P0 消息流问题的修改必须先保持双协议兼容，直到仅依赖新协议的运行事实被确认；若无法确认，保留旧解析路径。

## 15. 风险和回滚

| 变更类别 | 影响范围 | 主要风险 | 回滚方式 |
|---|---|---|---|
| SSE 适配 | `pages/chat/hooks`、`features/execution-trace`、query service | 流式内容、引用或完成状态丢失 | 以单一提交回退适配器变更，恢复当前已验证的事件分支 |
| API service 迁移 | `lib/api*`、调用页面/feature | 导入路径或请求细节变化 | 保留兼容导出，按领域回退调用点 |
| 类型收紧 | `types`、stream/chat/admin 调用点 | 未覆盖的后端返回值暴露为编译错误 | 回退对应领域类型提交，不降低为 `any` |
| feature 边界调整 | execution/integrations/tool approval | 页面挂载顺序或审批动作变化 | 独立 feature 提交回退，保持 Panel Props 接口 |
| CSS 主题收敛 | chat entry、theme、feature styles | 浅深色或小屏视觉回归 | 单独回退样式提交，不回退功能代码 |
| i18n 收敛 | locale 与组件 | 漏 key 导致原样显示 key | 同步回退 locale/组件变更，保留既有 key |

## 审查依据与验证基线

- 以用户确认的当前工作区为审查基线；其中包含未提交的 `features/`、ChatPage 与消息流改动，均不被覆盖或回滚。
- 2026-08-11 运行 `conda run -n rag-local npm run build`：TypeScript 编译和 Vite 生产构建成功。首次沙箱内运行因无法读取 Vite 配置被环境阻断；在批准的受限沙箱外复跑后成功。
- 未运行或修改任何测试；测试目录、后端、数据库和脚本均不在本次范围内。
