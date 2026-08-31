#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from persist_conf import upsert_peer_block  # noqa: E402


class PersistConfTest(unittest.TestCase):
    def test_appends_peer_when_missing(self) -> None:
        src = "[Interface]\nPrivateKey = aaa\nListenPort = 39783\n"
        out = upsert_peer_block(
            src,
            public_key="lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=",
            allowed_ip="10.8.1.2/32",
            preshared_key="psk",
        )
        self.assertIn("[Peer]", out)
        self.assertIn("AllowedIPs = 10.8.1.2/32", out)
        self.assertEqual(out.count("[Peer]"), 1)

    def test_does_not_duplicate_existing_peer(self) -> None:
        src = (
            "[Interface]\nListenPort = 1\n\n"
            "[Peer]\nPublicKey = lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=\n"
            "AllowedIPs = 10.8.1.2/32\n"
        )
        out = upsert_peer_block(
            src,
            public_key="lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=",
            allowed_ip="10.8.1.2/32",
            preshared_key="psk",
        )
        self.assertEqual(out.count("[Peer]"), 1)


if __name__ == "__main__":
    unittest.main()
