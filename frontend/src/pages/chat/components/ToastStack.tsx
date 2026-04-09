import type { Toast } from "@/pages/chat/types";

export function ToastStack({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>
          {t.text}
        </div>
      ))}
    </div>
  );
}
