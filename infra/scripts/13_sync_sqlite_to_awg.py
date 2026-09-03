#!/usr/bin/env python3
"""Push door SQLite guests onto amnezia-awg2. Run on the door as root.

Default: add missing keys, replace a room only if the occupant never shook hands.
Live peers with a handshake are left alone (set FORCE_REPLACE=1 to override).

  python3 infra/scripts/13_sync_sqlite_to_awg.py
  python3 infra/scripts/13_sync_sqlite_to_awg.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from pathlib import Path

CONTAINER = os.environ.get("NOVA_EDGE_CONTAINER", "amnezia-awg2")
INTERFACE = os.environ.get("NOVA_EDGE_INTERFACE", "awg0")
DB = os.environ.get("NOVA_USERS_DB", "/var/lib/nova-controlplane/nova_users.db")
INSIDE_CONF_CANDIDATES = (
    "/opt/amnezia/awg/awg0.conf",
    "/opt/amnezia/awg0.conf",
    "/config/awg0.conf",
)


def docker_exec(args: list[str], input_text: str | None = None, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", *(["-i"] if input_text is not None else []), CONTAINER, *args], input_text, timeout)


def run(
    cmd: list[str],
    input_text: str | None = None,
    timeout: int = 15,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def find_host_conf() -> Path | None:
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


def find_inside_conf() -> str | None:
    for path in INSIDE_CONF_CANDIDATES:
        probe = docker_exec(["test", "-f", path])
        if probe.returncode == 0:
            return path
    found = docker_exec(
        ["sh", "-c", "find /opt /etc /config -name awg0.conf 2>/dev/null | head -1"],
        timeout=20,
    )
    path = (found.stdout or "").strip().splitlines()
    return path[0] if path else None


def read_conf_text(host: Path | None, inside: str | None) -> str:
    if host is not None:
        return host.read_text(encoding="utf-8")
    if inside:
        result = docker_exec(["cat", inside])
        if result.returncode == 0:
            return result.stdout
    return ""


def write_conf_text(host: Path | None, inside: str | None, text: str) -> str:
    if host is not None:
        host.write_text(text, encoding="utf-8")
        return str(host)
    if inside:
        result = docker_exec(["tee", inside], input_text=text)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to write awg0.conf in container")
        return f"{CONTAINER}:{inside}"
    return ""


def psk_from_text(conf_text: str) -> str | None:
    for line in conf_text.splitlines():
        if line.lower().startswith("presharedkey"):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    return None


def psk_from_repo() -> str | None:
    path = Path(__file__).resolve().parents[1] / "servers.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    for server in payload.get("servers", []):
        protocols = server.get("active_protocols") if isinstance(server.get("active_protocols"), dict) else {}
        awg = protocols.get("amnezia_wg_2") if isinstance(protocols.get("amnezia_wg_2"), dict) else {}
        obf = awg.get("obfuscation") if isinstance(awg.get("obfuscation"), dict) else {}
        key = str(obf.get("preshared_key") or "").strip()
        if key:
            return key
    return None


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

    host_conf = find_host_conf()
    inside_conf = None if host_conf else find_inside_conf()
    conf_text = read_conf_text(host_conf, inside_conf)
    psk = psk_from_text(conf_text) or psk_from_repo()
    if not psk:
        raise SystemExit("no PresharedKey in awg0.conf or infra/servers.json")

    show = run(["docker", "exec", CONTAINER, "awg", "show", INTERFACE])
    if show.returncode != 0:
        raise SystemExit(show.stderr or "awg show failed")
    peers = parse_awg_show(show.stdout)
    book = load_book()
    pump_keys = set(peers)
    planned: list[str] = []
    conf_dirty = False
    changed_live = False

    for name, key, ip in book:
        if key in pump_keys:
            planned.append(f"ok     {ip}  {key[:8]}…  {name}")
            continue
        taken = occupant_for_ip(peers, ip)
        if taken is None:
            planned.append(f"add    {ip}  {key[:8]}…  {name}")
            if args.apply:
                add_peer(key, ip, psk)
                changed_live = True
                if conf_text:
                    conf_text = upsert_peer_block(conf_text, key, ip, psk)
                    conf_dirty = True
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
            changed_live = True
            if conf_text:
                conf_text = drop_peer_block(conf_text, old_key)
                conf_text = upsert_peer_block(conf_text, key, ip, psk)
                conf_dirty = True

    print("\n".join(planned))
    if not args.apply:
        where = str(host_conf) if host_conf else (f"{CONTAINER}:{inside_conf}" if inside_conf else "только память насоса")
        print(f"\nКонфиг: {where}")
        print("Это просмотр. Чтобы записать: python3 infra/scripts/13_sync_sqlite_to_awg.py --apply")
        return 0
    if conf_dirty:
        written = write_conf_text(host_conf, inside_conf, conf_text)
        if written:
            print(f"\nзаписал {written}")
        else:
            print("\nнасос обновлён, awg0.conf не нашли — после рестарта контейнера пиры могут пропасть")
    elif changed_live:
        print("\nнасос обновлён")
        if not conf_text:
            print("awg0.conf не нашли — после рестарта контейнера пиры могут пропасть")
    else:
        print("\nменять было нечего")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
