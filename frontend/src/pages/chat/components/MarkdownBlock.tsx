import { isValidElement } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";

function CodeBlock({ code, className = "" }: { code: string; className?: string }) {
  const { t } = useTranslation();
  const { copied, copy } = useCopyToClipboard(1200);

  return (
    <pre>
      <button type="button" className="copy-code-btn" onClick={() => void copy(code)}>
        {copied ? t("components.codeBlock.copied") : t("components.codeBlock.copy")}
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
