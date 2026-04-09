import { isValidElement, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function CodeBlock({ code, className = "" }: { code: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };

  return (
    <pre>
      <button type="button" className="copy-code-btn" onClick={() => void copyCode()}>
        {copied ? "已复制" : "复制"}
      </button>
      <code className={className}>{code}</code>
    </pre>
  );
}

export function MarkdownBlock({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        pre({ children }) {
          const child = Array.isArray(children) ? children[0] : children;
          if (!isValidElement(child)) return <pre>{children}</pre>;
          const className = String((child.props as { className?: string })?.className || "");
          const code = String((child.props as { children?: unknown })?.children || "").replace(/\n$/, "");
          return <CodeBlock className={className} code={code} />;
        },
      }}
    >
      {text || ""}
    </ReactMarkdown>
  );
}
