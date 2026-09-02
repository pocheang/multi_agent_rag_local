import { useEffect, useRef } from "react";

import { ExecutionTracePanel } from "@/features/execution-trace/ExecutionTracePanel";
import { useExecutionTrace } from "@/features/execution-trace/useExecutionTrace";
import { ToolApprovalPanel } from "@/features/tool-approval/ToolApprovalPanel";
import type { PendingApproval } from "@/types/api";

type Props = {
  executionId: string | null;
  /** From the query response, not from the SSE trace: only the response path
   *  knows the question, and resuming means re-sending it with the token. */
  pendingApproval: PendingApproval | null;
  onApproved: (token: string) => Promise<void> | void;
  onDismissApproval: () => void;
  /** The answer as it streams in, already redacted server-side. A draft: the
   *  final answer replaces it once citation numbering and the reference list
   *  are decided. */
  onDraft?: (text: string) => void;
};

export function ChatRuntimePanels({
  executionId,
  pendingApproval,
  onApproved,
  onDismissApproval,
  onDraft,
}: Props) {
  const executionTrace = useExecutionTrace(executionId);
  const draft = executionTrace.draft;

  // The effect must fire when the *draft* changes, not when the parent
  // re-renders. Depending on `onDraft` directly makes an inline arrow -- which
  // is what the call site passes -- a new dependency on every render, so
  // publishing a draft re-renders the parent, which recreates the callback,
  // which re-fires the effect: "Maximum update depth exceeded", and the chat
  // error boundary catches it. Holding the latest callback in a ref keeps the
  // parent free to pass a fresh closure without that closing a loop.
  const onDraftRef = useRef(onDraft);
  useEffect(() => {
    onDraftRef.current = onDraft;
  });
  useEffect(() => {
    onDraftRef.current?.(draft);
  }, [draft]);
  if (!executionId && !pendingApproval) return null;

  return (
    <>
      <ExecutionTracePanel trace={executionTrace} />
      <ToolApprovalPanel approval={pendingApproval} onApproved={onApproved} onDismiss={onDismissApproval} />
    </>
  );
}
