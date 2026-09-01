#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dashboard_auth import (  # noqa: E402
    authorization_header,
    credentials_match,
    dashboard_auth_required,
    is_protected_path,
)


class DashboardAuthUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            key: os.environ.get(key)
            for key in ("NOVA_DASHBOARD_PASSWORD", "NOVA_DASHBOARD_USER", "NOVA_BIND")
        }

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    def test_localhost_without_password_is_open(self) -> None:
        os.environ.pop("NOVA_DASHBOARD_PASSWORD", None)
        os.environ["NOVA_BIND"] = "127.0.0.1"
        self.assertFalse(dashboard_auth_required())

    def test_public_bind_without_password_is_closed(self) -> None:
        os.environ.pop("NOVA_DASHBOARD_PASSWORD", None)
        os.environ["NOVA_BIND"] = "0.0.0.0"
        self.assertTrue(dashboard_auth_required())

    def test_password_forces_auth_even_on_localhost(self) -> None:
        os.environ["NOVA_DASHBOARD_PASSWORD"] = "secret"
        os.environ["NOVA_BIND"] = "127.0.0.1"
        self.assertTrue(dashboard_auth_required())

    def test_protected_paths(self) -> None:
        self.assertTrue(is_protected_path("/"))
        self.assertTrue(is_protected_path("/index.html"))
        self.assertTrue(is_protected_path("/api/v1/overview"))
        self.assertFalse(is_protected_path("/api/v1/health"))
        self.assertFalse(is_protected_path("/api/v1/register"))

    def test_credentials_match_accepts_user_and_password(self) -> None:
        os.environ["NOVA_DASHBOARD_USER"] = "nova"
        os.environ["NOVA_DASHBOARD_PASSWORD"] = "s3cret"
        header = authorization_header("nova", "s3cret")
        self.assertTrue(credentials_match(header))

    def test_credentials_match_rejects_wrong_password(self) -> None:
        os.environ["NOVA_DASHBOARD_USER"] = "nova"
        os.environ["NOVA_DASHBOARD_PASSWORD"] = "s3cret"
        header = authorization_header("nova", "nope")
        self.assertFalse(credentials_match(header))
        self.assertFalse(credentials_match(None))
        self.assertFalse(credentials_match("Bearer abc"))


class DashboardAuthHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        cls._db = tmp.name
        os.environ["NOVA_PROVISION_MODE"] = "local"
        os.environ["NOVA_CONTROL_DB"] = cls._db
        os.environ["NOVA_BIND"] = "127.0.0.1"
        os.environ["NOVA_DASHBOARD_USER"] = "nova"
        os.environ["NOVA_DASHBOARD_PASSWORD"] = "board-pass"
        import importlib
        import server as server_mod

        importlib.reload(server_mod)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_mod.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.auth = {
            "Authorization": authorization_header("nova", "board-pass"),
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        os.unlink(cls._db)
        os.environ.pop("NOVA_DASHBOARD_PASSWORD", None)
        os.environ.pop("NOVA_DASHBOARD_USER", None)

    def _open(self, path: str, headers: dict | None = None, method: str = "GET", payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers=req_headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def test_dashboard_without_password_is_401(self) -> None:
        status, body, headers = self._open("/")
        self.assertEqual(status, 401)
        self.assertIn("basic", headers.get("WWW-Authenticate", "").lower())
        self.assertNotIn("Добавить устройство", body.decode("utf-8"))

    def test_dashboard_with_password_is_200(self) -> None:
        status, body, _headers = self._open("/", headers=self.auth)
        self.assertEqual(status, 200)
        self.assertIn("Добавить устройство", body.decode("utf-8"))

    def test_overview_without_password_is_401(self) -> None:
        status, _body, _headers = self._open("/api/v1/overview")
        self.assertEqual(status, 401)

    def test_overview_with_password_is_200(self) -> None:
        status, body, _headers = self._open("/api/v1/overview", headers=self.auth)
        self.assertEqual(status, 200)
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(payload["success"])

    def test_health_stays_open(self) -> None:
        status, body, _headers = self._open("/api/v1/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body.decode("utf-8"))["success"])

    def test_register_stays_open(self) -> None:
        key = base64.b64encode(b"\xbb" * 32).decode("ascii")
        status, body, _headers = self._open(
            "/api/v1/register",
            method="POST",
            payload={
                "email": "auth-guest@example.com",
                "display_name": "Auth guest",
                "public_key": key,
            },
        )
        self.assertEqual(status, 201)
        self.assertTrue(json.loads(body.decode("utf-8"))["success"])


if __name__ == "__main__":
    unittest.main()
