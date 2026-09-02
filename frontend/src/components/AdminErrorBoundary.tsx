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
 * Error boundary specifically for the Admin page
 * Provides admin-specific error recovery
 */
export class AdminErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("AdminPage Error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  handleReturnHome = () => {
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
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>⚙️</div>
            <h2 style={{ marginBottom: "1rem", color: "var(--text-primary, #212529)" }}>
              Admin Panel Error
            </h2>
            <p style={{ marginBottom: "1.5rem", color: "var(--text-secondary, #6c757d)" }}>
              An error occurred in the admin panel. System data is protected.
            </p>
            {this.state.error && (
              <details style={{ marginBottom: "1.5rem", textAlign: "left" }}>
                <summary style={{ cursor: "pointer", marginBottom: "0.5rem" }}>
                  Technical details
                </summary>
                <pre
                  style={{
                    fontSize: "0.85rem",
                    padding: "0.5rem",
                    backgroundColor: "var(--bg-code, #f5f5f5)",
                    borderRadius: "4px",
                    overflow: "auto",
                    maxHeight: "200px",
                  }}
                >
                  {this.state.error.message}
                  {"\n\n"}
                  {this.state.error.stack?.slice(0, 500)}
                </pre>
              </details>
            )}
            <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
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
                Try Again
              </button>
              <button
                onClick={this.handleReturnHome}
                style={{
                  padding: "0.75rem 1.5rem",
                  backgroundColor: "var(--secondary, #6c757d)",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "1rem",
                  fontWeight: "500",
                }}
              >
                Return Home
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export function withAdminErrorBoundary<P extends object>(
  Component: React.ComponentType<P>
): React.ComponentType<P> {
  return function AdminErrorBoundaryWrapper(props: P) {
    return (
      <AdminErrorBoundary>
        <Component {...props} />
      </AdminErrorBoundary>
    );
  };
}
