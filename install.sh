#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime="${HOME}/.local/share/voiceboard/venv"
mkdir -p "$HOME/.local/bin"
python3 -m venv "$runtime"
"$runtime/bin/python" -m pip install --quiet --upgrade "$root"
ln -sfn "$runtime/bin/voiceboard" "$HOME/.local/bin/voiceboard"
missing=""
for command_name in python3 xclip xdotool; do
  command -v "$command_name" >/dev/null 2>&1 || missing="$missing $command_name"
done
if [ -n "$missing" ]; then
  echo "Missing:$missing"
  echo "Install with: sudo apt install python3 xclip xdotool"
  exit 1
fi
echo "Installed voiceboard at $HOME/.local/bin/voiceboard"
echo "Runtime environment: $runtime"
echo "Run: voiceboard"
