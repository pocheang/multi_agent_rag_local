/**
 * usePermissions Hook
 *
 * Provides role-based permission checking for the frontend.
 * Syncs with backend RBAC permissions defined in app/services/rbac.py
 */

import { useMemo } from 'react';
import { toKnownUserRole, type KnownUserRole, type UserIdentity } from '@/types/auth';

export interface PermissionCheck {
  // Session permissions
  canCreateSession: boolean;
  canDeleteSession: boolean;
  canLockStrategy: boolean;

  // Message permissions
  canEditMessage: boolean;
  canDeleteMessage: boolean;

  // Prompt permissions
  canViewPrompts: boolean;
  canCreatePrompt: boolean;
  canEditPrompt: boolean;
  canDeletePrompt: boolean;

  // Document permissions
  canUploadDocument: boolean;
  canDeleteDocument: boolean;
  canReindexDocument: boolean;

  // Admin permissions
  canAccessAdmin: boolean;
  canManageUsers: boolean;
  canConfigureSystem: boolean;
  canViewAnalytics: boolean;

  // Core permissions
  canQuery: boolean;
  canViewAgentTracking: boolean;

  // Role info
  role: KnownUserRole;
  isAdmin: boolean;
  isAnalyst: boolean;
  isViewer: boolean;
}

/**
 * Role-based permissions mapping
 * Must match backend RBAC in app/services/rbac.py
 */
const ROLE_PERMISSIONS: Record<KnownUserRole, PermissionCheck> = {
  admin: {
    canCreateSession: true,
    canDeleteSession: true,
    canLockStrategy: true,
    canEditMessage: true,
    canDeleteMessage: true,
    canViewPrompts: true,
    canCreatePrompt: true,
    canEditPrompt: true,
    canDeletePrompt: true,
    canUploadDocument: true,
    canDeleteDocument: true,
    canReindexDocument: true,
    canAccessAdmin: true,
    canManageUsers: true,
    canConfigureSystem: true,
    canViewAnalytics: true,
    canQuery: true,
    canViewAgentTracking: true,
    role: 'admin',
    isAdmin: true,
    isAnalyst: false,
    isViewer: false,
  },
  analyst: {
    canCreateSession: true,
    canDeleteSession: true,
    canLockStrategy: true,
    canEditMessage: true,
    canDeleteMessage: true,
    canViewPrompts: true,
    canCreatePrompt: true,
    canEditPrompt: true,
    canDeletePrompt: true,
    canUploadDocument: true,
    canDeleteDocument: true,
    canReindexDocument: true,
    canAccessAdmin: false,
    canManageUsers: false,
    canConfigureSystem: false,
    canViewAnalytics: false,
    canQuery: true,
    canViewAgentTracking: true,
    role: 'analyst',
    isAdmin: false,
    isAnalyst: true,
    isViewer: false,
  },
  viewer: {
    canCreateSession: true,
    canDeleteSession: false,
    canLockStrategy: false,
    canEditMessage: false,
    canDeleteMessage: false,
    canViewPrompts: true,
    canCreatePrompt: false,
    canEditPrompt: false,
    canDeletePrompt: false,
    canUploadDocument: false,
    canDeleteDocument: false,
    canReindexDocument: false,
    canAccessAdmin: false,
    canManageUsers: false,
    canConfigureSystem: false,
    canViewAnalytics: false,
    canQuery: true,
    canViewAgentTracking: true,
    role: 'viewer',
    isAdmin: false,
    isAnalyst: false,
    isViewer: true,
  },
};

/**
 * Hook to check user permissions based on their role
 *
 * @param user - Current user object (can be null if not logged in)
 * @returns Permission check object with boolean flags for each permission
 *
 * @example
 * ```tsx
 * const permissions = usePermissions(user);
 *
 * if (permissions.canDeleteSession) {
 *   return <DeleteButton onClick={handleDelete} />;
 * }
 *
 * if (permissions.isAdmin) {
 *   return <AdminPanel />;
 * }
 * ```
 */
export function getPermissionCheck(user: UserIdentity | null): PermissionCheck {
  if (!user || !user.role) {
    // Default to viewer permissions for unauthenticated users
    return ROLE_PERMISSIONS.viewer;
  }

  return ROLE_PERMISSIONS[toKnownUserRole(user.role)];
}

export function usePermissions(user: UserIdentity | null): PermissionCheck {
  return useMemo(() => getPermissionCheck(user), [user]);
}

/**
 * Utility function to check a specific permission
 *
 * @param user - Current user object
 * @param permission - Permission key to check
 * @returns boolean indicating if user has the permission
 *
 * @example
 * ```tsx
 * if (hasPermission(user, 'canDeleteSession')) {
 *   // Show delete button
 * }
 * ```
 */
export function hasPermission(
  user: UserIdentity | null,
  permission: keyof PermissionCheck
): boolean {
  const permissions = getPermissionCheck(user);
  return Boolean(permissions[permission]);
}

/**
 * HOC to wrap components that require specific permissions
 *
 * @param Component - Component to wrap
 * @param requiredPermissions - Array of required permissions
 * @param fallback - Optional fallback component to show if permission denied
 *
 * @example
 * ```tsx
 * const ProtectedDeleteButton = withPermission(
 *   DeleteButton,
 *   ['canDeleteSession'],
 *   <span>No permission</span>
 * );
 * ```
 */
export function withPermission<P extends object>(
  Component: React.ComponentType<P>,
  requiredPermissions: Array<keyof PermissionCheck>,
  fallback: React.ReactNode = null
) {
  return function PermissionWrappedComponent(props: P & { user: UserIdentity | null }) {
    const { user, ...rest } = props;
    const permissions = usePermissions(user);

    const hasAllPermissions = requiredPermissions.every(
      (perm) => permissions[perm] === true
    );

    if (!hasAllPermissions) {
      return <>{fallback}</>;
    }

    return <Component {...(rest as P)} />;
  };
}

/**
 * Component to conditionally render children based on permissions
 *
 * @example
 * ```tsx
 * <PermissionGate user={user} requires={['canDeleteSession']}>
 *   <DeleteButton />
 * </PermissionGate>
 *
 * <PermissionGate user={user} requires={['isAdmin']}>
 *   <AdminPanel />
 * </PermissionGate>
 * ```
 */
export function PermissionGate({
  user,
  requires,
  fallback = null,
  children,
}: {
  user: UserIdentity | null;
  requires: Array<keyof PermissionCheck>;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}) {
  const permissions = usePermissions(user);

  const hasAllPermissions = requires.every(
    (perm) => permissions[perm] === true
  );

  if (!hasAllPermissions) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

/**
 * Role badge component to display user role
 */
export function RoleBadge({ role }: { role: string }) {
  const knownRole = toKnownUserRole(role);
  const labels: Record<KnownUserRole, string> = {
    admin: 'Admin',
    analyst: 'Analyst',
    viewer: 'Viewer',
  };

  return (
    <span className={`role-badge role-badge--${knownRole}`}>
      {labels[knownRole]}
    </span>
  );
}
