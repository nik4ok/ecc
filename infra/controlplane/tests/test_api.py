#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("NOVA_PROVISION_MODE", "local")


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        cls._db = tmp.name
        os.environ["NOVA_CONTROL_DB"] = cls._db
        import importlib

        import server as server_mod

        importlib.reload(server_mod)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_mod.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        os.unlink(cls._db)

    def _json(self, method: str, path: str, payload: dict | None = None, expected: int = 200):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(resp.status, expected)
                return body
        except urllib.error.HTTPError as err:
            body = json.loads(err.read().decode("utf-8"))
            self.assertEqual(err.code, expected)
            return body

    def test_overview_contains_reserved_rooms(self) -> None:
        body = self._json("GET", "/api/v1/overview")
        self.assertTrue(body["success"])
        emails = {u["email"] for u in body["data"]["users"]}
        self.assertIn("nova-test@device.local", emails)
        self.assertEqual(body["data"]["node"]["endpoint_host"], "89.19.217.190")

    def test_register_assigns_room_three(self) -> None:
        key = "qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqo="
        # 32 bytes of 0xAA
        import base64

        key = base64.b64encode(b"\xaa" * 32).decode("ascii")
        body = self._json(
            "POST",
            "/api/v1/register",
            {
                "email": "api-guest@example.com",
                "display_name": "API guest",
                "public_key": key,
            },
            expected=201,
        )
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["client_address"], "10.8.1.3/32")
        self.assertEqual(body["data"]["endpoint_port"], 39783)
        self.assertNotIn("client_private_key", body["data"])

    def test_dashboard_html_served(self) -> None:
        req = urllib.request.Request(self.base + "/")
        with urllib.request.urlopen(req, timeout=3) as resp:
            html = resp.read().decode("utf-8")
        self.assertIn("Добавить устройство", html)
        self.assertNotIn("Касса клуба", html)
        self.assertIn("/api/v1/register", html)
        self.assertIn("Подключений", html)
        self.assertIn("Первое", html)
        self.assertIn("Всего", html)

    def test_overview_users_include_usage_fields(self) -> None:
        body = self._json("GET", "/api/v1/overview")
        user = body["data"]["users"][0]
        self.assertIn("connect_count", user)
        self.assertIn("first_connected_at", user)
        self.assertIn("total_bytes", user)
        self.assertIn("total_transfer", user)
        self.assertIn("total_traffic", body["data"]["kpis"])
        self.assertNotIn("session_open", user)
        self.assertNotIn("last_rx_bytes", user)
        self.assertNotIn("last_tx_bytes", user)


if __name__ == "__main__":
    unittest.main()
