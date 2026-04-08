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
        host: "0.0.0.0",
        proxy: {
            "/auth": "http://127.0.0.1:8000",
            "/sessions": "http://127.0.0.1:8000",
            "/documents": "http://127.0.0.1:8000",
            "/upload": "http://127.0.0.1:8000",
            "/prompts": "http://127.0.0.1:8000",
            "/query": "http://127.0.0.1:8000",
            "/admin": "http://127.0.0.1:8000",
        },
    },
});
