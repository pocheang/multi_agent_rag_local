import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { LanguageToggle } from "@/components/LanguageToggle";
import type { AuthUser } from "@/types/api";
import { authApi } from "@/lib/auth-api";

import "@/styles/pages/profile.css";

type Props = {
  user: AuthUser | null;
  onUserUpdated: (user: AuthUser) => void;
};

export function ProfilePage({ user, onUserUpdated }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name || user.username);
      setEmail(user.username);
    }
  }, [user]);

  const handleSave = async () => {
    setLoading(true);
    setError("");
    setStatus(t("pages.profile.saving"));

    try {
      const updatedUser = await authApi.updateProfile(displayName);
      onUserUpdated(updatedUser);
      setStatus(t("pages.profile.saved"));
      window.setTimeout(() => setStatus(""), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("pages.profile.saveFailed"));
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return (
      <div className="profile-page">
        <div className="profile-card">
          <p>{t("pages.profile.loginRequired")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="profile-page">
      <div className="profile-header">
        <button type="button" className="back-btn" onClick={() => navigate("/app")}>
          ← {t("pages.profile.back")}
        </button>
        <h1>{t("pages.profile.title")}</h1>
        <LanguageToggle />
      </div>

      <div className="profile-card">
        <div className="profile-avatar-section">
          <div className="profile-avatar">{user.username.charAt(0).toUpperCase()}</div>
          <div className="profile-info">
            <h2>{user.username}</h2>
            <p className="profile-username">@{user.username}</p>
            <span className="profile-badge">
              {user.role === "admin" ? t("pages.profile.admin") : t("pages.profile.user")}
            </span>
          </div>
        </div>

        <div className="profile-section">
          <h3>{t("pages.profile.basicInfo")}</h3>

          <div className="form-group">
            <label htmlFor="username">{t("pages.profile.username")}</label>
            <input id="username" type="text" value={email} disabled className="disabled-input" />
            <div className="hint">{t("pages.profile.usernameHint")}</div>
          </div>

          <div className="form-group">
            <label htmlFor="display-name">{t("pages.profile.displayName")}</label>
            <input
              id="display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("pages.profile.displayNamePlaceholder")}
            />
            <div className="hint">{t("pages.profile.displayNameHint")}</div>
          </div>
        </div>

        <div className="profile-section">
          <h3>{t("pages.profile.accountInfo")}</h3>

          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">{t("pages.profile.userId")}</span>
              <span className="info-value">{user.user_id}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t("pages.profile.role")}</span>
              <span className="info-value">{user.role}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t("pages.profile.status")}</span>
              <span className="info-value status-active">{user.status}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t("pages.profile.credits")}</span>
              <span className="info-value">
                {user.role.toLowerCase() === "admin" ? t("pages.profile.unlimitedCredits") : user.credit_balance}
              </span>
            </div>
          </div>
        </div>

        <div className="profile-actions">
          <button type="button" onClick={handleSave} disabled={loading} className="primary-action-btn">
            {loading ? t("pages.profile.saving") : t("pages.profile.saveChanges")}
          </button>
          <button type="button" onClick={() => navigate("/app/change-password")} className="secondary">
            {t("pages.profile.changePassword")}
          </button>
        </div>

        {status && <div className="status success">{status}</div>}
        {error && <div className="status error">{error}</div>}
      </div>
    </div>
  );
}
