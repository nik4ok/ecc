#!/usr/bin/env python3
"""RED/GREEN: user book, IP allocation, duplicate badges."""
from __future__ import annotations

import base64
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from store import DuplicatePublicKeyError, InvalidPublicKeyError, UserStore  # noqa: E402


def _key(seed: int) -> str:
    return base64.b64encode(bytes([(seed + i) % 256 for i in range(32)])).decode("ascii")


class UserStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.store = UserStore(self._tmp.name)
        self.store.seed_reserved(
            [
                {
                    "email": "amnezia@device.local",
                    "display_name": "Amnezia (контрольный телефон)",
                    "public_key": "KvasB+XL6z4lAorYnh8OLrL71PPWYIKszRQjTk8zDTY=",
                    "client_address": "10.8.1.1/32",
                    "source": "reserved",
                },
                {
                    "email": "nova-test@device.local",
                    "display_name": "NOVA тестовый телефон",
                    "public_key": "lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=",
                    "client_address": "10.8.1.2/32",
                    "source": "reserved",
                },
            ]
        )

    def tearDown(self) -> None:
        os.unlink(self._tmp.name)

    def test_next_ip_skips_reserved_rooms(self) -> None:
        user = self.store.register(
            email="third@example.com",
            display_name="Третий гость",
            public_key=_key(3),
        )
        self.assertEqual(user["client_address"], "10.8.1.3/32")

    def test_ips_increment(self) -> None:
        first = self.store.register("a@example.com", "A", _key(10))
        second = self.store.register("b@example.com", "B", _key(11))
        self.assertEqual(first["client_address"], "10.8.1.3/32")
        self.assertEqual(second["client_address"], "10.8.1.4/32")

    def test_duplicate_public_key_rejected(self) -> None:
        with self.assertRaises(DuplicatePublicKeyError):
            self.store.register(
                "copy@example.com",
                "Копия",
                "lzMFxwiPIiewKz4KFxKQG6+f2BkUIZvu8woO3/+bT3w=",
            )

    def test_invalid_public_key_rejected(self) -> None:
        with self.assertRaises(InvalidPublicKeyError):
            self.store.register("bad@example.com", "Bad", "not-a-key")

    def test_list_includes_reserved_and_new(self) -> None:
        self.store.register("c@example.com", "C", _key(12))
        users = self.store.list_users()
        self.assertEqual(len(users), 3)
        emails = {u["email"] for u in users}
        self.assertIn("amnezia@device.local", emails)
        self.assertIn("c@example.com", emails)

    def test_revoke_marks_user_and_frees_nothing_yet(self) -> None:
        user = self.store.register("gone@example.com", "Gone", _key(13))
        self.store.revoke(user["id"])
        listed = [u for u in self.store.list_users() if u["id"] == user["id"]][0]
        self.assertEqual(listed["status"], "revoked")

    def test_new_user_starts_with_zero_usage(self) -> None:
        user = self.store.register("stats@example.com", "Stats", _key(20))
        self.assertEqual(user["connect_count"], 0)
        self.assertIsNone(user["first_connected_at"])
        self.assertEqual(user["total_rx_bytes"], 0)
        self.assertEqual(user["total_tx_bytes"], 0)

    def test_apply_tunnel_peers_counts_session_and_traffic(self) -> None:
        user = self.store.register("live@example.com", "Live", _key(21))
        self.store.apply_tunnel_peers(
            [
                {
                    "public_key": user["public_key"],
                    "latest_handshake": "12 seconds ago",
                    "transfer": "1.00 KiB received, 2.00 KiB sent",
                }
            ],
            now="2026-08-31T18:04:00+00:00",
        )
        stored = self.store.get(user["id"])
        self.assertEqual(stored["connect_count"], 1)
        self.assertEqual(stored["first_connected_at"], "2026-08-31T18:04:00+00:00")
        self.assertEqual(stored["total_rx_bytes"], 1024)
        self.assertEqual(stored["total_tx_bytes"], 2048)

    def test_apply_tunnel_peers_second_poll_same_session(self) -> None:
        user = self.store.register("hold@example.com", "Hold", _key(22))
        peer = {
            "public_key": user["public_key"],
            "latest_handshake": "12 seconds ago",
            "transfer": "1.00 KiB received, 2.00 KiB sent",
        }
        self.store.apply_tunnel_peers([peer], now="t1")
        peer = {**peer, "transfer": "2.00 KiB received, 2.00 KiB sent"}
        self.store.apply_tunnel_peers([peer], now="t2")
        stored = self.store.get(user["id"])
        self.assertEqual(stored["connect_count"], 1)
        self.assertEqual(stored["total_rx_bytes"], 2048)


if __name__ == "__main__":
    unittest.main()
