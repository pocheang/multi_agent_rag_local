/**
 * Skeleton - 骨架屏加载占位符
 *
 * 支持3种变体：text, circular, rectangular
 * 流畅的闪烁动画效果
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { motion } from 'framer-motion';
import './Skeleton.css';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  variant?: 'text' | 'circular' | 'rectangular';
  className?: string;
  animation?: 'pulse' | 'wave' | 'none';
}

export function Skeleton({
  width = '100%',
  height = 20,
  variant = 'text',
  className = '',
  animation = 'pulse',
}: SkeletonProps) {
  const borderRadius = {
    text: 4,
    circular: '50%',
    rectangular: 8,
  }[variant];

  const animationVariants = {
    pulse: {
      opacity: [0.5, 1, 0.5],
    },
    wave: {
      backgroundPosition: ['200% 0', '-200% 0'],
    },
    none: {},
  };

  const animationTransition = {
    pulse: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'easeInOut' as const,
    },
    wave: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'linear' as const,
    },
    none: {},
  };

  return (
    <motion.div
      className={`skeleton skeleton--${variant} skeleton--${animation} ${className}`}
      style={{
        width,
        height,
        borderRadius,
      }}
      animate={animationVariants[animation]}
      transition={animationTransition[animation]}
      role="status"
      aria-label="加载中"
    >
      <span className="skeleton__sr-only">加载中...</span>
    </motion.div>
  );
}

// 预设组件变体
export function SkeletonText({ lines = 3, lastLineWidth = '60%', ...props }:
  Omit<SkeletonProps, 'variant'> & { lines?: number; lastLineWidth?: string | number }
) {
  return (
    <div className="skeleton-text-group">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          width={i === lines - 1 ? lastLineWidth : '100%'}
          {...props}
        />
      ))}
    </div>
  );
}

export function SkeletonAvatar({ size = 40, ...props }:
  Omit<SkeletonProps, 'variant' | 'width' | 'height'> & { size?: number }
) {
  return (
    <Skeleton
      variant="circular"
      width={size}
      height={size}
      {...props}
    />
  );
}

export function SkeletonCard({ ...props }: Omit<SkeletonProps, 'variant'>) {
  return (
    <div className="skeleton-card">
      <Skeleton variant="rectangular" height={200} {...props} />
      <div className="skeleton-card__content">
        <Skeleton variant="text" width="80%" />
        <Skeleton variant="text" width="60%" />
      </div>
    </div>
  );
}
