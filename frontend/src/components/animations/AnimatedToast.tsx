/**
 * AnimatedToast - 通知提示组件
 *
 * 支持4种类型：info, success, warning, error
 * 特性：堆叠动画、自动关闭、悬停暂停、进度条
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';
import './AnimatedToast.css';

export interface Toast {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  duration?: number;
}

interface AnimatedToastProps {
  toast: Toast;
  index: number;
  onClose: (id: string) => void;
}

export function AnimatedToast({ toast, index, onClose }: AnimatedToastProps) {
  const [isPaused, setIsPaused] = useState(false);
  const duration = toast.duration || 4000;

  useEffect(() => {
    if (isPaused) return;

    const timer = setTimeout(() => {
      onClose(toast.id);
    }, duration);

    return () => clearTimeout(timer);
  }, [toast.id, duration, isPaused, onClose]);

  const icons = {
    info: 'ℹ️',
    success: '✓',
    warning: '⚠️',
    error: '✗',
  };

  return (
    <motion.div
      className={`animated-toast animated-toast--${toast.type}`}
      layout
      initial={{ opacity: 0, x: 300, scale: 0.8 }}
      animate={{
        opacity: 1,
        x: 0,
        scale: 1,
        y: -index * 70, // 堆叠偏移
      }}
      exit={{ opacity: 0, x: 300, scale: 0.8 }}
      transition={{
        type: 'spring',
        stiffness: 300,
        damping: 30,
      }}
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onClick={() => onClose(toast.id)}
      role="alert"
      aria-live="polite"
    >
      <span className="animated-toast__icon">{icons[toast.type]}</span>
      <span className="animated-toast__message">{toast.message}</span>

      {/* 进度条 */}
      {!isPaused && (
        <motion.div
          className="animated-toast__progress"
          initial={{ scaleX: 1 }}
          animate={{ scaleX: 0 }}
          transition={{ duration: duration / 1000, ease: 'linear' }}
        />
      )}

      <button
        className="animated-toast__close"
        onClick={(e) => {
          e.stopPropagation();
          onClose(toast.id);
        }}
        aria-label="关闭通知"
      >
        ✕
      </button>
    </motion.div>
  );
}

// Toast容器组件
interface ToastContainerProps {
  toasts: Toast[];
  onClose: (id: string) => void;
}

export function ToastContainer({ toasts, onClose }: ToastContainerProps) {
  return (
    <div className="toast-container" aria-live="polite" aria-atomic="false">
      <AnimatePresence mode="sync">
        {toasts.map((toast, index) => (
          <AnimatedToast
            key={toast.id}
            toast={toast}
            index={index}
            onClose={onClose}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

// Toast管理Hook
export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = (message: string, type: Toast['type'] = 'info', duration?: number) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    const newToast: Toast = { id, message, type, duration };
    setToasts((prev) => [...prev, newToast]);
    return id;
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const info = (message: string, duration?: number) => addToast(message, 'info', duration);
  const success = (message: string, duration?: number) => addToast(message, 'success', duration);
  const warning = (message: string, duration?: number) => addToast(message, 'warning', duration);
  const error = (message: string, duration?: number) => addToast(message, 'error', duration);

  return {
    toasts,
    addToast,
    removeToast,
    info,
    success,
    warning,
    error,
  };
}
