#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from provision import SshProvisioner, make_provisioner  # noqa: E402


class SshProvisionerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._prev = {
            key: os.environ.get(key)
            for key in ("NOVA_PROVISION_MODE", "NOVA_EDGE_SSH", "NOVA_EDGE_SSH_KEY", "NOVA_EDGE_SSH_PORT")
        }
        os.environ["NOVA_EDGE_SSH"] = "root@89.19.217.190"
        os.environ["NOVA_EDGE_SSH_KEY"] = "/etc/nova-controlplane/edge_ed25519"
        os.environ["NOVA_EDGE_SSH_PORT"] = "22"

    def tearDown(self) -> None:
        for key, value in self._prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @patch("edge_ssh.subprocess.run")
    def test_add_peer_runs_awg_set_over_ssh(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        note = SshProvisioner().add_peer(
            "lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=",
            "10.8.1.3/32",
            "psk-value",
        )
        self.assertIn("ssh", note)
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "ssh")
        self.assertIn("-i", argv)
        self.assertIn("/etc/nova-controlplane/edge_ed25519", argv)
        self.assertIn("root@89.19.217.190", argv)
        remote = argv[-1]
        self.assertIn("docker exec", remote)
        self.assertIn("awg set", remote)
        self.assertIn("10.8.1.3/32", remote)
        self.assertEqual(run.call_args.kwargs.get("input") or run.call_args[1].get("input"), "psk-value\n")

    @patch("edge_ssh.subprocess.run")
    def test_make_provisioner_ssh_mode(self, run) -> None:
        os.environ["NOVA_PROVISION_MODE"] = "ssh"
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        provisioner = make_provisioner()
        self.assertIsInstance(provisioner, SshProvisioner)

    def test_ssh_mode_requires_edge_target(self) -> None:
        os.environ["NOVA_PROVISION_MODE"] = "ssh"
        os.environ.pop("NOVA_EDGE_SSH", None)
        with self.assertRaises(RuntimeError):
            SshProvisioner()


if __name__ == "__main__":
    unittest.main()
