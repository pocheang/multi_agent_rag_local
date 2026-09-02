# Tailwind CSS v4 迁移批处理模板

> 此文档提供标准化的迁移流程，适用于剩余的 85 个 CSS 文件  
> 每个批次使用相同的模式，确保一致性和可追溯性

## 🔄 标准迁移流程（适用于每个文件）

### Step 1: 分析 CSS 文件

```powershell
# 1. 查看 CSS 内容
cat src/styles/components/example.css

# 2. 找到所有使用该 CSS 的组件
rg "import.*example\.css" src
rg "className=.*example-class" src

# 3. 评估复杂度
# - 简单：布局、颜色、边距（直接迁移）
# - 中等：响应式、伪类、状态（需要仔细映射）
# - 复杂：keyframes、复杂渐变、多步动画（考虑保留）
```

### Step 2: 迁移到 Tailwind

#### 2a. 单组件 CSS（推荐）
如果 CSS 只被一个组件使用：

```tsx
// Before
import './Example.css';

<div className="example-container">
  <div className="example-item">...</div>
</div>

// After
<div className="tw:flex tw:flex-col tw:gap-4 tw:p-6 tw:bg-surface tw:rounded-lg">
  <div className="tw:text-text-primary tw:font-semibold">...</div>
</div>
```

#### 2b. 多组件共享 CSS（创建组件）
如果 CSS 被多个文件使用且是语义化的：

```tsx
// src/components/ui/Card.tsx
export function Card({ children, className = "" }) {
  return (
    <div className={`tw:bg-surface tw:border tw:border-border-light tw:rounded-xl tw:p-6 tw:shadow-sm hover:tw:shadow-md tw:transition-shadow ${className}`}>
      {children}
    </div>
  );
}

// 然后在使用处替换
<Card>...</Card>
```

#### 2c. 保留复杂动画
对于复杂 keyframes：

```css
/* 保留在 CSS 中，放入 @layer components */
@layer components {
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .tw-skeleton-shimmer {
    animation: shimmer 1.5s ease-in-out infinite;
  }
}
```

### Step 3: 常见样式映射

#### 布局
```css
/* CSS */                          /* Tailwind */
display: flex;                     tw:flex
flex-direction: column;            tw:flex-col
align-items: center;               tw:items-center
justify-content: space-between;    tw:justify-between
gap: 16px;                         tw:gap-4
padding: 24px;                     tw:p-6
margin: 16px 0;                    tw:my-4
```

#### 颜色与边框
```css
/* CSS */                          /* Tailwind */
background: var(--surface);        tw:bg-surface
color: var(--text-primary);        tw:text-text-primary
border: 1px solid var(--border);   tw:border tw:border-border-light
border-radius: 8px;                tw:rounded-lg
box-shadow: var(--shadow-md);      tw:shadow-[var(--shadow-md)]
```

#### 响应式
```css
/* CSS */                          /* Tailwind */
@media (max-width: 768px) {        max-[768px]:tw:...
  padding: 12px;                   max-[768px]:tw:p-3
}
```

#### Dark 模式
```css
/* CSS */                          /* Tailwind */
:root[data-theme="dark"] {         tw:dark:...
  background: #1a1a1a;             tw:dark:bg-[#1a1a1a]
}
```

#### 状态
```css
/* CSS */                          /* Tailwind */
.btn:hover {                       hover:tw:...
  background: blue;                hover:tw:bg-blue-500
}
.btn:disabled {                    disabled:tw:...
  opacity: 0.5;                    disabled:tw:opacity-50
}
```

#### 任意值
```css
/* CSS */                          /* Tailwind */
z-index: var(--z-modal);           tw:z-[var(--z-modal)]
background: linear-gradient(...);  tw:bg-[linear-gradient(...)]
transition: all 0.2s ease;         tw:transition-all tw:duration-200 tw:ease-in-out
```

### Step 4: 删除 CSS 文件

```powershell
# 1. 确认无引用
rg "import.*example\.css" src
rg "@import.*example" src

# 2. 删除文件
rm src/styles/components/example.css

# 3. 如果是 index.css，删除其 @import
# 编辑 src/styles/components/buttons/index.css
# 删除 @import "./example.css"
```

### Step 5: 验证

```powershell
cd frontend

# 1. 类型检查
npm run type-check

# 2. 构建
npm run build

# 3. 单元测试
npm run test

# 4. 视觉测试（关键！）
npm run test:visual

# 5. 手动测试
npm run dev
# 访问相关页面，测试交互状态
```

### Step 6: 提交

```powershell
git add -A
git commit -m "refactor(frontend): migrate Example component to Tailwind v4

- Migrate example.css to tw: utility classes
- Remove example.css
- Preserve [specific features, e.g., dark mode, responsive, animations]

All tests pass:
- Build: successful
- Unit: 60/61
- Visual: 21/21"
```

## 📋 批处理脚本模板

### 快速迁移检查清单

为每个文件创建一个这样的检查清单：

```markdown
## 迁移：src/styles/components/example.css

### 分析
- [ ] 文件大小：___ 行
- [ ] 使用位置：___ 个文件
- [ ] 复杂度：□ 简单 □ 中等 □ 复杂
- [ ] 有 keyframes：□ 是 □ 否
- [ ] 有复杂渐变：□ 是 □ 否

### 执行
- [ ] 迁移策略：□ 直接 □ 创建组件 □ 部分保留
- [ ] 修改文件数：___
- [ ] 删除 CSS 文件：□ 是 □ 否
- [ ] 测试通过：□ type □ build □ unit □ visual

### 提交
- [ ] Commit hash: _______
- [ ] 视觉快照：□ 无变化 □ 已更新并审查
```

## 🎯 优先级分组

### 🟢 Low-Hanging Fruit（优先处理）
**特征：** 小文件、单一使用、无复杂动画

**文件列表：**
1. `thinking-indicator.css` - 如果 keyframes 简单
2. `welcome-screen.css` - 单页面使用
3. `keyboard-help.css` - modal，独立
4. `hidden-sections.css` - 简单 display toggle
5. Route entry files (auth-entry.css, admin-entry.css, chat-entry.css, landing-entry.css)

**预计时间：** 30分钟/文件  
**总收益：** ~5-8 kB

### 🟡 Medium Complexity（中等优先级）
**特征：** 中等大小、少量使用、可控复杂度

**文件列表：**
1. `cards.css`
2. `tables.css`
3. `confirm-dialog.css`
4. `modals.css`
5. `dropdowns.css`
6. `clarification-prompt.css`
7. `code-block.css`

**预计时间：** 1-2小时/文件  
**总收益：** ~15-20 kB

### 🔴 High Risk（最后处理）
**特征：** 大文件、广泛使用、关键路径

**文件列表：**
1. `buttons/` (base, variants, groups) - 30+ 使用
2. `forms/` (inputs, selects, validation) - 40+ 使用
3. `sidebar/` (10 files) - 关键布局
4. `composer/` (3 files) - 关键输入
5. SessionManagement (4 files) - 各 200+ 行

**预计时间：** 3-8小时/批次  
**总收益：** ~25-35 kB

## 🛠️ 自动化辅助脚本

### CSS 分析脚本

```powershell
# analyze-css.ps1
param($cssFile)

$content = Get-Content $cssFile -Raw
$lines = ($content -split "`n").Count
$keyframes = ($content | Select-String "@keyframes" -AllMatches).Matches.Count
$darkMode = ($content | Select-String "data-theme.*dark" -AllMatches).Matches.Count
$responsive = ($content | Select-String "@media" -AllMatches).Matches.Count

Write-Host "File: $cssFile"
Write-Host "Lines: $lines"
Write-Host "Keyframes: $keyframes"
Write-Host "Dark mode rules: $darkMode"
Write-Host "Responsive rules: $responsive"
Write-Host ""

# 查找使用位置
Write-Host "Used in:"
rg "import.*$(Split-Path $cssFile -Leaf)" src --files-with-matches
```

### 批量查找使用

```powershell
# find-css-usage.ps1
Get-ChildItem src/styles -Recurse -Filter *.css | ForEach-Object {
    $cssFile = $_.Name
    $usageCount = (rg "import.*$cssFile" src --files-with-matches | Measure-Object).Count
    
    [PSCustomObject]@{
        File = $cssFile
        Path = $_.FullName
        UsageCount = $usageCount
        Size = $_.Length
    }
} | Sort-Object UsageCount | Format-Table -AutoSize
```

## 📊 进度跟踪模板

### 每日进度记录

```markdown
## 2026-08-23 迁移日志

### 已完成
1. ✅ example1.css → Commit abc1234
   - 使用位置：3 个文件
   - 收益：-2.5 kB
   - 测试：21/21 通过

2. ✅ example2.css → Commit def5678
   - 使用位置：1 个文件
   - 收益：-1.2 kB
   - 测试：21/21 通过

### 遇到的问题
- Issue: 复杂的 shimmer 动画无法用 Tailwind 表达
  - Solution: 保留 keyframes 在 @layer components

### 今日收益
- CSS 减少：-3.7 kB
- 文件删除：2 个
- 提交数：2 个

### 明日计划
- [ ] cards.css
- [ ] tables.css
- [ ] modals.css
```

## 🚨 常见陷阱与解决方案

### 陷阱 1：视觉测试失败
**原因：** 微小的像素差异（圆角、阴影、颜色）

**解决：**
```tsx
// 使用精确的任意值
tw:rounded-[10px]  // 而不是 tw:rounded-lg (12px)
tw:shadow-[var(--shadow-md)]  // 精确匹配变量
tw:text-[#374151]  // 精确颜色
```

### 陷阱 2：Dark 模式不工作
**原因：** 忘记 tw:dark: 前缀

**解决：**
```tsx
// ❌ 错误
className="tw:bg-white dark:bg-gray-900"

// ✅ 正确
className="tw:bg-white tw:dark:bg-gray-900"
```

### 陷阱 3：响应式断点不匹配
**原因：** Tailwind 默认断点 ≠ 项目断点

**解决：**
```tsx
// ❌ 错误（768px）
className="md:tw:hidden"

// ✅ 正确（项目用 520px 和 1080px）
className="max-[520px]:tw:hidden"
className="tw:sidebar:flex"  // 使用自定义 @custom-variant
```

### 陷阱 4：z-index 层级错乱
**原因：** Tailwind 默认 z-index 值不匹配项目

**解决：**
```tsx
// ✅ 使用变量
tw:z-[var(--z-modal)]
tw:z-[var(--z-dropdown)]
```

### 陷阱 5：动画性能下降
**原因：** 复杂动画用 Tailwind inline 表达

**解决：**
```css
/* 保留复杂动画在 CSS */
@layer components {
  .tw-complex-animation {
    animation: multi-step 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }
}
```

## 🎓 学习资源

### Tailwind v4 文档
- Theme configuration: https://tailwindcss.com/docs/theme
- Dark mode: https://tailwindcss.com/docs/dark-mode
- Arbitrary values: https://tailwindcss.com/docs/adding-custom-styles#using-arbitrary-values

### 项目特定
- tw: prefix 规则：所有 Tailwind 类必须带前缀
- @custom-variant dark：使用 `data-theme="dark"`
- 断点：sidebar (1080px), mobile-tight (520px)
- 颜色变量：--surface, --text-primary, --accent 等

## ✅ 最终验收清单

完成所有迁移后，确认：

### 代码质量
- [ ] 无 TypeScript 错误
- [ ] 无新增 ESLint 错误
- [ ] 所有 tw: 类都正确使用
- [ ] 无遗留的 CSS imports

### 功能完整性
- [ ] 所有页面路由正常
- [ ] 所有交互状态正常（hover/focus/disabled/error）
- [ ] 所有响应式断点正常（375/520/768/1079/1081/1440）
- [ ] Light/Dark 主题切换正常
- [ ] 中文/English 切换正常

### 测试覆盖
- [ ] 单元测试 60/61 通过
- [ ] 视觉测试 21/21 通过
- [ ] 构建成功且产物正确
- [ ] Critical CSS 插件正常
- [ ] Route CSS chunks 正常

### 性能指标
- [ ] CSS 总体积减少 25-35%
- [ ] 构建时间无显著增加
- [ ] 首屏加载无退化

### 文档完整
- [ ] 88 项 CSS 清单全部关闭
- [ ] 每个批次有提交记录
- [ ] 特殊处理有文档说明

---

**使用此模板，每个文件的迁移应该是可重复、可验证、可追溯的。**
