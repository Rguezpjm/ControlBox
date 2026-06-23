/**
 * Production entrypoint: proxies /api and /ws to the API container and forwards
 * everything else to the Next.js standalone server (WebSocket upgrades need this).
 */
const { spawn } = require("node:child_process");
const { createServer } = require("node:http");
const httpProxy = require("http-proxy");
const { parse } = require("node:url");

const port = Number(process.env.PORT || 3000);
const hostname = process.env.HOSTNAME || "0.0.0.0";
const nextPort = Number(process.env.INTERNAL_NEXT_PORT || port + 1);
const apiBase = (process.env.API_PROXY_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const wsBase = apiBase.replace(/^http/i, "ws");
const basePath = (process.env.NEXT_PUBLIC_BASE_PATH || "").replace(/\/$/, "");

// Proxy para la API: changeOrigin=true porque el target es un contenedor distinto
const apiProxy = httpProxy.createProxyServer({
  changeOrigin: true,
  xfwd: true,
});

// Proxy para Next.js: changeOrigin=false para que Next.js vea el Host original
// del cliente y genere redirects con la IP/dominio real en lugar de localhost:3001
const nextProxy = httpProxy.createProxyServer({
  ws: true,
  changeOrigin: false,
  xfwd: true,
});

function onProxyError(label) {
  return (err, _req, res) => {
    if (res && !res.headersSent && typeof res.writeHead === "function") {
      res.writeHead(502, { "Content-Type": "text/plain" });
      res.end("Bad gateway");
    }
    console.error(`[${label}]`, err.message);
  };
}

apiProxy.on("error", onProxyError("api-proxy"));
nextProxy.on("error", onProxyError("next-proxy"));

function normalizePath(pathname) {
  if (!pathname) return "/";
  if (basePath && pathname.startsWith(basePath)) {
    return pathname.slice(basePath.length) || "/";
  }
  return pathname;
}

function isApiPath(pathname) {
  const path = normalizePath(pathname);
  return path === "/health" || path.startsWith("/api/");
}

function isWsPath(pathname) {
  return normalizePath(pathname) === "/ws";
}

const nextProcess = spawn("node", ["server.js"], {
  env: { ...process.env, PORT: String(nextPort), HOSTNAME: "127.0.0.1" },
  stdio: "inherit",
});

nextProcess.on("exit", (code) => {
  console.error(`[proxy] Next.js exited with code ${code ?? 1}`);
  process.exit(code ?? 1);
});

const server = createServer((req, res) => {
  const parsed = parse(req.url || "", false);
  const pathname = parsed.pathname || "/";

  if (isApiPath(pathname)) {
    req.url = normalizePath(pathname) + (parsed.search || "");
    apiProxy.web(req, res, { target: apiBase });
    return;
  }

  nextProxy.web(req, res, { target: `http://127.0.0.1:${nextPort}` });
});

server.on("upgrade", (req, socket, head) => {
  const pathname = parse(req.url || "", false).pathname || "/";

  if (isWsPath(pathname)) {
    req.url = "/ws";
    apiProxy.ws(req, socket, head, { target: wsBase });
    return;
  }

  nextProxy.ws(req, socket, head, { target: `http://127.0.0.1:${nextPort}` });
});

server.listen(port, hostname, () => {
  console.log(`[proxy] Listening on http://${hostname}:${port} (Next.js → ${nextPort}, API → ${apiBase})`);
});

function shutdown(signal) {
  console.log(`[proxy] ${signal} received, shutting down`);
  server.close();
  nextProcess.kill(signal);
  process.exit(0);
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
