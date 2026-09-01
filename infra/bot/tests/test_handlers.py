#!/usr/bin/env python3
"""RED/GREEN: витрина бота — старт, оплата, скачивание, статус."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from handlers import (  # noqa: E402
    BUTTON_DOWNLOAD,
    BUTTON_PAY,
    BUTTON_STATUS,
    Document,
    Invoice,
    PreCheckoutAnswer,
    Reply,
    ShopContext,
    handle_update,
)
from shop import MONTH_PLAN, EntitlementStore  # noqa: E402


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def _update(
    text: str | None = None,
    user_id: int = 1001,
    name: str = "Гость",
    successful_payment: dict | None = None,
    pre_checkout: dict | None = None,
) -> dict:
    if pre_checkout is not None:
        return {"pre_checkout_query": pre_checkout}
    message: dict = {
        "from": {"id": user_id, "first_name": name},
        "chat": {"id": user_id, "type": "private"},
    }
    if text is not None:
        message["text"] = text
    if successful_payment is not None:
        message["successful_payment"] = successful_payment
    return {"message": message}


class HandlerTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db = tmp.name
        self.store = EntitlementStore(self._db)
        apk = tempfile.NamedTemporaryFile(suffix=".apk", delete=False)
        apk.write(b"apk-bytes")
        apk.close()
        self._apk = apk.name
        self.ctx = ShopContext(
            store=self.store,
            plan=MONTH_PLAN,
            apk_path=Path(self._apk),
            payment_mode="stars",
            now=NOW,
        )

    def tearDown(self) -> None:
        self.store.close()
        os.unlink(self._db)
        os.unlink(self._apk)

    def _handle(self, update: dict, ctx: ShopContext | None = None) -> list:
        return handle_update(update, ctx or self.ctx)

    def test_start_explains_shop_and_shows_buttons(self) -> None:
        actions = self._handle(_update("/start"))
        self.assertEqual(len(actions), 1)
        reply = actions[0]
        self.assertIsInstance(reply, Reply)
        self.assertIn("NOVA", reply.text)
        self.assertIn("Google Play", reply.text)
        self.assertTrue(reply.keyboard)
        self.assertIn("Оплатите", reply.text)

    def test_pay_in_stars_sends_invoice(self) -> None:
        actions = self._handle(_update(BUTTON_PAY))
        invoices = [a for a in actions if isinstance(a, Invoice)]
        self.assertEqual(len(invoices), 1)
        invoice = invoices[0]
        self.assertEqual(invoice.currency, "XTR")
        self.assertEqual(invoice.amount, MONTH_PLAN.stars)
        self.assertIn("nova:", invoice.payload)
        self.assertIn("1001", invoice.payload)

    def test_download_without_pay_asks_to_pay(self) -> None:
        actions = self._handle(_update(BUTTON_DOWNLOAD))
        self.assertTrue(any(isinstance(a, Reply) for a in actions))
        self.assertFalse(any(isinstance(a, Document) for a in actions))
        self.assertIn("оплат", actions[0].text.lower())

    def test_status_without_pay(self) -> None:
        actions = self._handle(_update(BUTTON_STATUS))
        self.assertIn("нет", actions[0].text.lower())

    def test_successful_payment_grants_and_offers_apk(self) -> None:
        pay = self._handle(_update(BUTTON_PAY))
        payload = next(a for a in pay if isinstance(a, Invoice)).payload
        actions = self._handle(
            _update(
                successful_payment={
                    "currency": "XTR",
                    "total_amount": MONTH_PLAN.stars,
                    "invoice_payload": payload,
                    "telegram_payment_charge_id": "chg-ok",
                }
            )
        )
        self.assertTrue(self.store.has_access(1001, now=NOW))
        self.assertTrue(any(isinstance(a, Document) for a in actions))
        document = next(a for a in actions if isinstance(a, Document))
        self.assertEqual(document.path, self._apk)
        self.assertIn("Telegram", document.caption)

    def test_download_after_pay_sends_apk(self) -> None:
        self.store.grant(1001, days=30, now=NOW, display_name="Гость")
        actions = self._handle(_update(BUTTON_DOWNLOAD))
        document = next(a for a in actions if isinstance(a, Document))
        self.assertEqual(document.path, self._apk)

    def test_status_after_pay_shows_date(self) -> None:
        self.store.grant(1001, days=30, now=NOW, display_name="Гость")
        actions = self._handle(_update(BUTTON_STATUS))
        self.assertIn("2 октября 2026", actions[0].text)

    def test_paid_but_apk_missing_explains(self) -> None:
        self.store.grant(1001, days=30, now=NOW, display_name="Гость")
        missing = ShopContext(
            store=self.store,
            plan=MONTH_PLAN,
            apk_path=Path("/tmp/nova-missing-file.apk"),
            payment_mode="stars",
            now=NOW,
        )
        actions = self._handle(_update(BUTTON_DOWNLOAD), missing)
        self.assertFalse(any(isinstance(a, Document) for a in actions))
        self.assertIn("сборк", actions[0].text.lower())

    def test_dev_pay_grants_without_invoice(self) -> None:
        ctx = ShopContext(
            store=self.store,
            plan=MONTH_PLAN,
            apk_path=Path(self._apk),
            payment_mode="dev",
            now=NOW,
        )
        actions = self._handle(_update(BUTTON_PAY), ctx)
        self.assertFalse(any(isinstance(a, Invoice) for a in actions))
        self.assertTrue(self.store.has_access(1001, now=NOW))
        self.assertTrue(any(isinstance(a, Document) for a in actions))

    def test_pre_checkout_ok(self) -> None:
        pay = self._handle(_update(BUTTON_PAY))
        payload = next(a for a in pay if isinstance(a, Invoice)).payload
        actions = self._handle(
            _update(
                pre_checkout={
                    "id": "q1",
                    "from": {"id": 1001},
                    "currency": "XTR",
                    "total_amount": MONTH_PLAN.stars,
                    "invoice_payload": payload,
                }
            )
        )
        answer = actions[0]
        self.assertIsInstance(answer, PreCheckoutAnswer)
        self.assertTrue(answer.ok)
        self.assertEqual(answer.query_id, "q1")

    def test_pre_checkout_rejects_wrong_amount(self) -> None:
        pay = self._handle(_update(BUTTON_PAY))
        payload = next(a for a in pay if isinstance(a, Invoice)).payload
        actions = self._handle(
            _update(
                pre_checkout={
                    "id": "q2",
                    "from": {"id": 1001},
                    "currency": "XTR",
                    "total_amount": 1,
                    "invoice_payload": payload,
                }
            )
        )
        answer = actions[0]
        self.assertFalse(answer.ok)
        self.assertTrue(answer.error_message)

    def test_pre_checkout_rejects_other_user_payload(self) -> None:
        pay = self._handle(_update(BUTTON_PAY, user_id=1001))
        payload = next(a for a in pay if isinstance(a, Invoice)).payload
        actions = self._handle(
            _update(
                pre_checkout={
                    "id": "q3",
                    "from": {"id": 2002},
                    "currency": "XTR",
                    "total_amount": MONTH_PLAN.stars,
                    "invoice_payload": payload,
                }
            )
        )
        self.assertFalse(actions[0].ok)

    def test_unknown_text_repeats_menu(self) -> None:
        actions = self._handle(_update("привет"))
        self.assertIsInstance(actions[0], Reply)
        self.assertTrue(actions[0].keyboard)

    def test_empty_update_is_ignored(self) -> None:
        self.assertEqual(self._handle({}), [])

    def test_start_with_bot_suffix(self) -> None:
        actions = self._handle(_update("/start@NovaShopBot"))
        self.assertIsInstance(actions[0], Reply)
        self.assertIn("NOVA", actions[0].text)

    def test_group_chat_is_ignored(self) -> None:
        update = _update("/start")
        update["message"]["chat"]["type"] = "group"
        self.assertEqual(self._handle(update), [])

    def test_successful_payment_still_grants_if_price_changed(self) -> None:
        pay = self._handle(_update(BUTTON_PAY))
        payload = next(a for a in pay if isinstance(a, Invoice)).payload
        actions = self._handle(
            _update(
                successful_payment={
                    "currency": "XTR",
                    "total_amount": 1,
                    "invoice_payload": payload,
                    "telegram_payment_charge_id": "chg-price",
                }
            )
        )
        self.assertTrue(self.store.has_access(1001, now=NOW))
        self.assertTrue(any(isinstance(a, Document) for a in actions))

    def test_payment_replay_does_not_add_extra_month(self) -> None:
        pay = self._handle(_update(BUTTON_PAY))
        payload = next(a for a in pay if isinstance(a, Invoice)).payload
        payment = {
            "currency": "XTR",
            "total_amount": MONTH_PLAN.stars,
            "invoice_payload": payload,
            "telegram_payment_charge_id": "chg-replay",
        }
        self._handle(_update(successful_payment=payment))
        first_until = self.store.get(1001)["paid_until"]
        self._handle(_update(successful_payment=payment))
        self.assertEqual(self.store.get(1001)["paid_until"], first_until)


if __name__ == "__main__":
    unittest.main()
