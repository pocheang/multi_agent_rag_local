import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{
          padding: "2rem",
          textAlign: "center",
          backgroundColor: "var(--bg-error, #fee)",
          border: "1px solid var(--border-error, #fcc)",
          borderRadius: "8px",
          margin: "2rem auto",
          maxWidth: "600px"
        }}>
          <h2 style={{ color: "var(--text-error, #c33)", marginBottom: "1rem" }}>
            Something went wrong
          </h2>
          <p style={{ marginBottom: "1rem", color: "var(--text-muted, #666)" }}>
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={this.handleReset}
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: "var(--primary, #007bff)",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer"
            }}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
