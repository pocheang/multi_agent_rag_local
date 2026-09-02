# Tailwind CSS v4 完整迁移执行计划（方案 A）

> 日期：2026-08-23  
> 策略：完整迁移（100% Tailwind）  
> 预计工作量：80-100 小时（2-3 个会话）  
> 目标：将 85/88 剩余 CSS 文件迁移到 Tailwind v4

## 执行原则

### 核心策略
1. **小批量迁移**：每批 3-5 个文件，立即验证
2. **独立提交**：每个逻辑单元独立提交，便于回滚
3. **持续验证**：每批后运行 type-check + build + test + visual
4. **风险隔离**：高风险组件单独处理，不与低风险混合

### 动画与复杂样式处理
1. **简单动画**：用 Tailwind 的 animate-* 或 transition-*
2. **复杂 keyframes**：保留 CSS，用 @layer components 包裹
3. **精确渐变**：使用任意值 `tw:bg-[linear-gradient(...)]`
4. **z-index**：使用 `tw:z-[var(--z-modal)]` 保持变量引用

### 全局工具类策略
对于广泛使用的类（buttons/forms/badges）：
1. **先迁移组件**：修改所有使用处到 Tailwind
2. **再删除 CSS**：确认无引用后删除
3. **分批进行**：不一次性修改 30+ 文件

## 当前状态

### 已完成（3/88）
- ✅ theme-toggle.css
- ✅ language-toggle.css  
- ✅ Spinner.css

### 剩余（85/88）
- Phase 2 剩余：buttons, forms, badges, skeletons, animations
- Phase 3：复合组件与 SessionManagement
- Phase 4：Chat, Sidebar, Topbar, Composer
- Phase 5：页面迁移
- Phase 6：清理与优化

## 执行路线（按优先级）

### Batch 1: 简单原子组件（低风险）
**预计时间：** 2-3 小时  
**目标文件：**
1. ✅ Spinner.css（已完成）
2. Skeleton.css（动画组件）
3. 如果有独立的 Badge 组件文件

**验证：** build + visual（应该无变化）

### Batch 2: SessionManagement 模块（中等风险）
**预计时间：** 3-4 小时  
**目标文件：**
1. SessionExportImport.css
2. SessionMetadataEditor.css
3. SessionSearch.css
4. TagInput.css

**策略：** 功能独立，可以整体迁移
**验证：** admin 页面 session 管理功能

### Batch 3: 卡片与表格（中等风险）
**预计时间：** 2-3 小时  
**目标文件：**
1. cards.css
2. tables.css

**使用位置：** admin, analytics, 多个页面
**验证：** admin/analytics 视觉快照

### Batch 4: Dialogs 与 Dropdowns（中等风险）
**预计时间：** 3-4 小时  
**目标文件：**
1. confirm-dialog.css
2. modals.css
3. dropdowns.css
4. keyboard-help.css

**验证：** modal 状态、focus 状态

### Batch 5: 复杂组件（中等风险）
**预计时间：** 4-5 小时  
**目标文件：**
1. clarification-prompt.css
2. thinking-indicator.css
3. code-block.css
4. welcome-screen.css

**策略：** thinking-indicator 的 keyframes 可能需要保留
**验证：** chat 页面各种状态

### Batch 6: Chat Features（高风险）
**预计时间：** 5-6 小时  
**目标文件：**
1. messages.css
2. citations.css
3. graph.css
4. process.css
5. runtime-panels.css
6. hidden-sections.css

**策略：** 逐个迁移，不合并
**验证：** chat 页面所有 viewport（375/768/1079/1081/1440）

### Batch 7: Composer（高风险）
**预计时间：** 4-5 小时  
**目标文件：**
1. composer/editor.css
2. composer/actions.css
3. composer/layout.css

**验证：** 输入区 focus/disabled/error 状态

### Batch 8: Sidebar（高风险）
**预计时间：** 6-7 小时  
**目标文件：**
1. sidebar/layout.css
2. sidebar/modern-layout.css
3. sidebar/modern-sessions.css
4. sidebar/navigation.css
5. sidebar/modules.css
6. sidebar/actions.css
7. sidebar/footer.css
8. sidebar/backdrop.css
9. sidebar/rail.css
10. sidebar/responsive.css（关键：1080px 边界）

**策略：** 最关键的批次，分 2-3 次提交
**验证：** 1079px vs 1081px 必须通过

### Batch 9: Topbar（中等风险）
**预计时间：** 2-3 小时  
**目标文件：**
1. topbar.css
2. topbar-responsive.css

**验证：** fixed/overlay 结构

### Batch 10: Auth Pages（中等风险）
**预计时间：** 4-5 小时  
**目标文件：**
1. auth/layout.css
2. auth/forms.css
3. auth/social.css（审计可达性）

**验证：** login EN/ZH, light/dark, desktop/mobile

### Batch 11: Landing Page（中等风险）
**预计时间：** 3-4 小时  
**目标文件：**
1. landing.css

**验证：** landing EN/ZH, light/dark, mobile-375

### Batch 12: Admin Pages（中等风险）
**预计时间：** 4-5 小时  
**目标文件：**
1. admin/layout.css
2. admin/forms.css
3. admin/tables.css
4. admin/actions.css
5. admin/ops.css

**验证：** admin light/dark snapshot

### Batch 13: Other Pages（低风险）
**预计时间：** 3-4 小时  
**目标文件：**
1. analytics.css
2. architecture.css
3. profile.css

**验证：** 各自页面 snapshot

### Batch 14: Chat Page Wrappers（低风险）
**预计时间：** 2-3 小时  
**目标文件：**
1. chat.css
2. chat-responsive.css（关键：375/768/1079/1081）

**验证：** chat viewport matrix

### Batch 15: Buttons（高风险，广泛使用）
**预计时间：** 8-10 小时  
**策略：** 最后处理，因为影响面最大

**阶段 1：** 创建 Tailwind 版本的 button 组件
```tsx
// src/components/ui/Button.tsx
export function Button({ variant, size, ... }) {
  const classes = clsx(
    'tw:inline-flex tw:items-center tw:justify-center',
    variant === 'primary' && 'tw:bg-gradient-to-br tw:from-[#2f63e6] tw:to-[#356af0]',
    // ...
  );
}
```

**阶段 2：** 逐个文件替换使用
- 从简单页面开始（analytics, architecture）
- 再到复杂页面（admin, chat）
- 共 30+ 文件

**阶段 3：** 删除 buttons/ CSS

### Batch 16: Forms（高风险，广泛使用）
**预计时间：** 6-8 小时  
**策略：** 类似 buttons

**阶段 1：** 创建 form 组件库
```tsx
// src/components/ui/Input.tsx
// src/components/ui/Select.tsx
// src/components/ui/Textarea.tsx
```

**阶段 2：** 逐个文件替换
**阶段 3：** 删除 forms/ CSS

### Batch 17: Badges & Status（中等风险）
**预计时间：** 3-4 小时  
**目标文件：**
1. badges.css

**策略：** 17 文件使用，需要逐个替换或创建组件

### Batch 18: Skeletons（低风险）
**预计时间：** 2-3 小时  
**目标文件：**
1. skeletons.css

**策略：** shimmer 动画可能需要保留 keyframes

### Batch 19: Spinners（全局工具）
**预计时间：** 2-3 小时  
**目标文件：**
1. spinners.css

**策略：** 已有独立 Spinner 组件，替换全局 .spinner 使用

### Batch 20: Animation Wrappers（中等风险）
**预计时间：** 4-5 小时  
**目标文件：**
1. AnimatedButton.css
2. AnimatedButtonLite.css
3. AnimatedToast.css
4. AnimatedToastLite.css
5. Skeleton.css（动画组件版本）

**策略：** 保留复杂 keyframes，迁移基础样式

### Batch 21: Dark Theme Overrides（低风险）
**预计时间：** 2-3 小时  
**目标文件：**
1. themes/dark/chat.css
2. themes/dark/effects.css
3. themes/light/chat.css

**策略：** 迁移到组件的 tw:dark: 类

### Batch 22: Route Entries（低风险）
**预计时间：** 1-2 小时  
**目标文件：**
1. pages/auth-entry.css
2. pages/admin-entry.css
3. pages/chat-entry.css
4. pages/landing-entry.css

**策略：** 这些是空的或只有 imports，删除 imports 后即可删除

### Batch 23: DataFlow & Third-party（特殊处理）
**预计时间：** 1-2 小时  
**目标文件：**
1. data-flow.css（wrapper 样式）

**策略：** reactflow/dist/style.css 保留，只迁移 wrapper

### Batch 24: Core Utilities Cleanup（低风险）
**预计时间：** 2-3 小时  
**目标文件：**
1. core/utilities.css

**策略：** 逐规则审计，已迁移的删除，未迁移的保留

### Batch 25: Tokens Audit（审计）
**预计时间：** 1-2 小时  
**目标文件：**
1. tokens/colors.css
2. tokens/spacing.css
3. tokens/timing.css

**策略：** 确认不可达后删除

### Batch 26: Final Cleanup（清理）
**预计时间：** 2-3 小时  
**任务：**
1. 删除空的 index.css 文件
2. 清理 main.css imports
3. 验证 route CSS chunks
4. 验证 critical CSS 插件

## 验证清单（每批执行）

```powershell
cd frontend

# 1. 类型检查
npm run type-check

# 2. 构建
npm run build

# 3. 单元测试
npm run test

# 4. 视觉测试（必须）
npm run test:visual

# 5. 检查禁止指令
rg "@tailwind|module\.exports|tailwindcss init" .

# 6. 检查 CSS imports
rg "import.*\.css|@import.*\.css" src
```

## 风险控制

### 每批后检查点
1. ✅ 构建成功
2. ✅ 60/61 单元测试通过
3. ✅ 21/21 视觉测试通过
4. ✅ 关键 CSS chunks 存在
5. ✅ critical CSS 插件工作

### 回滚策略
```bash
# 如果某批失败
git log --oneline -5
git revert <commit-hash>
# 或
git reset --hard HEAD~1  # 仅在未推送时
```

### 高风险批次的额外验证
- Sidebar：手动测试 1079px vs 1081px
- Buttons/Forms：手动测试所有状态（hover/focus/disabled/error）
- Chat：手动测试消息渲染、引用、思考指示器

## 预计收益

### CSS 体积减少
- 当前：~150 kB（main + chunks）
- 目标：~105 kB（Tailwind 生成 + 保留的 keyframes）
- 减少：~45 kB（30%）

### 构建产物变化
- Route CSS chunks：可能合并到 Tailwind
- Critical CSS：应该变小（更少全局样式）
- Main CSS：增加（Tailwind utilities），但总体减少

### 维护性提升
- 样式与组件同位置
- 减少 CSS 文件数量：88 → ~10（tokens + critical + keyframes）
- 降低样式冲突风险

## 时间表

### Session 1（当前会话）
- ✅ Phase 1 完成
- ✅ Phase 2 部分完成（3/5）
- 目标：完成 Batch 1-8（到 Sidebar 前）

### Session 2（预计）
- Batch 9-16（Topbar 到 Forms）
- 预计工作量：35-45 小时

### Session 3（预计）
- Batch 17-26（Badges 到最终清理）
- 预计工作量：25-35 小时

## 成功标准

### 必须满足
- ✅ 所有 88 项 CSS 清单已关闭（迁移或删除）
- ✅ 21/21 视觉测试通过
- ✅ 60/61 单元测试通过
- ✅ 构建成功
- ✅ Route CSS chunks 正常
- ✅ Critical CSS 插件正常

### 期望达到
- CSS 体积减少 25-35%
- 无新增 lint 错误
- 构建时间不增加

## 开始执行

从 **Batch 2: SessionManagement** 开始...
