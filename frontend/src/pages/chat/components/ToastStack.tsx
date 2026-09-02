import { AnimatedToastLite } from "@/components/animations/AnimatedToastLite";
import type { Toast } from "@/pages/chat/types";

// 将Chat的Toast类型映射到AnimatedToastLite的类型
function mapToastKind(kind: string): 'info' | 'success' | 'warning' | 'error' {
  if (kind === 'success') return 'success';
  if (kind === 'warning') return 'warning';
  if (kind === 'error' || kind === 'danger') return 'error';
  return 'info';
}

interface ToastStackProps {
  toasts: Toast[];
  onRemove?: (id: string) => void;
}

export function ToastStack({ toasts, onRemove }: ToastStackProps) {
  // 将Chat的Toast格式转换为AnimatedToastLite的格式
  const animatedToasts = toasts.map((t) => ({
    id: t.id,
    message: t.text,
    type: mapToastKind(t.kind),
    duration: 4000,
  }));

  const handleClose = (id: string) => {
    if (onRemove) {
      onRemove(id);
    }
  };

  return (
    <div
      className="toast-stack"
      style={{
        position: 'fixed',
        top: '20px',
        right: '20px',
        zIndex: 9999,
        pointerEvents: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      {animatedToasts.map((toast, index) => (
        <AnimatedToastLite
          key={toast.id}
          toast={toast}
          index={index}
          onClose={handleClose}
        />
      ))}
    </div>
  );
}
