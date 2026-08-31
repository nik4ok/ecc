"""Parse `awg show` text into peer dicts. Never invent handshake data."""
from __future__ import annotations

from typing import Any


def parse_awg_show(raw: str) -> dict[str, Any]:
    peers: list[dict[str, Any]] = []
    interface: dict[str, Any] = {}
    current: dict[str, Any] | None = None

    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("interface:"):
            interface["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("public key:") and "public_key" not in interface:
            interface["public_key"] = line.split(":", 1)[1].strip()
        elif line.startswith("listening port:"):
            interface["listening_port"] = line.split(":", 1)[1].strip()
        elif line.startswith("peer:"):
            if current:
                peers.append(current)
            current = {"public_key": line.split(":", 1)[1].strip()}
        elif current is None:
            continue
        elif line.startswith("endpoint:"):
            current["endpoint"] = line.split(":", 1)[1].strip()
        elif line.startswith("allowed ips:"):
            current["allowed_ips"] = line.split(":", 1)[1].strip()
        elif line.startswith("latest handshake:"):
            current["latest_handshake"] = line.split(":", 1)[1].strip()
        elif line.startswith("transfer:"):
            current["transfer"] = line.split(":", 1)[1].strip()

    if current:
        peers.append(current)

    return {"interface": interface, "peers": peers}


def merge_users_with_tunnel(
    users: list[dict[str, Any]],
    tunnel_peers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {p.get("public_key"): p for p in tunnel_peers}
    merged = []
    for user in users:
        peer = by_key.get(user["public_key"], {})
        handshake = peer.get("latest_handshake")
        online = handshake_is_fresh(handshake) and user.get("status") == "active"
        merged.append(
            {
                **user,
                "endpoint": peer.get("endpoint"),
                "latest_handshake": handshake,
                "transfer": peer.get("transfer"),
                "tunnel_present": bool(peer),
                "online": online,
            }
        )
    return merged


def handshake_is_fresh(handshake: str | None) -> bool:
    if not handshake:
        return False
    text = handshake.strip().lower()
    if text in {"never"}:
        return False
    if "second" in text or "minute" in text:
        return True
    return False
