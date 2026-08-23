import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { authApi } from "@/lib/api";
import { applyTheme, getSavedTheme, nextTheme, saveTheme, type ThemeMode } from "@/lib/theme";
import type { AuthUser } from "@/types/api";
import { ToastProvider } from "@/components/animations/AnimatedToastLite";
import { getPermissionCheck } from "@/hooks/usePermissions";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { usePerformanceMonitoring } from "@/hooks/usePerformanceMonitoring";

const LoginPage = lazy(() => import("@/pages/LoginPage").then(({ LoginPage }) => ({ default: LoginPage })));
const ChatPage = lazy(() => import("@/pages/ChatPage").then(({ ChatPage }) => ({ default: ChatPage })));
const AdminPage = lazy(() => import("@/pages/AdminPage").then(({ AdminPage }) => ({ default: AdminPage })));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage").then(({ AnalyticsPage }) => ({ default: AnalyticsPage })));
const ArchitecturePage = lazy(() => import("@/pages/ArchitecturePage").then(({ ArchitecturePage }) => ({ default: ArchitecturePage })));
const ChangePasswordPage = lazy(() => import("@/pages/ChangePasswordPage").then(({ ChangePasswordPage }) => ({ default: ChangePasswordPage })));
const ProfilePage = lazy(() => import("@/pages/ProfilePage").then(({ ProfilePage }) => ({ default: ProfilePage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then(({ NotFoundPage }) => ({ default: NotFoundPage })));
const LandingPage = lazy(() => import("@/pages/LandingPage").then(({ LandingPage }) => ({ default: LandingPage })));

function RouteFallback() {
  return <div className="app-loading" aria-live="polite" />;
}

function Protected({
  user,
  authReady,
  allowed = true,
  children,
}: {
  user: AuthUser | null;
  authReady: boolean;
  allowed?: boolean;
  children: ReactNode;
}) {
  if (!authReady) return null;
  if (!user) return <Navigate to="/app/login" replace />;
  if (!allowed) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export function App() {
  const { t } = useTranslation();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>(getSavedTheme());
  const location = useLocation();
  const navigate = useNavigate();

  // Performance monitoring (production only)
  usePerformanceMonitoring(import.meta.env.PROD);

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

  const refreshUser = async () => {
    setUser(await authApi.me());
  };

  const renderGuestOnly = (page: ReactNode) => {
    if (user) {
      return <Navigate to="/app" replace />;
    }
    return page;
  };

  const renderProtected = (page: ReactNode, allowed = true) => (
    <Protected user={user} authReady={authReady} allowed={allowed}>
      {page}
    </Protected>
  );

  const permissions = getPermissionCheck(user);

  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        console.error("App Error:", error, errorInfo);
        // TODO: Send to error tracking service (e.g., Sentry)
      }}
    >
      {/* Tailwind v4 smoke test - hidden element verifying tw: prefix and theme variables */}
      <div
        className="tw:hidden tw:flex tw:bg-surface tw:text-text-primary"
        data-testid="tailwind-smoke-test"
        aria-hidden="true"
      />
      <ToastProvider>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
          <Route
            path="/app/login"
            element={renderGuestOnly(<LoginPage onLogin={loginSuccess} {...themeControls} />)}
          />
          <Route
            path="/app"
            element={renderProtected(<ChatPage user={user} onLogout={logout} onUserRefresh={refreshUser} {...themeControls} />)}
          />
          <Route
            path="/app/admin"
            element={renderProtected(
              <AdminPage user={user} onLogout={logout} {...themeControls} />,
              permissions.canAccessAdmin,
            )}
          />
          <Route
            path="/app/analytics"
            element={renderProtected(
              <AnalyticsPage user={user} onLogout={logout} {...themeControls} />,
              permissions.canViewAnalytics,
            )}
          />
          <Route
            path="/app/change-password"
            element={renderProtected(<ChangePasswordPage {...themeControls} />)}
          />
          <Route
            path="/app/profile"
            element={renderProtected(<ProfilePage user={user} onUserUpdated={setUser} />)}
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
    </ToastProvider>
    </ErrorBoundary>
  );
}
