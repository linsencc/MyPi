/**
 * Serves web/dist on 127.0.0.1:4173 and proxies /api/* to GUNICORN_API (default 8765).
 * Used for pre-release smoke: production build + API on a worker process.
 * Usage: GUNICORN_API_PORT=8765 node prod_smoke_static.mjs
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../web/dist");
const API_PORT = Number(process.env.GUNICORN_API_PORT || "8765");
const LISTEN = Number(process.env.PROD_SMOKE_PORT || "4173");

function contentType(filePath) {
  const ext = path.extname(filePath);
  if (ext === ".html") return "text/html; charset=utf-8";
  if (ext === ".js") return "text/javascript; charset=utf-8";
  if (ext === ".css") return "text/css; charset=utf-8";
  if (ext === ".svg") return "image/svg+xml";
  if (ext === ".png") return "image/png";
  if (ext === ".ico") return "image/x-icon";
  return "application/octet-stream";
}

function sendFile(res, filePath) {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }
    res.writeHead(200, { "Content-Type": contentType(filePath) });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  const u = new URL(req.url || "/", "http://127.0.0.1");
  const p = u.pathname;

  if (p.startsWith("/api")) {
    const opts = {
      hostname: "127.0.0.1",
      port: API_PORT,
      path: u.pathname + u.search,
      method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${API_PORT}` },
    };
    const preq = http.request(opts, (pres) => {
      res.writeHead(pres.statusCode || 500, pres.headers);
      pres.pipe(res);
    });
    preq.on("error", (e) => {
      res.writeHead(502, { "Content-Type": "text/plain" });
      res.end(`proxy error: ${e.message}`);
    });
    req.pipe(preq);
    return;
  }

  let file = path.join(ROOT, p === "/" ? "index.html" : path.normalize(p));
  if (!file.startsWith(ROOT)) {
    res.writeHead(403);
    res.end();
    return;
  }
  fs.stat(file, (err, st) => {
    if (!err && st.isFile()) {
      sendFile(res, file);
      return;
    }
    sendFile(res, path.join(ROOT, "index.html"));
  });
});

server.listen(LISTEN, "127.0.0.1", () => {
  console.error(`prod_smoke_static: http://127.0.0.1:${LISTEN} -> dist + /api -> :${API_PORT}`);
});
