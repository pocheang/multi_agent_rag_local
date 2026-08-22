/**
 * Spinner - 旋转加载指示器
 *
 * 支持3种尺寸和自定义颜色
 * 使用SVG实现流畅的60fps动画
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { motion } from 'framer-motion';
import './Spinner.css';

interface SpinnerProps {
  size?: 'small' | 'medium' | 'large' | number;
  color?: string;
  className?: string;
}

const sizeMap = {
  small: 16,
  medium: 24,
  large: 32,
};

export function Spinner({
  size = 'medium',
  color = 'currentColor',
  className = ''
}: SpinnerProps) {
  const pixelSize = typeof size === 'number' ? size : sizeMap[size];

  return (
    <motion.div
      className={`spinner spinner--${typeof size === 'string' ? size : 'custom'} ${className}`}
      style={{ width: pixelSize, height: pixelSize }}
      animate={{ rotate: 360 }}
      transition={{
        duration: 1,
        repeat: Infinity,
        ease: 'linear',
      }}
      role="status"
      aria-label="加载中"
    >
      <svg
        viewBox="0 0 50 50"
        className="spinner__svg"
      >
        <circle
          className="spinner__circle"
          cx="25"
          cy="25"
          r="20"
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray="80, 200"
          strokeDashoffset="0"
        />
      </svg>
    </motion.div>
  );
}
