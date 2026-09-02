# QueryMind Tailwind CSS v4 迁移实施计划

> 日期：2026-08-23  
> 依据：`docs/superpowers/specs/2026-08-23-tailwind-migration-design.md`  
> 执行方式：小批次迁移；每批必须通过测试、构建和视觉基线后才进入下一批

## 0. 执行原则

- 目标是 Tailwind CSS v4，不混用 v3 安装、指令或配置格式。
- 所有 Tailwind 类使用 `tw:` 前缀。
- 不一次性删除现有 CSS；按下方 88 项清单逐个关闭。
- 不把 UI 重设计混入迁移。
- 不更新视觉快照来掩盖回归。
- 保留用户工作树中的无关变更；禁止 `git reset --hard`。
- 回滚使用独立分支/工作树和 `git revert <phase-commit>`，或在确认目标后恢复具体文件。

## 1. 迁移前视觉基线（已完成）

- [x] 添加 `frontend/playwright.visual.config.ts`。
- [x] 添加 `frontend/e2e/visual/migration-baseline.spec.ts`。
- [x] 增加 `test:visual` 和 `test:visual:update` npm scripts。
- [x] 忽略临时的 `test-results/` 和 `playwright-report/`。
- [x] 使用确定性 API mock，不依赖真实后端或生产数据。
- [x] 固定系统时间、禁用动画、隐藏 caret、单 worker 执行。
- [x] 建立并人工抽查 21 张 Chromium/Windows 快照。
- [x] 验证 21/21 场景通过。

### 1.1 基线矩阵

| 类别   | 覆盖                                                                                |
| ------ | ----------------------------------------------------------------------------------- |
| 路由   | landing、login、chat、admin、analytics、architecture、profile、change-password、404 |
| 主题   | English light：9 个核心路由；English dark：landing/login/chat/admin                 |
| 语言   | 中文 light：landing/login/chat                                                      |
| 响应式 | landing 375；chat 375/768/1079/1081/1440                                            |
| 认证   | guest 与确定性的 admin 用户                                                         |

日常验证：

```powershell
cd frontend
npm run test:visual
```

只有产品确认了预期视觉变化后才更新：

```powershell
npm run test:visual:update
```

## 2. Phase 1：安装与 CSS-first 基础设施

### Task 2.1：确认运行环境

- [ ] 记录 `node --version`，必须为项目支持版本；若运行官方升级工具则至少 Node 20。
- [ ] 确认浏览器支持基线至少 Safari 16.4、Chrome 111、Firefox 128。
- [ ] 运行迁移前验证并保存结果：

```powershell
cd frontend
npm run test
npm run build
npm run test:visual
```

### Task 2.2：安装 v4 Vite 插件

```powershell
cd frontend
npm install -D tailwindcss@^4 @tailwindcss/vite@^4
```

验收：

- [ ] lockfile 只引入 v4 主版本。
- [ ] 未创建 `tailwind.config.js` 或 `postcss.config.js`。
- [ ] 未执行 `tailwindcss init -p`。

### Task 2.3：接入 Vite

修改 `frontend/vite.config.ts`：

```ts
import tailwindcss from "@tailwindcss/vite";

plugins: [react(), tailwindcss(), inlineCriticalCSS()];
```

保留 alias、manualChunks、proxy 与 critical CSS 插件的其余配置。

### Task 2.4：创建 Tailwind CSS 入口

新增 `frontend/src/styles/tailwind.css`：

```css
@layer theme, base, components, utilities;

@import "tailwindcss/theme.css" layer(theme) prefix(tw);
@import "tailwindcss/utilities.css" layer(utilities) prefix(tw);

@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

@theme inline {
  --color-bg: var(--bg);
  --color-bg-secondary: var(--bg-secondary);
  --color-bg-tertiary: var(--bg-tertiary);
  --color-surface: var(--surface);
  --color-surface-hover: var(--surface-hover);
  --color-surface-active: var(--surface-active);
  --color-text-primary: var(--text-primary);
  --color-text-secondary: var(--text-secondary);
  --color-text-tertiary: var(--text-tertiary);
  --color-text-inverse: var(--text-inverse);
  --color-border-light: var(--border-light);
  --color-border-medium: var(--border-medium);
  --color-border-strong: var(--border-strong);
  --color-accent: var(--accent);
  --color-accent-hover: var(--accent-hover);
  --color-accent-light: var(--accent-light);
  --color-accent-soft: var(--accent-soft);
  --color-success: var(--success);
  --color-success-light: var(--success-light);
  --color-warning: var(--warning);
  --color-warning-light: var(--warning-light);
  --color-danger: var(--danger);
  --color-danger-light: var(--danger-light);
  --color-info: var(--info);
  --color-info-light: var(--info-light);
  --font-sans: var(--font-sans);
  --font-mono: var(--font-mono);
  --radius-sm: var(--radius-sm);
  --radius-md: var(--radius-md);
  --radius-lg: var(--radius-lg);
  --radius-xl: var(--radius-xl);
  --radius-2xl: var(--radius-2xl);
  --shadow-sm: var(--shadow-sm);
  --shadow-md: var(--shadow-md);
  --shadow-lg: var(--shadow-lg);
  --shadow-xl: var(--shadow-xl);
  --shadow-2xl: var(--shadow-2xl);
  --shadow-brand-sm: var(--shadow-brand-sm);
  --shadow-brand-md: var(--shadow-brand-md);
  --shadow-brand-lg: var(--shadow-brand-lg);
  --breakpoint-mobile-tight: 32.5rem;
  --breakpoint-sidebar: 67.5rem;
}
```

将其添加到 `src/styles/main.css` 当前 dark theme entry 之后，不重排既有 imports。Tailwind utilities 位于独立 layer，迁移期不导入 `tailwindcss/preflight.css`。

### Task 2.5：基础设施红/绿验证

先添加一个不会改变现有页面视觉的 smoke fixture，确认：

- [ ] `tw:flex` 能生成并生效；
- [ ] `tw:bg-surface` 在 light/dark 中读取既有变量；
- [ ] `tw:sidebar:*` 在 1080px 生效；
- [ ] 无前缀 `flex` 不由 Tailwind 生成；
- [ ] Preflight 未注入全局重置。

随后运行：

```powershell
npm run type-check
npm run test
npm run build
npm run test:visual
```

建议阶段提交：`chore(frontend): add Tailwind v4 Vite foundation`

## 3. Phase 2：原子组件

按以下小组迁移，每组完成后运行相关单元测试与全部视觉测试：

1. buttons；
2. forms；
3. badge/skeleton/spinner；
4. language/theme toggle；
5. animation wrappers。

实施规则：

- React 中用静态可扫描的完整类名，动态分支使用 `clsx()`；不要拼接 `tw:bg-${color}`。
- 精确渐变、阴影、动画和复杂伪元素可暂留 CSS；“使用 Tailwind”不等于强制消灭所有 CSS。
- 每删除一个 CSS import，先用 `rg` 证明无其他消费者。

建议阶段提交：`refactor(frontend): migrate atomic styles to Tailwind v4`

## 4. Phase 3：复合组件与 SessionManagement

迁移 cards、tables、dialogs、dropdowns、code block、data flow、thinking/welcome 及 SessionManagement 四个组件。

- [ ] 保留 ReactFlow 外部样式导入。
- [ ] 弹窗层级继续使用 `tw:z-[var(--z-modal)]` 等精确值。
- [ ] 表单、dropdown、dialog 验证 focus、disabled、hover、error 状态。
- [ ] 中英文长文本均不溢出。

建议阶段提交：`refactor(frontend): migrate shared composite styles`

## 5. Phase 4：Chat、Sidebar、Topbar、Composer

这是高风险批次，拆成四个独立提交：

1. sidebar layout/navigation/modules；
2. topbar 与 responsive overlay；
3. messages/citations/process/graph/runtime panels；
4. composer/editor/actions 与 chat route wrappers。

强制验证：

- [ ] 375px 移动端 overlay、按钮与输入区无遮挡。
- [ ] 768px 平板布局保持当前行为。
- [ ] 1079px 与 1081px 分别落在 1080px 边界两侧。
- [ ] 1440px sidebar、消息区与 composer 宽度一致。
- [ ] topbar 仍保持现有 fixed/overlay 结构，不套用假定的固定高度。
- [ ] light/dark、中文/英文聊天快照通过。

建议阶段提交：`refactor(frontend): migrate chat workspace styles`

## 6. Phase 5：页面迁移

按路由逐个迁移：

1. auth；
2. landing；
3. admin；
4. analytics；
5. architecture；
6. profile。

每个路由必须：

- [ ] 保持 lazy import 与 route entry；
- [ ] 检查 Vite CSS chunk；
- [ ] 运行对应 light/dark 或语言快照；
- [ ] 再运行 21 场景全量基线。

建议每个高复杂路由单独提交，避免一个提交同时覆盖 admin 与 chat。

## 7. Phase 6：清理与优化

### Task 7.1：关闭 CSS 清单

- [ ] 下方 88 项的最终状态全部更新为“保留”或“已删除”，不得留“待迁移”。
- [ ] 对 `src/styles/tokens/*` 重新做可达性搜索；只有确定无 import/动态加载后删除。
- [ ] 搜索所有生产源码 CSS imports，确认第三方例外仍存在。

### Task 7.2：处理 critical CSS

- [ ] 保留并更新 `src/styles/core/critical.css`；或
- [ ] 在同一提交修改 `vite-plugin-inline-critical.js`、生成机制及构建验证。

禁止只删除或移动文件。

### Task 7.3：清理 PurgeCSS

Tailwind v4 自带源码检测与按需生成，不再新增 PurgeCSS 流程。确认没有 npm script、CI 或构建插件使用后，才执行：

```powershell
npm uninstall -D purgecss @fullhuman/postcss-purgecss
```

然后删除确认无引用的 `purgecss.config.js`。若仍有外部流程依赖，则记录并保留。

### Task 7.4：测量而非猜测

记录迁移前后：

- `dist/assets/*.css` 总字节数与 gzip 大小；
- 首屏加载的 CSS chunk；
- chat/admin/auth 路由 CSS chunk；
- 构建时间。

不设置未经测量的“必须减少 50%”类指标。

建议阶段提交：`chore(frontend): remove verified legacy CSS tooling`

## 8. 完整 CSS 清单（88/88）

状态含义：

- **迁移**：逐规则移到组件 `tw:` 类或受控的 Tailwind layer；验证后删除原规则/文件。
- **保留**：它是 token、入口、关键 CSS 或仍需精确自定义 CSS；可重构但不能无条件删除。
- **审计**：当前看似不可达，必须再次以 import/动态引用证明后删除。

|   # | 文件                                                         | 归属/动作                              | 阶段  | 关闭条件                |
| --: | ------------------------------------------------------------ | -------------------------------------- | ----- | ----------------------- |
|   1 | `src/components/animations/AnimatedButton.css`               | 动画；迁移/精确保留 keyframes          | P2    | button 状态快照         |
|   2 | `src/components/animations/AnimatedButtonLite.css`           | 动画；迁移/精确保留 keyframes          | P2    | button 状态快照         |
|   3 | `src/components/animations/AnimatedToast.css`                | 动画；迁移/精确保留 keyframes          | P2    | toast 状态检查          |
|   4 | `src/components/animations/AnimatedToastLite.css`            | 动画；迁移/精确保留 keyframes          | P2    | toast 状态检查          |
|   5 | `src/components/animations/Skeleton.css`                     | 动画；迁移/精确保留 keyframes          | P2    | loading 状态检查        |
|   6 | `src/components/animations/Spinner.css`                      | 动画；迁移/精确保留 keyframes          | P2    | loading 状态检查        |
|   7 | `src/components/SessionManagement/SessionExportImport.css`   | SessionManagement；迁移                | P3    | dialog/export flow      |
|   8 | `src/components/SessionManagement/SessionMetadataEditor.css` | SessionManagement；迁移                | P3    | editor states           |
|   9 | `src/components/SessionManagement/SessionSearch.css`         | SessionManagement；迁移                | P3    | search states           |
|  10 | `src/components/SessionManagement/TagInput.css`              | SessionManagement；迁移                | P3    | input/tag states        |
|  11 | `src/styles/main.css`                                        | 全局入口；保留并缩减 imports           | P1/P6 | build 与 chunk 检查     |
|  12 | `src/styles/components/badges.css`                           | 原子组件；迁移                         | P2    | chat/admin snapshots    |
|  13 | `src/styles/components/cards.css`                            | 复合组件；迁移                         | P3    | route snapshots         |
|  14 | `src/styles/components/clarification-prompt.css`             | 复合组件；迁移                         | P3    | prompt states           |
|  15 | `src/styles/components/code-block.css`                       | 复合组件；迁移/保留内容 CSS            | P3    | markdown/code check     |
|  16 | `src/styles/components/confirm-dialog.css`                   | dialog；迁移                           | P3    | modal states            |
|  17 | `src/styles/components/data-flow.css`                        | ReactFlow wrapper；迁移，外部 CSS 保留 | P3    | architecture snapshot   |
|  18 | `src/styles/components/dropdowns.css`                        | dropdown；迁移                         | P3    | focus/open states       |
|  19 | `src/styles/components/keyboard-help.css`                    | dialog；迁移                           | P3    | keyboard help state     |
|  20 | `src/styles/components/language-toggle.css`                  | 原子组件；迁移                         | P2    | zh/en snapshots         |
|  21 | `src/styles/components/modals.css`                           | modal；迁移                            | P3    | modal states/chunk      |
|  22 | `src/styles/components/skeletons.css`                        | 原子组件；迁移                         | P2    | loading state           |
|  23 | `src/styles/components/spinners.css`                         | 原子组件；迁移                         | P2    | loading state           |
|  24 | `src/styles/components/tables.css`                           | table；迁移                            | P3    | admin snapshot          |
|  25 | `src/styles/components/theme-toggle.css`                     | 原子组件；迁移                         | P2    | light/dark snapshots    |
|  26 | `src/styles/components/thinking-indicator.css`               | 复合组件；迁移/保留 keyframes          | P3    | thinking state          |
|  27 | `src/styles/components/topbar-responsive.css`                | topbar；迁移                           | P4    | 375/1079/1081           |
|  28 | `src/styles/components/topbar.css`                           | topbar；迁移                           | P4    | chat snapshots          |
|  29 | `src/styles/components/welcome-screen.css`                   | chat welcome；迁移                     | P3    | empty chat state        |
|  30 | `src/styles/components/buttons/base.css`                     | button；迁移                           | P2    | button matrix           |
|  31 | `src/styles/components/buttons/groups.css`                   | button group；迁移                     | P2    | group layout            |
|  32 | `src/styles/components/buttons/index.css`                    | button entry；删除 imports 清零后      | P2/P6 | import proof            |
|  33 | `src/styles/components/buttons/variants.css`                 | button variants；迁移                  | P2    | variant matrix          |
|  34 | `src/styles/components/forms/index.css`                      | form entry；删除 imports 清零后        | P2/P6 | import proof            |
|  35 | `src/styles/components/forms/inputs.css`                     | input；迁移                            | P2    | focus/error/disabled    |
|  36 | `src/styles/components/forms/selects.css`                    | select；迁移                           | P2    | open/focus states       |
|  37 | `src/styles/components/forms/validation.css`                 | validation；迁移                       | P2    | error/success states    |
|  38 | `src/styles/components/sidebar/actions.css`                  | sidebar；迁移                          | P4    | chat viewport matrix    |
|  39 | `src/styles/components/sidebar/backdrop.css`                 | sidebar；迁移                          | P4    | mobile overlay          |
|  40 | `src/styles/components/sidebar/footer.css`                   | sidebar；迁移                          | P4    | auth controls           |
|  41 | `src/styles/components/sidebar/index.css`                    | sidebar entry；删除 imports 清零后     | P4/P6 | import proof            |
|  42 | `src/styles/components/sidebar/layout.css`                   | sidebar；迁移                          | P4    | 1079/1081               |
|  43 | `src/styles/components/sidebar/modern-layout.css`            | sidebar；迁移                          | P4    | desktop snapshot        |
|  44 | `src/styles/components/sidebar/modern-sessions.css`          | sidebar；迁移                          | P4    | sessions list           |
|  45 | `src/styles/components/sidebar/modules.css`                  | sidebar；迁移                          | P4    | module cards            |
|  46 | `src/styles/components/sidebar/navigation.css`               | sidebar；迁移                          | P4    | navigation states       |
|  47 | `src/styles/components/sidebar/rail.css`                     | sidebar；迁移                          | P4    | collapsed state         |
|  48 | `src/styles/components/sidebar/responsive.css`               | sidebar；迁移，保留 1080px             | P4    | 1079/1081               |
|  49 | `src/styles/core/critical.css`                               | 关键 CSS；保护/同步生成                | P1/P6 | inline plugin + build   |
|  50 | `src/styles/core/reset.css`                                  | 全局 reset；迁移期保留                 | P1/P6 | Preflight 单独决策      |
|  51 | `src/styles/core/tokens.css`                                 | light token 真值；保留并整合           | P1    | light/dark snapshots    |
|  52 | `src/styles/core/utilities.css`                              | 旧工具类；逐规则迁移                   | P1-P6 | selector/import 清零    |
|  53 | `src/styles/features/citations.css`                          | chat feature；迁移                     | P4    | citation snapshot       |
|  54 | `src/styles/features/graph.css`                              | chat feature；迁移                     | P4    | graph state             |
|  55 | `src/styles/features/hidden-sections.css`                    | chat behavior；迁移/保留               | P4    | hide/show state         |
|  56 | `src/styles/features/messages.css`                           | chat feature；迁移                     | P4    | message snapshots       |
|  57 | `src/styles/features/process.css`                            | chat feature；迁移                     | P4    | process state           |
|  58 | `src/styles/features/runtime-panels.css`                     | chat feature；迁移                     | P4    | runtime state           |
|  59 | `src/styles/features/composer/actions.css`                   | composer；迁移                         | P4    | actions states          |
|  60 | `src/styles/features/composer/editor.css`                    | composer；迁移                         | P4    | input/focus states      |
|  61 | `src/styles/features/composer/index.css`                     | composer entry；删除 imports 清零后    | P4/P6 | import proof            |
|  62 | `src/styles/features/composer/layout.css`                    | composer；迁移                         | P4    | viewport matrix         |
|  63 | `src/styles/pages/admin-entry.css`                           | admin route entry；保留到子样式关闭    | P5    | chunk + admin snapshots |
|  64 | `src/styles/pages/analytics.css`                             | analytics page；迁移                   | P5    | analytics snapshot      |
|  65 | `src/styles/pages/architecture.css`                          | architecture page；迁移                | P5    | architecture snapshot   |
|  66 | `src/styles/pages/auth-entry.css`                            | auth route entry；保留到子样式关闭     | P5    | chunk + login snapshots |
|  67 | `src/styles/pages/chat-entry.css`                            | chat route entry；保留到子样式关闭     | P4    | chat chunk              |
|  68 | `src/styles/pages/chat-responsive.css`                       | chat responsive；迁移                  | P4    | 375/768/1079/1081       |
|  69 | `src/styles/pages/chat.css`                                  | chat page；迁移                        | P4    | chat snapshots          |
|  70 | `src/styles/pages/landing-entry.css`                         | landing route entry；保留到子样式关闭  | P5    | landing chunk           |
|  71 | `src/styles/pages/landing.css`                               | landing page；迁移                     | P5    | en/zh/light/dark/mobile |
|  72 | `src/styles/pages/profile.css`                               | profile page；迁移                     | P5    | profile snapshot        |
|  73 | `src/styles/pages/admin/actions.css`                         | admin page；迁移                       | P5    | admin actions           |
|  74 | `src/styles/pages/admin/forms.css`                           | admin page；迁移                       | P5    | form states             |
|  75 | `src/styles/pages/admin/layout.css`                          | admin page；迁移                       | P5    | admin snapshots         |
|  76 | `src/styles/pages/admin/ops.css`                             | admin page；迁移                       | P5    | ops snapshot            |
|  77 | `src/styles/pages/admin/tables.css`                          | admin page；迁移                       | P5    | table states            |
|  78 | `src/styles/pages/auth/forms.css`                            | auth page；迁移                        | P5    | en/zh login             |
|  79 | `src/styles/pages/auth/layout.css`                           | auth page；迁移                        | P5    | desktop/mobile login    |
|  80 | `src/styles/pages/auth/social.css`                           | auth page；迁移/审计功能可达性         | P5    | import + UI proof       |
|  81 | `src/styles/themes/dark/chat.css`                            | dark chat overrides；迁移              | P4    | dark chat snapshot      |
|  82 | `src/styles/themes/dark/colors.css`                          | dark token 真值；保留并去重            | P1    | dark snapshots          |
|  83 | `src/styles/themes/dark/effects.css`                         | dark effects；迁移/精确保留            | P5    | dark snapshots          |
|  84 | `src/styles/themes/dark/index.css`                           | dark entry；保留并缩减 imports         | P1/P6 | import proof            |
|  85 | `src/styles/themes/light/chat.css`                           | light chat overrides；迁移             | P4    | light chat snapshots    |
|  86 | `src/styles/tokens/colors.css`                               | 当前疑似不可达；审计后删除或合并       | P1/P6 | `rg` import proof       |
|  87 | `src/styles/tokens/spacing.css`                              | 当前疑似不可达；审计后删除或合并       | P1/P6 | `rg` import proof       |
|  88 | `src/styles/tokens/timing.css`                               | 当前疑似不可达；审计后删除或合并       | P1/P6 | `rg` import proof       |

## 9. 受保护的非清单样式

以下外部导入不计入 88 项，必须保留：

```ts
// frontend/src/components/DataFlowVisualization.tsx
import "reactflow/dist/style.css";
```

## 10. 每阶段统一验证门

在每个阶段提交前执行：

```powershell
cd frontend
npm run type-check
npm run lint
npm run test
npm run build
npm run test:visual
```

检查生产 CSS import：

```powershell
rg -n "(?:import|@import).*\.css" src
```

检查禁止的 v3 配置/指令：

```powershell
rg -n "@tailwind|module\.exports|tailwindcss init|purge:" .
```

阶段完成条件：

- 命令退出码均为 0；
- 视觉测试 21/21；
- 快照无未审查更新；
- 对应 CSS 清单项已更新；
- 构建产物仍含预期路由 CSS chunks；
- critical CSS 与 ReactFlow CSS 仍受保护。

## 11. 文档跟踪说明

当前根 `.gitignore` 忽略 `docs/superpowers/`。这些设计/计划文件会在本地生效，但不会被普通 `git add` 自动纳入提交。若团队决定跟踪，应单独评审忽略规则或明确使用强制添加；不要在迁移阶段提交中静默绕过该规则。
