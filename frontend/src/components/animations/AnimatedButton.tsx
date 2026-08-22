/**
 * AnimatedButton - 带动画效果的按钮组件
 *
 * 支持5种状态：idle, hover, active, loading, success, error
 * 使用Framer Motion实现流畅的动画效果
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { motion } from 'framer-motion';
import { useState } from 'react';
import './AnimatedButton.css';

type ButtonState = 'idle' | 'hover' | 'active' | 'loading' | 'success' | 'error';

interface AnimatedButtonProps {
  children: React.ReactNode;
  onClick?: () => Promise<void> | void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  state?: ButtonState;
  className?: string;
}

export function AnimatedButton({
  children,
  onClick,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  state: externalState,
  className = '',
}: AnimatedButtonProps) {
  const [internalState, setInternalState] = useState<ButtonState>('idle');

  // 如果外部传入state，优先使用外部state
  const state = externalState || internalState;

  const handleClick = async () => {
    if (disabled || state === 'loading') return;

    // 如果没有外部state控制，使用内部state
    if (!externalState && onClick) {
      setInternalState('loading');

      try {
        await onClick();
        setInternalState('success');
        setTimeout(() => setInternalState('idle'), 2000);
      } catch (error) {
        setInternalState('error');
        setTimeout(() => setInternalState('idle'), 2000);
      }
    } else {
      onClick?.();
    }
  };

  // 错误状态的抖动动画
  const errorAnimation = state === 'error' ? {
    x: [0, -10, 10, -10, 10, 0],
    transition: { duration: 0.5 }
  } : {};

  return (
    <motion.button
      className={`animated-btn animated-btn--${variant} animated-btn--${size} animated-btn--${state} ${className}`}
      onClick={handleClick}
      disabled={disabled || state === 'loading'}
      whileHover={state === 'idle' && !disabled ? { scale: 1.02 } : {}}
      whileTap={state === 'idle' && !disabled ? { scale: 0.97 } : {}}
      animate={errorAnimation}
      transition={{
        scale: {
          duration: 0.2,
          ease: [0, 0, 0.2, 1] // --ease-out
        }
      }}
    >
      {/* 按钮内容 */}
      <motion.span
        className="animated-btn__content"
        animate={{
          opacity: state === 'loading' || state === 'success' || state === 'error' ? 0 : 1
        }}
        transition={{ duration: 0.2 }}
      >
        {children}
      </motion.span>

      {/* Loading状态：旋转的spinner */}
      {state === 'loading' && (
        <motion.span
          className="animated-btn__icon animated-btn__spinner"
          animate={{ rotate: 360 }}
          transition={{
            duration: 1,
            repeat: Infinity,
            ease: 'linear',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 50 50">
            <circle
              cx="25"
              cy="25"
              r="20"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray="80, 200"
              strokeDashoffset="0"
            />
          </svg>
        </motion.span>
      )}

      {/* Success状态：对勾图标 */}
      {state === 'success' && (
        <motion.span
          className="animated-btn__icon animated-btn__success"
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{
            type: 'spring',
            stiffness: 300,
            damping: 30,
          }}
        >
          ✓
        </motion.span>
      )}

      {/* Error状态：错误图标 */}
      {state === 'error' && (
        <motion.span
          className="animated-btn__icon animated-btn__error"
          initial={{ scale: 0, rotate: 180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{
            type: 'spring',
            stiffness: 300,
            damping: 30,
          }}
        >
          ✗
        </motion.span>
      )}

      {/* 波纹效果（用CSS伪元素实现）*/}
    </motion.button>
  );
}
