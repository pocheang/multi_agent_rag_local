import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { authApi } from "@/lib/api";
import { applyTheme, getSavedTheme, nextTheme, saveTheme, type ThemeMode } from "@/lib/theme";
import { LoginPage } from "@/pages/LoginPage";
import { ChatPage } from "@/pages/ChatPage";
import { AdminPage } from "@/pages/AdminPage";
import { ArchitecturePage } from "@/pages/ArchitecturePage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import type { AuthUser } from "@/types/api";

function Protected({
  user,
  authReady,
  children,
}: {
  user: AuthUser | null;
  authReady: boolean;
  children: React.ReactNode;
}) {
  if (!authReady) return null;
  if (!user) return <Navigate to="/app/login" replace />;
  return <>{children}</>;
}

export function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>(getSavedTheme());
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    applyTheme(theme);
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        authApi.setToken("");
        setUser(null);
      })
      .finally(() => setAuthReady(true));
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handle = () => {
      if (theme === "auto") applyTheme("auto");
    };
    mq.addEventListener("change", handle);
    return () => mq.removeEventListener("change", handle);
  }, [theme]);

  const themeLabel = useMemo(() => {
    if (theme === "light") return "主题: 亮色";
    if (theme === "dark") return "主题: 暗色";
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    return `主题: 跟随系统(${dark ? "暗" : "亮"})`;
  }, [theme]);

  const logout = async () => {
    await authApi.logout();
    authApi.setToken("");
    setUser(null);
    navigate("/app/login");
  };

  const loginSuccess = (nextUser: AuthUser) => {
    setUser(nextUser);
    navigate("/app");
  };

  return (
    <Routes>
      <Route
        path="/app/login"
        element={
          user ? (
            <Navigate to="/app" replace />
          ) : (
            <LoginPage
              onLogin={loginSuccess}
              themeLabel={themeLabel}
              onThemeToggle={() => setTheme((prev) => nextTheme(prev))}
            />
          )
        }
      />
      <Route
        path="/app"
        element={
          <Protected user={user} authReady={authReady}>
            <ChatPage
              user={user}
              onLogout={logout}
              themeLabel={themeLabel}
              onThemeToggle={() => setTheme((prev) => nextTheme(prev))}
            />
          </Protected>
        }
      />
      <Route
        path="/app/admin"
        element={
          <Protected user={user} authReady={authReady}>
            <AdminPage
              user={user}
              onLogout={logout}
              themeLabel={themeLabel}
              onThemeToggle={() => setTheme((prev) => nextTheme(prev))}
            />
          </Protected>
        }
      />
      <Route
        path="/app/architecture"
        element={
          <ArchitecturePage
            isLoggedIn={!!user}
            themeLabel={themeLabel}
            onThemeToggle={() => setTheme((prev) => nextTheme(prev))}
          />
        }
      />
      <Route path="/" element={<Navigate to={user ? "/app" : "/app/login"} replace />} />
      <Route path="*" element={<NotFoundPage pathname={location.pathname} />} />
    </Routes>
  );
}
