import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { authApi } from "@/lib/api";
import { validatePassword } from "@/lib/validation";
import { useFormState } from "@/hooks/useFormState";
import { AuthInput } from "@/components/AuthInput";
import { LanguageToggle } from "@/components/LanguageToggle";
import { PasswordRequirements } from "@/components/PasswordRequirements";

import "@/styles/pages/auth-entry.css";

export function ChangePasswordPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const { status, setStatus, error, setError, loading, setLoading } = useFormState();

  const formValid = useMemo(() => {
    return (
      oldPassword.length > 0 &&
      validatePassword(newPassword) &&
      newPassword === confirmPassword &&
      oldPassword !== newPassword
    );
  }, [oldPassword, newPassword, confirmPassword]);

  const changePassword = async () => {
    if (!formValid) {
      setError(t("pages.changePassword.fixInputs"));
      return;
    }
    setLoading(true);
    setError("");
    setStatus(t("pages.changePassword.changing"));
    try {
      const data = await authApi.changePassword(oldPassword, newPassword);
      setStatus(data.message || t("pages.changePassword.changed"));
      window.setTimeout(() => {
        navigate("/app");
      }, 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("pages.changePassword.failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-root">
      <div className="auth-toolbar">
        <LanguageToggle />
      </div>

      <main className="auth-card change-password-card">
        <section className="auth-intro auth-intro-security">
          <div className="badge">{t("pages.changePassword.badge")}</div>
          <div className="auth-intro-copy">
            <h1>{t("pages.changePassword.title")}</h1>
            <p>{t("pages.changePassword.description")}</p>
          </div>

          <PasswordRequirements password={newPassword} />
        </section>

        <section className="auth-form">
          <div className="auth-form-header">
            <h2>{t("pages.changePassword.formTitle")}</h2>
            <p className="auth-form-subtitle">{t("pages.changePassword.formSubtitle")}</p>
          </div>

          <div className="input-group">
            <label htmlFor="old-password">{t("pages.changePassword.currentPassword")}</label>
            <AuthInput
              id="old-password"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder={t("pages.changePassword.currentPlaceholder")}
              autoComplete="current-password"
              icon="lock"
            />
            <div className={`hint ${oldPassword.length > 0 ? "ok" : ""}`}>
              {oldPassword.length > 0
                ? t("pages.changePassword.currentReady")
                : t("pages.changePassword.currentHint")}
            </div>
          </div>

          <div className="input-group">
            <label htmlFor="new-password">{t("pages.changePassword.newPassword")}</label>
            <AuthInput
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder={t("pages.changePassword.newPlaceholder")}
              autoComplete="new-password"
              icon="lock"
            />
            <div className={`hint ${validatePassword(newPassword) ? "ok" : newPassword.length > 0 ? "error" : ""}`}>
              {validatePassword(newPassword)
                ? t("pages.changePassword.newValid")
                : newPassword.length > 0
                  ? t("pages.changePassword.newInvalid")
                  : t("pages.changePassword.newHint")}
            </div>
          </div>

          <div className="input-group">
            <label htmlFor="confirm-password">{t("pages.changePassword.confirmPassword")}</label>
            <AuthInput
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder={t("pages.changePassword.confirmPlaceholder")}
              autoComplete="new-password"
              onKeyDown={(e) => {
                if (e.key === "Enter") void changePassword();
              }}
              icon="lock"
            />
            <div
              className={`hint ${
                confirmPassword.length > 0 ? (newPassword === confirmPassword ? "ok" : "error") : ""
              }`}
            >
              {confirmPassword.length === 0
                ? t("pages.changePassword.confirmHint")
                : newPassword === confirmPassword
                  ? t("pages.changePassword.confirmMatch")
                  : t("pages.changePassword.confirmMismatch")}
            </div>
          </div>

          {oldPassword === newPassword && newPassword.length > 0 && (
            <div className="alert alert-warning">{t("pages.changePassword.samePassword")}</div>
          )}

          <div className="action-grid">
            <button
              type="button"
              className="primary-action-btn"
              disabled={!formValid || loading}
              onClick={() => void changePassword()}
            >
              {loading ? t("pages.changePassword.submitting") : t("pages.changePassword.submit")}
            </button>
            <button type="button" className="secondary auth-secondary-btn" onClick={() => navigate("/app")}>
              {t("pages.changePassword.cancel")}
            </button>
          </div>

          {status && <div className="status success">{status}</div>}
          {error && <div className="status error">{error}</div>}
        </section>
      </main>
    </div>
  );
}
