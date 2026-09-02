import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary specifically for the Chat page
 * Provides chat-specific error recovery
 */
export class ChatErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ChatPage Error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = () => {
    // Clear local storage cache that might be corrupted
    try {
      const keysToPreserve = ["auth_token", "theme"];
      const allKeys = Object.keys(localStorage);
      allKeys.forEach((key) => {
        if (!keysToPreserve.includes(key) && key.startsWith("chat_")) {
          localStorage.removeItem(key);
        }
      });
    } catch (e) {
      console.warn("Failed to clear cache:", e);
    }

    this.setState({ hasError: false, error: null });
    window.location.href = "/app";
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            padding: "2rem",
            backgroundColor: "var(--bg-primary, #fff)",
          }}
        >
          <div
            style={{
              maxWidth: "500px",
              textAlign: "center",
              backgroundColor: "var(--bg-secondary, #f8f9fa)",
              padding: "2rem",
              borderRadius: "12px",
              border: "1px solid var(--border-color, #dee2e6)",
            }}
          >
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>💬</div>
            <h2 style={{ marginBottom: "1rem", color: "var(--text-primary, #212529)" }}>
              Chat Error
            </h2>
            <p style={{ marginBottom: "1.5rem", color: "var(--text-secondary, #6c757d)" }}>
              The chat encountered an error. Your conversation data is safe.
            </p>
            {this.state.error && (
              <details style={{ marginBottom: "1.5rem", textAlign: "left" }}>
                <summary style={{ cursor: "pointer", marginBottom: "0.5rem" }}>
                  Error details
                </summary>
                <pre
                  style={{
                    fontSize: "0.85rem",
                    padding: "0.5rem",
                    backgroundColor: "var(--bg-code, #f5f5f5)",
                    borderRadius: "4px",
                    overflow: "auto",
                  }}
                >
                  {this.state.error.message}
                </pre>
              </details>
            )}
            <button
              onClick={this.handleReset}
              style={{
                padding: "0.75rem 1.5rem",
                backgroundColor: "var(--primary, #007bff)",
                color: "white",
                border: "none",
                borderRadius: "6px",
                cursor: "pointer",
                fontSize: "1rem",
                fontWeight: "500",
              }}
            >
              Return to Chat
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// HOC for functional components
export function withChatErrorBoundary<P extends object>(
  Component: React.ComponentType<P>
): React.ComponentType<P> {
  return function ChatErrorBoundaryWrapper(props: P) {
    return (
      <ChatErrorBoundary>
        <Component {...props} />
      </ChatErrorBoundary>
    );
  };
}
