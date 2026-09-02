# Tailwind CSS v4 迁移 - 会话交接提示词

> 用于新聊天框继续迁移工作

## 📋 复制以下内容到新聊天框

```markdown
继续执行 Tailwind CSS v4 完整迁移（方案 A）。

项目路径：
C:\Users\pocheang\Desktop\llm\multi_agent_rag_local_v4

## 当前状态

**已完成（Session 1）：**
- ✅ Phase 1: Tailwind v4 基础设施（tailwindcss@^4.3.3 + @tailwindcss/vite@^4.3.3）
- ✅ Phase 2 部分：ThemeToggle, LanguageToggle, Spinner 已迁移
- ✅ 进度：3/88 文件（3.4%）
- ✅ 所有测试通过：21/21 视觉测试，60/61 单元测试
- ✅ 提交：7e1ab755, c8d9cb18, 13c4869a

**关键约束：**
- 所有 Tailwind 类使用 tw: 前缀（例如 tw:flex, tw:bg-surface）
- Dark 模式通过 tw:dark: 前缀（基于 data-theme="dark"）
- 保留 520px/1080px 响应式边界（不用默认 md:）
- 不启用 Preflight（保留现有 reset.css）
- 精确保留颜色、阴影、圆角、字体、z-index 变量
- 复杂 keyframes 动画保留在 CSS 中

**执行资源：**
1. 详细执行计划：`docs/superpowers/plans/2026-08-23-tailwind-migration-execution-plan-a.md`
2. 标准化模板：`docs/superpowers/plans/2026-08-23-tailwind-migration-template.md`
3. 88项清单：`docs/superpowers/plans/2026-08-23-tailwind-migration-88-checklist.md`
4. 进度报告：`docs/superpowers/plans/2026-08-23-tailwind-migration-progress.md`

## 下一步行动

从 **Batch 2** 开始执行（低风险快速胜利）：

### 优先处理（推荐顺序）：

1. **keyboard-help.css**（简单 dialog）
   - 位置：`src/styles/components/keyboard-help.css`
   - 使用：1 个文件
   - 预计：1 小时

2. **welcome-screen.css**（单页面）
   - 位置：`src/styles/components/welcome-screen.css`
   - 使用：1 个文件（chat）
   - 预计：1 小时

3. **hidden-sections.css**（简单 toggle）
   - 位置：`src/styles/features/hidden-sections.css`
   - 使用：少量
   - 预计：30 分钟

4. **Route entry files**（只删除 imports）
   - `pages/auth-entry.css`
   - `pages/admin-entry.css`
   - `pages/chat-entry.css`
   - `pages/landing-entry.css`
   - 预计：5 分钟/文件

### 执行流程（每个文件）：

```powershell
# 1. 分析
cat src/styles/components/example.css
rg "import.*example\.css" src
rg "className=.*example-class" src

# 2. 迁移到 Tailwind（使用 tw: 前缀）
# 编辑相关 .tsx 文件

# 3. 删除 CSS
rm src/styles/components/example.css

# 4. 验证
cd frontend
npm run type-check
npm run build
npm run test
npm run test:visual  # 必须！21/21 通过

# 5. 提交
git add -A
git commit -m "refactor(frontend): migrate Example to Tailwind v4

- Migrate example.css to tw: utility classes
- Remove example.css
- Preserve [specific features]

All tests pass:
- Build: successful
- Unit: 60/61
- Visual: 21/21"
```

### 样式映射速查：

```css
/* CSS */                          /* Tailwind */
display: flex;                     tw:flex
flex-direction: column;            tw:flex-col
gap: 16px;                         tw:gap-4
background: var(--surface);        tw:bg-surface
color: var(--text-primary);        tw:text-text-primary
border: 1px solid var(--border);   tw:border tw:border-border-light
border-radius: 8px;                tw:rounded-lg
z-index: var(--z-modal);           tw:z-[var(--z-modal)]

/* Dark mode */
:root[data-theme="dark"] { ... }   tw:dark:...

/* 响应式 */
@media (max-width: 768px) { ... }  max-[768px]:tw:...
```

### 必须验证：

- ✅ 类型检查：`npm run type-check`
- ✅ 构建成功：`npm run build`
- ✅ 单元测试：`npm run test`（60/61）
- ✅ **视觉测试**：`npm run test:visual`（21/21）

### 禁止事项：

- ❌ 不删除未确认无引用的 CSS
- ❌ 不为通过测试而随意更新快照
- ❌ 不一次性修改 30+ 文件
- ❌ 不用近似值替代精确变量

### 目标：

Session 2 完成 Batch 2-3，达到 36/88 文件（41% 进度）。

请从第一个文件（keyboard-help.css）开始执行迁移。
```

## 备注

- 所有文档位于 `docs/superpowers/plans/` 下
- 当前 git 分支：main
- 既有单元测试失败：session-api.test.ts（与迁移无关）
- 视觉快照位于：`frontend/e2e/visual/__screenshots__/`
