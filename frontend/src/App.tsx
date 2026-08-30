import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { authApi } from "@/lib/api";
import type { AuthUser } from "@/types/api";
import { ToastProvider } from "@/components/animations/AnimatedToastLite";
import { getPermissionCheck } from "@/hooks/usePermissions";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ChatErrorBoundary } from "@/components/ChatErrorBoundary";
import { AdminErrorBoundary } from "@/components/AdminErrorBoundary";
import { usePerformanceMonitoring } from "@/hooks/usePerformanceMonitoring";
import { useChatStore } from "@/stores/useChatStore";
import { useAdminStore } from "@/stores/useAdminStore";

/**
 * Drop everything the previous user filled in.
 *
 * Zustand stores live for the lifetime of the tab, so without this the next
 * person to sign in on a shared browser sees the previous one's session list,
 * documents and prompts until the first refetch lands.
 */
function clearUserState() {
  useChatStore.getState().reset();
  useAdminStore.getState().reset();
}

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
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  // Performance monitoring (production only)
  usePerformanceMonitoring(import.meta.env.PROD);

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        authApi.setToken("");
        clearUserState();
        setUser(null);
      })
      .finally(() => setAuthReady(true));
  }, []);

  const logout = async () => {
    await authApi.logout();
    authApi.setToken("");
    clearUserState();
    setUser(null);
    navigate("/app/login");
  };

  const loginSuccess = (nextUser: AuthUser) => {
    setUser(nextUser);
  };

  // Belt and braces for identity changes that do not go through `logout` --
  // a session expiring and someone else signing in on the same tab, say.
  const lastUserId = useRef<string | null>(null);
  useEffect(() => {
    const nextId = user?.user_id ?? null;
    if (lastUserId.current !== null && lastUserId.current !== nextId) {
      clearUserState();
    }
    lastUserId.current = nextId;
  }, [user?.user_id]);

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
            element={renderGuestOnly(<LoginPage onLogin={loginSuccess} />)}
          />
          <Route
            path="/app"
            element={renderProtected(
              <ChatErrorBoundary>
                <ChatPage user={user} onLogout={logout} onUserRefresh={refreshUser} />
              </ChatErrorBoundary>,
            )}
          />
          <Route
            path="/app/admin"
            element={renderProtected(
              <AdminErrorBoundary>
                <AdminPage user={user} onLogout={logout} />
              </AdminErrorBoundary>,
              permissions.canAccessAdmin,
            )}
          />
          <Route
            path="/app/analytics"
            element={renderProtected(
              <AnalyticsPage user={user} onLogout={logout} />,
              permissions.canViewAnalytics,
            )}
          />
          <Route
            path="/app/change-password"
            element={renderProtected(<ChangePasswordPage />)}
          />
          <Route
            path="/app/profile"
            element={renderProtected(<ProfilePage user={user} onUserUpdated={setUser} />)}
          />
          <Route
            path="/app/architecture"
            element={<ArchitecturePage isLoggedIn={!!user} />}
          />
          <Route
            path="/"
            element={<LandingPage isLoggedIn={!!user} />}
          />
          <Route path="*" element={<NotFoundPage pathname={location.pathname} />} />
        </Routes>
      </Suspense>
    </ToastProvider>
    </ErrorBoundary>
  );
}
