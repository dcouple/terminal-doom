// A static file server for the terminal-doom page.
//
// The game is a wasm build, so it cannot be loaded over file:// — chromium
// refuses to instantiate wasm and to XHR the wad from a file url. This serves
// the same directory over loopback instead, on an ephemeral port unless one is
// given, and prints the chosen port on stdout so the launcher can read it.
import { createServer } from "node:http";
import { appendFileSync, createReadStream, statSync, writeFileSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";

const root = resolve(process.argv[2] ?? ".");
const wanted = Number(process.argv[3] ?? 0);

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".wasm": "application/wasm",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".wad": "application/octet-stream",
  ".cfg": "text/plain; charset=utf-8",
};

// Capture mode drops two files here: the game's own audio, and the moment the
// recorder started, which is what the capture harness aligns the video against.
const captureDir = process.env.TERMINAL_DOOM_CAPTURE_DIR;

const server = createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");

  if (req.method === "POST" && captureDir) {
    if (url.pathname === "/__mark") {
      writeFileSync(join(captureDir, "audio-start"), String(Date.now() / 1000));
      res.writeHead(204).end();
      return;
    }
    if (url.pathname === "/__audio") {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => {
        appendFileSync(join(captureDir, "audio.webm"), Buffer.concat(chunks));
        res.writeHead(204).end();
      });
      return;
    }
  }
  const rel = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, "");
  const path = join(root, rel === "/" ? "/index.html" : rel);

  if (!path.startsWith(root)) {
    res.writeHead(403).end("forbidden");
    return;
  }

  let stat;
  try {
    stat = statSync(path);
  } catch {
    res.writeHead(404).end("not found");
    return;
  }
  if (!stat.isFile()) {
    res.writeHead(404).end("not found");
    return;
  }

  res.writeHead(200, {
    "content-type": TYPES[extname(path).toLowerCase()] ?? "application/octet-stream",
    "content-length": stat.size,
    // The wad and the wasm never change under a given install, but a stale
    // cached copy after an upgrade is worse than re-reading from loopback.
    "cache-control": "no-store",
  });
  createReadStream(path).pipe(res);
});

server.listen(wanted, "127.0.0.1", () => {
  process.stdout.write(`${server.address().port}\n`);
});
