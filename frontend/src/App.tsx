import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { authApi } from "@/lib/api";
import { applyTheme, getSavedTheme, nextTheme, saveTheme, type ThemeMode } from "@/lib/theme";
import type { AuthUser } from "@/types/api";

const LoginPage = lazy(() => import("@/pages/LoginPage").then(({ LoginPage }) => ({ default: LoginPage })));
const ChatPage = lazy(() => import("@/pages/ChatPage").then(({ ChatPage }) => ({ default: ChatPage })));
const AdminPage = lazy(() => import("@/pages/AdminPage").then(({ AdminPage }) => ({ default: AdminPage })));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage").then(({ AnalyticsPage }) => ({ default: AnalyticsPage })));
const ArchitecturePage = lazy(() => import("@/pages/ArchitecturePage").then(({ ArchitecturePage }) => ({ default: ArchitecturePage })));
const ChangePasswordPage = lazy(() => import("@/pages/ChangePasswordPage").then(({ ChangePasswordPage }) => ({ default: ChangePasswordPage })));
const ProfilePage = lazy(() => import("@/pages/ProfilePage").then(({ ProfilePage }) => ({ default: ProfilePage })));
const ForgotPasswordPage = lazy(() => import("@/pages/ForgotPasswordPage").then(({ ForgotPasswordPage }) => ({ default: ForgotPasswordPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then(({ NotFoundPage }) => ({ default: NotFoundPage })));
const LandingPage = lazy(() => import("@/pages/LandingPage").then(({ LandingPage }) => ({ default: LandingPage })));

function RouteFallback() {
  return <div className="app-loading" aria-live="polite" />;
}

function Protected({
  user,
  authReady,
  children,
}: {
  user: AuthUser | null;
  authReady: boolean;
  children: ReactNode;
}) {
  if (!authReady) return null;
  if (!user) return <Navigate to="/app/login" replace />;
  return <>{children}</>;
}

export function App() {
  const { t } = useTranslation();
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

  const themeLabel = theme === "dark" ? t("theme.dark") : t("theme.light");
  const handleThemeToggle = () => setTheme((prev) => nextTheme(prev));
  const themeControls = {
    themeLabel,
    onThemeToggle: handleThemeToggle,
  };

  const logout = async () => {
    await authApi.logout();
    authApi.setToken("");
    setUser(null);
    navigate("/app/login");
  };

  const loginSuccess = (nextUser: AuthUser) => {
    setUser(nextUser);
  };

  const renderGuestOnly = (page: ReactNode) => {
    if (user) {
      return <Navigate to="/app" replace />;
    }
    return page;
  };

  const renderProtected = (page: ReactNode) => (
    <Protected user={user} authReady={authReady}>
      {page}
    </Protected>
  );

  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route
          path="/app/login"
          element={renderGuestOnly(<LoginPage onLogin={loginSuccess} {...themeControls} />)}
        />
        <Route
          path="/app/forgot-password"
          element={renderGuestOnly(<ForgotPasswordPage {...themeControls} />)}
        />
        <Route
          path="/app"
          element={renderProtected(<ChatPage user={user} onLogout={logout} {...themeControls} />)}
        />
        <Route
          path="/app/admin"
          element={renderProtected(<AdminPage user={user} onLogout={logout} {...themeControls} />)}
        />
        <Route
          path="/app/analytics"
          element={renderProtected(<AnalyticsPage user={user} onLogout={logout} {...themeControls} />)}
        />
        <Route
          path="/app/change-password"
          element={renderProtected(<ChangePasswordPage {...themeControls} />)}
        />
        <Route
          path="/app/profile"
          element={renderProtected(<ProfilePage user={user} />)}
        />
        <Route
          path="/app/architecture"
          element={<ArchitecturePage isLoggedIn={!!user} {...themeControls} />}
        />
        <Route
          path="/"
          element={<LandingPage isLoggedIn={!!user} {...themeControls} />}
        />
        <Route path="*" element={<NotFoundPage pathname={location.pathname} />} />
      </Routes>
    </Suspense>
  );
}
