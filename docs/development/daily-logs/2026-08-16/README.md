# AnimatedButton 组件

## 概述

带动画效果的按钮组件，支持5种状态和多种变体，使用Framer Motion实现流畅的60fps动画。

## 特性

✅ **5种状态**：idle, hover, active, loading, success, error  
✅ **4种变体**：primary, secondary, ghost, danger  
✅ **3种尺寸**：small, medium, large  
✅ **动画效果**：
- Hover: scale 1.02 (200ms ease-out)
- Active: scale 0.97 (100ms ease-in)
- Loading: 旋转spinner (1s linear infinite)
- Success: 弹簧入场动画 + ✓ 图标
- Error: 抖动动画 + ✗ 图标

✅ **无障碍支持**：
- 键盘导航（focus-visible outline）
- prefers-reduced-motion 支持
- 语义化HTML

✅ **性能优化**：
- GPU加速（transform, opacity）
- will-change 优化
- 60fps保证

## 使用示例

### 基础用法

```tsx
import { AnimatedButton } from '@/components/animations';

function App() {
  return (
    <AnimatedButton onClick={() => console.log('clicked')}>
      点击我
    </AnimatedButton>
  );
}
```

### 异步操作（自动状态管理）

```tsx
<AnimatedButton 
  onClick={async () => {
    await fetch('/api/submit');
    // 自动显示loading → success/error
  }}
>
  提交
</AnimatedButton>
```

### 变体

```tsx
<AnimatedButton variant="primary">主要操作</AnimatedButton>
<AnimatedButton variant="secondary">次要操作</AnimatedButton>
<AnimatedButton variant="ghost">幽灵按钮</AnimatedButton>
<AnimatedButton variant="danger">危险操作</AnimatedButton>
```

### 尺寸

```tsx
<AnimatedButton size="small">小按钮</AnimatedButton>
<AnimatedButton size="medium">中按钮</AnimatedButton>
<AnimatedButton size="large">大按钮</AnimatedButton>
```

### 外部状态控制

```tsx
const [state, setState] = useState<'idle' | 'loading'>('idle');

<AnimatedButton 
  state={state}
  onClick={() => {
    setState('loading');
    // 手动控制状态
  }}
>
  自定义状态
</AnimatedButton>
```

### 禁用状态

```tsx
<AnimatedButton disabled>禁用按钮</AnimatedButton>
```

## Props API

```typescript
interface AnimatedButtonProps {
  children: React.ReactNode;           // 按钮内容
  onClick?: () => Promise<void> | void; // 点击回调
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; // 变体
  size?: 'small' | 'medium' | 'large'; // 尺寸
  disabled?: boolean;                   // 禁用状态
  state?: ButtonState;                  // 外部状态控制
  className?: string;                   // 自定义类名
}

type ButtonState = 'idle' | 'hover' | 'active' | 'loading' | 'success' | 'error';
```

## 动画参数

基于Design Tokens系统：

- **Hover**: scale 1.02, 200ms ease-out (`--timing-button-hover`)
- **Active**: scale 0.97, 100ms ease-in (`--timing-button-active`)
- **Loading**: rotate 360deg, 1s linear infinite
- **Success/Error**: spring(stiffness: 300, damping: 30)
- **Error shake**: 0.5s 抖动动画

## 颜色变体

| 变体 | 背景 | 用途 |
|------|------|------|
| primary | 蓝紫渐变 | 主要操作（提交、确认）|
| secondary | 半透明白色 | 次要操作（取消、返回）|
| ghost | 透明 | 文本链接式按钮 |
| danger | 红色渐变 | 危险操作（删除、重置）|

## 无障碍

- ✅ 键盘导航：`Tab` 聚焦，`Enter/Space` 触发
- ✅ Focus visible outline（2px primary color）
- ✅ `prefers-reduced-motion` 自动禁用动画
- ✅ Loading/Disabled状态自动设置 `pointer-events: none`

## 浏览器兼容性

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## 依赖

- `framer-motion`: ^10.x
- `react`: ^18.x
- Design Tokens: `colors.css`, `timing.css`, `spacing.css`

## 文件结构

```
animations/
├── AnimatedButton.tsx       # 组件逻辑
├── AnimatedButton.css       # 样式
├── index.ts                 # 导出
└── README.md               # 本文件
```

## 性能

- 60fps动画（Chrome DevTools验证）
- GPU加速（transform + will-change）
- 无内存泄漏（2秒后自动恢复state）

---

**版本**: v1.0.0  
**创建日期**: 2026-08-16  
**规格参考**: [micro-interactions-spec.md](../../../superpowers/2026-08-16/specs/micro-interactions-spec.md)
