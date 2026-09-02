# QueryMind Tailwind CSS v4 迁移设计

> 日期：2026-08-23  
> 状态：已批准，待按实施计划执行  
> 目标版本：Tailwind CSS v4.x  
> 配套计划：`docs/superpowers/plans/2026-08-23-tailwind-migration.md`

## 1. 结论

本项目选择 Tailwind CSS v4，通过官方 Vite 插件接入，并采用 CSS-first 配置。迁移目标是逐步替换项目自有的 88 个 CSS 文件，同时保持现有视觉、交互、主题、国际化、路由级 CSS 拆分和关键 CSS 内联能力。

关键决策如下：

1. 只安装 `tailwindcss@^4` 与 `@tailwindcss/vite@^4`；不执行 `tailwindcss init`，不创建 v3 风格的 `tailwind.config.js` 或 PostCSS 配置。
2. Tailwind 配置放在 CSS 中，使用 `@import`、`@theme inline` 和 `@custom-variant`。
3. Tailwind 工具类保留 `tw:` 前缀，例如 `tw:flex`、`tw:bg-surface`，避免与现有 `.rounded-sm`、`.shadow-md`、`.text-*` 等类冲突。
4. 迁移期不启用 Preflight；现有 `core/reset.css` 继续负责全局重置。是否启用 Preflight 必须单独评审并通过视觉基线。
5. 主题唯一状态源仍是 `<html data-theme="light|dark">`；不新增 `.dark`，也不让 Tailwind单独管理主题。
6. 现有 CSS 变量是颜色、阴影、圆角、字体和层级的事实来源。Tailwind 仅提供语义化工具类映射，不以默认值近似替换。
7. 每一批迁移都必须通过已建立的 21 场景 Playwright 迁移前视觉基线。

## 2. 范围与非目标

### 2.1 范围

- React/Vite 前端的 Tailwind v4 安装与配置。
- 88 个项目 CSS 文件的逐项迁移、保留或删除审计。
- light/dark、中文/英文、核心路由及响应式边界的视觉回归。
- 现有 CSS code splitting、critical CSS 和第三方样式的兼容。

### 2.2 非目标

- 不在迁移中重新设计 UI。
- 不修改产品交互、路由、API 或状态管理。
- 不为了减少文件数量而删除尚未验证可达性的 CSS。
- 不迁移或复制第三方 `reactflow/dist/style.css`。
- 不承诺预设百分比的 CSS 体积下降；优化结果以迁移后的构建测量为准。

## 3. 当前约束

### 3.1 模块与构建

`frontend/package.json` 使用 `"type": "module"`。所有配置必须是 ESM/TypeScript 形式，不能使用 `module.exports` 或 `require()`。

`frontend/vite.config.ts` 目前还负责：

- React SWC 插件；
- 路由/组件 CSS 拆分；
- 本地后端代理；
- `vite-plugin-inline-critical.js` 关键 CSS 内联。

Tailwind 插件只能作为新增插件插入，不能覆盖这些能力。

### 3.2 主题

`frontend/src/lib/theme.ts` 已正确执行：

```ts
document.documentElement.setAttribute("data-theme", mode);
```

暗色变量位于 `src/styles/themes/dark/colors.css`，同时含有：

- `:root[data-theme="dark"]` 的显式主题；
- `:root:not([data-theme="light"])` 的系统暗色回退。

因此 light 模式也必须保留 `data-theme="light"`，不能通过移除属性表示 light。

### 3.3 旧工具类冲突

`src/styles/core/utilities.css` 定义了与 Tailwind 同名或近似同名的类，例如圆角、阴影、颜色和布局工具类。无前缀共存会产生依赖加载顺序的覆盖行为。

本设计把 `prefix(tw)` 作为稳定命名空间，而不是临时过渡开关。组件只迁移一次；迁移完成后也无需进行第二轮“去前缀”改写。

### 3.4 响应式边界

项目关键边界不是 Tailwind 默认 `md`：

- 520px：紧凑移动布局；
- 1080px：聊天侧栏结构切换；
- 基线额外覆盖 375px、768px、1079px、1081px、1440px。

不能把现有 1080px 行为直接替换成默认 768px 的 `md:`。

## 4. 安装设计

在 `frontend` 目录执行：

```powershell
npm install -D tailwindcss@^4 @tailwindcss/vite@^4
```

说明：

- 使用 `^4` 锁定 v4 主版本，避免 `@latest` 将来静默升级到新的主版本。
- 不安装 `@tailwindcss/postcss`，因为项目直接使用官方 Vite 插件。
- 不执行 `npx tailwindcss init -p`；这是 v3 流程。
- `@tailwindcss/forms`、`@tailwindcss/typography` 不是初始迁移依赖。只有出现明确使用场景并通过视觉验证后才加入，避免 forms 基础样式改变现有控件。
- v4 依赖现代 CSS 特性；执行前须确认产品浏览器基线至少为 Safari 16.4、Chrome 111、Firefox 128。

## 5. Vite 配置设计

在 `frontend/vite.config.ts` 中只增加插件导入和插件调用：

```ts
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import inlineCriticalCSS from "./vite-plugin-inline-critical.js";

export default defineConfig({
  plugins: [react(), tailwindcss(), inlineCriticalCSS()],
  // 其余 alias、build、manualChunks、server/proxy 配置保持不变
});
```

约束：

- 保留 `inlineCriticalCSS()` 及其相对顺序，实际构建验证后才能调整。
- 保留 `manualChunks` 的路由样式规则，迁移某一路由时同步检查其 CSS chunk。
- 不新增 `tailwind.config.js`、`postcss.config.js` 或 CommonJS 配置。

## 6. CSS-first 配置设计

新增 `frontend/src/styles/tailwind.css`。迁移期使用分拆导入以禁用 Preflight：

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

`@theme inline` 是必要条件：这些主题变量引用了在 `:root` 与 `[data-theme]` 中切换的既有 CSS 变量。它让生成的工具类使用实际变量值，避免变量作用域产生意外解析。

初始接入顺序：

```css
/* src/styles/main.css */
@import "./core/tokens.css";
@import "./core/reset.css";
@import "./core/utilities.css";
@import "./themes/dark/index.css";
@import "./tailwind.css";
/* 其余现有导入保持原顺序 */
```

不要为接入 Tailwind 重排现有 imports，只在当前 dark theme entry 后插入新入口。Tailwind utilities 使用独立 layer；旧 CSS 不强行塞入 Tailwind layer，以免一次性改变层叠优先级。`@theme inline` 生成的声明在运行时读取既有变量，dark 覆盖仍由 `data-theme` 决定。

## 7. Theme 迁移设计

### 7.1 单一状态源

保持以下流程不变：

1. `theme_preference` 保存 `light` 或 `dark`；
2. `applyTheme()` 总是设置 `data-theme`；
3. CSS 变量响应 `[data-theme="dark"]`；
4. Tailwind 的 `dark:` 通过同一 data attribute 激活。

禁止：

- 同时写入 `.dark` 和 `data-theme`；
- light 时移除 `data-theme`；
- 在 React 组件中维护第二份主题状态；
- 用 Tailwind 默认色直接近似现有主题色。

### 7.2 语义工具类

颜色迁移优先使用会自动响应主题变量的类：

```tsx
<section className="tw:bg-surface tw:text-text-primary tw:border-border-light" />
```

这类语义色不需要重复添加 `dark:`。只有结构或非语义的暗色差异才使用：

```tsx
<div className="tw:grid tw:dark:hidden" />
```

所有透明度组合都要单独截图验证。若 `tw:bg-accent/10` 不能精确复现既有 `rgba(...)`，使用已存在的 `--accent-soft` 映射，不以视觉近似替代。

### 7.3 精确 token 原则

- light 值继续由 `core/tokens.css` 提供；
- dark 值及 dark shadow 覆盖继续由 `themes/dark/colors.css` 提供；
- `--panel`、`--panel-strong`、`--bg-soft` 等兼容别名在引用清零前保留；
- 渐变使用既有 `--gradient-*`/`--accent-gradient` 或任意值，不改成相近预设；
- z-index 继续使用 `var(--z-*)` 的任意值写法，例如 `tw:z-[var(--z-modal)]`，避免猜测主题命名空间；
- transition 可使用 `tw:duration-[150ms] tw:ease-[cubic-bezier(0.4,0,0.2,1)]`，或继续使用现有变量。

## 8. 迁移方法

### 8.1 批次顺序

1. 基础设施与 token 映射；
2. 原子组件（button、form、badge、spinner、skeleton）；
3. 复合组件与 SessionManagement；
4. chat、sidebar、topbar、composer；
5. admin/auth/landing/analytics/profile/architecture 页面；
6. 删除审计和构建优化。

每批使用同一循环：

1. 为组件或路由选定对应视觉场景；
2. 用 `tw:` 工具类迁移一小组样式；
3. 只删除已无引用且不再产生视觉差异的规则；
4. 运行单元测试、构建与 `npm run test:visual`；
5. 只有经产品确认的设计变化才运行 `npm run test:visual:update`。

### 8.2 CSS 删除规则

CSS 文件只有同时满足以下条件才能删除：

- 导入路径和运行时动态导入均已清零；
- 文件内每个选择器已迁移、确认无效或属于可删除死代码；
- 对应路由在 light/dark、语言和适用视口下通过视觉基线；
- `npm run build` 成功；
- 关键 CSS 插件与路由 chunk 不再依赖该路径。

禁止使用“一次删除全部 CSS import”的做法。

## 9. 必须保护的例外

### 9.1 第三方 ReactFlow CSS

`frontend/src/components/DataFlowVisualization.tsx` 中的：

```ts
import "reactflow/dist/style.css";
```

必须保留。它不计入 88 个项目 CSS 文件，也不属于 Tailwind 迁移目标。

### 9.2 Critical CSS

`frontend/vite-plugin-inline-critical.js` 硬编码读取 `src/styles/core/critical.css`。该文件不能单独移动或删除。

允许的结束状态只有：

- 保留该文件并维护必要关键规则；或
- 在同一个原子变更中修改插件、生成流程和构建验证。

### 9.3 Route CSS splitting

迁移 route entry 时必须同步检查 `vite.config.ts` 的 `manualChunks`。迁移不能意外把 chat/admin/auth 全部样式合并回主包。

## 10. 视觉基线

迁移前基线已经真实建立：

- 配置：`frontend/playwright.visual.config.ts`
- 测试：`frontend/e2e/visual/migration-baseline.spec.ts`
- 快照：`frontend/e2e/visual/__screenshots__/chromium-win32/`
- 场景数：21
- 固定时间：`2026-08-23T08:00:00Z`
- 后端：浏览器层确定性 API mock，无需启动真实后端
- 快照行为：禁用动画、隐藏 caret、单 worker、全页截图

覆盖：

- 核心路由：landing、login、chat、admin、analytics、architecture、profile、change-password、404；
- 主题：light/dark；
- 语言：English/中文；
- 视口：375、768、1079、1081、1440；
- 认证状态：admin 用户与 guest。

命令：

```powershell
cd frontend
npm run test:visual
```

只有确认视觉变化符合预期时才允许：

```powershell
npm run test:visual:update
```

快照必须与测试代码一起评审和提交。`test-results/` 与 `playwright-report/` 是临时输出，已忽略。

## 11. 验收条件

- Tailwind v4 通过 `@tailwindcss/vite` 构建，无 v3 指令或 CommonJS 配置。
- 所有新工具类使用 `tw:` 前缀。
- theme 仍由 `data-theme` 单一驱动，light/dark 均通过基线。
- 520px 与 1080px 边界保持现有行为。
- 88 个项目 CSS 文件在实施计划中逐项有状态和验收方式。
- ReactFlow 外部样式、critical CSS 和 route chunks 未丢失。
- 单元测试、类型检查、生产构建和 21 个视觉场景通过。
- 任何快照更新都有人工审查依据，而不是为了消除测试失败。

## 12. 官方依据

- Tailwind v4 Vite 安装：<https://tailwindcss.com/docs/installation/using-vite>
- v3 → v4 升级说明：<https://tailwindcss.com/docs/upgrade-guide>
- 禁用 Preflight 与分拆导入：<https://tailwindcss.com/docs/preflight>
- CSS-first theme 与 `inline`：<https://tailwindcss.com/docs/theme>
- data attribute 暗色模式：<https://tailwindcss.com/docs/dark-mode>
