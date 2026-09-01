"""VPN door catalog for the operator dashboard. No secrets in the listing."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def catalog_nodes(servers_json: Path) -> list[dict[str, Any]]:
    payload = json.loads(servers_json.read_text(encoding="utf-8"))
    nodes: list[dict[str, Any]] = []
    for server in payload.get("servers", []):
        network = server.get("network") if isinstance(server.get("network"), dict) else {}
        protocols = server.get("active_protocols") if isinstance(server.get("active_protocols"), dict) else {}
        awg = protocols.get("amnezia_wg_2") if isinstance(protocols.get("amnezia_wg_2"), dict) else {}
        ipv4 = str(network.get("ipv4") or "").strip()
        if not ipv4:
            continue
        port = awg.get("port")
        nodes.append(
            {
                "id": str(server.get("id") or ""),
                "name": str(server.get("name") or ""),
                "ipv4": ipv4,
                "endpoint_port": int(port) if port is not None else None,
            }
        )
    return nodes


def present_nodes(
    catalog: list[dict[str, Any]],
    *,
    live_server_id: str,
    tunnel_source: str,
    peers: list[dict[str, Any]],
    online_count: int,
) -> list[dict[str, Any]]:
    presented: list[dict[str, Any]] = []
    for node in catalog:
        if node.get("id") == live_server_id:
            status = _status_for_source(tunnel_source)
            peer_count = len(peers) if status != "down" else 0
            presented.append(
                {
                    "id": node["id"],
                    "name": node.get("name") or "",
                    "ipv4": node["ipv4"],
                    "endpoint_port": node.get("endpoint_port"),
                    "status": status,
                    "peer_count": peer_count,
                    "online_count": online_count if status != "down" else 0,
                    "reachable": tunnel_source == "live",
                }
            )
            continue
        presented.append(
            {
                "id": node.get("id") or "",
                "name": node.get("name") or "",
                "ipv4": node["ipv4"],
                "endpoint_port": node.get("endpoint_port"),
                "status": "inactive",
                "peer_count": 0,
                "online_count": 0,
                "reachable": False,
            }
        )
    return presented


def _status_for_source(tunnel_source: str) -> str:
    if tunnel_source == "live":
        return "active"
    if tunnel_source in {"snapshot", "file"}:
        return "snapshot"
    return "down"
