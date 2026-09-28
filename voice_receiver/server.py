#!/usr/bin/env python3
import argparse
import errno
import os
import json
import secrets
import shutil
import socket
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from .config import Config

MAX_BYTES = 1024 * 1024

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
        "name": "Voice Prompt",
        "short_name": "Voice Prompt",
        "id": f"/?token={token}",
        "start_url": f"/?token={token}",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f3efe8",
        "theme_color": "#17202a",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    }).encode()

def app_script():
    return b'''(() => {
const savedKey = "voice-receiver-url";
const savedUrl = localStorage.getItem(savedKey);
if (location.search) localStorage.setItem(savedKey, location.href);
const main = document.querySelector("main");
const status = document.querySelector("#status");
const connection = document.createElement("div");
connection.style.cssText = "margin:12px 0 0;font-size:13px;color:#667078";
main.insertBefore(connection, status);
const install = document.createElement("button");
install.textContent = "Install app";
install.hidden = true;
install.style.cssText = "margin-top:12px;border:1px solid #cfc8bc;border-radius:10px;padding:9px 12px;background:#fffdf9;color:#17202a;font-weight:600";
main.insertBefore(install, status);
let deferredInstall;
window.addEventListener("beforeinstallprompt", event => { event.preventDefault(); deferredInstall = event; install.hidden = false; });
install.onclick = async () => { if (!deferredInstall) return; deferredInstall.prompt(); await deferredInstall.userChoice; deferredInstall = null; install.hidden = true; };
function checkConnection() {
  if (!navigator.onLine) { connection.textContent = "Offline - reconnect Tailscale"; connection.style.color = "#b33b2e"; return; }
  fetch("/api/health" + location.search, { cache: "no-store" }).then(response => {
    if (!response.ok) throw Error();
    connection.textContent = "Connected via Tailscale"; connection.style.color = "#277c70";
  }).catch(() => { connection.textContent = "Receiver unreachable - check Tailscale"; connection.style.color = "#b33b2e"; });
}
window.addEventListener("online", checkConnection);
window.addEventListener("offline", checkConnection);
checkConnection();
setInterval(checkConnection, 10000);
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("/sw.js").catch(() => {});
if (!location.search && savedUrl && savedUrl.startsWith(location.origin)) {
  const reconnect = document.createElement("button");
  reconnect.textContent = "Reconnect to saved receiver";
  reconnect.style.cssText = install.style.cssText;
  reconnect.onclick = () => { location.href = savedUrl; };
  main.insertBefore(reconnect, status);
}
if (!window.isSecureContext) {
  connection.title = "Chrome may offer Add to Home screen, but full PWA installation needs HTTPS.";
}
})();'''

def service_worker():
    return b'''const CACHE = "voice-prompt-shell-v1";
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(["/icon.svg"]))));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", event => { if (event.request.method === "GET" && new URL(event.request.url).pathname === "/icon.svg") event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request))); });'''

def icon_svg():
    return b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="112" fill="#17202a"/><circle cx="256" cy="238" r="112" fill="#df5c3c"/><path d="M256 148c-35 0-64 29-64 64v52c0 35 29 64 64 64s64-29 64-64v-52c0-35-29-64-64-64Zm0 232c-63 0-114-51-114-114h32c0 45 37 82 82 82s82-37 82-82h32c0 63-51 114-114 114Zm-16 0h32v54h-32z" fill="#fff"/></svg>'''

def legacy_page(token):
    config = json.dumps(token)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Voice Prompt</title>
<style>*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:#f3efe8;color:#17202a;font:16px system-ui;display:grid;place-items:center;padding:20px}}main{{width:min(100%,430px);background:#fffdf9;border:1px solid #ded8ce;border-radius:24px;padding:28px 22px;box-shadow:0 16px 45px #28231c18;text-align:center}}h1{{margin:0 0 24px}}.mic{{width:104px;height:104px;border:0;border-radius:50%;background:#df5c3c;color:#fff;font-size:42px;box-shadow:0 8px #b53f27;margin:4px 0 20px}}.listening{{background:#277c70!important;transform:translateY(4px);box-shadow:0 4px #1d5a52!important}}p{{color:#667078}}textarea{{width:100%;min-height:170px;border:1px solid #cfc8bc;border-radius:14px;padding:14px;font:16px monospace}}.send{{width:100%;margin-top:16px;border:0;border-radius:12px;padding:14px;background:#17202a;color:#fff;font-size:17px;font-weight:700}}.status{{min-height:24px;margin-top:16px;font-size:14px;color:#667078}}.ok{{color:#277c70}}.error{{color:#b33b2e}}</style></head>
<body><main><h1>Voice Prompt</h1><button id="mic" class="mic">🎙</button><p id="hint">Tap to speak, then review your text</p><textarea id="text" placeholder="Transcribed text..."></textarea><label><input id="submit" type="checkbox"> Press Enter after sending</label><button id="send" class="send">Send</button><div id="status" class="status">Connected</div></main>
<script>
const token={config},mic=document.querySelector("#mic"),text=document.querySelector("#text"),send=document.querySelector("#send"),status=document.querySelector("#status"),hint=document.querySelector("#hint");const SR=window.SpeechRecognition||window.webkitSpeechRecognition;let rec,listening=false;function msg(s,c=""){{status.textContent=s;status.className="status "+c}}if(SR){{rec=new SR;rec.continuous=true;rec.interimResults=true;rec.lang=navigator.language||"en-US";rec.onstart=()=>{{listening=true;mic.classList.add("listening");hint.textContent="Listening… tap again to stop";msg("Listening")}};rec.onend=()=>{{listening=false;mic.classList.remove("listening");hint.textContent="Tap to speak, then review your text";if(!status.classList.contains("error"))msg("Ready")}};rec.onerror=e=>msg("Speech recognition: "+e.error,"error");rec.onresult=e=>{{let f="",i="";for(let n=e.resultIndex;n<e.results.length;n++)e.results[n].isFinal?f+=e.results[n][0].transcript:i+=e.results[n][0].transcript;if(f)text.value+=(text.value?" ":"")+f;hint.textContent=i||"Tap again when finished"}};mic.onclick=()=>listening?rec.stop():rec.start()}}else{{mic.onclick=()=>{{text.focus();msg("Speech recognition unavailable — use keyboard microphone/dictation","error")}};hint.textContent="Use keyboard microphone, then edit the text"}}send.onclick=async()=>{{if(!text.value.trim())return msg("Enter or dictate some text first","error");send.disabled=true;msg("Sending…");try{{let r=await fetch("/api/send",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{token,text:text.value}})}}),d=await r.json();if(!r.ok)throw Error(d.error||"Send failed");text.value="";msg("Sent to the focused application","ok")}}catch(e){{msg(e.message,"error")}}finally{{send.disabled=false}}}};
</script><script>const nativeFetch=window.fetch;window.fetch=(url,options)=>{{if(url==="/api/send"&&options&&options.body){{const payload=JSON.parse(options.body);payload.submit=document.querySelector("#submit").checked;options.body=JSON.stringify(payload)}}return nativeFetch(url,options)}};</script></body></html>""".encode()

def page(token):
    config = json.dumps(token)
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Voice Prompt</title><style>*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:#f3efe8;color:#17202a;font:16px system-ui,sans-serif;display:grid;place-items:center;padding:20px}}main{{width:min(100%,430px);background:#fffdf9;border:1px solid #ded8ce;border-radius:24px;padding:28px 22px;box-shadow:0 16px 45px #28231c18;text-align:center}}h1{{margin:0 0 24px}}.mic{{width:104px;height:104px;border:0;border-radius:50%;background:#df5c3c;color:#fff;font-size:42px;box-shadow:0 8px #b53f27;margin:4px 0 20px}}.listening{{background:#277c70!important;transform:translateY(4px);box-shadow:0 4px #1d5a52!important}}p{{color:#667078}}textarea{{width:100%;min-height:170px;border:1px solid #cfc8bc;border-radius:14px;padding:14px;font:16px monospace}}label{{display:block;margin-top:14px;color:#667078;font-size:14px}}.send{{width:100%;margin-top:16px;border:0;border-radius:12px;padding:14px;background:#17202a;color:#fff;font-size:17px;font-weight:700}}.status{{min-height:24px;margin-top:16px;font-size:14px;color:#667078}}.ok{{color:#277c70}}.error{{color:#b33b2e}}</style></head><body><main><h1>Voice Prompt</h1><button id="mic" class="mic">🎙</button><p id="hint">Tap to speak, then review your text</p><textarea id="text" placeholder="Transcribed text..."></textarea><label><input id="submit" type="checkbox"> Press Enter after sending</label><button id="send" class="send">Send</button><div id="status" class="status">Connected</div></main><script>
const token={config},mic=document.querySelector("#mic"),text=document.querySelector("#text"),send=document.querySelector("#send"),status=document.querySelector("#status"),hint=document.querySelector("#hint"),submit=document.querySelector("#submit");const SR=window.SpeechRecognition||window.webkitSpeechRecognition;let rec,listening=false,committed="";function msg(s,c=""){{status.textContent=s;status.className="status "+c}}if(SR){{rec=new SR;rec.continuous=true;rec.interimResults=true;rec.lang=navigator.language||"en-US";rec.onstart=()=>{{listening=true;committed=text.value;mic.classList.add("listening");hint.textContent="Listening… tap again to stop";msg("Listening")}};rec.onend=()=>{{listening=false;committed=text.value;mic.classList.remove("listening");hint.textContent="Tap to speak, then review your text";if(!status.classList.contains("error"))msg("Ready")}};rec.onerror=e=>msg("Speech recognition: "+e.error,"error");rec.onresult=e=>{{let finals="",interim="";for(let n=0;n<e.results.length;n++){{const phrase=e.results[n][0].transcript;if(e.results[n].isFinal)finals+=phrase;else interim+=phrase}}if(finals){{if(!committed)committed=finals;else if(finals.startsWith(committed))committed=finals;else if(!committed.endsWith(finals))committed+=(committed?" ":"")+finals}}text.value=committed+(interim?(committed?" ":"")+interim:"");hint.textContent=interim||"Tap again when finished"}};mic.onclick=()=>{{if(listening)rec.stop();else{{try{{rec.start()}}catch(e){{}}}}}}}}else{{mic.onclick=()=>{{text.focus();msg("Speech recognition unavailable - use keyboard microphone/dictation","error")}};hint.textContent="Use keyboard microphone, then edit the text"}}send.onclick=async()=>{{if(!text.value.trim())return msg("Enter or dictate some text first","error");send.disabled=true;msg("Sending…");try{{let r=await fetch("/api/send",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{token,text:text.value,submit:submit.checked}})}}),d=await r.json();if(!r.ok)throw Error(d.error||"Send failed");text.value="";committed="";msg("Sent to the focused application","ok")}}catch(e){{msg(e.message,"error")}}finally{{send.disabled=false}}}};</script></body></html>'''.encode()

class Handler(BaseHTTPRequestHandler):
    server_version = "VoiceReceiver/1.0"
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
        body = body.replace(b"rec.continuous=true;rec.interimResults=true;", b"rec.continuous=false;rec.interimResults=false;")
        manifest_link = f'<link rel="manifest" href="/manifest.webmanifest?token={self.server.token}"><link rel="icon" href="/icon.svg">'.encode()
        app_script_tag = f'<script src="/app.js?token={self.server.token}"></script>'.encode()
        body = body.replace(b"</head>", manifest_link + b"</head>")
        body = body.replace(b"</body>", app_script_tag + b"</body>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        if self.path != "/api/send":
            return self.send_json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BYTES:
                raise ValueError("Request is empty or too large")
            data = json.loads(self.rfile.read(length))
            if not secrets.compare_digest(str(data.get("token", "")), self.server.token):
                return self.send_json(403, {"error": "Invalid pairing token"})
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

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--host", help="Override the config host; default is Tailscale-only")
    parser.add_argument("--port", type=int, help="Override the config port")
    parser.add_argument("--clipboard", action="store_true", default=None, help="Copy without pasting")
    parser.add_argument("--no-qr", action="store_true", help="Do not print a terminal QR code")
    args = parser.parse_args(argv)
    config = Config.load(args.config)
    configured_host = args.host or config.host
    host = tailscale_ip() if configured_host == "tailscale" else configured_host
    port = args.port or config.port
    clipboard_only = config.clipboard_only if args.clipboard is None else args.clipboard
    state_path = f"/tmp/voice-receiver-{port}.url"
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            try:
                current_url = open(state_path, encoding="utf-8").read().strip()
            except OSError:
                current_url = ""
            print(f"Voice Receiver is already running on {host}:{port}.")
            if current_url:
                print(f"Current phone URL: {current_url}")
                print_qr(current_url)
            else:
                print("The current phone URL is not available from this shell.")
            print("Use the existing receiver, or stop it with Ctrl+C in its original terminal before starting again.")
            raise SystemExit(1)
        raise
    server.token = secrets.token_urlsafe(12)
    server.clipboard_only = clipboard_only
    url = f"http://{host}:{server.server_port}/?token={server.token}"
    print(f"Voice Receiver\n\nPhone: {url}\n\nWaiting for connection...", flush=True)
    if config.qr and not args.no_qr:
        print_qr(url)
    try:
        with open(state_path, "w", encoding="utf-8") as state:
            state.write(url + "\n")
        os.chmod(state_path, 0o600)
    except OSError:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
        try:
            os.unlink(state_path)
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    main()
