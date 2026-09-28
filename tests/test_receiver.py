import json
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch
from voice_receiver.server import Handler, ThreadingHTTPServer

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

    def test_pwa_and_health_routes(self):
        for path, content_type in (("/app.js", "application/javascript"), ("/sw.js", "application/javascript"), ("/icon.svg", "image/svg+xml")):
            status, actual_type, body = self.get(path)
            self.assertEqual(status, 200)
            self.assertTrue(actual_type.startswith(content_type))
            self.assertTrue(body)
        status, _, manifest = self.get("/manifest.webmanifest?token=test-token")
        self.assertEqual(status, 200)
        self.assertIn(b"Voice Prompt", manifest)
        status, _, health = self.get("/api/health?token=test-token")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(health), {"ok": True})

if __name__ == "__main__":
    unittest.main()
