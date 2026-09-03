#!/usr/bin/env python3
"""Push door SQLite guests onto amnezia-awg2. Run on the door as root.

Default: add missing keys, replace a room only if the occupant never shook hands.
Live peers with a handshake are left alone (set FORCE_REPLACE=1 to override).

  python3 infra/scripts/13_sync_sqlite_to_awg.py
  python3 infra/scripts/13_sync_sqlite_to_awg.py --apply
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
from pathlib import Path

CONTAINER = os.environ.get("NOVA_EDGE_CONTAINER", "amnezia-awg2")
INTERFACE = os.environ.get("NOVA_EDGE_INTERFACE", "awg0")
DB = os.environ.get("NOVA_USERS_DB", "/var/lib/nova-controlplane/nova_users.db")


def run(cmd: list[str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def find_awg0_conf() -> Path | None:
    inspect = run(
        [
            "docker",
            "inspect",
            CONTAINER,
            "--format",
            "{{range .Mounts}}{{.Source}}\n{{end}}",
        ]
    )
    for line in inspect.stdout.splitlines():
        root = line.strip()
        if not root:
            continue
        try:
            found = next(Path(root).rglob("awg0.conf"), None)
        except OSError:
            found = None
        if found and found.is_file():
            return found
    return None


def psk_from_conf(conf: Path) -> str:
    for line in conf.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("presharedkey"):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"no PresharedKey in {conf}")


def load_book() -> list[tuple[str, str, str]]:
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """
        SELECT display_name, public_key, client_address
        FROM users
        WHERE status = 'active'
        ORDER BY client_address
        """
    ).fetchall()
    conn.close()
    return [(str(n), str(k), str(a)) for n, k, a in rows]


def parse_awg_show(raw: str) -> dict[str, dict[str, str]]:
    peers: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in raw.splitlines():
        text = line.strip()
        if text.startswith("peer:"):
            current = text.split(":", 1)[1].strip()
            peers[current] = {"ip": "", "handshake": ""}
            continue
        if current is None:
            continue
        if text.startswith("allowed ips:"):
            peers[current]["ip"] = text.split(":", 1)[1].strip()
        if text.startswith("latest handshake:"):
            peers[current]["handshake"] = text.split(":", 1)[1].strip()
    return peers


def occupant_for_ip(peers: dict[str, dict[str, str]], ip: str) -> tuple[str, dict[str, str]] | None:
    for key, meta in peers.items():
        if meta["ip"] == ip:
            return key, meta
    return None


def remove_peer(public_key: str) -> None:
    result = run(
        ["docker", "exec", CONTAINER, "awg", "set", INTERFACE, "peer", public_key, "remove"]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "awg set remove failed")


def add_peer(public_key: str, ip: str, psk: str) -> None:
    result = run(
        [
            "docker",
            "exec",
            "-i",
            CONTAINER,
            "awg",
            "set",
            INTERFACE,
            "peer",
            public_key,
            "preshared-key",
            "/dev/stdin",
            "allowed-ips",
            ip,
        ],
        input_text=psk + "\n",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "awg set failed")


def drop_peer_block(conf_text: str, public_key: str) -> str:
    chunks = conf_text.split("\n[Peer]")
    keep = [chunks[0]]
    for chunk in chunks[1:]:
        if public_key not in chunk:
            keep.append("[Peer]" + chunk)
    return "\n".join(keep) if len(keep) == 1 else keep[0] + "\n" + "\n".join(keep[1:])


def upsert_peer_block(conf_text: str, public_key: str, ip: str, psk: str) -> str:
    stripped = drop_peer_block(conf_text, public_key)
    if public_key in stripped:
        return stripped
    block = (
        "\n[Peer]\n"
        f"PublicKey = {public_key}\n"
        f"PresharedKey = {psk}\n"
        f"AllowedIPs = {ip}\n"
    )
    return stripped.rstrip() + block


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    force = os.environ.get("FORCE_REPLACE", "") == "1"

    conf = find_awg0_conf()
    if conf is None:
        raise SystemExit("awg0.conf not found next to amnezia-awg2")
    psk = psk_from_conf(conf)
    show = run(["docker", "exec", CONTAINER, "awg", "show", INTERFACE])
    if show.returncode != 0:
        raise SystemExit(show.stderr or "awg show failed")
    peers = parse_awg_show(show.stdout)
    book = load_book()
    pump_keys = set(peers)
    conf_text = conf.read_text(encoding="utf-8")
    planned: list[str] = []

    for name, key, ip in book:
        if key in pump_keys:
            planned.append(f"ok     {ip}  {key[:8]}…  {name}")
            continue
        taken = occupant_for_ip(peers, ip)
        if taken is None:
            planned.append(f"add    {ip}  {key[:8]}…  {name}")
            if args.apply:
                add_peer(key, ip, psk)
                conf_text = upsert_peer_block(conf_text, key, ip, psk)
            continue
        old_key, meta = taken
        live = bool(meta["handshake"])
        if live and not force:
            planned.append(
                f"skip   {ip}  книга {key[:8]}… занята живым {old_key[:8]}… ({meta['handshake']})  {name}"
            )
            continue
        planned.append(
            f"swap   {ip}  {old_key[:8]}… -> {key[:8]}…  {name}"
        )
        if args.apply:
            remove_peer(old_key)
            add_peer(key, ip, psk)
            conf_text = drop_peer_block(conf_text, old_key)
            conf_text = upsert_peer_block(conf_text, key, ip, psk)

    print("\n".join(planned))
    if not args.apply:
        print("\nЭто просмотр. Чтобы записать: python3 infra/scripts/13_sync_sqlite_to_awg.py --apply")
        return 0
    conf.write_text(conf_text, encoding="utf-8")
    print(f"\nзаписал {conf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
