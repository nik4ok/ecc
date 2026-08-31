#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ticket import issue_ticket, load_node  # noqa: E402


class TicketTest(unittest.TestCase):
    def test_ticket_has_dialect_and_room_not_private_key(self) -> None:
        node = load_node(Path(ROOT).parent / "servers.json")
        user = {
            "id": "u-1",
            "email": "third@example.com",
            "display_name": "Третий",
            "client_address": "10.8.1.3/32",
            "public_key": "lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=",
        }
        ticket = issue_ticket(node, user)
        self.assertEqual(ticket["endpoint_host"], "89.19.217.190")
        self.assertEqual(ticket["endpoint_port"], 39783)
        self.assertEqual(ticket["client_address"], "10.8.1.3/32")
        self.assertEqual(ticket["amnezia"]["header_protection_key"][:8], "81A3uK4f")
        self.assertTrue(ticket["amnezia"]["random_trailers"])
        self.assertNotIn("private_key", ticket)
        self.assertNotIn("client_private_key", ticket)


if __name__ == "__main__":
    unittest.main()
