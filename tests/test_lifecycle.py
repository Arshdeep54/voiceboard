import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from http.client import HTTPConnection


class LifecycleTests(unittest.TestCase):
    def test_background_start_repeat_and_authenticated_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env = dict(os.environ, XDG_RUNTIME_DIR=directory)
            command = [sys.executable, "-m", "voice_receiver.server", "--host", "127.0.0.1", "--port", str(port), "--no-qr"]
            def run(action="up"):
                return subprocess.run(command + [action], env=env, capture_output=True, text=True, timeout=10)
            try:
                started = run()
                self.assertEqual(started.returncode, 0, started.stderr)
                state_path = Path(directory) / "voiceboard" / f"{port}.json"
                state = json.loads(state_path.read_text())
                self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)
                self.assertIn(state["url"], started.stdout)
                repeated = run()
                self.assertEqual(repeated.returncode, 0, repeated.stderr)
                self.assertIn(state["url"], repeated.stdout)
                self.assertEqual(json.loads(state_path.read_text()), state)
                conn = HTTPConnection("127.0.0.1", port, timeout=2)
                conn.request("POST", "/api/shutdown", json.dumps({"token": "wrong"}))
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                conn.close()
                stopped = run("down")
                self.assertEqual(stopped.returncode, 0, stopped.stderr)
                self.assertFalse(state_path.exists())
                self.assertEqual(run("down").returncode, 0)
            finally:
                run("down")


if __name__ == "__main__":
    unittest.main()
