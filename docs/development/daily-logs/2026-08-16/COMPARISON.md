# AnimatedButton vs AnimatedButtonLite - 选择指南

**版本**: v1.0.0  
**创建日期**: 2026-08-16

---

## 🎯 快速决策

| 场景 | 推荐版本 | 理由 |
|------|---------|------|
| **Chat UI / 核心页面** | `AnimatedButtonLite` | 零bundle影响，CSS-only |
| **营销页面 / Landing** | `AnimatedButton` | 复杂动画效果更丰富 |
| **Admin后台** | `AnimatedButtonLite` | 性能优先 |
| **文档/帮助页面** | `AnimatedButtonLite` | 轻量级优先 |
| **需要复杂编排** | `AnimatedButton` | Framer Motion的编排能力 |

---

## 📊 功能对比

| 功能 | AnimatedButton | AnimatedButtonLite |
|------|----------------|-------------------|
| **Hover动画** | ✅ scale 1.02 | ✅ scale 1.02 |
| **Active动画** | ✅ scale 0.97 | ✅ scale 0.97 |
| **Loading状态** | ✅ 旋转spinner | ✅ 旋转spinner |
| **Success状态** | ✅ 弹簧动画 + ✓ | ✅ 弹出动画 + ✓ |
| **Error状态** | ✅ 抖动 + ✗ | ✅ 抖动 + ✗ |
| **变体支持** | ✅ 4种 | ✅ 4种 |
| **尺寸支持** | ✅ 3种 | ✅ 3种 |
| **无障碍** | ✅ 完整 | ✅ 完整 |
| **Bundle影响** | ❌ +126 kB | ✅ +0.6 kB |
| **依赖** | framer-motion | 无 |
| **复杂动画编排** | ✅ 支持 | ❌ 不支持 |

---

## 💻 使用示例

### AnimatedButtonLite (推荐用于Chat UI)

```tsx
import { AnimatedButtonLite } from '@/components/animations/AnimatedButtonLite';

// 基础用法
<AnimatedButtonLite
  onClick={handleSend}
  variant="primary"
  size="large"
  state={isSending ? 'loading' : 'idle'}
>
  发送消息
</AnimatedButtonLite>

// 危险操作
<AnimatedButtonLite
  onClick={handleDelete}
  variant="danger"
  size="small"
>
  删除
</AnimatedButtonLite>
```

### AnimatedButton (用于需要复杂动画的场景)

```tsx
import { AnimatedButton } from '@/components/animations';

// 相同的API
<AnimatedButton
  onClick={handleAction}
  variant="primary"
  size="medium"
>
  执行操作
</AnimatedButton>
```

---

## 🔄 迁移指南

### 从普通button迁移到AnimatedButtonLite

**之前**:
```tsx
<button
  className="composer-primary-btn"
  onClick={handleClick}
  disabled={isLoading}
>
  {isLoading && <span className="spinner" />}
  <span>发送</span>
</button>
```

**之后**:
```tsx
<AnimatedButtonLite
  onClick={handleClick}
  variant="primary"
  size="large"
  state={isLoading ? 'loading' : 'idle'}
  className="composer-primary-btn"
>
  发送
</AnimatedButtonLite>
```

### 从AnimatedButton迁移到AnimatedButtonLite

**只需要改导入**:
```tsx
// 之前
import { AnimatedButton } from '@/components/animations';

// 之后
import { AnimatedButtonLite as AnimatedButton } from '@/components/animations/AnimatedButtonLite';
```

API完全兼容，无需修改JSX代码。

---

## 🎨 CSS自定义

### 覆盖样式

AnimatedButtonLite使用CSS变量，可以轻松自定义：

```css
/* 自定义主题色 */
.my-custom-button.animated-btn-lite--primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.my-custom-button.animated-btn-lite--primary:hover {
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
}

/* 自定义动画时长 */
.my-custom-button {
  transition-duration: 300ms; /* 默认200ms */
}

/* 自定义尺寸 */
.my-custom-button.animated-btn-lite--large {
  padding: 18px 36px;
  font-size: 18px;
}
```

---

## ⚡ 性能考虑

### AnimatedButtonLite的优势

1. **零JS开销** - 纯CSS动画，无运行时计算
2. **GPU加速** - 使用`transform`和`will-change`
3. **Tree-shaking友好** - 没有依赖需要打包
4. **浏览器原生** - 利用浏览器的CSS引擎

### 何时使用AnimatedButton

1. **复杂动画序列** - 需要精确控制时间轴
2. **手势交互** - 拖拽、滑动等
3. **物理模拟** - 弹簧、惯性等效果
4. **动态动画** - 基于数据驱动的动画

---

## 📦 Bundle影响实测

### 实际项目测试（ChatPage）

| 版本 | ChatPage.js | Gzip | 模块数 |
|------|-------------|------|--------|
| 原始（无动画） | 260.74 kB | 75.23 kB | 1238 |
| AnimatedButton | 387.11 kB | 116.56 kB | 1649 |
| AnimatedButtonLite | 261.37 kB | 75.46 kB | 1240 |

**结论**: AnimatedButtonLite对bundle几乎无影响（+0.24%）

---

## 🔧 技术实现细节

### AnimatedButtonLite核心技术

```css
/* GPU加速 */
.animated-btn-lite {
  will-change: transform;
  transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* 避免layout重排 */
.animated-btn-lite:hover {
  transform: scale(1.02); /* 只改变transform，不触发reflow */
}

/* 60fps动画 */
@keyframes spin-lite {
  to { transform: rotate(360deg); } /* 使用transform而非margin */
}
```

### 性能最佳实践

✅ **使用**: `transform`, `opacity`  
❌ **避免**: `width`, `height`, `margin`, `padding`

---

## 🎓 推荐阅读

- [CSS动画性能优化](https://web.dev/animations-guide/)
- [GPU加速的CSS属性](https://www.html5rocks.com/en/tutorials/speed/high-performance-animations/)
- [will-change最佳实践](https://developer.mozilla.org/en-US/docs/Web/CSS/will-change)

---

## 📝 总结

- **默认选择**: `AnimatedButtonLite` - 适用于99%的场景
- **特殊需求**: `AnimatedButton` - 需要复杂动画编排时
- **性能第一**: 核心业务流程使用Lite版本
- **体验第一**: 营销页面可以使用完整版本

**记住**: 最好的动画是用户感觉不到的动画 - 自然、流畅、不打扰。
