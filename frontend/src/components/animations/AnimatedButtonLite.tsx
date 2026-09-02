/**
 * AnimatedButtonLite - 轻量级动画按钮（CSS-only）
 *
 * 不依赖Framer Motion，使用纯CSS实现核心动画效果
 * 适用于对bundle大小敏感的场景（如Chat UI）
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { useState } from 'react';
import './AnimatedButtonLite.css';

import { animatedButton } from './animatedButtonVariants';

type ButtonState = 'idle' | 'loading' | 'success' | 'error';

interface AnimatedButtonLiteProps {
  children: React.ReactNode;
  onClick?: () => Promise<void> | void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  state?: ButtonState;
  className?: string;
}

export function AnimatedButtonLite({
  children,
  onClick,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  state: externalState,
  className = '',
}: AnimatedButtonLiteProps) {
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

  return (
    <button
      type="button"
      className={animatedButton({ variant, size, state, class: className })}
      onClick={handleClick}
      disabled={disabled || state === 'loading'}
      aria-busy={state === 'loading'}
    >
      {state === 'loading' && (
        <span className="animated-btn-lite__spinner" aria-hidden="true" />
      )}
      {state === 'success' && (
        <span className="animated-btn-lite__icon" aria-hidden="true">✓</span>
      )}
      {state === 'error' && (
        <span className="animated-btn-lite__icon" aria-hidden="true">✗</span>
      )}
      <span className="animated-btn-lite__content">{children}</span>
    </button>
  );
}
