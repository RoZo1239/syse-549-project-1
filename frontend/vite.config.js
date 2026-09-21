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
  // Two people sharing one server means two dev servers wanting 5173.
  // Loopback is not per-user, so whoever starts second collides with the
  // first - and an SSH tunnel aimed at 5173 would reach whichever one won.
  // Set VITE_PORT per person.
  const port = Number(process.env.VITE_PORT || env.VITE_PORT || 5173);

  const to = (offset) => ({
    target: `http://${host}:${block + offset}`,
    changeOrigin: true,
  });

  const proxy = {
    "/api/csp": { ...to(1), rewrite: (p) => p.replace(/^\/api\/csp/, "") },
    "/api/verifier": { ...to(2), rewrite: (p) => p.replace(/^\/api\/verifier/, "") },
    "/api/rp": { ...to(3), rewrite: (p) => p.replace(/^\/api\/rp/, "") },
  };

  // strictPort: without it Vite silently moves to 5174 when 5173 is taken and
  // prints it in a line that is easy to miss. On a shared server that means
  // quietly binding a second port we did not claim, and an SSH tunnel aimed at
  // 5173 then refuses for a reason that looks like the app is broken. Fail
  // loudly instead. host is left at Vite's default (localhost) on purpose -
  // 5173 is outside our 4100-4103 block, so it must not be published.
  // host is pinned to 127.0.0.1 rather than left at Vite's default of
  // "localhost". Node resolves that name, and on a machine where localhost
  // resolves to ::1 first, Vite binds [::1]:PORT only - at which point
  // `ssh -L PORT:127.0.0.1:PORT` is refused by the server end and the app
  // looks broken when it is running perfectly. Pinning the literal address
  // removes the resolution step. It is still loopback-only, so nothing is
  // published on a port we did not claim.
  const server = { host: "127.0.0.1", port, strictPort: true, proxy };
  return { plugins: [react()], server, preview: server };
});
