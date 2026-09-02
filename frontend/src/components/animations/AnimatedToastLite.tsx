/**
 * AnimatedToastLite - 轻量级Toast通知组件（CSS-only）
 *
 * 不依赖Framer Motion，使用纯CSS实现动画效果
 * 适用于对bundle大小敏感的场景
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { useEffect, useState, createContext, useContext, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import './AnimatedToastLite.css';

export interface Toast {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  duration?: number;
}

interface AnimatedToastLiteProps {
  toast: Toast;
  index: number;
  onClose: (id: string) => void;
}

export function AnimatedToastLite({ toast, index, onClose }: AnimatedToastLiteProps) {
  const { t } = useTranslation();
  const [isPaused, setIsPaused] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const duration = toast.duration || 4000;

  useEffect(() => {
    if (isPaused || isExiting) return;

    const timer = setTimeout(() => {
      setIsExiting(true);
      // 等待退出动画完成后再移除
      setTimeout(() => onClose(toast.id), 300);
    }, duration);

    return () => clearTimeout(timer);
  }, [toast.id, duration, isPaused, isExiting, onClose]);

  const icons = {
    info: 'ℹ️',
    success: '✓',
    warning: '⚠️',
    error: '✗',
  };

  const handleClick = () => {
    if (!isExiting) {
      setIsExiting(true);
      setTimeout(() => onClose(toast.id), 300);
    }
  };

  return (
    <div
      className={`toast-lite toast-lite--${toast.type} ${isExiting ? 'toast-lite--exiting' : ''}`}
      style={{
        '--toast-index': index,
      } as React.CSSProperties}
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onClick={handleClick}
      role="alert"
      aria-live="polite"
    >
      <span className="toast-lite__icon">{icons[toast.type]}</span>
      <span className="toast-lite__message">{toast.message}</span>
      <button
        className="toast-lite__close"
        onClick={handleClick}
        aria-label={t('toast.close')}
      >
        ✕
      </button>

      {/* 进度条 */}
      {!isPaused && !isExiting && (
        <div
          className="toast-lite__progress"
          style={{
            '--toast-duration': `${duration}ms`,
          } as React.CSSProperties}
        />
      )}
    </div>
  );
}

// Toast容器组件
interface ToastContainerProps {
  toasts: Toast[];
  onClose: (id: string) => void;
}

export function ToastContainer({ toasts, onClose }: ToastContainerProps) {
  return (
    <div className="toast-lite-container">
      {toasts.map((toast, index) => (
        <AnimatedToastLite
          key={toast.id}
          toast={toast}
          index={index}
          onClose={onClose}
        />
      ))}
    </div>
  );
}

// Toast Context 和 Hook
interface ToastContextValue {
  toasts: Toast[];
  addToast: (message: string, type: Toast['type'], duration?: number) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: Toast['type'], duration?: number) => {
    const id = `toast-${crypto.randomUUID()}`;
    const newToast: Toast = { id, message, type, duration };

    setToasts((prev) => [...prev, newToast]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} onClose={removeToast} />
    </ToastContext.Provider>
  );
}

// 便捷的 Hook
export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }

  return {
    info: (message: string, duration?: number) => context.addToast(message, 'info', duration),
    success: (message: string, duration?: number) => context.addToast(message, 'success', duration),
    warning: (message: string, duration?: number) => context.addToast(message, 'warning', duration),
    error: (message: string, duration?: number) => context.addToast(message, 'error', duration),
  };
}
