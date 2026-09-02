# 前端低风险修复设计

日期：2026-08-24

状态：待用户审阅

## 目标

在不迁移认证协议、不重构 CSS、不批量格式化全仓库的前提下，修复审计中证据充分、影响面可隔离的问题，并恢复前端运行逻辑与测试门禁的可信度。

成功标准：

1. 会话重命名契约测试与当前前后端能力一致。
2. Chat 设置轮询不会因普通 rerender 重复初始请求，自动刷新定时器不会被持续重置。
3. 流式回答内容增长时可以继续自动滚动，同时用户主动向上阅读时不会被强制拉回底部。
4. Vitest 能收集 `.test.tsx`，DOM 组件测试在 jsdom 中执行，纯逻辑测试仍使用 node 环境。
5. ESLint 不再产生 TypeScript/DOM `no-undef` 误报，并清理现有真实 warning，使 `npm run lint` 通过。
6. 语言与 Chat 布局偏好在 Storage 不可用或抛异常时安全降级。
7. 类型检查、单元测试、生产构建和 17 个视觉回归均通过。

## 明确不做

- 不迁移 localStorage bearer 到纯 HttpOnly Cookie；该项涉及后端兼容和登录迁移，留待独立设计。
- 不运行全仓库 Prettier 写入，不处理 238 个格式差异。
- 不重构超大 CSS、设计 token 或 bundle 分包。
- 不批量删除旧动画体系、专用 ErrorBoundary 和全部零引用文件。
- 不改变页面视觉设计、路由、权限或后端接口。

## 方案选择

采用隔离小补丁方案。每个问题先建立可复现测试，再只修改对应边界，避免通过大规模 memo 化或全局配置放宽掩盖问题。

没有选择以下方案：

- 仅修配置：改动最少，但会留下 Chat 轮询和自动滚动的用户可感知缺陷。
- 一次修复全部审计项：会同时触及认证、CSS、死代码和可访问性，难以证明回归来自哪一组改动。

## 设计

### 1. 会话重命名契约

保留现有 `sessionRename(sessionId, title)` 能力。将“API 不应存在”的旧测试替换为请求级契约测试，验证：

- method 为 `PATCH`；
- session ID 经过路径编码；
- body 为 `{ "title": "..." }`；
- 非成功响应继续走统一 `ApiError` 路径。

不修改后端路由或 UI 重命名交互。

### 2. Chat 轮询稳定性

不对整个 `useChatActions` 树进行大规模 `useCallback` 重构。把稳定性责任放在轮询 hook 内部：

- `useSettingsPolling` 用 ref 保存最新 `onNotify`，轮询 effect 不直接依赖调用方每次 render 创建的新函数；语言变化允许受控重启。
- `useAutoRefresh` 用 ref 保存最新的 session/document/prompt 刷新函数，25 秒 interval 只在 mount/unmount 建立和清理。
- 两个 hook 都保持现有间隔和错误降级语义。
- 添加 fake timer + rerender 测试，断言普通 rerender 不增加初始设置请求，也不会创建多个 interval；tick 后调用最新回调。
- 增加 in-flight 防重入，上一轮未结束时不启动下一轮，避免慢网络下请求重叠。

### 3. 自动滚动与拖拽副作用所有权

自动滚动只由 `ChatMessages` 负责，删除 `ChatPage` 的重复调用。

`useAutoScroll` 记录前一次 scrollHeight，并以用户更新前是否接近底部为判断条件：

- 新消息或同一流式消息内容增长时，如果用户原本距离底部不超过阈值，则滚到最新底部；
- 用户主动向上滚动超过阈值时，不抢夺滚动位置；
- 流结束后的最后一次内容更新也执行同一逻辑。

拖拽职责保持分离：`useDragDropPrevention` 唯一负责 window 级 `dragover/drop` 防默认行为；`useDragHandlers` 只返回 composer 局部事件处理函数，不再重复注册全局监听。

### 4. Vitest 测试收集

将 include 扩展为 `.test.ts` 与 `.test.tsx`。纯逻辑测试继续使用 node；需要 DOM 的 TSX 测试通过文件级 jsdom 指令或独立匹配配置运行，避免让流式/Response 测试被全局 jsdom 环境改变。

现有两个 TSX 测试必须真正被收集。若它们只覆盖未使用旧组件，则保留其有效断言，同时为当前 `AnimatedButtonLite`/`AnimatedToastLite` 增加最小行为覆盖；不在本阶段删除旧动画体系。

### 5. ESLint 基线

TypeScript 文件关闭 ESLint 核心 `no-undef`，由 TypeScript 编译器负责类型和全局名称检查。浏览器、node 和测试环境使用各自 globals，避免手工漏列 DOM 构造器。

不降低 `--max-warnings 0`。现有 37 个 warning 按以下方式消除：

- 删除未使用 catch 参数、测试 console 和不必要 non-null assertion；
- 对真正的 hook dependency 警告稳定回调或调整 effect 边界，并用相关测试保护；
- 将非组件导出移出组件文件，或对确属 HOC/工具文件做最窄文件级规则配置；
- 不通过全局关闭 hooks、unused-vars 或 react-refresh 规则来“变绿”。

### 6. Storage 安全降级

新增一个小型 safe storage adapter，提供 `get`、`set`、`remove`：

- Storage 不存在、读取抛 `SecurityError` 或写入配额失败时不向外抛异常；
- 读取失败返回调用方提供的默认值；
- 不吞掉业务数据解析错误之外的全局异常。

语言初始化和 `useSectionToggle`/`useTopbarToggle` 改用该 adapter。语言默认 `en`，布局默认显示。添加模拟 Storage getter/setter 抛错的测试，证明应用初始化与 hook render 不崩溃。

## 错误处理与兼容性

- 轮询失败继续静默降级，但不会改变上一次成功状态。
- 自动滚动不依赖浏览器专有 API；jsdom 测试显式设置 scrollTop、scrollHeight 和 clientHeight。
- safe storage 不迁移或重命名现有 key，正常浏览器的用户偏好保持不变。
- API 请求路径、后端 payload、认证 header/cookie 和视觉结构保持不变。

## 测试策略

每一组使用红绿循环：

1. 先运行新测试确认能复现旧行为。
2. 实现最小修复并运行该组测试。
3. 完成全部组后运行：
   - `npm run type-check`
   - `npm run lint`
   - `npm run test -- --run`
   - `npm run build`
   - `npm run test:visual`
4. `format:check` 只记录现有基线，本阶段不以批量修改 238 个文件为代价宣称通过。

## 变更边界与回滚

按以下独立批次实施，任一批次失败可单独回退：

1. session API 契约测试；
2. polling hook 与测试；
3. auto-scroll/drag 副作用与测试；
4. Vitest 收集和组件测试；
5. ESLint 配置及 warning 清理；
6. safe storage 与调用方测试。

每个批次不得顺手触碰认证迁移、CSS 重构或无关后端文件。仓库已有未提交改动，实施时只编辑明确列入批次的文件并保留用户现有修改。
