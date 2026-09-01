"""SSH to the VPN door from the office. Token and bot secrets never go here."""
from __future__ import annotations

import os
import subprocess
from typing import Optional


def ssh_argv() -> list[str]:
    target = os.environ.get("NOVA_EDGE_SSH", "").strip()
    if not target:
        raise RuntimeError("NOVA_EDGE_SSH is not set")
    argv = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    key = os.environ.get("NOVA_EDGE_SSH_KEY", "").strip()
    if key:
        argv.extend(["-i", key])
    port = os.environ.get("NOVA_EDGE_SSH_PORT", "").strip()
    if port:
        argv.extend(["-p", port])
    argv.append(target)
    return argv


def run_on_edge(
    remote: str,
    input_text: Optional[str] = None,
    timeout: int = 8,
) -> subprocess.CompletedProcess:
    argv = ssh_argv() + [remote]
    return subprocess.run(
        argv,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
