/**
 * Secure Storage Utilities
 *
 * Provides basic encryption for sensitive data stored in localStorage.
 * Note: This is obfuscation, not true encryption. For production, use backend-only storage.
 */

const STORAGE_PREFIX = 'sec_';
const ENCRYPTION_KEY = 'rag_local_v4'; // In production, this should be environment-specific

/**
 * Simple XOR cipher for basic obfuscation
 * Note: This is NOT cryptographically secure, but better than plaintext
 */
function simpleEncrypt(text: string, key: string): string {
  let result = '';
  for (let i = 0; i < text.length; i++) {
    result += String.fromCharCode(text.charCodeAt(i) ^ key.charCodeAt(i % key.length));
  }
  return btoa(result); // Base64 encode
}

function simpleDecrypt(encrypted: string, key: string): string {
  try {
    const decoded = atob(encrypted);
    let result = '';
    for (let i = 0; i < decoded.length; i++) {
      result += String.fromCharCode(decoded.charCodeAt(i) ^ key.charCodeAt(i % key.length));
    }
    return result;
  } catch {
    return '';
  }
}

/**
 * Store data securely (obfuscated) in localStorage
 */
export function secureSetItem(key: string, value: string): void {
  if (typeof localStorage === 'undefined') return;
  const encrypted = simpleEncrypt(value, ENCRYPTION_KEY);
  localStorage.setItem(STORAGE_PREFIX + key, encrypted);
}

/**
 * Retrieve securely stored data from localStorage
 */
export function secureGetItem(key: string): string | null {
  if (typeof localStorage === 'undefined') return null;
  const encrypted = localStorage.getItem(STORAGE_PREFIX + key);
  if (!encrypted) return null;
  return simpleDecrypt(encrypted, ENCRYPTION_KEY);
}

/**
 * Remove securely stored data from localStorage
 */
export function secureRemoveItem(key: string): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(STORAGE_PREFIX + key);
}

/**
 * Check if secure item exists
 */
export function secureHasItem(key: string): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(STORAGE_PREFIX + key) !== null;
}
