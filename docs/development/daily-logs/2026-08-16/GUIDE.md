# 动画组件库 - 完整使用指南

**版本**: v1.0.0  
**创建日期**: 2026-08-16  
**状态**: ✅ 生产就绪

---

## 📦 已实现组件

- ✅ **AnimatedButton** - 5状态智能按钮
- ✅ **AnimatedToast** - 堆叠通知系统
- ✅ **Spinner** - 旋转加载指示器
- ✅ **Skeleton** - 骨架屏占位符

---

## 🚀 快速开始

### 安装依赖

```bash
# 已包含在项目中
npm install framer-motion
```

### 导入组件

```typescript
import {
  AnimatedButton,
  AnimatedToast,
  ToastContainer,
  useToast,
  Spinner,
  Skeleton,
  SkeletonText,
  SkeletonAvatar,
  SkeletonCard
} from '@/components/animations';
```

---

## 1️⃣ AnimatedButton

### 基础用法

```tsx
<AnimatedButton onClick={() => console.log('clicked')}>
  点击我
</AnimatedButton>
```

### 异步操作（自动状态管理）

```tsx
<AnimatedButton 
  onClick={async () => {
    await fetch('/api/submit');
    // 自动显示 loading → success/error
  }}
>
  提交
</AnimatedButton>
```

### 所有变体

```tsx
<AnimatedButton variant="primary">主要操作</AnimatedButton>
<AnimatedButton variant="secondary">次要操作</AnimatedButton>
<AnimatedButton variant="ghost">幽灵按钮</AnimatedButton>
<AnimatedButton variant="danger">删除</AnimatedButton>
```

### 所有尺寸

```tsx
<AnimatedButton size="small">小</AnimatedButton>
<AnimatedButton size="medium">中</AnimatedButton>
<AnimatedButton size="large">大</AnimatedButton>
```

**详细文档**: [AnimatedButton/README.md](./AnimatedButton/README.md)

---

## 2️⃣ AnimatedToast

### 使用Toast Hook

```tsx
function MyComponent() {
  const toast = useToast();

  const handleClick = () => {
    toast.success('操作成功！');
    toast.error('出错了！');
    toast.warning('警告信息');
    toast.info('提示信息');
  };

  return (
    <>
      <button onClick={handleClick}>显示通知</button>
      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </>
  );
}
```

### 自定义持续时间

```tsx
toast.success('保存成功', 6000); // 6秒后自动关闭
```

### 特性

- ✅ 4种类型（info, success, warning, error）
- ✅ 自动堆叠动画
- ✅ 悬停暂停自动关闭
- ✅ 进度条指示剩余时间
- ✅ 点击关闭

---

## 3️⃣ Spinner

### 基础用法

```tsx
<Spinner />
```

### 不同尺寸

```tsx
<Spinner size="small" />   {/* 16px */}
<Spinner size="medium" />  {/* 24px */}
<Spinner size="large" />   {/* 32px */}
<Spinner size={48} />      {/* 自定义 */}
```

### 自定义颜色

```tsx
<Spinner color="#5B8CFF" />
<Spinner color="var(--color-primary)" />
```

### 在按钮中使用

```tsx
<button disabled>
  <Spinner size="small" color="white" />
  <span>加载中...</span>
</button>
```

---

## 4️⃣ Skeleton

### 基础骨架屏

```tsx
<Skeleton width={200} height={20} />
```

### 三种变体

```tsx
<Skeleton variant="text" />        {/* 文本行 */}
<Skeleton variant="circular" />    {/* 圆形（头像）*/}
<Skeleton variant="rectangular" /> {/* 矩形（卡片）*/}
```

### 动画类型

```tsx
<Skeleton animation="pulse" />  {/* 脉冲动画（默认）*/}
<Skeleton animation="wave" />   {/* 波浪动画 */}
<Skeleton animation="none" />   {/* 无动画 */}
```

### 预设组件

#### 多行文本骨架屏

```tsx
<SkeletonText lines={3} lastLineWidth="60%" />
```

#### 头像骨架屏

```tsx
<SkeletonAvatar size={40} />
```

#### 卡片骨架屏

```tsx
<SkeletonCard />
```

### 实际场景示例

#### 列表加载

```tsx
function UserList({ loading, users }) {
  if (loading) {
    return (
      <div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
            <SkeletonAvatar size={48} />
            <div style={{ flex: 1 }}>
              <Skeleton width="60%" height={16} />
              <Skeleton width="40%" height={14} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return users.map(user => <UserCard key={user.id} user={user} />);
}
```

#### 文章加载

```tsx
function ArticleLoading() {
  return (
    <div>
      <Skeleton variant="rectangular" height={200} />
      <div style={{ padding: '16px' }}>
        <Skeleton width="80%" height={24} />
        <SkeletonText lines={4} />
      </div>
    </div>
  );
}
```

---

## 🎨 组合使用示例

### 完整的表单提交流程

```tsx
function SubmitForm() {
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await api.submit();
      toast.success('提交成功！');
    } catch (error) {
      toast.error('提交失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <AnimatedButton 
        onClick={handleSubmit}
        disabled={loading}
      >
        {loading ? <Spinner size="small" color="white" /> : '提交'}
      </AnimatedButton>
      
      <ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
    </div>
  );
}
```

### 数据加载页面

```tsx
function DataPage() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchData().then(result => {
      setData(result);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div>
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  return <DataDisplay data={data} />;
}
```

---

## 🎯 性能优化

### 所有组件均已优化

- ✅ GPU加速（transform, opacity）
- ✅ 60fps动画保证
- ✅ prefers-reduced-motion支持
- ✅ Tree-shaking友好
- ✅ 无内存泄漏

### Bundle大小

| 组件 | 大小 |
|------|------|
| AnimatedButton | ~3KB |
| AnimatedToast | ~2.5KB |
| Spinner | ~0.8KB |
| Skeleton | ~1.2KB |
| **总计** | **~7.5KB** |

---

## ♿ 无障碍支持

### 已实现的无障碍特性

1. **键盘导航**
   - 所有按钮支持 Tab 聚焦
   - Enter/Space 触发操作

2. **屏幕阅读器**
   - 适当的 ARIA 标签
   - role="status" 和 aria-live

3. **减少动画**
   - 自动检测 prefers-reduced-motion
   - 降级为简单过渡或无动画

4. **高对比度模式**
   - 自动适配 prefers-contrast: high

---

## 📱 响应式支持

### Toast移动端适配

```css
/* 自动适配小屏幕 */
@media (max-width: 640px) {
  .toast-container {
    left: 12px;
    right: 12px;
  }
}
```

### Skeleton响应式

```tsx
<Skeleton width={{ base: '100%', md: '300px' }} />
```

---

## 🧪 测试

### 运行测试

```bash
npm run test AnimatedButton
npm run test AnimationComponents
```

### 测试覆盖

- ✅ 单元测试（20+ test cases）
- ✅ 渲染性能测试
- ✅ 批量渲染测试
- ✅ 无障碍测试

---

## 📚 相关文档

- [AnimatedButton详细文档](./AnimatedButton/README.md)
- [性能基线报告](../../../superpowers/2026-08-16/reports/performance-baseline-report.md)
- [设计规格](../../../superpowers/2026-08-16/specs/micro-interactions-spec.md)

---

## 🔧 故障排查

### 动画不流畅？

1. 检查是否使用了非GPU加速属性（width, height, left, top）
2. 确认Framer Motion版本 ≥10.x
3. 使用Chrome DevTools Performance分析

### Toast不显示？

确保ToastContainer已添加到页面：

```tsx
<ToastContainer toasts={toast.toasts} onClose={toast.removeToast} />
```

### TypeScript类型错误？

确保已安装类型定义：

```bash
npm install --save-dev @types/react @types/react-dom
```

---

**最后更新**: 2026-08-16  
**维护者**: Animation Team  
**状态**: ✅ 生产就绪
