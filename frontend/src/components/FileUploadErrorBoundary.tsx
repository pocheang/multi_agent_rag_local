import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  onRetry?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary for file upload components
 * Handles upload failures gracefully
 */
export class FileUploadErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("FileUpload Error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onRetry?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "1.5rem",
            margin: "1rem 0",
            backgroundColor: "var(--bg-warning, #fff3cd)",
            border: "1px solid var(--border-warning, #ffc107)",
            borderRadius: "8px",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>📁</div>
          <h4 style={{ marginBottom: "0.5rem", color: "var(--text-primary, #212529)" }}>
            Upload Error
          </h4>
          <p style={{ marginBottom: "1rem", fontSize: "0.9rem", color: "var(--text-secondary, #6c757d)" }}>
            {this.state.error?.message || "Failed to upload file"}
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: "0.5rem 1rem",
              backgroundColor: "var(--primary, #007bff)",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "0.9rem",
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
