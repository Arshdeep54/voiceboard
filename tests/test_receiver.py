import json
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch
from voice_receiver import server as receiver
from voice_receiver.server import Handler, ThreadingHTTPServer

class PairingUrlTests(unittest.TestCase):
    def serve_config(self, proxy="http://100.111.242.101:8787", port="443", https=True):
        return json.dumps({
            "TCP": {port: {"HTTPS": https}},
            "Web": {f"lappy.example.ts.net:{port}": {"Handlers": {"/": {"Proxy": proxy}}}},
        })

    @patch("voice_receiver.server.subprocess.check_output")
    def test_matching_serve_route_uses_https(self, check_output):
        check_output.return_value = self.serve_config()
        self.assertEqual(receiver.pairing_url("100.111.242.101", 8787, "pair-token"), "https://lappy.example.ts.net/?token=pair-token")

    @patch("voice_receiver.server.subprocess.check_output")
    def test_custom_https_port_is_preserved(self, check_output):
        check_output.return_value = self.serve_config(port="8443")
        self.assertEqual(receiver.pairing_url("100.111.242.101", 8787, "pair-token"), "https://lappy.example.ts.net:8443/?token=pair-token")

    @patch("voice_receiver.server.subprocess.check_output")
    def test_unrelated_or_insecure_route_keeps_receiver_url(self, check_output):
        for config in (self.serve_config(proxy="http://127.0.0.1:3000"), self.serve_config(https=False), "{}", "null"):
            with self.subTest(config=config):
                check_output.return_value = config
                self.assertEqual(receiver.pairing_url("100.111.242.101", 8787, "pair-token"), "http://100.111.242.101:8787/?token=pair-token")

    @patch("voice_receiver.server.subprocess.check_output")
    def test_missing_tailscale_cli_keeps_receiver_url(self, check_output):
        check_output.side_effect = FileNotFoundError()
        self.assertEqual(receiver.pairing_url("127.0.0.1", 8787, "pair-token"), "http://127.0.0.1:8787/?token=pair-token")

class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.token = "test-token"
        self.server.clipboard_only = True
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
    def post(self, payload):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request("POST", "/api/send", json.dumps(payload), {"Content-Type": "application/json"})
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    def get(self, path):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type", ""), response.read()
    def test_bad_token_rejected(self):
        self.assertEqual(self.post({"token": "wrong", "text": "hello"})[0], 403)
    @patch("voice_receiver.server.inject")
    def test_unicode_multiline(self, inject):
        value = "Rust → PostgreSQL\nRocksDB, gRPC, Kubernetes, OpenTelemetry, Mastra"
        self.assertEqual(self.post({"token": "test-token", "text": value}), (200, {"ok": True}))
        inject.assert_called_once_with(value, True, False)

    @patch("voice_receiver.server.inject")
    def test_submit_option_is_forwarded(self, inject):
        self.assertEqual(self.post({"token": "test-token", "text": "submit", "submit": True}), (200, {"ok": True}))
        inject.assert_called_once_with("submit", True, True)

    def test_health_and_pairing_token(self):
        status, _, health = self.get("/api/health?token=test-token")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(health), {"ok": True})
        self.assertEqual(self.get("/api/health?token=wrong")[0], 403)
        self.assertEqual(self.get("/?token=wrong")[0], 403)
        self.assertEqual(self.get("/fonts/../../config.py")[0], 404)

if __name__ == "__main__":
    unittest.main()
