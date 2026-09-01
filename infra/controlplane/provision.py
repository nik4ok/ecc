"""Add or remove an AmneziaWG peer. Local mode records intent only."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Protocol

from edge_ssh import run_on_edge
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


class SshProvisioner:
    """Office talks to the door over SSH: docker exec awg set on the Edge."""

    def __init__(self) -> None:
        if not os.environ.get("NOVA_EDGE_SSH", "").strip():
            raise RuntimeError("NOVA_EDGE_SSH is not set")
        self.container = os.environ.get("NOVA_EDGE_CONTAINER", "amnezia-awg2").strip() or "amnezia-awg2"
        self.interface = os.environ.get("NOVA_EDGE_INTERFACE", "awg0").strip() or "awg0"

    def add_peer(self, public_key: str, allowed_ip: str, preshared_key: str) -> str:
        remote = (
            f"docker exec -i {shlex.quote(self.container)} awg set {shlex.quote(self.interface)} "
            f"peer {shlex.quote(public_key)} preshared-key /dev/stdin "
            f"allowed-ips {shlex.quote(allowed_ip)}"
        )
        result = run_on_edge(remote, input_text=preshared_key + "\n", timeout=8)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "awg set failed").strip())
        persisted = self._persist(public_key, allowed_ip, preshared_key)
        return f"ssh: live interface updated; {persisted}"

    def remove_peer(self, public_key: str) -> str:
        remote = (
            f"docker exec {shlex.quote(self.container)} awg set {shlex.quote(self.interface)} "
            f"peer {shlex.quote(public_key)} remove"
        )
        result = run_on_edge(remote, timeout=8)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "awg set remove failed").strip())
        return "ssh: peer removed from live interface"

    def _persist(self, public_key: str, allowed_ip: str, preshared_key: str) -> str:
        path = os.environ.get("NOVA_EDGE_AWG_CONF", "").strip()
        if not path:
            return "awg0.conf persist skipped (set NOVA_EDGE_AWG_CONF)"
        quoted = shlex.quote(path)
        read = run_on_edge(f"cat {quoted}", timeout=8)
        if read.returncode != 0:
            return "awg0.conf not readable on the door"
        updated = upsert_peer_block(
            read.stdout,
            public_key=public_key,
            allowed_ip=allowed_ip,
            preshared_key=preshared_key,
        )
        if updated == read.stdout:
            return f"already in {path}"
        write = run_on_edge(f"cat > {quoted}", input_text=updated, timeout=8)
        if write.returncode != 0:
            return "awg0.conf write failed on the door"
        return f"wrote {path}"


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
    if mode == "ssh":
        return SshProvisioner()
    return LocalProvisioner()
