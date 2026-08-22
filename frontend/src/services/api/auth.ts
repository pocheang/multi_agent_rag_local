import type { AuthUser, LoginResponse } from "@/types/api";
import { request, getToken, setToken as setTokenInternal } from "@/services/http/client";
import { refreshCsrfToken, clearCsrfToken } from "@/lib/csrf";

export const authApi = {
  async me() {
    return request<AuthUser>("/auth/me");
  },
  async login(username: string, password: string) {
    const response = await request<LoginResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (response.token) {
      setTokenInternal(response.token);
      refreshCsrfToken(); // Generate new CSRF token on login
    }
    return response;
  },
  async register(username: string, password: string) {
    return request<AuthUser>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  },
  async logout() {
    try {
      await request("/auth/logout", { method: "POST" });
    } catch {
      // ignore logout error
    } finally {
      clearCsrfToken(); // Clear CSRF token on logout
    }
  },
  async changePassword(oldPassword: string, newPassword: string) {
    return request<{ ok: boolean; message: string }>("/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
  },
  async updateProfile(displayName: string) {
    return request<AuthUser>("/auth/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName }),
    });
  },
  setToken(token: string) {
    setTokenInternal(token);
    if (!token) {
      clearCsrfToken(); // Clear CSRF token when clearing auth token
    }
  },
  token() {
    return getToken();
  },
};
