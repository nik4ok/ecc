#!/usr/bin/env python3
"""RED/GREEN: session count, first connect, lifetime traffic."""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from usage import (  # noqa: E402
    UsageSnapshot,
    apply_observation,
    format_bytes,
    parse_transfer,
    usage_source_is_usable,
)


def _empty() -> UsageSnapshot:
    return UsageSnapshot(
        connect_count=0,
        first_connected_at=None,
        total_rx_bytes=0,
        total_tx_bytes=0,
        last_rx_bytes=0,
        last_tx_bytes=0,
        session_open=False,
    )


class ParseTransferTest(unittest.TestCase):
    def test_parses_mib_pair(self) -> None:
        rx, tx = parse_transfer("12.40 MiB received, 40.02 MiB sent")
        self.assertEqual(rx, int(12.40 * 1024 * 1024))
        self.assertEqual(tx, int(40.02 * 1024 * 1024))

    def test_parses_mixed_units(self) -> None:
        rx, tx = parse_transfer("800 B received, 1.50 KiB sent")
        self.assertEqual(rx, 800)
        self.assertEqual(tx, int(1.50 * 1024))

    def test_empty_is_zero(self) -> None:
        self.assertEqual(parse_transfer(None), (0, 0))
        self.assertEqual(parse_transfer(""), (0, 0))


class ApplyObservationTest(unittest.TestCase):
    def test_first_online_opens_session_and_stamps_first_connect(self) -> None:
        next_state = apply_observation(
            _empty(),
            online=True,
            rx_bytes=100,
            tx_bytes=200,
            now="2026-08-31T18:00:00+00:00",
        )
        self.assertEqual(next_state.connect_count, 1)
        self.assertEqual(next_state.first_connected_at, "2026-08-31T18:00:00+00:00")
        self.assertTrue(next_state.session_open)
        self.assertEqual(next_state.total_rx_bytes, 100)
        self.assertEqual(next_state.total_tx_bytes, 200)

    def test_staying_online_does_not_count_another_session(self) -> None:
        opened = apply_observation(
            _empty(),
            online=True,
            rx_bytes=100,
            tx_bytes=0,
            now="2026-08-31T18:00:00+00:00",
        )
        stayed = apply_observation(
            opened,
            online=True,
            rx_bytes=150,
            tx_bytes=10,
            now="2026-08-31T18:00:10+00:00",
        )
        self.assertEqual(stayed.connect_count, 1)
        self.assertEqual(stayed.first_connected_at, opened.first_connected_at)
        self.assertEqual(stayed.total_rx_bytes, 150)
        self.assertEqual(stayed.total_tx_bytes, 10)

    def test_offline_then_online_counts_a_new_session(self) -> None:
        opened = apply_observation(
            _empty(), online=True, rx_bytes=10, tx_bytes=10, now="t1"
        )
        closed = apply_observation(
            opened, online=False, rx_bytes=10, tx_bytes=10, now="t2"
        )
        self.assertFalse(closed.session_open)
        self.assertEqual(closed.connect_count, 1)
        reopened = apply_observation(
            closed, online=True, rx_bytes=11, tx_bytes=10, now="t3"
        )
        self.assertEqual(reopened.connect_count, 2)
        self.assertEqual(reopened.first_connected_at, "t1")

    def test_tiny_backwards_jump_is_not_a_reset(self) -> None:
        filled = apply_observation(
            _empty(), online=True, rx_bytes=40_000_000, tx_bytes=40_000_000, now="t1"
        )
        stale = apply_observation(
            filled, online=True, rx_bytes=39_990_000, tx_bytes=39_990_000, now="t2"
        )
        self.assertEqual(stale.total_rx_bytes, 40_000_000)
        self.assertEqual(stale.last_rx_bytes, 40_000_000)
        filled = apply_observation(
            _empty(), online=True, rx_bytes=1000, tx_bytes=2000, now="t1"
        )
        after_restart = apply_observation(
            filled, online=True, rx_bytes=50, tx_bytes=80, now="t2"
        )
        self.assertEqual(after_restart.total_rx_bytes, 1050)
        self.assertEqual(after_restart.total_tx_bytes, 2080)
        self.assertEqual(after_restart.last_rx_bytes, 50)

    def test_missing_counters_leave_totals_unchanged(self) -> None:
        filled = apply_observation(
            _empty(), online=True, rx_bytes=100, tx_bytes=200, now="t1"
        )
        offline = apply_observation(
            filled, online=False, rx_bytes=None, tx_bytes=None, now="t2"
        )
        self.assertEqual(offline.total_rx_bytes, 100)
        self.assertEqual(offline.total_tx_bytes, 200)
        self.assertFalse(offline.session_open)


class FormatBytesTest(unittest.TestCase):
    def test_formats_gib_and_bytes(self) -> None:
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(512), "512 B")
        self.assertEqual(format_bytes(1024), "1.00 KiB")
        self.assertEqual(format_bytes(int(1.5 * 1024 * 1024)), "1.50 MiB")


class UsageSourceTest(unittest.TestCase):
    def test_empty_source_is_not_recorded(self) -> None:
        self.assertFalse(usage_source_is_usable("empty"))
        self.assertTrue(usage_source_is_usable("live"))
        self.assertTrue(usage_source_is_usable("snapshot"))
        self.assertTrue(usage_source_is_usable("file"))


if __name__ == "__main__":
    unittest.main()
