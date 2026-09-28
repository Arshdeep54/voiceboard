from dataclasses import dataclass
from pathlib import Path
import os
import tomllib


@dataclass(frozen=True)
class Config:
    host: str = "tailscale"
    port: int = 8787
    clipboard_only: bool = False
    qr: bool = True

    @classmethod
    def load(cls, path=None):
        config_path = Path(path or os.environ.get("VOICEBOARD_CONFIG", "~/.config/voiceboard/config.toml")).expanduser()
        if not config_path.exists():
            return cls()
        with config_path.open("rb") as config_file:
            values = tomllib.load(config_file).get("receiver", {})
        return cls(
            host=str(values.get("host", cls.host)),
            port=int(values.get("port", cls.port)),
            clipboard_only=bool(values.get("clipboard_only", cls.clipboard_only)),
            qr=bool(values.get("qr", cls.qr)),
        )
