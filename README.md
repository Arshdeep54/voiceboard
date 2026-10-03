# Voiceboard

Use an Android phone as a private voice/text input device for the currently
focused Linux application. Speech recognition happens in the phone browser;
the Linux side receives text and pastes it with `Ctrl+Shift+V`.

## Security model

The default listener binds only to the local Tailscale IPv4 address. Both
devices must be on the same tailnet. Each process start creates a fresh,
ephemeral pairing token. The token is never written to the config file and
prompts are not logged or stored.

Do not use `--host 0.0.0.0` on an untrusted network. Do not use router port
forwarding or Tailscale Funnel.

## Install

The quick local install links the CLI into `~/.local/bin`:

```sh
./install.sh
voiceboard
```

For a packaged install from a checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/voiceboard
```

The package declares its only runtime dependency, `qrcode`, for terminal QR
output. Linux input prerequisites are `xdotool` and `xclip` (or `xsel`).

## Use

```sh
voiceboard
voiceboard up
voiceboard down
voiceboard --port 8788
voiceboard down --port 8788
voiceboard --clipboard
voiceboard --no-qr
voiceboard --foreground
```

`voiceboard` (or `voiceboard up`) prints the phone URL and a terminal QR code,
then detaches into the background. You can close the terminal. Running it again
shows the existing session's link and QR without creating another receiver.
Use `voiceboard down` to stop it from any terminal. For a custom port or config,
pass the same `--port` or `--config` when stopping.

`--foreground` keeps it attached for debugging; `Ctrl+C` or `voiceboard down`
stops it. Private session files and logs live under `$XDG_RUNTIME_DIR/voiceboard`
(fallback: `~/.local/state/voiceboard`); startup prints the log path. Logs contain
errors and character counts, not received text. Shutdown is authenticated with
the session token. There is no automatic restart or start-at-login service.
Every new session creates a fresh link, so reopen it on your phone after restart.

Open the printed URL in Chrome on Android. The page supports browser speech
recognition where available, Android keyboard dictation as a fallback, editable
text, optional “Press Enter after sending,” PWA metadata, remembered URLs, and
Tailscale connection status.

Dictation shows live partial text as the browser returns it; words may change
as recognition corrects the phrase. Voiceboard keeps listening until you tap
Stop or Send. Android uses single-phrase cycles with live partials because
Chromium's native continuous mode can treat growing partials as separate final
phrases. Other browsers request continuous mode. When a recognition cycle ends,
the app restarts it and keeps each cycle's text separate to avoid cumulative
duplicates. Restarts can leave brief gaps or trigger the phone's recognition
sound. Sending waits for the last phrase, and recognition also stops on errors
or when you leave the page. Availability and latency depend on the browser's
speech service; this is not the same engine as keyboard dictation.

## Configuration

Copy `examples/config.example.toml` to `~/.config/voiceboard/config.toml`:

```toml
[receiver]
host = "tailscale"
port = 8787
clipboard_only = false
qr = true
```

Use `--config PATH` or `VOICEBOARD_CONFIG` for another config location.
CLI flags override config values. The pairing token is intentionally not a
configurable or persistent secret.

## HTTPS, microphone access, and PWA

Browser microphone access needs a secure HTTPS origin. A MagicDNS hostname
over plain HTTP is not enough. Expose the receiver through Tailscale Serve
HTTPS (replace the IP with your machine's Tailscale IP):

```sh
sudo tailscale serve --bg --https=443 http://100.111.242.101:8787
```

Restart `voiceboard` after configuring Serve. Startup detects the HTTPS route
that proxies to this receiver and uses its MagicDNS URL in both the link and
QR code. It keeps the fresh pairing token and remains tailnet-only. Chrome can
then request microphone permission and offer the full “Install app” prompt.

If no matching HTTPS route exists, Voiceboard prints its HTTP IP URL with a
microphone warning. Keyboard dictation and manual text input remain available.

## Development

### Landing page

The public landing page lives in `site/`. It uses plain HTML, CSS, and
JavaScript, with locally hosted fonts and no build step or runtime dependencies.
Its interactive demo is a browser-only preview; it does not connect to the
receiver, request microphone access, or send text over the network.

```sh
python3 -m http.server 4173 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:4173`. Deploy the contents of `site/` to any static
host (such as GitHub Pages, Cloudflare Pages, or Netlify). Keep this public
website separate from the private Tailscale receiver.

### Receiver

```sh
python3 -m py_compile voice_receiver/server.py
python3 -m unittest discover -s tests -p "test_*.py" -v
node tests/test_dictation.cjs
```

The JavaScript check tests core dictation behavior with simulated speech
results; it has no browser, UI/design checks, or package dependencies.

See `SECURITY.md`, `CONTRIBUTING.md`, and `LICENSE` before publishing changes.
