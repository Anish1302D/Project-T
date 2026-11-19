import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const proxyTarget = process.env.VITE_CLOUD_PROXY_TARGET ?? "http://127.0.0.1:4780";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api/cloud": {
        target: proxyTarget,
        changeOrigin: true
      },
      "/health": {
        target: proxyTarget,
        changeOrigin: true
      }
    }
  },
  preview: {
    host: "127.0.0.1",
    port: 4173
  }
});
