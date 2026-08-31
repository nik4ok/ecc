"""Idempotent [Peer] block for awg0.conf. Does not touch Docker."""
from __future__ import annotations


def upsert_peer_block(
    conf_text: str,
    *,
    public_key: str,
    allowed_ip: str,
    preshared_key: str,
) -> str:
    if public_key in conf_text:
        return conf_text
    block = (
        "\n[Peer]\n"
        f"PublicKey = {public_key}\n"
        f"PresharedKey = {preshared_key}\n"
        f"AllowedIPs = {allowed_ip}\n"
    )
    return conf_text.rstrip() + block
