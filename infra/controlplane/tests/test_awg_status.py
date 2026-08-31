#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from awg_status import merge_users_with_tunnel, parse_awg_show  # noqa: E402


SAMPLE = """
interface: awg0
  public key: s1bBvq1mlFNu+VeAJSP3lD4PGz/SJhAM9Jw3HPNuekw=
  listening port: 39783

peer: KvasB+XL6z4lAorYnh8OLrL71PPWYIKszRQjTk8zDTY=
  endpoint: 217.107.126.227:1077
  allowed ips: 10.8.1.1/32
  latest handshake: 3 minutes, 6 seconds ago
  transfer: 5.76 MiB received, 86.59 MiB sent

peer: lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=
  endpoint: 217.107.126.227:1082
  allowed ips: 10.8.1.2/32
  latest handshake: 12 seconds ago
  transfer: 12.40 MiB received, 40.02 MiB sent
"""


class AwgStatusTest(unittest.TestCase):
    def test_parse_two_peers(self) -> None:
        parsed = parse_awg_show(SAMPLE)
        self.assertEqual(parsed["interface"]["listening_port"], "39783")
        self.assertEqual(len(parsed["peers"]), 2)
        self.assertEqual(parsed["peers"][0]["allowed_ips"], "10.8.1.1/32")

    def test_merge_marks_online_from_handshake(self) -> None:
        users = [
            {
                "id": "1",
                "email": "a@x",
                "display_name": "Amnezia",
                "public_key": "KvasB+XL6z4lAorYnh8OLrL71PPWYIKszRQjTk8zDTY=",
                "client_address": "10.8.1.1/32",
                "status": "active",
            },
            {
                "id": "2",
                "email": "new@x",
                "display_name": "New",
                "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                "client_address": "10.8.1.3/32",
                "status": "active",
            },
        ]
        peers = parse_awg_show(SAMPLE)["peers"]
        merged = merge_users_with_tunnel(users, peers)
        self.assertTrue(merged[0]["online"])
        self.assertFalse(merged[1]["online"])
        self.assertFalse(merged[1]["tunnel_present"])

    def test_stale_handshake_is_not_online(self) -> None:
        users = [
            {
                "id": "1",
                "email": "a@x",
                "display_name": "Old",
                "public_key": "KvasB+XL6z4lAorYnh8OLrL71PPWYIKszRQjTk8zDTY=",
                "client_address": "10.8.1.1/32",
                "status": "active",
            }
        ]
        peers = [
            {
                "public_key": "KvasB+XL6z4lAorYnh8OLrL71PPWYIKszRQjTk8zDTY=",
                "latest_handshake": "2 days, 1 hour ago",
            }
        ]
        merged = merge_users_with_tunnel(users, peers)
        self.assertFalse(merged[0]["online"])
        self.assertTrue(merged[0]["tunnel_present"])


if __name__ == "__main__":
    unittest.main()
