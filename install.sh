#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime="${HOME}/.local/share/voice-prompt-receiver/venv"
mkdir -p "$HOME/.local/bin"
python3 -m venv "$runtime"
"$runtime/bin/python" -m pip install --quiet --upgrade "$root"
chmod +x "$root/bin/voice-receiver"
ln -sfn "$root/bin/voice-receiver" "$HOME/.local/bin/voice-receiver"
missing=""
for command_name in python3 xclip xdotool; do
  command -v "$command_name" >/dev/null 2>&1 || missing="$missing $command_name"
done
if [ -n "$missing" ]; then
  echo "Missing:$missing"
  echo "Install with: sudo apt install python3 xclip xdotool"
  exit 1
fi
echo "Installed voice-receiver at $HOME/.local/bin/voice-receiver"
echo "Runtime environment: $runtime"
echo "Run: voice-receiver"
