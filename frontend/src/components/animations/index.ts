/**
 * Animation Components Index
 * 统一导出所有动画组件
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

// 按钮组件 - Framer Motion版本（功能完整）
export { AnimatedButton } from './AnimatedButton';

// 按钮组件 - 轻量级版本（CSS-only，零依赖）
export { AnimatedButtonLite } from './AnimatedButtonLite';

// Toast通知组件 - Framer Motion版本
export { AnimatedToast, ToastContainer, useToast } from './AnimatedToast';
export type { Toast } from './AnimatedToast';

// Toast通知组件 - 轻量级版本（CSS-only，零依赖）
export {
  AnimatedToastLite,
  ToastContainer as ToastContainerLite,
  ToastProvider,
  useToast as useToastLite
} from './AnimatedToastLite';
export type { Toast as ToastLite } from './AnimatedToastLite';

// 加载状态组件
export { Spinner } from './Spinner';
export { Skeleton, SkeletonText, SkeletonAvatar, SkeletonCard } from './Skeleton';

// 未来组件导出
// export { AnimatedToggle } from './AnimatedToggle';
// export { ProgressBar } from './ProgressBar';
// export { AnimatedDropdown } from './AnimatedDropdown';
