import { useTranslation } from "react-i18next";
import "@/styles/components/code-block.css";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";

export interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
}

export function CodeBlock({ code, language, filename }: CodeBlockProps) {
  const { t } = useTranslation();
  const { copied, copy } = useCopyToClipboard(2000);

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        {filename && <span className="code-block-filename">{filename}</span>}
        {language && !filename && <span className="code-block-language">{language}</span>}
        <button
          type="button"
          className="code-block-copy"
          onClick={() => copy(code)}
          aria-label={copied ? t("components.codeBlock.copiedAria") : t("components.codeBlock.copyAria")}
          title={copied ? t("components.codeBlock.copiedTitle") : t("components.codeBlock.copyTitle")}
        >
          {copied ? (
            <>
              <span className="copy-icon">✓</span>
              <span className="copy-text">{t("components.codeBlock.copied")}</span>
            </>
          ) : (
            <>
              <span className="copy-icon">⎘</span>
              <span className="copy-text">{t("components.codeBlock.copy")}</span>
            </>
          )}
        </button>
      </div>
      <pre className="code-block-content">
        <code className={language ? `language-${language}` : undefined}>{code}</code>
      </pre>
    </div>
  );
}
