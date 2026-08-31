#!/usr/bin/env python3
"""NOVA control plane: guest registration + operator dashboard.

Default bind is 127.0.0.1:8090 and local provision (no docker).
On the VPS set NOVA_PROVISION_MODE=docker and NOVA_BIND=0.0.0.0.
"""
from __future__ import annotations

import json
import os
import subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from awg_status import merge_users_with_tunnel, parse_awg_show
from provision import make_provisioner
from store import DuplicatePublicKeyError, InvalidPublicKeyError, UserStore
from ticket import issue_ticket, load_node

HERE = Path(__file__).resolve().parent
INFRA = HERE.parent
DB_PATH = Path(os.environ.get("NOVA_CONTROL_DB", str(HERE / "nova_users.db")))
BIND_HOST = os.environ.get("NOVA_BIND", "127.0.0.1")
PORT = int(os.environ.get("NOVA_CONTROL_PORT", "8090"))
DASHBOARD = (HERE / "dashboard.html").read_text(encoding="utf-8")


def _servers_json() -> Path:
    env = os.environ.get("NOVA_SERVERS_JSON")
    if env:
        return Path(env)
    for candidate in (HERE / "servers.json", INFRA / "servers.json"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("servers.json not found")


def _envelope(success: bool, data: Any = None, error: str | None = None) -> bytes:
    return json.dumps({"success": success, "data": data, "error": error}, ensure_ascii=False).encode("utf-8")


class ControlPlane:
    def __init__(self) -> None:
        self.store = UserStore(str(DB_PATH))
        self.store.seed_reserved(
            [
                {
                    "email": "amnezia@device.local",
                    "display_name": "Amnezia (контрольный телефон)",
                    "public_key": "KvasB+XL6z4lAorYnh8OLrL71PPWYIKszRQjTk8zDTY=",
                    "client_address": "10.8.1.1/32",
                    "source": "reserved",
                },
                {
                    "email": "nova-test@device.local",
                    "display_name": "NOVA тестовый телефон",
                    "public_key": "lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=",
                    "client_address": "10.8.1.2/32",
                    "source": "reserved",
                },
            ]
        )
        self.node = load_node(_servers_json())
        self.provisioner = make_provisioner()

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        user = self.store.register(
            email=str(payload.get("email", "")),
            display_name=str(payload.get("display_name", "")),
            public_key=str(payload.get("public_key", "")),
        )
        try:
            note = self.provisioner.add_peer(
                user["public_key"],
                user["client_address"],
                self.node["preshared_key"],
            )
        except Exception:
            self.store.revoke(user["id"])
            raise
        ticket = issue_ticket(self.node, user)
        ticket["provision"] = note
        return ticket

    def tunnel_peers(self) -> tuple[list[dict[str, Any]], str]:
        raw, source = _read_awg_show()
        return parse_awg_show(raw)["peers"], source

    def overview(self) -> dict[str, Any]:
        peers, source = self.tunnel_peers()
        users = merge_users_with_tunnel(self.store.list_users(), peers)
        active = [u for u in users if u["status"] == "active"]
        online = sum(1 for u in active if u["online"])
        waiting = sum(1 for u in active if not u["online"])
        return {
            "node": {
                "server_id": self.node["server_id"],
                "endpoint_host": self.node["endpoint_host"],
                "endpoint_port": self.node["endpoint_port"],
            },
            "tunnel": {"source": source},
            "kpis": {
                "total": len(users),
                "online": online,
                "waiting": waiting,
                "next_address": self.store.next_address(),
            },
            "users": users,
        }


PLANE = ControlPlane()


def _read_awg_show() -> tuple[str, str]:
    override = os.environ.get("NOVA_AWG_SHOW_FILE")
    if override and Path(override).is_file():
        return Path(override).read_text(encoding="utf-8"), "file"
    mode = os.environ.get("NOVA_PROVISION_MODE", "local").strip().lower()
    if mode == "docker":
        try:
            result = subprocess.run(
                ["docker", "exec", "amnezia-awg2", "awg", "show", "awg0"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout, "live"
        except Exception:
            return "", "empty"
        return "", "empty"
    demo = HERE / "demo_awg_show.txt"
    if demo.is_file():
        return demo.read_text(encoding="utf-8"), "snapshot"
    return "", "empty"


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, success: bool, data: Any = None, error: str | None = None) -> None:
        body = _envelope(success, data, error)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            body = DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/v1/overview":
            self._json(200, True, PLANE.overview())
            return
        if path == "/api/v1/health":
            self._json(200, True, {"ok": True})
            return
        self._json(404, False, error="not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            self._json(400, False, error="invalid content-length")
            return
        if length < 0 or length > 65536:
            self._json(413, False, error="payload too large")
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, False, error="invalid json")
            return
        if path == "/api/v1/register":
            try:
                ticket = PLANE.register(payload)
            except DuplicatePublicKeyError as exc:
                self._json(409, False, error=str(exc))
                return
            except (InvalidPublicKeyError, ValueError) as exc:
                self._json(400, False, error=str(exc))
                return
            except Exception as exc:
                self._json(500, False, error=str(exc))
                return
            self._json(201, True, ticket)
            return
        self._json(404, False, error="not found")

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((BIND_HOST, PORT), Handler)
    print(f"NOVA control plane http://{BIND_HOST}:{PORT}", flush=True)
    print(f"db={DB_PATH} provision={os.environ.get('NOVA_PROVISION_MODE', 'local')}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
