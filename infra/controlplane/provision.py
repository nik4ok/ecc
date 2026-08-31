"""Add or remove an AmneziaWG peer. Local mode records intent only."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Protocol

from persist_conf import upsert_peer_block


class Provisioner(Protocol):
    def add_peer(self, public_key: str, allowed_ip: str, preshared_key: str) -> str: ...

    def remove_peer(self, public_key: str) -> str: ...


class LocalProvisioner:
    """Does not touch Docker. Safe default on a laptop."""

    def add_peer(self, public_key: str, allowed_ip: str, preshared_key: str) -> str:
        return f"local: book {public_key[:8]}… as {allowed_ip}"

    def remove_peer(self, public_key: str) -> str:
        return f"local: revoke {public_key[:8]}…"


class DockerProvisioner:
    """Live awg set + persist into awg0.conf so a container restart keeps the guest."""

    def __init__(self, container: str = "amnezia-awg2", interface: str = "awg0") -> None:
        self.container = container
        self.interface = interface

    def add_peer(self, public_key: str, allowed_ip: str, preshared_key: str) -> str:
        cmd = [
            "docker",
            "exec",
            "-i",
            self.container,
            "awg",
            "set",
            self.interface,
            "peer",
            public_key,
            "preshared-key",
            "/dev/stdin",
            "allowed-ips",
            allowed_ip,
        ]
        result = subprocess.run(
            cmd,
            input=preshared_key + "\n",
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "awg set failed")
        persisted = self._persist(public_key, allowed_ip, preshared_key)
        return f"docker: live interface updated; {persisted}"

    def remove_peer(self, public_key: str) -> str:
        cmd = [
            "docker",
            "exec",
            self.container,
            "awg",
            "set",
            self.interface,
            "peer",
            public_key,
            "remove",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "awg set remove failed")
        return "docker: peer removed from live interface"

    def _persist(self, public_key: str, allowed_ip: str, preshared_key: str) -> str:
        conf = _find_awg0_conf(self.container)
        if conf is None:
            return "awg0.conf not found (peer lives in memory until container restart)"
        text = conf.read_text(encoding="utf-8")
        updated = upsert_peer_block(
            text,
            public_key=public_key,
            allowed_ip=allowed_ip,
            preshared_key=preshared_key,
        )
        if updated == text:
            return f"already in {conf}"
        conf.write_text(updated, encoding="utf-8")
        return f"wrote {conf}"


def _find_awg0_conf(container: str) -> Path | None:
    override = os.environ.get("NOVA_AWG_CONF")
    if override:
        path = Path(override)
        return path if path.is_file() else None
    inspect = subprocess.run(
        [
            "docker",
            "inspect",
            container,
            "--format",
            "{{range .Mounts}}{{.Source}}\n{{end}}",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
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


def make_provisioner() -> Provisioner:
    mode = os.environ.get("NOVA_PROVISION_MODE", "local").strip().lower()
    if mode == "docker":
        return DockerProvisioner()
    return LocalProvisioner()
