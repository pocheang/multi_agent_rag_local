import { ExecutionTracePanel } from "@/features/execution-trace/ExecutionTracePanel";
import { useExecutionTrace } from "@/features/execution-trace/useExecutionTrace";
import { ToolApprovalPanel } from "@/features/tool-approval/ToolApprovalPanel";

type Props = {
  executionId: string | null;
};

export function ChatRuntimePanels({ executionId }: Props) {
  const executionTrace = useExecutionTrace(executionId);
  if (!executionId && !executionTrace.pendingApproval) return null;

  return (
    <>
      <ExecutionTracePanel trace={executionTrace} />
      <ToolApprovalPanel approval={executionTrace.pendingApproval} onResolved={executionTrace.resolveApproval} />
    </>
  );
}
