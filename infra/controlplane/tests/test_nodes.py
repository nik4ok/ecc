#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nodes import catalog_nodes, present_nodes  # noqa: E402


class NodesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = catalog_nodes(Path(ROOT).parent / "servers.json")

    def test_catalog_lists_door_ips(self) -> None:
        by_id = {n["id"]: n for n in self.catalog}
        self.assertEqual(by_id["SRV-NL-02"]["ipv4"], "89.19.217.190")
        self.assertEqual(by_id["SRV-NL-02"]["endpoint_port"], 39783)
        self.assertEqual(by_id["SRV-NL-01"]["ipv4"], "92.51.46.12")

    def test_live_door_is_active_with_peer_count(self) -> None:
        peers = [{"public_key": "a"}, {"public_key": "b"}]
        presented = present_nodes(
            self.catalog,
            live_server_id="SRV-NL-02",
            tunnel_source="live",
            peers=peers,
            online_count=1,
        )
        by_id = {n["id"]: n for n in presented}
        self.assertEqual(by_id["SRV-NL-02"]["status"], "active")
        self.assertEqual(by_id["SRV-NL-02"]["peer_count"], 2)
        self.assertEqual(by_id["SRV-NL-02"]["online_count"], 1)
        self.assertTrue(by_id["SRV-NL-02"]["reachable"])
        self.assertEqual(by_id["SRV-NL-01"]["status"], "inactive")
        self.assertEqual(by_id["SRV-NL-01"]["peer_count"], 0)
        self.assertFalse(by_id["SRV-NL-01"]["reachable"])

    def test_empty_tunnel_marks_live_door_down(self) -> None:
        presented = present_nodes(
            self.catalog,
            live_server_id="SRV-NL-02",
            tunnel_source="empty",
            peers=[],
            online_count=0,
        )
        door = next(n for n in presented if n["id"] == "SRV-NL-02")
        self.assertEqual(door["status"], "down")
        self.assertFalse(door["reachable"])
        self.assertEqual(door["peer_count"], 0)


if __name__ == "__main__":
    unittest.main()
