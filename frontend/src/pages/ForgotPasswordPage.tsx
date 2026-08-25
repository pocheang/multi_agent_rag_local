import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useFormState } from "@/hooks/useFormState";
import { AuthInput } from "@/components/AuthInput";
import { LanguageToggle } from "@/components/LanguageToggle";

import "@/styles/pages/auth-entry.css";

export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const { status, setStatus, error, setError, loading, setLoading } = useFormState();
  const [submitted, setSubmitted] = useState(false);
  const securityTips = t("pages.forgotPassword.tips", { returnObjects: true }) as string[];
  const nextSteps = t("pages.forgotPassword.nextSteps", { returnObjects: true }) as string[];

  const handleSubmit = async () => {
    if (!email.trim()) {
      setError(t("pages.forgotPassword.required"));
      return;
    }

    setLoading(true);
    setError("");
    setStatus(t("pages.forgotPassword.processing"));

    try {
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
      setSubmitted(true);
      setStatus(t("pages.forgotPassword.success"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("pages.forgotPassword.failed"));
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="auth-root">
        <div className="auth-toolbar">
          <LanguageToggle />
        </div>

        <main className="auth-card forgot-password-card">
          <section className="auth-intro auth-intro-support">
            <div className="badge badge-success">{t("pages.forgotPassword.sentBadge")}</div>
            <div className="auth-intro-copy">
              <h1>{t("pages.forgotPassword.sentTitle")}</h1>
              <p>{t("pages.forgotPassword.sentDescription")}</p>
            </div>

            <div className="auth-info-panel">
              <h3>{t("pages.forgotPassword.nextTitle")}</h3>
              <ol className="steps-list">
                {nextSteps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          </section>

          <section className="auth-form">
            <div className="auth-form-header">
              <h2>{t("pages.forgotPassword.notReceived")}</h2>
              <p className="auth-form-subtitle">{t("pages.forgotPassword.notReceivedText")}</p>
            </div>

            <div className="help-options">
              <div className="help-option">
                <div className="help-option-copy">
                  <h4>{t("pages.forgotPassword.resendTitle")}</h4>
                  <p>{t("pages.forgotPassword.resendText")}</p>
                </div>
                <button type="button" className="secondary auth-secondary-btn" onClick={() => setSubmitted(false)}>
                  {t("pages.forgotPassword.resend")}
                </button>
              </div>

              <div className="help-option">
                <div className="help-option-copy">
                  <h4>{t("pages.forgotPassword.contactTitle")}</h4>
                  <p>{t("pages.forgotPassword.contactText")}</p>
                </div>
                <Link to="/app/login" className="link-button">
                  {t("pages.forgotPassword.loginPage")}
                </Link>
              </div>
            </div>

            {status && <div className="status success">{status}</div>}

            <div className="auth-footer">
              <Link className="text-link" to="/app/login">
                {t("pages.forgotPassword.backToLogin")}
              </Link>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="auth-root">
      <div className="auth-toolbar">
        <LanguageToggle />
      </div>

      <main className="auth-card forgot-password-card">
        <section className="auth-intro auth-intro-support">
          <div className="badge">{t("pages.forgotPassword.badge")}</div>
          <div className="auth-intro-copy">
            <h1>{t("pages.forgotPassword.title")}</h1>
            <p>{t("pages.forgotPassword.description")}</p>
          </div>

          <div className="auth-info-panel">
            <h3>{t("pages.forgotPassword.securityTitle")}</h3>
            <ul className="security-tips">
              {securityTips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="auth-form">
          <div className="auth-form-header">
            <h2>{t("pages.forgotPassword.formTitle")}</h2>
            <p className="auth-form-subtitle">{t("pages.forgotPassword.formSubtitle")}</p>
          </div>

          <div className="input-group">
            <label htmlFor="email">{t("pages.forgotPassword.identifier")}</label>
            <AuthInput
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("pages.forgotPassword.identifierPlaceholder")}
              autoComplete="email"
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleSubmit();
              }}
              icon="email"
            />
            <div className={`hint ${email.trim() ? "ok" : ""}`}>
              {email.trim() ? t("pages.forgotPassword.identifierReady") : t("pages.forgotPassword.identifierHint")}
            </div>
          </div>

          <div className="action-grid">
            <button
              type="button"
              className="primary-action-btn"
              disabled={!email.trim() || loading}
              onClick={() => void handleSubmit()}
            >
              {loading ? t("pages.forgotPassword.sending") : t("pages.forgotPassword.send")}
            </button>
            <Link to="/app/login" className="secondary link-button">
              {t("pages.forgotPassword.cancel")}
            </Link>
          </div>

          {status && <div className="status success">{status}</div>}
          {error && <div className="status error">{error}</div>}

          <div className="auth-footer">
            <p className="footer-text">{t("pages.forgotPassword.remembered")}</p>
            <Link className="text-link" to="/app/login">
              {t("pages.forgotPassword.backToLogin")}
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
