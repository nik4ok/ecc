"""Build the client ticket: dialect of the club, never the doorman's private key."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_node(servers_json: Path) -> dict[str, Any]:
    payload = json.loads(servers_json.read_text(encoding="utf-8"))
    for server in payload.get("servers", []):
        if server.get("id") == "SRV-NL-02":
            awg = server["active_protocols"]["amnezia_wg_2"]
            network = server["network"]
            obf = awg["obfuscation"]
            return {
                "server_id": server["id"],
                "name": server["name"],
                "endpoint_host": network["ipv4"],
                "endpoint_port": awg["port"],
                "server_public_key": awg["server_public_key"],
                "preshared_key": obf["preshared_key"],
                "amnezia": {
                    "jc": obf["jc"],
                    "jmin": obf["jmin"],
                    "jmax": obf["jmax"],
                    "s1": obf["s1"],
                    "s2": obf["s2"],
                    "s3": obf["s3"],
                    "s4": obf["s4"],
                    "h1": obf["h1"],
                    "h2": obf["h2"],
                    "h3": obf["h3"],
                    "h4": obf["h4"],
                    "header_protection_key": obf["header_protection_key"],
                    "content_padding_addition": "10-100",
                    "random_trailers": True,
                    "disable_cookies": True,
                },
            }
    raise KeyError("SRV-NL-02 not found in servers.json")


def issue_ticket(node: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": user["id"],
        "display_name": user["display_name"],
        "email": user["email"],
        "client_address": user["client_address"],
        "client_public_key": user["public_key"],
        "endpoint_host": node["endpoint_host"],
        "endpoint_port": node["endpoint_port"],
        "server_public_key": node["server_public_key"],
        "preshared_key": node["preshared_key"],
        "amnezia": node["amnezia"],
    }
