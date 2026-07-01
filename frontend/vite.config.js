import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import Icons from "unplugin-icons/vite";
import path from "path";

export default defineConfig(({ command }) => ({
  // Prod assets are served from /assets/accounting_portal/. Gate on
  // command==="build" (not mode) because Frappe's bench-build runs Vite
  // without NODE_ENV=production, so `mode` stays "development".
  base: command === "build" ? "/assets/accounting_portal/" : "/",
  // Belt-and-suspenders: rewrite EVERY emitted asset URL with the prefix so
  // CSS-embedded @fontsource url() references resolve in production.
  experimental: command === "build" ? {
    renderBuiltUrl(filename) {
      return "/assets/accounting_portal/" + filename;
    },
  } : undefined,
  plugins: [vue(), Icons()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    outDir: "../accounting_portal/public",
    emptyOutDir: false,
    target: "es2015",
    cssCodeSplit: false,
    rollupOptions: {
      input: path.resolve(__dirname, "src/main.js"),
      output: {
        // Split code so first load ships only the shell + vendor + landing page;
        // every other module loads on demand. Safe here because the HTML page is
        // `no_cache` and cache-busts `app.js?v={mtime}` every build — fresh HTML
        // always points at the current app.js, which references the current
        // content-hashed chunks. Hashed chunks are immutable → cache-forever with
        // no stale-name 404s. (An already-open tab surviving a deploy is handled
        // by the vite:preloadError hard-reload in main.js.)
        entryFileNames: "app.js",
        chunkFileNames: "assets/[name]-[hash].js",
        // Keep the big, rarely-changing runtime (Vue, router, i18n) in its own
        // chunk so it stays cached across app deploys.
        manualChunks: {
          vendor: ["vue", "vue-router", "vue-i18n"],
        },
        assetFileNames: (info) => {
          const name = info.name || "";
          if (name.endsWith(".css")) return "app.css";
          return "assets/[name][extname]";
        },
      },
    },
  },
  server: {
    port: 8090,
    proxy: {
      "^/(api|login|app|assets|socket\\.io)": {
        // Point at the ERPNext backend. Override with VITE_PROXY_TARGET to
        // hit a local bench. cookieDomainRewrite lets the browser accept the
        // sid + csrf cookies on localhost.
        target: process.env.VITE_PROXY_TARGET || "https://admin-dev.justyol.com",
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: { "*": "" },
        followRedirects: true,
      },
    },
  },
}));
