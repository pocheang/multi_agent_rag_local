import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { authApi } from "@/lib/api";
import type { AuthUser } from "@/types/api";

type Props = {
  onLogin: (user: AuthUser) => void;
  themeLabel: string;
  onThemeToggle: () => void;
};

function validateUsername(value: string) {
  return /^[A-Za-z0-9._-]{3,32}$/.test(value.trim());
}

function validatePassword(value: string) {
  return value.length >= 8 && /[a-z]/.test(value) && /[A-Z]/.test(value) && /[0-9]/.test(value);
}

export function LoginPage({ onLogin, themeLabel, onThemeToggle }: Props) {
  const [username, setUsername] = useState(localStorage.getItem("remembered_username") || "");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(!!localStorage.getItem("remembered_username"));
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loginValid = useMemo(() => validateUsername(username) && password.length > 0, [username, password]);
  const registerValid = useMemo(
    () => validateUsername(username) && validatePassword(password),
    [username, password],
  );

  const login = async () => {
    if (!loginValid) {
      setError("请输入有效用户名和密码");
      return;
    }
    setLoading(true);
    setError("");
    setStatus("登录中...");
    try {
      const data = await authApi.login(username.trim(), password);
      if (rememberMe) localStorage.setItem("remembered_username", username.trim());
      else localStorage.removeItem("remembered_username");
      onLogin(data.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败");
    } finally {
      setLoading(false);
      setStatus("");
    }
  };

  const register = async () => {
    if (!registerValid) {
      setError("请先修正输入");
      return;
    }
    setLoading(true);
    setError("");
    setStatus("注册中...");
    try {
      const data = await authApi.register(username.trim(), password);
      setStatus(`注册成功: ${data.username}，请登录`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "注册失败");
    } finally {
      setLoading(false);
    }
  };

  const showOAuthHint = (provider: "GitHub" | "Google") => {
    setError("");
    setStatus(`${provider} OAuth 待后端接入后启用`);
  };

  const forgotPassword = () => {
    setError("");
    setStatus("忘记密码流程待接入，可先联系管理员重置");
  };

  return (
    <div className="auth-root">
      <button type="button" className="theme-toggle" onClick={onThemeToggle}>
        {themeLabel}
      </button>

      <main className="auth-card">
        <section className="auth-intro">
          <div className="badge">React Migration</div>
          <h1>CyberSec RAG</h1>
          <p>React + TypeScript + Vite 前端。登录后进入完整会话、文档、Prompt 与管理功能。</p>
        </section>

        <section className="auth-form">
          <h2>登录系统</h2>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="用户名"
            autoComplete="username"
          />
          <div className={`hint ${validateUsername(username) ? "ok" : "error"}`}>
            {validateUsername(username) ? "用户名格式可用" : "用户名需 3-32 位（字母数字._-）"}
          </div>

          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密码"
            autoComplete="current-password"
            onKeyDown={(e) => {
              if (e.key === "Enter") void login();
            }}
          />
          <div className={`hint ${validatePassword(password) ? "ok" : "error"}`}>
            {validatePassword(password) ? "密码复杂度达标" : "注册至少8位，含大小写和数字"}
          </div>

          <div className="action-grid">
            <button type="button" disabled={loading} onClick={() => void login()}>
              登录
            </button>
            <button type="button" className="secondary" disabled={loading} onClick={() => void register()}>
              注册
            </button>
          </div>

          <div className="row-actions auth-extra-row">
            <label className="checkline auth-checkline">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              记住我
            </label>
            <button type="button" className="text-link-btn" onClick={forgotPassword}>
              忘记密码
            </button>
          </div>

          <div className="social-grid">
            <button type="button" className="secondary" onClick={() => showOAuthHint("GitHub")}>
              GitHub 登录
            </button>
            <button type="button" className="secondary" onClick={() => showOAuthHint("Google")}>
              Google 登录
            </button>
          </div>

          <div className="auth-link-row">
            <Link className="text-link" to="/app/architecture">
              查看系统架构总览
            </Link>
          </div>

          {status && <div className="status">{status}</div>}
          {error && <div className="status error">{error}</div>}
        </section>
      </main>
    </div>
  );
}
