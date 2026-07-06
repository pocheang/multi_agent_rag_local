import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { authApi } from "@/lib/api";
import type { AuthUser } from "@/types/api";
import { validateUsername, validatePassword } from "@/lib/validation";
import { useFormState } from "@/hooks/useFormState";
import { AuthInput } from "@/components/AuthInput";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";

// Route-specific CSS (code-split by Vite)
import "@/styles/pages/auth-entry.css";

type Props = {
  onLogin: (user: AuthUser) => void;
  themeLabel: string;
  onThemeToggle: () => void;
};

export function LoginPage({ onLogin, themeLabel, onThemeToggle }: Props) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = searchParams.get("mode") === "register" ? "register" : "login";

  const [username, setUsername] = useState(localStorage.getItem("remembered_username") || "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(!!localStorage.getItem("remembered_username"));
  const { status, setStatus, error, setError, loading, setLoading } = useFormState();

  const loginValid = useMemo(() => validateUsername(username) && password.length > 0, [username, password]);
  const registerValid = useMemo(
    () => validateUsername(username) && validatePassword(password) && password === confirmPassword,
    [username, password, confirmPassword],
  );

  const setMode = (newMode: "login" | "register") => {
    setSearchParams({ mode: newMode });
    setError("");
    setStatus("");
    setPassword("");
    setConfirmPassword("");
  };

  const login = async () => {
    if (!loginValid) {
      setError(t('auth.loginFailed'));
      return;
    }
    setLoading(true);
    setError("");
    setStatus(t('query.searching'));
    try {
      const data = await authApi.login(username.trim(), password);
      if (rememberMe) localStorage.setItem("remembered_username", username.trim());
      else localStorage.removeItem("remembered_username");
      onLogin(data.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('auth.loginFailed'));
    } finally {
      setLoading(false);
      setStatus("");
    }
  };

  const register = async () => {
    if (!registerValid) {
      setError(t('auth.registerFailed'));
      return;
    }
    setLoading(true);
    setError("");
    setStatus(t('query.searching'));
    try {
      const data = await authApi.register(username.trim(), password);
      setStatus(`${t('auth.registerSuccess')}: ${data.username}`);
      setTimeout(() => {
        setSearchParams({ mode: "login" });
        setPassword("");
        setConfirmPassword("");
        setStatus("");
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('auth.registerFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = "/api/auth/google/login";
  };

  const handleGitHubLogin = () => {
    setError("");
    setStatus(t("pages.login.githubUnavailable"));
  };

  return (
    <div className="auth-root">
      <div className="auth-toolbar">
        <LanguageToggle />
        <ThemeToggle themeLabel={themeLabel} onThemeToggle={onThemeToggle} />
      </div>

      <main className="auth-card">
        <section className="auth-intro auth-intro-primary">
          <div className="badge">{t('app.title')}</div>
          <div className="auth-intro-copy">
            <h1>
              {t("pages.login.headline")
                .split("\n")
                .map((line) => (
                  <span key={line}>
                    {line}
                    <br />
                  </span>
                ))}
            </h1>
            <p>{t('app.subtitle')}</p>
          </div>

          <div className="auth-feature-stack">
            <div className="auth-feature-card">
              <span className="auth-feature-icon auth-feature-icon-purple" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path d="M9 3h6v3h3v4h-2V8H8v2H6V6h3V3Zm-1 9h8v7H8v-7Zm4-4a2 2 0 1 0 0 4a2 2 0 0 0 0-4Z" />
                </svg>
              </span>
              <span>{t('features.multiAgent')}</span>
            </div>
            <div className="auth-feature-card">
              <span className="auth-feature-icon auth-feature-icon-blue" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path d="M10.5 4a6.5 6.5 0 1 1-4.03 11.6L3 19l1.4 1.4l3.4-3.47A6.5 6.5 0 1 1 10.5 4Zm0 2a4.5 4.5 0 1 0 0 9a4.5 4.5 0 0 0 0-9Z" />
                </svg>
              </span>
              <span>{t('features.hybridSearch')}</span>
            </div>
            <div className="auth-feature-card">
              <span className="auth-feature-icon auth-feature-icon-amber" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path d="M17 9h-1V7a4 4 0 1 0-8 0v2H7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2Zm-7-2a2 2 0 1 1 4 0v2h-4V7Z" />
                </svg>
              </span>
              <span>{t('features.enterpriseSecurity')}</span>
            </div>
          </div>

          <div className="auth-intro-orb auth-intro-orb-large" aria-hidden="true" />
          <div className="auth-intro-orb auth-intro-orb-small" aria-hidden="true" />
        </section>

        <section className="auth-form">
          <div className="auth-form-header">
            <h2>{mode === "register" ? t('auth.register') : t('auth.login')}</h2>
            <p className="auth-form-subtitle">{t('app.subtitle')}</p>
          </div>

          <div className="input-group">
            <label htmlFor="username">{t('auth.username')}</label>
            <AuthInput
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('auth.username')}
              autoComplete="username"
              icon="user"
            />
            <div className={`hint ${validateUsername(username) ? "ok" : username.length > 0 ? "error" : ""}`}>
              {username.length === 0
                ? t("pages.login.usernameHint")
                : validateUsername(username)
                  ? t("pages.login.usernameValid")
                  : t("pages.login.invalidFormat")}
            </div>
          </div>

          <div className="input-group">
            <label htmlFor="password">{t('auth.password')}</label>
            <AuthInput
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('auth.password')}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  if (mode === "register") void register();
                  else void login();
                }
              }}
              icon="lock"
            />
            <div className={`hint ${validatePassword(password) ? "ok" : password.length > 0 ? "error" : ""}`}>
              {password.length === 0
                ? t("pages.login.passwordHint")
                : validatePassword(password)
                  ? t("pages.login.passwordValid")
                  : t("pages.login.weakPassword")}
            </div>
          </div>

          {mode === "register" && (
            <div className="input-group">
              <label htmlFor="confirmPassword">{t('auth.confirmPassword')}</label>
              <AuthInput
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder={t('auth.confirmPassword')}
                autoComplete="new-password"
                onKeyDown={(e) => {
                  if (e.key === "Enter") void register();
                }}
                icon="lock"
              />
              {confirmPassword.length > 0 && (
                <div className={`hint ${password === confirmPassword ? "ok" : "error"}`}>
                  {password === confirmPassword
                    ? t("pages.changePassword.confirmMatch")
                    : t("pages.changePassword.confirmMismatch")}
                </div>
              )}
            </div>
          )}

          {mode === "login" && (
            <div className="row-actions auth-extra-row">
              <label className="auth-checkline">
                <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
                {t("pages.login.rememberMe")}
              </label>
              <Link to="/app/forgot-password" className="text-link-btn">
                {t("pages.login.forgotPassword")}
              </Link>
            </div>
          )}

          <div className="action-grid auth-action-grid-single">
            {mode === "login" ? (
              <button
                type="button"
                className="primary-action-btn auth-button-full"
                disabled={!loginValid || loading}
                onClick={() => void login()}
              >
                {loading ? t('query.searching') : t('auth.loginButton')}
              </button>
            ) : (
              <button
                type="button"
                className="primary-action-btn auth-button-full"
                disabled={!registerValid || loading}
                onClick={() => void register()}
              >
                {loading ? t('query.searching') : t('auth.registerButton')}
              </button>
            )}
          </div>

          <div className="auth-mode-switch">
            {mode === "login" ? (
              <button
                type="button"
                className="text-link-btn auth-mode-switch-btn"
                onClick={() => setMode("register")}
              >
                {t("auth.switchToRegister")}
              </button>
            ) : (
              <button
                type="button"
                className="text-link-btn auth-mode-switch-btn"
                onClick={() => setMode("login")}
              >
                {t("auth.switchToLogin")}
              </button>
            )}
          </div>

          {mode === "login" && (
            <>
              <div className="divider">
                <span>{t("pages.login.socialDivider")}</span>
              </div>

              <div className="social-grid">
                <button type="button" className="social-btn google-btn" onClick={handleGoogleLogin}>
                  <span className="social-icon social-icon-google" aria-hidden="true">
                    G
                  </span>
                  Google
                </button>
                <button type="button" className="social-btn github-btn" onClick={handleGitHubLogin}>
                  <span className="social-icon social-icon-github" aria-hidden="true">
                    <svg viewBox="0 0 24 24" focusable="false">
                      <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.1.68-.21.68-.48v-1.68c-2.77.6-3.35-1.18-3.35-1.18c-.45-1.15-1.1-1.46-1.1-1.46c-.9-.61.07-.6.07-.6c1 .07 1.52 1.02 1.52 1.02c.88 1.5 2.3 1.07 2.86.82c.09-.64.35-1.08.64-1.32c-2.21-.25-4.54-1.11-4.54-4.93c0-1.09.39-1.98 1.03-2.67c-.11-.25-.45-1.27.1-2.64c0 0 .84-.27 2.75 1.02A9.53 9.53 0 0 1 12 6.84a9.5 9.5 0 0 1 2.5.34c1.9-1.29 2.74-1.02 2.74-1.02c.56 1.37.22 2.39.11 2.64c.64.69 1.03 1.58 1.03 2.67c0 3.83-2.33 4.67-4.55 4.92c.36.31.68.92.68 1.86v2.76c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" />
                    </svg>
                  </span>
                  GitHub
                </button>
              </div>
            </>
          )}

          <div className="auth-footer">
            <Link className="text-link" to="/app/architecture">
              {t('dataFlow.title')}
            </Link>
          </div>

          {status && <div className="status success">{status}</div>}
          {error && <div className="status error">{error}</div>}
        </section>
      </main>
    </div>
  );
}
