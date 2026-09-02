#!/usr/bin/env python3
"""RED/GREEN: снимок офиса и двери из ответа кассы, без живой сети."""
from __future__ import annotations

import json
import os
import sys
import unittest
from urllib.error import URLError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from houses import CashierHouseProbe, parse_overview  # noqa: E402


OVERVIEW = {
    "success": True,
    "data": {
        "kpis": {"total": 4, "online": 2},
        "nodes": [
            {
                "name": "ams-1-vm-q76q",
                "ipv4": "89.19.217.190",
                "status": "active",
                "peer_count": 4,
                "online_count": 2,
                "reachable": True,
            },
            {
                "name": "ams-1-vm-ca1m",
                "ipv4": "92.51.46.12",
                "status": "inactive",
                "peer_count": 0,
                "online_count": 0,
                "reachable": False,
            },
        ],
        "users": [
            {"address": "10.8.1.5/32", "online": True, "status": "active"},
            {"address": "10.8.1.6/32", "online": False, "status": "active"},
        ],
    },
}


class ParseOverviewTest(unittest.TestCase):
    def test_reads_office_health_and_doors(self) -> None:
        snap = parse_overview(OVERVIEW, office_ok=True)
        self.assertTrue(snap.office.ok)
        self.assertEqual(snap.vpn_total, 4)
        self.assertEqual(snap.vpn_online, 2)
        self.assertEqual(len(snap.doors), 2)
        live = snap.doors[0]
        self.assertTrue(live.ok)
        self.assertIn("89.19.217.190", live.detail)
        self.assertIn("10.8.1.5", snap.vpn_devices[0].label)

    def test_office_down_ignores_stale_book(self) -> None:
        snap = parse_overview(OVERVIEW, office_ok=False)
        self.assertFalse(snap.office.ok)
        self.assertEqual(snap.vpn_total, 0)
        self.assertEqual(snap.doors, ())


class CashierHouseProbeTest(unittest.TestCase):
    def test_timeout_marks_office_down(self) -> None:
        def boom(_url: str, timeout: float, headers: dict | None = None):
            raise URLError("timed out")

        probe = CashierHouseProbe(
            base_url="http://127.0.0.1:8090",
            username="nova",
            password="secret",
            fetch=boom,
        )
        snap = probe.snapshot()
        self.assertFalse(snap.office.ok)
        self.assertIn("не отвечает", snap.office.detail)

    def test_health_ok_overview_ok(self) -> None:
        def fake(url: str, timeout: float, headers: dict | None = None):
            if url.endswith("/health"):
                return json.dumps({"success": True, "data": {"ok": True}}).encode()
            return json.dumps(OVERVIEW).encode()

        probe = CashierHouseProbe(
            base_url="http://127.0.0.1:8090",
            username="nova",
            password="secret",
            fetch=fake,
        )
        snap = probe.snapshot()
        self.assertTrue(snap.office.ok)
        self.assertEqual(snap.vpn_online, 2)


if __name__ == "__main__":
    unittest.main()
