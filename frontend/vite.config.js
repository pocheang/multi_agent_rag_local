import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
export default defineConfig({
    plugins: [react()],
    base: "/app/",
    resolve: {
        alias: {
            "@": "/src",
        },
    },
    server: {
        port: 5173,
        host: "127.0.0.1",
        proxy: {
            "/auth": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
                timeout: 600000,
                proxyTimeout: 600000,
                configure: function (proxy, _options) {
                    proxy.on('proxyRes', function (proxyRes, req, res) {
                        // Remove 'secure' flag from cookies in development
                        var setCookie = proxyRes.headers['set-cookie'];
                        if (setCookie) {
                            proxyRes.headers['set-cookie'] = Array.isArray(setCookie)
                                ? setCookie.map(function (cookie) { return cookie.replace(/; secure/gi, ''); })
                                : [setCookie.replace(/; secure/gi, '')];
                        }
                    });
                }
            },
            "/sessions": { target: "http://127.0.0.1:8000", changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
            "/documents": { target: "http://127.0.0.1:8000", changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
            "/upload": { target: "http://127.0.0.1:8000", changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
            "/prompts": { target: "http://127.0.0.1:8000", changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
            "/query": { target: "http://127.0.0.1:8000", changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
            "/admin": { target: "http://127.0.0.1:8000", changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
            "/user": { target: "http://127.0.0.1:8000", changeOrigin: true, timeout: 600000, proxyTimeout: 600000 },
        },
    },
});
