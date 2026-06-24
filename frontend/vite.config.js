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
        // Inline every lazy route chunk into one fixed-name app.js. On the
        // no-node bench deploy the only cache key is app.js?v={mtime}; a separate
        // hash-named chunk (Module-XXXX.js) would change name each build and a
        // cached old app.js would 404 on it. One file = deterministic deploys.
        inlineDynamicImports: true,
        entryFileNames: "app.js",
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
