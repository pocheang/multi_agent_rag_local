interface ThinkingIndicatorProps {
  elapsedSeconds?: number;
}

export function ThinkingIndicator({ elapsedSeconds: _elapsedSeconds }: ThinkingIndicatorProps) {
  return (
    <div className="thinking-indicator">
      <span className="thinking-dots" aria-hidden="true"></span>
      <span className="thinking-text">正在思考</span>
    </div>
  );
}
