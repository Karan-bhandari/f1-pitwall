import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import { cloudflare } from "@cloudflare/vite-plugin";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";

// https://vite.dev/config/
export default defineConfig({
  base: "/f1-pitwall/",
  plugins: [
    vue(),
    process.env.NODE_ENV !== "production" && vueDevTools(),
    cloudflare(),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5005",
        changeOrigin: true,
      },
      "/f1-pitwall/api": {
        target: "http://127.0.0.1:5005",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/f1-pitwall/, ""),
      },
    },
  },
});
