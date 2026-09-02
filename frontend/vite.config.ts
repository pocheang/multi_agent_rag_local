import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";
// @ts-ignore - JavaScript plugin without type definitions
import inlineCriticalCSS from './vite-plugin-inline-critical.js';

function isCss(id: string) {
  return id.endsWith(".css");
}

function isChatRouteCss(id: string) {
  return (
    id.includes('pages/chat-entry.css') ||
    id.includes('pages/chat.css') ||
    id.includes('pages/chat-responsive.css') ||
    id.includes('themes/light/chat.css') ||
    id.includes('components/topbar') ||
    id.includes('components/sidebar') ||
    id.includes('components/welcome-screen.css') ||
    id.includes('features/messages.css') ||
    id.includes('features/composer') ||
    id.includes('features/citations.css') ||
    id.includes('features/graph.css') ||
    id.includes('features/process.css')
  );
}

function createBackendProxy(rewriteAppBase = false) {
  return {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    timeout: 600000,
    proxyTimeout: 600000,
    rewrite: rewriteAppBase ? (path: string) => path.replace(/^\/app/, "") : undefined,
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), inlineCriticalCSS()],
  base: "/",
  resolve: {
    alias: {
      "@": "/src",
    },
  },
  build: {
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Component-level CSS splitting (Phase 4)
          if (isCss(id) && id.includes('components/modals.css')) {
            return 'modal-styles';
          }
          if (isCss(id) && id.includes('components/dropdowns.css')) {
            return 'dropdown-styles';
          }
          // Route-specific CSS splitting (Phase 3)
          if (isCss(id) && (id.includes('pages/auth-entry.css') || id.includes('pages/auth/'))) {
            return 'auth-styles';
          }
          if (isCss(id) && isChatRouteCss(id)) {
            return 'chat-styles';
          }
          if (isCss(id) && (id.includes('pages/admin-entry.css') || id.includes('pages/admin/'))) {
            return 'admin-styles';
          }
          if (isCss(id) && id.includes('pages/profile')) {
            return 'profile-styles';
          }
        }
      }
    }
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/auth": {
        ...createBackendProxy(),
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('proxyRes', (proxyRes, _req, _res) => {
            // Remove 'secure' flag from cookies in development
            const setCookie = proxyRes.headers['set-cookie'];
            if (setCookie) {
              proxyRes.headers['set-cookie'] = Array.isArray(setCookie)
                ? setCookie.map(cookie => cookie.replace(/; secure/gi, ''))
                : [(setCookie as string).replace(/; secure/gi, '')];
            }
          });
        }
      },
      "/sessions": createBackendProxy(),
      "/documents": createBackendProxy(),
      "/upload": createBackendProxy(),
      "/prompts": createBackendProxy(),
      "/query": createBackendProxy(),
      "/admin": createBackendProxy(),
      "/user": createBackendProxy(),
      "/api/v1": createBackendProxy(),
      "/api": createBackendProxy(),
      "/app/auth": createBackendProxy(true),
      "/app/sessions": createBackendProxy(true),
      "/app/documents": createBackendProxy(true),
      "/app/upload": createBackendProxy(true),
      "/app/prompts": createBackendProxy(true),
      "/app/query": createBackendProxy(true),
      // Note: /app/admin is handled by frontend router, not proxied to backend
      "/app/user": createBackendProxy(true),
      "/app/api": createBackendProxy(true),
    },
  },
});
