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
voiceboard --port 8788
voiceboard --clipboard
voiceboard --no-qr
```

Startup prints the Tailscale URL and a compact terminal QR code. If the port is
already occupied, a second invocation prints the active URL and QR code rather
than a traceback. Stop the active process with `Ctrl+C` in its original
terminal.

Open the printed URL in Chrome on Android. The page supports browser speech
recognition where available, Android keyboard dictation as a fallback, editable
text, optional “Press Enter after sending,” PWA metadata, remembered URLs, and
Tailscale connection status.

The phone app uses one finalized speech phrase per microphone session. Tap the
microphone again to add another phrase; this avoids cumulative-result bugs in
Android Chrome speech recognition.

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

## HTTPS/PWA

For Chrome’s full “Install app” prompt, expose the receiver through Tailscale
Serve HTTPS:

```sh
sudo tailscale serve --bg --https=443 http://100.111.242.101:8787
```

Then use the machine’s HTTPS MagicDNS URL. The HTTP Tailscale IP still works as
a home-screen shortcut on Android browsers that allow it.

## Development

```sh
python3 -m py_compile voice_receiver/server.py
python3 -m unittest discover -s tests -p "test_*.py" -v
```

See `SECURITY.md`, `CONTRIBUTING.md`, and `LICENSE` before publishing changes.
