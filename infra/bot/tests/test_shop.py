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


if __name__ == "__main__":
    unittest.main()
