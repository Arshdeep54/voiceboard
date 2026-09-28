import tempfile
import unittest
from pathlib import Path

from voice_receiver.config import Config


class ConfigTests(unittest.TestCase):
    def test_defaults_are_tailscale_only_and_non_secret(self):
        config = Config.load("/path/that/does/not/exist")
        self.assertEqual(config.host, "tailscale")
        self.assertEqual(config.port, 8787)
        self.assertTrue(config.qr)

    def test_toml_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[receiver]\nhost = "127.0.0.1"\nport = 9999\nclipboard_only = true\nqr = false\n')
            config = Config.load(path)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 9999)
        self.assertTrue(config.clipboard_only)
        self.assertFalse(config.qr)
