/**
 * The username the login form prefills.
 *
 * This used to live behind a module called `secureStorage`, which XORed the value
 * against a key hardcoded three lines above it and base64'd the result. It
 * protected nothing -- the key ships in the bundle, and its own comment said so --
 * while the name invited the next person to put something that really is a secret
 * behind it.
 *
 * It also stopped people logging in. `btoa` throws on any code unit above 255, so
 * a Chinese username XORed into that range threw inside the login handler's `try`,
 * *before* `onLogin`: the credentials were accepted, the exception was caught as a
 * login failure, and the app never moved on. Ticking "remember me" made signing in
 * impossible for anyone whose name is not Latin-1, in an application whose reason
 * for existing is that it works in Chinese.
 *
 * A remembered username is a convenience, not a secret, and it is stored as itself.
 */

const STORAGE_KEY = "remembered_username";

/** What the obfuscated version wrote. Cleared on the way past, never read. */
const OBFUSCATED_KEY = "sec_remembered_username";

function read(key: string): string | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage.getItem(key);
  } catch {
    // A private window or blocked site data throws on access, not only on write.
    return null;
  }
}

export function rememberedUsername(): string {
  return read(STORAGE_KEY) ?? "";
}

export function hasRememberedUsername(): boolean {
  return read(STORAGE_KEY) !== null;
}

export function rememberUsername(username: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, username);
    localStorage.removeItem(OBFUSCATED_KEY);
  } catch {
    // Remembering the name is a convenience. Failing at it must not become a
    // failed login, which is exactly what the previous implementation made of it.
  }
}

export function forgetRememberedUsername(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(OBFUSCATED_KEY);
  } catch {
    // As above.
  }
}
