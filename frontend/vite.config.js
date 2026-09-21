import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Proxies to the three services a browser touches so that it only ever talks
// to one origin and never trips CORS against the raw http.server-based
// backends (which don't implement OPTIONS preflight). Shared between
// `npm run dev` (hot reload) and `npm run preview` (the built output).
//
// The target host and port block come from the environment, so the same UI can
// drive a local copy of the services or the deployment on the lab server:
//
//   npm run dev                                   -> 127.0.0.1:4101-4103
//   VITE_API_HOST=daily-server.research.colostate.edu npm run dev
//
// That second form matters for packet capture. Pointed at 127.0.0.1 every
// request is loopback traffic, which Wireshark can only see on the loopback
// interface (and on Windows only with Npcap's loopback adapter installed).
// Pointed at the server's hostname, the browser's five steps cross a real
// network interface in cleartext HTTP and capture normally.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const host = env.VITE_API_HOST || "127.0.0.1";
  const block = Number(env.VITE_PORT_BLOCK || 4100);

  const to = (offset) => ({
    target: `http://${host}:${block + offset}`,
    changeOrigin: true,
  });

  const proxy = {
    "/api/csp": { ...to(1), rewrite: (p) => p.replace(/^\/api\/csp/, "") },
    "/api/verifier": { ...to(2), rewrite: (p) => p.replace(/^\/api\/verifier/, "") },
    "/api/rp": { ...to(3), rewrite: (p) => p.replace(/^\/api\/rp/, "") },
  };

  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 5173, proxy },
  };
});
