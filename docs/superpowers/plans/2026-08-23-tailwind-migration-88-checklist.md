# Tailwind CSS v4 迁移 - 88项CSS清单详细追踪

> 最后更新：2026-08-23  
> 进度：8/88 已完成（9.1%）  
> 预计剩余工作量：70-80 小时

## 📊 进度概览

| 状态 | 数量 | 百分比 |
|------|------|--------|
| ✅ 已完成 | 8 | 9.1% |
| 🟢 Low Priority (简单) | 11 | 12.5% |
| 🟡 Medium Priority | 34 | 38.6% |
| 🔴 High Risk (复杂) | 20 | 22.7% |
| 🔒 保留必要 | 15 | 17.0% |

## 📋 详细清单（按阶段分组）

### Phase 2: 原子组件（5/5 groups）

#### ✅ 已完成（8 items）

| # | 文件 | 状态 | 使用位置 | 大小 | 提交 | 备注 |
|---|------|------|----------|------|------|------|
| 1 | `components/theme-toggle.css` | ✅ 已删除 | 1 | ~50行 | c8d9cb18 | 迁移到 ThemeToggle.tsx |
| 2 | `components/language-toggle.css` | ✅ 已删除 | 1 | ~59行 | c8d9cb18 | 迁移到 LanguageToggle.tsx |
| 3 | `animations/Spinner.css` | ✅ 已删除 | 1 | ~50行 | 13c4869a | 迁移到 Spinner.tsx |
| 4 | `components/keyboard-help.css` | ✅ 已删除 | 1 | ~232行 | 543def84 | 迁移到 KeyboardHelp.tsx，keyframes 保留 |
| 5 | `components/welcome-screen.css` | ✅ 已删除 | 1 | ~402行 | 477e768f | 迁移到 WelcomeScreen.tsx，fadeSlideIn 保留 |
| 6 | `components/data-flow.css` | ✅ 已删除 | 1 | ~178行 | 2500a74a | 迁移到 DataFlowVisualization.tsx，dashdraw 保留 |
| 7 | `animations/Skeleton.css` | ✅ 已删除 | 多个 | ~93行 | cdd0e015 | 迁移到 Skeleton.tsx，Framer Motion 动画 |
| 8 | `components/confirm-dialog.css` | ✅ 已删除 | 5+ | ~177行 | 9f4f7de4 | 迁移到 ConfirmDialog.tsx，overlayFadeIn/dialogSlideIn 保留 |

#### 🟡 Buttons（待处理，3 items）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | 策略 | 备注 |
|---|------|--------|----------|----------|------|------|
| 30 | `buttons/base.css` | 🔴 High | 100+ | 3h | 创建 Button 组件 | 全局 button 样式 |
| 33 | `buttons/variants.css` | 🔴 High | 30+ | 3h | Button 组件变体 | primary/secondary/danger |
| 31 | `buttons/groups.css` | 🔴 High | 20+ | 2h | Button 组件扩展 | row-actions 样式 |
| 32 | `buttons/index.css` | 🟢 Low | - | 5min | 删除 imports | Entry 文件 |

**建议顺序：** 先创建 ui/Button.tsx 组件，再逐个替换使用，最后删除 CSS

#### 🟡 Forms（待处理，4 items）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | 策略 | 备注 |
|---|------|--------|----------|----------|------|------|
| 35 | `forms/inputs.css` | 🔴 High | 50+ | 3h | 创建 Input/Textarea | 全局 input 样式 |
| 36 | `forms/selects.css` | 🔴 High | 30+ | 2h | 创建 Select | 全局 select 样式 |
| 37 | `forms/validation.css` | 🟡 Medium | 20+ | 1h | Form validation | error/success 状态 |
| 34 | `forms/index.css` | 🟢 Low | - | 5min | 删除 imports | Entry 文件 |

**建议顺序：** 先创建 ui/Input, ui/Select 组件，再逐个替换，最后删除 CSS

#### 🟡 Badges & Status（待处理，1 item）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | 策略 | 备注 |
|---|------|--------|----------|----------|------|------|
| 12 | `components/badges.css` | 🟡 Medium | 17 | 2-3h | 创建 Badge/Status | role-badge, status |

**keyframes:** 无  
**dark mode:** 是  
**响应式:** 否

#### 🟡 Skeletons（待处理，1 item）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | 策略 | 备注 |
|---|------|--------|----------|----------|------|------|
| 22 | `components/skeletons.css` | 🟡 Medium | 10 | 1-2h | 保留 shimmer keyframes | skeleton-list |

**keyframes:** ✅ skeleton-shimmer（保留）  
**dark mode:** 是  
**建议:** 保留 @keyframes，迁移基础样式

#### 🟡 Spinners（待处理，1 item）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | 策略 | 备注 |
|---|------|--------|----------|----------|------|------|
| 23 | `components/spinners.css` | 🟡 Medium | 10 | 1-2h | 替换为 Spinner 组件 | 全局 .spinner 类 |

**建议:** 替换所有 `.spinner` 使用为 `<Spinner />` 组件

#### 🟡 Animation Wrappers（待处理，5 items）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | 策略 | 备注 |
|---|------|--------|----------|----------|------|------|
| 1 | `animations/AnimatedButton.css` | 🟡 Medium | 1 | 1h | 保留 keyframes | 复杂动画 |
| 2 | `animations/AnimatedButtonLite.css` | 🟡 Medium | 1 | 1h | 保留 keyframes | 复杂动画 |
| 3 | `animations/AnimatedToast.css` | 🟡 Medium | 1 | 1h | 保留 keyframes | slide-in/out |
| 4 | `animations/AnimatedToastLite.css` | 🟡 Medium | 1 | 1h | 保留 keyframes | slide-in/out |

**建议:** 所有 keyframes 保留在 CSS，只迁移基础布局样式

---

### Phase 3: 复合组件与 SessionManagement（16 items）

#### 🔴 SessionManagement（4 items，高复杂度）

| # | 文件 | 优先级 | 行数 | 预计时间 | keyframes | 备注 |
|---|------|--------|------|----------|-----------|------|
| 7 | `SessionManagement/SessionExportImport.css` | 🔴 High | 370 | 3-4h | spin | file-drop-zone 复杂交互 |
| 8 | `SessionManagement/SessionMetadataEditor.css` | 🔴 High | ~200 | 2-3h | 否 | 表单编辑器 |
| 9 | `SessionManagement/SessionSearch.css` | 🟡 Medium | ~150 | 2h | 否 | 搜索界面 |
| 10 | `SessionManagement/TagInput.css` | 🟡 Medium | ~100 | 1-2h | 否 | tag 输入组件 |

**建议:** 分4次提交，逐个迁移

#### 🟡 Cards & Tables（2 items）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | 备注 |
|---|------|--------|----------|----------|------|
| 13 | `components/cards.css` | 🟡 Medium | 10+ | 2h | panel 样式 |
| 24 | `components/tables.css` | 🟡 Medium | 8+ | 2h | admin tables |

#### 🟡 Dialogs & Modals（3 items）

| # | 文件 | 优先级 | 使用位置 | 预计时间 | keyframes | 备注 |
|---|------|--------|----------|----------|-----------|------|
| 21 | `components/modals.css` | 🟡 Medium | 10+ | 2-3h | 可能 | 通用 modal |
| 18 | `components/dropdowns.css` | 🟡 Medium | 8+ | 1-2h | 否 | dropdown 菜单 |

#### 🟡 其他复合组件（6 items）

| # | 文件 | 优先级 | 预计时间 | keyframes | 备注 |
|---|------|--------|----------|-----------|------|
| 14 | `components/clarification-prompt.css` | 🟡 Medium | 2h | 否 | 澄清提示 UI |
| 26 | `components/thinking-indicator.css` | 🟡 Medium | 1-2h | ✅ pulse | 保留 keyframes |
| 15 | `components/code-block.css` | 🟡 Medium | 1-2h | 否 | 代码块样式 |
| 25 | `components/topbar.css` | 🟡 Medium | 2h | 否 | 顶部导航栏 |
| 27 | `components/topbar-responsive.css` | 🟡 Medium | 1h | 否 | topbar 响应式 |

---

### Phase 4: Chat, Sidebar, Topbar, Composer（20 items）

#### 🔴 Sidebar（10 items，最关键）

| # | 文件 | 优先级 | 预计时间 | 关键点 | 备注 |
|---|------|--------|----------|--------|------|
| 42 | `sidebar/layout.css` | 🔴 High | 2h | 1080px 边界 | 核心布局 |
| 43 | `sidebar/modern-layout.css` | 🔴 High | 2h | flex/grid | 现代布局 |
| 44 | `sidebar/modern-sessions.css` | 🔴 High | 2h | session 列表 | 交互状态 |
| 45 | `sidebar/navigation.css` | 🟡 Medium | 1-2h | nav 状态 | active/hover |
| 46 | `sidebar/modules.css` | 🟡 Medium | 1h | module cards | 卡片布局 |
| 38 | `sidebar/actions.css` | 🟡 Medium | 1h | 操作按钮 | 小按钮 |
| 40 | `sidebar/footer.css` | 🟡 Medium | 1h | 底部控件 | auth controls |
| 39 | `sidebar/backdrop.css` | 🟢 Low | 30min | mobile overlay | 遮罩层 |
| 47 | `sidebar/rail.css` | 🟢 Low | 30min | 折叠态 | collapsed |
| 48 | `sidebar/responsive.css` | 🔴 High | 2h | 1079/1081 | **关键验证** |
| 41 | `sidebar/index.css` | 🟢 Low | 5min | Entry | 删除 imports |

**总计:** ~13-15 小时  
**建议:** 分 3-4 次提交，每次 2-3 个文件  
**验证重点:** 1079px vs 1081px 必须通过视觉测试

#### 🔴 Composer（4 items）

| # | 文件 | 优先级 | 预计时间 | 关键点 | 备注 |
|---|------|--------|----------|--------|------|
| 60 | `composer/editor.css` | 🔴 High | 2-3h | textarea 状态 | focus/disabled |
| 59 | `composer/actions.css` | 🟡 Medium | 1-2h | 操作按钮 | send/attach |
| 62 | `composer/layout.css` | 🟡 Medium | 1-2h | 响应式布局 | viewport matrix |
| 61 | `composer/index.css` | 🟢 Low | 5min | Entry | 删除 imports |

**总计:** ~5-7 小时

#### 🟡 Chat Features（6 items）

| # | 文件 | 优先级 | 预计时间 | 关键点 | 备注 |
|---|------|--------|----------|--------|------|
| 56 | `features/messages.css` | 🔴 High | 3h | message cards | 最重要 |
| 53 | `features/citations.css` | 🟡 Medium | 1-2h | 引用样式 | inline citations |
| 54 | `features/graph.css` | 🟡 Medium | 1h | 图表 | process graph |
| 57 | `features/process.css` | 🟡 Medium | 1h | 过程面板 | runtime info |
| 58 | `features/runtime-panels.css` | 🟡 Medium | 1h | 运行时面板 | debug panels |
| 55 | `features/hidden-sections.css` | 🟢 Low | 30min | toggle 状态 | show/hide |

**总计:** ~8-10 小时

---

### Phase 5: 页面迁移（15 items）

#### 🟡 Auth Pages（4 items）

| # | 文件 | 优先级 | 行数 | 预计时间 | 验证场景 |
|---|------|--------|------|----------|----------|
| 79 | `pages/auth/layout.css` | 🟡 Medium | 334 | 3-4h | login EN/ZH light/dark |
| 78 | `pages/auth/forms.css` | 🟡 Medium | ~150 | 2h | 表单状态 |
| 80 | `pages/auth/social.css` | 🟢 Low | ~50 | 30min | 审计可达性 |
| 66 | `pages/auth-entry.css` | 🟢 Low | - | 5min | Entry，删除 imports |

**总计:** ~6-7 小时  
**验证:** login-en-light, login-en-dark, login-zh-light

#### 🟡 Landing Page（2 items）

| # | 文件 | 优先级 | 行数 | 预计时间 | 验证场景 |
|---|------|--------|------|----------|----------|
| 71 | `pages/landing.css` | 🟡 Medium | ~400 | 3-4h | landing 所有场景 |
| 70 | `pages/landing-entry.css` | 🟢 Low | - | 5min | Entry |

**验证:** landing-en-light, landing-en-dark, landing-zh-light, landing-en-mobile-375

#### 🟡 Admin Pages（6 items）

| # | 文件 | 优先级 | 预计时间 | 备注 |
|---|------|--------|----------|------|
| 75 | `pages/admin/layout.css` | 🟡 Medium | 2-3h | admin 主布局 |
| 74 | `pages/admin/forms.css` | 🟡 Medium | 1-2h | admin 表单 |
| 77 | `pages/admin/tables.css` | 🟡 Medium | 1-2h | admin 表格 |
| 73 | `pages/admin/actions.css` | 🟡 Medium | 1h | 操作按钮 |
| 76 | `pages/admin/ops.css` | 🟡 Medium | 1h | ops 面板 |
| 63 | `pages/admin-entry.css` | 🟢 Low | 5min | Entry |

**总计:** ~7-10 小时  
**验证:** admin-en-light, admin-en-dark

#### 🟡 Other Pages（3 items）

| # | 文件 | 优先级 | 预计时间 | 验证场景 |
|---|------|--------|----------|----------|
| 64 | `pages/analytics.css` | 🟡 Medium | 2h | analytics-en-light |
| 65 | `pages/architecture.css` | 🟡 Medium | 2h | architecture-en-light |
| 72 | `pages/profile.css` | 🟡 Medium | 1-2h | profile-en-light |

**总计:** ~5-6 小时

---

### Phase 6: Chat Page & Dark Themes（5 items）

#### 🟡 Chat Page Wrappers（3 items）

| # | 文件 | 优先级 | 预计时间 | 关键点 | 验证 |
|---|------|--------|----------|--------|------|
| 69 | `pages/chat.css` | 🟡 Medium | 2h | chat 主样式 | chat 所有场景 |
| 68 | `pages/chat-responsive.css` | 🔴 High | 2-3h | 响应式 | 375/768/1079/1081/1440 |
| 67 | `pages/chat-entry.css` | 🟢 Low | 5min | Entry | - |

**验证:** chat-en-light-desktop, chat-en-dark-desktop, chat-zh-light-desktop, chat 所有 viewport

#### 🟢 Dark Theme Overrides（2 items）

| # | 文件 | 优先级 | 预计时间 | 策略 |
|---|------|--------|----------|------|
| 81 | `themes/dark/chat.css` | 🟢 Low | 1h | 迁移到 tw:dark: |
| 83 | `themes/dark/effects.css` | 🟢 Low | 1h | 迁移到 tw:dark: |
| 85 | `themes/light/chat.css` | 🟢 Low | 1h | 迁移到组件 |

---

### Phase 7: Core & Cleanup（8 items）

#### 🔒 Core Files（保留必要，4 items）

| # | 文件 | 状态 | 预计行动 | 备注 |
|---|------|------|----------|------|
| 49 | `core/critical.css` | 🔒 保留 | 更新内容 | 关键 CSS 插件依赖 |
| 50 | `core/reset.css` | 🔒 保留 | 保持不变 | 全局 reset |
| 51 | `core/tokens.css` | 🔒 保留 | 保持不变 | Light 变量真值 |
| 52 | `core/utilities.css` | 🟡 审计 | 逐规则删除 | 已迁移的删除 |

#### 🟢 Tokens（审计，3 items）

| # | 文件 | 状态 | 预计时间 | 行动 |
|---|------|------|----------|------|
| 86 | `tokens/colors.css` | 🟢 审计 | 30min | 确认不可达后删除 |
| 87 | `tokens/spacing.css` | 🟢 审计 | 30min | 确认不可达后删除 |
| 88 | `tokens/timing.css` | 🟢 审计 | 30min | 确认不可达后删除 |

**行动:**
```powershell
rg "import.*colors\.css" src
rg "import.*spacing\.css" src
rg "import.*timing\.css" src
# 如果无引用，删除
```

#### 🔒 Dark Theme & Entries（保留/清理，4 items）

| # | 文件 | 状态 | 预计行动 |
|---|------|------|----------|
| 82 | `themes/dark/colors.css` | 🔒 保留 | Dark 变量真值 |
| 84 | `themes/dark/index.css` | 🔒 保留 | 缩减 imports |
| 11 | `styles/main.css` | 🔒 保留 | 缩减 imports |

---

## 📈 工作量估算

### 按复杂度

| 复杂度 | 文件数 | 单文件时间 | 总时间 |
|--------|--------|------------|--------|
| 🟢 Low | 15 | 30min | 7.5h |
| 🟡 Medium | 35 | 1.5h | 52.5h |
| 🔴 High | 20 | 3h | 60h |
| 🔒 保留 | 15 | 30min | 7.5h |
| ✅ 完成 | 3 | - | - |

**总计：** 127.5 小时（理论最大值）

### 实际预估（考虑批处理效率）

| 阶段 | 文件数 | 预计时间 | 备注 |
|------|--------|----------|------|
| Phase 2 剩余 | 17 | 20-25h | buttons/forms 最耗时 |
| Phase 3 | 16 | 15-20h | SessionManagement 复杂 |
| Phase 4 | 20 | 20-25h | Sidebar 最关键 |
| Phase 5 | 15 | 18-25h | 页面迁移 |
| Phase 6 | 5 | 5-8h | Chat wrappers |
| Phase 7 | 8 | 3-5h | 审计清理 |

**实际总计：** 81-108 小时

### 按会话分配

| 会话 | 完成阶段 | 预计时间 | 进度 |
|------|----------|----------|------|
| Session 1（当前）| Phase 1 + Phase 2 部分 | 已完成 | 3/88 (3.4%) |
| Session 2 | Phase 2 剩余 + Phase 3 | 35-45h | → 36/88 (41%) |
| Session 3 | Phase 4 + Phase 5 部分 | 35-45h | → 71/88 (81%) |
| Session 4 | Phase 5 剩余 + Phase 6 + Phase 7 | 15-25h | → 88/88 (100%) |

---

## 🎯 快速参考

### 当前会话已完成
- ✅ Phase 1: Tailwind v4 基础设施
- ✅ ThemeToggle, LanguageToggle, Spinner

### 下一批建议（低风险快速胜利）
1. keyboard-help.css（简单 dialog）
2. welcome-screen.css（单页面）
3. hidden-sections.css（简单 toggle）
4. Route entry files（只删除 imports）
5. tokens/审计（确认后删除）

### 高优先级关键路径
1. Sidebar（10 files）- 1080px 边界
2. Composer（4 files）- 输入区
3. Messages（1 file）- 核心 chat
4. Buttons/Forms（全局工具类）

### 必须保留
- core/critical.css
- core/reset.css
- core/tokens.css
- themes/dark/colors.css
- reactflow/dist/style.css（第三方）

---

**使用此清单追踪迁移进度，每完成一个文件更新状态和提交 hash。**
