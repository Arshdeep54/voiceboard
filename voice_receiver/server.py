#!/usr/bin/env python3
import argparse
import errno
import os
import json
import secrets
import shutil
import socket
import subprocess
import signal
import sys
import threading
import time
from pathlib import Path
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from .config import Config

MAX_BYTES = 1024 * 1024
STATIC_DIR = Path(__file__).with_name("static")

def local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))
        address = sock.getsockname()[0]
        sock.close()
        return address
    except OSError:
        return "127.0.0.1"

def tailscale_ip():
    try:
        output = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "dev", "tailscale0"],
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        raise RuntimeError("Tailscale interface tailscale0 is not available")
    for field in output.split():
        if field.count(".") == 3 and "/" in field:
            return field.split("/", 1)[0]
    raise RuntimeError("No IPv4 address found on tailscale0")

def pairing_url(host, port, token):
    backend = f"http://{host}:{port}"
    try:
        config = json.loads(subprocess.check_output(
            ["tailscale", "serve", "status", "--json"],
            text=True, stderr=subprocess.DEVNULL, timeout=3,
        )) or {}
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return f"{backend}/?token={token}"
    for address, site in config.get("Web", {}).items():
        hostname, https_port = address.rsplit(":", 1)
        proxy = site.get("Handlers", {}).get("/", {}).get("Proxy", "")
        if config.get("TCP", {}).get(https_port, {}).get("HTTPS") and proxy.rstrip("/") == backend:
            origin = hostname if https_port == "443" else address
            return f"https://{origin}/?token={token}"
    return f"{backend}/?token={token}"

def copy_clipboard(text):
    if shutil.which("xclip"):
        command = ["xclip", "-selection", "clipboard"]
    elif shutil.which("xsel"):
        command = ["xsel", "--clipboard", "--input"]
    else:
        raise RuntimeError("xclip or xsel is required")
    subprocess.run(command, input=text.encode("utf-8"), check=True)

def inject(text, clipboard_only, submit=False):
    copy_clipboard(text)
    if not clipboard_only:
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+shift+v"], check=True)
        if submit:
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True)

def print_qr(value):
    try:
        import qrcode
    except ImportError:
        print("QR output requires the optional 'qrcode' package: python3 -m pip install --user qrcode")
        return
    code = qrcode.QRCode(border=1)
    code.add_data(value)
    code.make(fit=True)
    print("\nScan this QR code:\n", flush=True)
    matrix = code.get_matrix()
    for y in range(0, len(matrix), 2):
        top = matrix[y]
        bottom = matrix[y + 1] if y + 1 < len(matrix) else [False] * len(top)
        line = []
        for upper, lower in zip(top, bottom):
            line.append("█" if upper and lower else "▀" if upper else "▄" if lower else " ")
        print("".join(line), flush=True)

def manifest(token):
    return json.dumps({
        "name": "Voiceboard",
        "short_name": "Voiceboard",
        "id": f"/?token={token}",
        "start_url": f"/?token={token}",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f4f8f2",
        "theme_color": "#f4f8f2",
        "icons": [{"src": "/icon.svg?v=2", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    }).encode()

def app_script():
    return b'''(() => {
const savedKey = "voice-receiver-url";
const savedUrl = localStorage.getItem(savedKey);
if (location.search) localStorage.setItem(savedKey, location.href);
const main = document.querySelector("main");
const status = document.querySelector("#status");
const connection = document.querySelector("#connection");
const install = document.createElement("button");
install.textContent = "Install app";
install.hidden = true;
install.className = "secondary-button";
main.insertBefore(install, status);
let deferredInstall;
window.addEventListener("beforeinstallprompt", event => { event.preventDefault(); deferredInstall = event; install.hidden = false; });
install.onclick = async () => { if (!deferredInstall) return; deferredInstall.prompt(); await deferredInstall.userChoice; deferredInstall = null; install.hidden = true; };
function checkConnection() {
  if (!navigator.onLine) { connection.textContent = "Offline"; connection.classList.add("error"); return; }
  fetch("/api/health" + location.search, { cache: "no-store" }).then(response => {
    if (!response.ok) throw Error();
    connection.textContent = "Connected"; connection.classList.remove("error");
  }).catch(() => { connection.textContent = "Check Tailscale"; connection.classList.add("error"); });
}
window.addEventListener("online", checkConnection);
window.addEventListener("offline", checkConnection);
checkConnection();
setInterval(checkConnection, 10000);
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("/sw.js").catch(() => {});
if (!location.search && savedUrl && savedUrl.startsWith(location.origin)) {
  const reconnect = document.createElement("button");
  reconnect.textContent = "Reconnect to saved receiver";
  reconnect.className = "secondary-button";
  reconnect.onclick = () => { location.href = savedUrl; };
  main.insertBefore(reconnect, status);
}
if (!window.isSecureContext) {
  connection.title = "Chrome may offer Add to Home screen, but full PWA installation needs HTTPS.";
}
})();'''

def service_worker():
    return b'''const CACHE = "voiceboard-shell-v2";
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(["/icon.svg?v=2"]))));
self.addEventListener("activate", event => event.waitUntil(caches.delete("voice-prompt-shell-v1").then(() => self.clients.claim())));
self.addEventListener("fetch", event => { if (event.request.method === "GET" && new URL(event.request.url).pathname === "/icon.svg") event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request))); });'''

def icon_svg():
    return b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#193b2d"/><path d="M14 26v12m9-21v30m9-38v46m9-38v30m9-21v12" fill="none" stroke="#d0ecae" stroke-width="5" stroke-linecap="round"/></svg>'''

def legacy_page(token):
    return page(token)

def page(token):
    config = json.dumps(token)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#f4f8f2"><title>Voiceboard — Your voice keyboard</title>
<link rel="preload" href="/fonts/outfit.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/phone.css"></head><body><main>
<header class="app-header"><h1 class="brand"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 13v6M10.5 8v16M16 3v26M21.5 8v16M27 13v6" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/></svg>voiceboard</h1><div id="connection" class="connection" role="status">Connecting…</div></header>
<div class="recorder"><button id="mic" class="mic" type="button" aria-label="Start dictation" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/></svg></button><p id="hint">Tap to speak</p></div>
<div class="composer"><textarea id="text" aria-label="Your text" placeholder="Your words appear here…" rows="6"></textarea><label class="submit-option"><input id="submit" type="checkbox"><span>Enter after sending</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 5v9H5m5-5-5 5 5 5"/></svg></label><button id="send" class="send" type="button">Send<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6"/></svg></button></div>
<div id="status" class="status" role="status" aria-live="polite"></div>
</main><script>const token={config};</script><script src="/receiver.js"></script></body></html>'''.encode()

class Handler(BaseHTTPRequestHandler):
    server_version = "Voiceboard/1.0"
    def log_message(self, *_):
        pass
    def send_json(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def send_bytes(self, content_type, body):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        parsed = urlparse(self.path)
        assets = {
            "/phone.css": ("text/css; charset=utf-8", "phone.css"),
            "/receiver.js": ("application/javascript; charset=utf-8", "receiver.js"),
            "/fonts/outfit.woff2": ("font/woff2", "fonts/outfit.woff2"),
            "/fonts/dm-sans.woff2": ("font/woff2", "fonts/dm-sans.woff2"),
        }
        if parsed.path in assets:
            content_type, filename = assets[parsed.path]
            return self.send_bytes(content_type, (STATIC_DIR / filename).read_bytes())
        if parsed.path == "/app.js":
            return self.send_bytes("application/javascript; charset=utf-8", app_script())
        if parsed.path == "/sw.js":
            return self.send_bytes("application/javascript; charset=utf-8", service_worker())
        if parsed.path == "/icon.svg":
            return self.send_bytes("image/svg+xml", icon_svg())
        token = parse_qs(parsed.query).get("token", [""])[0]
        if parsed.path == "/manifest.webmanifest":
            if not secrets.compare_digest(token, self.server.token):
                return self.send_error(403, "Invalid pairing token")
            return self.send_bytes("application/manifest+json", manifest(self.server.token))
        if parsed.path == "/api/health":
            if not secrets.compare_digest(token, self.server.token):
                return self.send_json(403, {"error": "Invalid pairing token"})
            return self.send_json(200, {"ok": True})
        if parsed.path != "/":
            return self.send_error(404)
        if not secrets.compare_digest(token, self.server.token):
            return self.send_error(403, "Invalid pairing token")
        body = page(self.server.token)
        manifest_link = f'<link rel="manifest" href="/manifest.webmanifest?token={self.server.token}"><link rel="icon" href="/icon.svg?v=2">'.encode()
        app_script_tag = f'<script src="/app.js?token={self.server.token}"></script>'.encode()
        body = body.replace(b"</head>", manifest_link + b"</head>")
        body = body.replace(b"</body>", app_script_tag + b"</body>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        if self.path not in ("/api/send", "/api/shutdown"):
            return self.send_json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BYTES:
                raise ValueError("Request is empty or too large")
            data = json.loads(self.rfile.read(length))
            if not secrets.compare_digest(str(data.get("token", "")), self.server.token):
                return self.send_json(403, {"error": "Invalid pairing token"})
            if self.path == "/api/shutdown":
                self.send_json(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Text must not be empty")
            if len(text.encode("utf-8")) > MAX_BYTES:
                raise ValueError("Text is too large")
            inject(text, self.server.clipboard_only, bool(data.get("submit", False)))
            print(f"Received text ({len(text)} characters)", flush=True)
            self.send_json(200, {"ok": True})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            self.send_json(500, {"error": f"Could not inject text: {error}"})

def receiver_request(state, shutdown=False):
    address = urlparse(state["local_url"])
    token = parse_qs(address.query)["token"][0]
    connection = HTTPConnection(address.hostname, address.port, timeout=2)
    try:
        if shutdown:
            connection.request("POST", "/api/shutdown", json.dumps({"token": token}), {"Content-Type": "application/json"})
        else:
            connection.request("GET", f"/api/health?token={token}")
        response = connection.getresponse()
        response.read()
        return response.status == 200
    finally:
        connection.close()

def show_pairing(url, qr):
    print(f"Voiceboard\n\nPhone: {url}", flush=True)
    if url.startswith("http://"):
        print("Browser microphone access needs HTTPS. Set up Tailscale Serve, then restart voiceboard.", flush=True)
    if qr:
        print_qr(url)

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=("up", "down"), default="up")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--host", help="Override the config host; default is Tailscale-only")
    parser.add_argument("--port", type=int, help="Override the config port")
    parser.add_argument("--clipboard", action="store_true", default=None, help="Copy without pasting")
    parser.add_argument("--no-qr", action="store_true", help="Do not print a terminal QR code")
    parser.add_argument("--foreground", action="store_true", help="Stay attached to this terminal")
    args = parser.parse_args(argv)
    config = Config.load(args.config)
    port = args.port if args.port is not None else config.port
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".local/state"))) / "voiceboard"
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    runtime.chmod(0o700)
    state_path = runtime / f"{port}.json"
    try:
        current = json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        current = None
    if args.command == "down":
        if current is None:
            print("Voiceboard is not running.")
            return
        try:
            if not receiver_request(current, shutdown=True):
                raise RuntimeError("The saved pairing token was rejected; no process was stopped")
            deadline = time.monotonic() + 5
            while state_path.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            if state_path.exists():
                raise RuntimeError("Voiceboard did not finish stopping")
        except (OSError, RuntimeError) as error:
            print(f"Could not stop Voiceboard: {error}", file=sys.stderr)
            raise SystemExit(1)
        print("Voiceboard stopped.")
        return
    configured_host = args.host or config.host
    host = tailscale_ip() if configured_host == "tailscale" else configured_host
    clipboard_only = config.clipboard_only if args.clipboard is None else args.clipboard
    qr = config.qr and not args.no_qr
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            try:
                if current and receiver_request(current):
                    print(f"Voiceboard is already running on port {port}.")
                    show_pairing(current["url"], qr)
                    print("Stop with: voiceboard down" + (f" --port {port}" if port != 8787 else ""))
                    return
            except OSError:
                pass
            print(f"Port {port} is occupied, but no matching Voiceboard session was found. Stop the old foreground receiver or choose another port.", file=sys.stderr)
            raise SystemExit(1)
        raise
    server.token = secrets.token_urlsafe(12)
    server.clipboard_only = clipboard_only
    url = pairing_url(host, server.server_port, server.token)
    state = {"url": url, "local_url": f"http://{host}:{server.server_port}/?token={server.token}"}
    with os.fdopen(os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as state_file:
        json.dump(state, state_file)
    show_pairing(url, qr)
    if not args.foreground:
        log_path = runtime / f"{port}.log"
        log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        stdin_fd = os.open(os.devnull, os.O_RDONLY)
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            pid = os.fork()
        except OSError:
            state_path.unlink(missing_ok=True)
            server.server_close()
            os.close(log_fd)
            os.close(stdin_fd)
            raise
        if pid:
            server.server_close()
            os.close(log_fd)
            os.close(stdin_fd)
            print(f"Running in background. Log: {log_path}")
            print("Stop with: voiceboard down" + (f" --port {port}" if port != 8787 else ""))
            return
        os.setsid()
        os.dup2(stdin_fd, 0)
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
        os.close(stdin_fd)
        os.close(log_fd)
    def stop_signal(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_signal)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        state_path.unlink(missing_ok=True)
        server.server_close()

if __name__ == "__main__":
    main()
