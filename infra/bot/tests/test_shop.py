#!/usr/bin/env python3
"""RED/GREEN: подписка, срок, payload счёта."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shop import (  # noqa: E402
    MONTH_PLAN,
    OS_ANDROID,
    OS_IOS,
    EntitlementStore,
    InvalidOsError,
    InvalidTelegramIdError,
    make_invoice_payload,
    parse_admin_ids,
    parse_invoice_payload,
)


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


class EntitlementStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._path = tmp.name
        self.store = EntitlementStore(self._path)

    def tearDown(self) -> None:
        self.store.close()
        os.unlink(self._path)

    def test_new_user_has_no_access(self) -> None:
        self.assertFalse(self.store.has_access(42, now=NOW))

    def test_grant_opens_thirty_days(self) -> None:
        row = self.store.grant(42, days=30, now=NOW, display_name="Никита")
        self.assertTrue(self.store.has_access(42, now=NOW))
        self.assertTrue(self.store.has_access(42, now=NOW + timedelta(days=29)))
        self.assertFalse(self.store.has_access(42, now=NOW + timedelta(days=30)))
        self.assertEqual(row["telegram_id"], 42)
        self.assertEqual(row["display_name"], "Никита")
        self.assertEqual(row["paid_until"], (NOW + timedelta(days=30)).isoformat())

    def test_grant_extends_from_remaining_time(self) -> None:
        self.store.grant(7, days=30, now=NOW, display_name="A")
        later = NOW + timedelta(days=10)
        row = self.store.grant(7, days=30, now=later, display_name="A")
        self.assertEqual(row["paid_until"], (NOW + timedelta(days=60)).isoformat())

    def test_grant_from_now_if_expired(self) -> None:
        self.store.grant(8, days=30, now=NOW, display_name="B")
        later = NOW + timedelta(days=40)
        row = self.store.grant(8, days=30, now=later, display_name="B")
        self.assertEqual(row["paid_until"], (later + timedelta(days=30)).isoformat())

    def test_invalid_telegram_id_rejected(self) -> None:
        with self.assertRaises(InvalidTelegramIdError):
            self.store.grant(0, days=30, now=NOW)
        with self.assertRaises(InvalidTelegramIdError):
            self.store.has_access(-3, now=NOW)

    def test_get_missing_returns_none(self) -> None:
        self.assertIsNone(self.store.get(99))

    def test_same_charge_id_does_not_extend_twice(self) -> None:
        first = self.store.apply_payment(
            telegram_id=42,
            days=30,
            now=NOW,
            display_name="Никита",
            charge_id="chg-1",
        )
        second = self.store.apply_payment(
            telegram_id=42,
            days=30,
            now=NOW,
            display_name="Никита",
            charge_id="chg-1",
        )
        self.assertEqual(first["paid_until"], second["paid_until"])
        self.assertEqual(first["paid_until"], (NOW + timedelta(days=30)).isoformat())

    def test_new_charge_id_extends(self) -> None:
        self.store.apply_payment(42, 30, NOW, "A", "chg-a")
        row = self.store.apply_payment(42, 30, NOW, "A", "chg-b")
        self.assertEqual(row["paid_until"], (NOW + timedelta(days=60)).isoformat())

    def test_set_os_roundtrip(self) -> None:
        row = self.store.set_os(42, OS_ANDROID, now=NOW, display_name="Никита")
        self.assertEqual(row["os"], OS_ANDROID)
        self.assertEqual(self.store.get_profile(42)["os"], OS_ANDROID)
        switched = self.store.set_os(42, OS_IOS, now=NOW, display_name="Никита")
        self.assertEqual(switched["os"], OS_IOS)

    def test_invalid_os_rejected(self) -> None:
        with self.assertRaises(InvalidOsError):
            self.store.set_os(42, "windows", now=NOW)

    def test_remember_visit_creates_visitor_and_event(self) -> None:
        self.store.remember_visit(
            42,
            now=NOW,
            display_name="Никита",
            username="nick",
            language_code="ru",
            action="start",
        )
        row = self.store.get_visitor(42)
        self.assertEqual(row["username"], "nick")
        self.assertEqual(row["display_name"], "Никита")
        self.assertEqual(row["language_code"], "ru")
        self.assertEqual(row["visit_count"], 1)
        self.assertEqual(row["first_seen"], NOW.isoformat())
        events = self.store.list_events(42)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "start")

    def test_second_visit_bumps_count_keeps_first_seen(self) -> None:
        self.store.remember_visit(42, now=NOW, display_name="Никита", action="start")
        later = NOW + timedelta(hours=3)
        self.store.remember_visit(
            42,
            now=later,
            display_name="Никита",
            username="nick",
            action="android",
            os_name=OS_ANDROID,
        )
        row = self.store.get_visitor(42)
        self.assertEqual(row["visit_count"], 2)
        self.assertEqual(row["first_seen"], NOW.isoformat())
        self.assertEqual(row["last_seen"], later.isoformat())
        self.assertEqual(row["username"], "nick")
        self.assertEqual(self.store.list_events(42)[-1]["os"], OS_ANDROID)

    def test_shop_stats_counts_os_and_window(self) -> None:
        self.store.remember_visit(1, now=NOW, display_name="A", action="start")
        self.store.set_os(1, OS_ANDROID, now=NOW, display_name="A")
        self.store.remember_visit(
            1, now=NOW, display_name="A", action="download", os_name=OS_ANDROID
        )
        self.store.remember_visit(2, now=NOW, display_name="B", action="start")
        self.store.set_os(2, OS_IOS, now=NOW, display_name="B")
        old = NOW - timedelta(days=3)
        self.store.remember_visit(3, now=old, display_name="C", action="start")
        stats = self.store.shop_stats(now=NOW)
        self.assertEqual(stats["visitors"], 3)
        self.assertEqual(stats["visitors_recent"], 2)
        self.assertEqual(stats["android"], 1)
        self.assertEqual(stats["ios"], 1)
        self.assertEqual(stats["unknown_os"], 1)
        self.assertEqual(stats["downloads_recent"], 1)
        self.assertEqual(stats["reports_total"], 0)

    def test_recent_visitors_newest_first(self) -> None:
        self.store.remember_visit(1, now=NOW, display_name="Старый", action="start")
        later = NOW + timedelta(minutes=5)
        self.store.remember_visit(2, now=later, display_name="Новый", action="start")
        rows = self.store.list_recent_visitors(limit=10)
        self.assertEqual([row["telegram_id"] for row in rows], [2, 1])


class InvoicePayloadTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        payload = make_invoice_payload(telegram_id=15, plan_id=MONTH_PLAN.id, nonce="abc")
        parsed = parse_invoice_payload(payload)
        self.assertEqual(parsed.telegram_id, 15)
        self.assertEqual(parsed.plan_id, MONTH_PLAN.id)
        self.assertEqual(parsed.nonce, "abc")

    def test_garbage_is_none(self) -> None:
        self.assertIsNone(parse_invoice_payload("not-a-payload"))
        self.assertIsNone(parse_invoice_payload("nova:month:nope:x"))
        self.assertIsNone(parse_invoice_payload(""))


class PlanFromEnvTest(unittest.TestCase):
    def test_default_stars(self) -> None:
        from shop import plan_from_env

        self.assertEqual(plan_from_env(None).stars, 250)
        self.assertEqual(plan_from_env("").stars, 250)

    def test_custom_stars(self) -> None:
        from shop import plan_from_env

        self.assertEqual(plan_from_env("399").stars, 399)

    def test_rejects_zero_and_garbage(self) -> None:
        from shop import plan_from_env

        with self.assertRaises(ValueError):
            plan_from_env("0")
        with self.assertRaises(ValueError):
            plan_from_env("ten")


class ParseAdminIdsTest(unittest.TestCase):
    def test_empty_is_no_admins(self) -> None:
        self.assertEqual(parse_admin_ids(None), frozenset())
        self.assertEqual(parse_admin_ids(""), frozenset())
        self.assertEqual(parse_admin_ids("  "), frozenset())

    def test_comma_list_skips_garbage(self) -> None:
        self.assertEqual(parse_admin_ids("1001, abc, 2002"), frozenset({1001, 2002}))
        self.assertEqual(parse_admin_ids("7;8"), frozenset({7, 8}))

    def test_rejects_zero_and_negative(self) -> None:
        self.assertEqual(parse_admin_ids("0, -4, 9"), frozenset({9}))


if __name__ == "__main__":
    unittest.main()
