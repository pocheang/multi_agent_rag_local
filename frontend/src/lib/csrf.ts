/**
 * CSRF Protection Utilities
 *
 * Implements CSRF token generation and validation for state-changing requests.
 * The backend should validate the X-CSRF-Token header on all POST/PUT/PATCH/DELETE requests.
 */

const CSRF_TOKEN_KEY = 'csrf_token';
const CSRF_TOKEN_LENGTH = 32;

/**
 * Generate a cryptographically secure random token
 */
function generateSecureToken(): string {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const array = new Uint8Array(CSRF_TOKEN_LENGTH);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
  }

  // Fallback for older browsers (less secure)
  return Array.from({ length: CSRF_TOKEN_LENGTH }, () =>
    Math.floor(Math.random() * 16).toString(16)
  ).join('');
}

/**
 * Get or create CSRF token
 */
export function getCsrfToken(): string {
  if (typeof sessionStorage === 'undefined') return '';

  let token = sessionStorage.getItem(CSRF_TOKEN_KEY);

  if (!token) {
    token = generateSecureToken();
    sessionStorage.setItem(CSRF_TOKEN_KEY, token);
  }

  return token;
}

/**
 * Refresh CSRF token (call after login/logout)
 */
export function refreshCsrfToken(): void {
  if (typeof sessionStorage === 'undefined') return;
  const token = generateSecureToken();
  sessionStorage.setItem(CSRF_TOKEN_KEY, token);
}

/**
 * Clear CSRF token (call on logout)
 */
export function clearCsrfToken(): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(CSRF_TOKEN_KEY);
}

/**
 * Add CSRF token to request headers
 */
export function addCsrfHeader(headers: Headers): void {
  const token = getCsrfToken();
  if (token) {
    headers.set('X-CSRF-Token', token);
  }
}

/**
 * Check if request method requires CSRF protection
 */
export function requiresCsrfProtection(method: string): boolean {
  const safeMethod = method.toUpperCase();
  return !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(safeMethod);
}
