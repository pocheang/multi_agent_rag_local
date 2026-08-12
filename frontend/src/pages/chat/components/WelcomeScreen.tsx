import { useTranslation } from "react-i18next";
import "@/styles/components/welcome-screen.css";

type Props = {
  documentsCount?: number;
  sessionsCount?: number;
  onCreateSession?: () => void;
  onNavigateToArchitecture?: () => void;
};

export function WelcomeScreen({
  documentsCount = 0,
  sessionsCount = 0,
  onCreateSession,
  onNavigateToArchitecture
}: Props) {
  const { t } = useTranslation();

  return (
    <div className="welcome-screen">
      <div className="welcome-header">
        <span className="welcome-badge">{t("components.chat.welcomeBadge")}</span>
        <h2 className="welcome-title">{t("components.chat.welcomeTitle")}</h2>
        <p className="welcome-subtitle">{t("components.chat.welcomeSubtitle")}</p>
      </div>

      <div className="welcome-stats">
        <div className="stat-card">
          <div className="stat-icon" aria-hidden="true">▣</div>
          <div className="stat-content">
            <div className="stat-value">{documentsCount}</div>
            <div className="stat-label">{t("components.chat.knowledgeDocs")}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" aria-hidden="true">◫</div>
          <div className="stat-content">
            <div className="stat-value">{sessionsCount}</div>
            <div className="stat-label">{t("components.chat.historySessions")}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" aria-hidden="true">◆</div>
          <div className="stat-content">
            <div className="stat-value">4</div>
            <div className="stat-label">{t("components.chat.agentModes")}</div>
          </div>
        </div>
      </div>

      <div className="welcome-actions">
        <button type="button" className="welcome-action-btn primary" onClick={onCreateSession}>
          <span className="action-icon" aria-hidden="true">+</span>
          <span className="action-text">{t("components.chat.startConversation")}</span>
        </button>

        <button type="button" className="welcome-action-btn secondary" onClick={onNavigateToArchitecture}>
          <span className="action-icon" aria-hidden="true">▦</span>
          <span className="action-text">{t("components.chat.viewArchitecture")}</span>
        </button>
      </div>

      <div className="welcome-features">
        <div className="feature-card">
          <div className="feature-icon" aria-hidden="true">⌁</div>
          <h4 className="feature-title">{t("components.chat.smartRetrieval")}</h4>
          <p className="feature-desc">{t("components.chat.smartRetrievalDesc")}</p>
        </div>

        <div className="feature-card">
          <div className="feature-icon" aria-hidden="true">◎</div>
          <h4 className="feature-title">{t("components.chat.webResearch")}</h4>
          <p className="feature-desc">{t("components.chat.webResearchDesc")}</p>
        </div>

        <div className="feature-card">
          <div className="feature-icon" aria-hidden="true">□</div>
          <h4 className="feature-title">{t("components.chat.multimodal")}</h4>
          <p className="feature-desc">{t("components.chat.multimodalDesc")}</p>
        </div>

        <div className="feature-card">
          <div className="feature-icon" aria-hidden="true">∞</div>
          <h4 className="feature-title">{t("components.chat.evidenceTrace")}</h4>
          <p className="feature-desc">{t("components.chat.evidenceTraceDesc")}</p>
        </div>
      </div>

      <div className="welcome-tips">
        <div className="tip-item">
          <span className="tip-icon" aria-hidden="true">i</span>
          <span className="tip-text">{t("components.chat.tipSend")}</span>
        </div>
        <div className="tip-item">
          <span className="tip-icon" aria-hidden="true">↑</span>
          <span className="tip-text">{t("components.chat.tipUpload")}</span>
        </div>
        <div className="tip-item">
          <span className="tip-icon" aria-hidden="true">◎</span>
          <span className="tip-text">{t("components.chat.tipAgent")}</span>
        </div>
      </div>
    </div>
  );
}
