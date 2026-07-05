import type { IncomingMessage, ServerResponse } from "node:http";

import react from "@vitejs/plugin-react";
import type { ProxyOptions } from "vite";
import { defineConfig } from "vitest/config";

function createApiProxy(): ProxyOptions {
  return {
    target: "http://127.0.0.1:8010",
    changeOrigin: true,
    proxyTimeout: 0,
    timeout: 0,
    configure(proxy) {
      proxy.on("proxyReq", (proxyReq, req) => {
        if (req.url?.includes("/events")) {
          proxyReq.setHeader("accept-encoding", "identity");
        }
      });

      proxy.on(
        "proxyRes",
        (proxyRes: IncomingMessage, req: IncomingMessage, res: ServerResponse<IncomingMessage>) => {
          if (!req.url?.includes("/events")) {
            return;
          }

          delete proxyRes.headers["content-length"];
          proxyRes.headers["cache-control"] = "no-cache";
          proxyRes.headers["x-accel-buffering"] = "no";
          res.setHeader("Cache-Control", "no-cache");
          res.setHeader("X-Accel-Buffering", "no");
        }
      );
    }
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api/runs": createApiProxy(),
      "/api": createApiProxy()
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: true
  }
});
