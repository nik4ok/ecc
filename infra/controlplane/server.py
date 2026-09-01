#!/usr/bin/env python3
"""NOVA control plane: guest registration + operator dashboard.

Default bind is 127.0.0.1:8090 and local provision (no docker).
On the VPS set NOVA_PROVISION_MODE=docker and NOVA_BIND=0.0.0.0.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from awg_status import handshake_is_fresh, merge_users_with_tunnel, parse_awg_show
from dashboard_auth import (
    credentials_match,
    dashboard_auth_required,
    is_protected_path,
)
from nodes import catalog_nodes, present_nodes
from provision import make_provisioner
from store import DuplicatePublicKeyError, InvalidPublicKeyError, UserStore
from ticket import issue_ticket, load_node
from usage import format_bytes, present_user, usage_source_is_usable

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
        self.catalog = catalog_nodes(_servers_json())
        self.provisioner = make_provisioner()
        self._usage_lock = threading.Lock()

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

    def refresh_usage(self) -> tuple[list[dict[str, Any]], str]:
        with self._usage_lock:
            peers, source = self.tunnel_peers()
            if usage_source_is_usable(source):
                self.store.apply_tunnel_peers(peers)
            return peers, source

    def overview(self) -> dict[str, Any]:
        peers, source = self.refresh_usage()
        users = [
            present_user(user)
            for user in merge_users_with_tunnel(self.store.list_users(), peers)
        ]
        active = [u for u in users if u["status"] == "active"]
        online = sum(1 for u in active if u["online"])
        waiting = sum(1 for u in active if not u["online"])
        total_bytes = sum(int(u.get("total_bytes") or 0) for u in users)
        online_peers = sum(1 for peer in peers if handshake_is_fresh(peer.get("latest_handshake")))
        return {
            "node": {
                "server_id": self.node["server_id"],
                "endpoint_host": self.node["endpoint_host"],
                "endpoint_port": self.node["endpoint_port"],
            },
            "nodes": present_nodes(
                self.catalog,
                live_server_id=self.node["server_id"],
                tunnel_source=source,
                peers=peers,
                online_count=online_peers,
            ),
            "tunnel": {"source": source},
            "kpis": {
                "total": len(users),
                "online": online,
                "waiting": waiting,
                "next_address": self.store.next_address(),
                "total_traffic": format_bytes(total_bytes),
                "total_bytes": total_bytes,
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
    if mode == "ssh":
        try:
            from edge_ssh import run_on_edge

            container = os.environ.get("NOVA_EDGE_CONTAINER", "amnezia-awg2").strip() or "amnezia-awg2"
            interface = os.environ.get("NOVA_EDGE_INTERFACE", "awg0").strip() or "awg0"
            result = run_on_edge(
                f"docker exec {shlex.quote(container)} awg show {shlex.quote(interface)}",
                timeout=4,
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

    def _unauthorized(self) -> None:
        body = _envelope(False, error="dashboard login required")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="NOVA"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _dashboard_allowed(self, path: str) -> bool:
        if not is_protected_path(path):
            return True
        if not dashboard_auth_required():
            return True
        return credentials_match(self.headers.get("Authorization"))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if is_protected_path(path) and not self._dashboard_allowed(path):
            self._unauthorized()
            return
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
    poller = threading.Thread(target=_usage_poll_loop, daemon=True)
    poller.start()
    server = ThreadingHTTPServer((BIND_HOST, PORT), Handler)
    print(f"NOVA control plane http://{BIND_HOST}:{PORT}", flush=True)
    print(f"db={DB_PATH} provision={os.environ.get('NOVA_PROVISION_MODE', 'local')}", flush=True)
    if dashboard_auth_required():
        print("dashboard: basic auth on (user from NOVA_DASHBOARD_USER)", flush=True)
    else:
        print("dashboard: open (localhost, no NOVA_DASHBOARD_PASSWORD)", flush=True)
    server.serve_forever()


def _usage_poll_loop() -> None:
    while True:
        time.sleep(10)
        try:
            PLANE.refresh_usage()
        except Exception as exc:
            print(f"usage poll failed: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
