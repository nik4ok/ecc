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
    BUTTON_ADMIN,
    BUTTON_ADMIN_CLIENTS,
    BUTTON_ADMIN_HOUSE,
    BUTTON_ADMIN_STATS,
    BUTTON_ANDROID,
    BUTTON_DOWNLOAD,
    BUTTON_IOS,
    BUTTON_PAY,
    BUTTON_REPORT,
    BUTTON_SHOP,
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
    username: str | None = None,
    language_code: str | None = None,
    successful_payment: dict | None = None,
    pre_checkout: dict | None = None,
) -> dict:
    if pre_checkout is not None:
        return {"pre_checkout_query": pre_checkout}
    from_user: dict = {"id": user_id, "first_name": name}
    if username is not None:
        from_user["username"] = username
    if language_code is not None:
        from_user["language_code"] = language_code
    message: dict = {
        "from": from_user,
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

    def _android(self, ctx: ShopContext | None = None) -> list:
        return self._handle(_update(BUTTON_ANDROID), ctx)

    def test_start_explains_shop_and_shows_buttons(self) -> None:
        actions = self._handle(_update("/start", name="Никита"))
        self.assertEqual(len(actions), 1)
        reply = actions[0]
        self.assertIsInstance(reply, Reply)
        self.assertIn("Никита", reply.text)
        self.assertIn("NOVA", reply.text)
        self.assertIn("Google Play", reply.text)
        self.assertIn("С какого телефона", reply.text)
        self.assertTrue(reply.keyboard)
        texts = [cell["text"] for row in reply.markup["keyboard"] for cell in row]
        self.assertEqual(texts, [BUTTON_ANDROID, BUTTON_IOS, BUTTON_REPORT])

    def test_pay_in_stars_sends_invoice(self) -> None:
        self._android()
        actions = self._handle(_update(BUTTON_PAY))
        invoices = [a for a in actions if isinstance(a, Invoice)]
        self.assertEqual(len(invoices), 1)
        invoice = invoices[0]
        self.assertEqual(invoice.currency, "XTR")
        self.assertEqual(invoice.amount, MONTH_PLAN.stars)
        self.assertIn("nova:", invoice.payload)
        self.assertIn("1001", invoice.payload)

    def test_download_without_pay_asks_to_pay(self) -> None:
        self._android()
        actions = self._handle(_update(BUTTON_DOWNLOAD))
        self.assertTrue(any(isinstance(a, Reply) for a in actions))
        self.assertFalse(any(isinstance(a, Document) for a in actions))
        self.assertIn("оплат", actions[0].text.lower())

    def test_status_without_pay(self) -> None:
        self._android()
        actions = self._handle(_update(BUTTON_STATUS))
        self.assertIn("нет", actions[0].text.lower())

    def test_successful_payment_grants_and_offers_apk(self) -> None:
        self._android()
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
        self._android()
        self.store.grant(1001, days=30, now=NOW, display_name="Гость")
        actions = self._handle(_update(BUTTON_DOWNLOAD))
        document = next(a for a in actions if isinstance(a, Document))
        self.assertEqual(document.path, self._apk)

    def test_status_after_pay_shows_date(self) -> None:
        self._android()
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
        self._android(missing)
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
        self._android(ctx)
        actions = self._handle(_update(BUTTON_PAY), ctx)
        self.assertFalse(any(isinstance(a, Invoice) for a in actions))
        self.assertTrue(self.store.has_access(1001, now=NOW))
        self.assertTrue(any(isinstance(a, Document) for a in actions))

    def test_pre_checkout_ok(self) -> None:
        self._android()
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
        self._android()
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
        self._android()
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
        self._android()
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

    def test_payment_survives_tracking_failure(self) -> None:
        self._android()
        pay = self._handle(_update(BUTTON_PAY))
        payload = next(a for a in pay if isinstance(a, Invoice)).payload

        def boom(*_args, **_kwargs):
            raise RuntimeError("disk full")

        self.store.remember_visit = boom  # type: ignore[method-assign]
        actions = self._handle(
            _update(
                successful_payment={
                    "currency": "XTR",
                    "total_amount": MONTH_PLAN.stars,
                    "invoice_payload": payload,
                    "telegram_payment_charge_id": "chg-track-fail",
                }
            )
        )
        self.assertTrue(self.store.has_access(1001, now=NOW))
        self.assertTrue(any(isinstance(a, Document) for a in actions))

    def test_payment_replay_does_not_add_extra_month(self) -> None:
        self._android()
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


class WaitlistJourneyTest(unittest.TestCase):
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
            payment_mode="off",
            now=NOW,
        )

    def tearDown(self) -> None:
        self.store.close()
        os.unlink(self._db)
        os.unlink(self._apk)

    def _handle(self, text: str, name: str = "Никита") -> list:
        return handle_update(_update(text, name=name), self.ctx)

    def test_android_preview_downloads_without_pay(self) -> None:
        ready = self._handle(BUTTON_ANDROID)
        self.assertIn("превью", ready[0].text.lower())
        actions = self._handle(BUTTON_DOWNLOAD)
        document = next(a for a in actions if isinstance(a, Document))
        self.assertEqual(document.path, self._apk)

    def test_pay_explains_cashier_is_closed(self) -> None:
        self._handle(BUTTON_ANDROID)
        actions = self._handle(BUTTON_PAY)
        self.assertFalse(any(isinstance(a, Invoice) for a in actions))
        self.assertIn("касса ещё не подключена", actions[0].text)

    def test_ios_download_does_not_send_file(self) -> None:
        wait = self._handle(BUTTON_IOS)
        self.assertIn("App Store", wait[0].text)
        actions = self._handle(BUTTON_DOWNLOAD)
        self.assertFalse(any(isinstance(a, Document) for a in actions))
        self.assertIn("скачать нельзя", actions[0].text.lower())

    def test_ios_pay_does_not_send_invoice(self) -> None:
        self._handle(BUTTON_IOS)
        actions = self._handle(BUTTON_PAY)
        self.assertFalse(any(isinstance(a, Invoice) for a in actions))
        self.assertIn("iPhone", actions[0].text)

    def test_status_while_payments_off(self) -> None:
        self._handle(BUTTON_ANDROID)
        actions = self._handle(BUTTON_STATUS)
        self.assertIn("оплата ещё не открыта", actions[0].text.lower())

    def test_anon_start_has_no_comma_name(self) -> None:
        actions = handle_update(_update("/start", name=""), self.ctx)
        self.assertFalse(actions[0].text.startswith(","))
        self.assertIn("Это NOVA", actions[0].text)

    def test_switch_from_ios_to_android(self) -> None:
        self._handle(BUTTON_IOS)
        ready = self._handle(BUTTON_ANDROID)
        self.assertEqual(self.store.get_profile(1001)["os"], "android")
        self.assertIn("Android можно ставить", ready[0].text)

    def test_report_prompt_then_saves_message(self) -> None:
        prompt = self._handle(BUTTON_REPORT)
        self.assertIn("одним сообщением", prompt[0].text)
        thanks = self._handle("Не включается защита после установки файла")
        self.assertIn("Записали", thanks[0].text)
        rows = self.store.list_reports(1001)
        self.assertEqual(len(rows), 1)
        self.assertIn("Не включается защита", rows[0]["body"])

    def test_report_short_message_asks_again(self) -> None:
        self._handle(BUTTON_REPORT)
        again = self._handle("ок")
        self.assertIn("подробнее", again[0].text)
        self.assertEqual(self.store.list_reports(1001), [])

    def test_report_then_android_is_not_saved_as_ticket(self) -> None:
        self._handle(BUTTON_REPORT)
        self._handle(BUTTON_ANDROID)
        self.assertEqual(self.store.list_reports(1001), [])
        self.assertEqual(self.store.get_profile(1001)["os"], "android")

    def test_start_remembers_visitor(self) -> None:
        handle_update(
            _update("/start", name="Никита", username="nick", language_code="ru"),
            self.ctx,
        )
        row = self.store.get_visitor(1001)
        self.assertEqual(row["username"], "nick")
        self.assertEqual(row["language_code"], "ru")
        self.assertEqual(self.store.list_events(1001)[0]["action"], "start")


class AdminJourneyTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db = tmp.name
        self.store = EntitlementStore(self._db)
        from houses import HouseSnapshot, HouseStatus, VpnDevice

        self.snapshot = HouseSnapshot(
            office=HouseStatus(name="Офис", kind="office", ok=True, detail="касса отвечает"),
            doors=(
                HouseStatus(
                    name="Дверь Амстердам",
                    kind="door",
                    ok=True,
                    detail="active, пиров 4, онлайн 2",
                ),
            ),
            vpn_total=4,
            vpn_online=2,
            vpn_devices=(VpnDevice(label="10.8.1.5", online=True),),
        )
        self.ctx = ShopContext(
            store=self.store,
            plan=MONTH_PLAN,
            apk_path=None,
            payment_mode="off",
            now=NOW,
            admin_ids=frozenset({1001}),
            houses=lambda: self.snapshot,
        )

    def tearDown(self) -> None:
        self.store.close()
        os.unlink(self._db)

    def _handle(self, text: str, user_id: int = 1001, name: str = "Никита") -> list:
        return handle_update(_update(text, user_id=user_id, name=name), self.ctx)

    def test_stranger_admin_looks_like_unknown(self) -> None:
        actions = self._handle("/admin", user_id=2002)
        self.assertIn("Нажмите кнопку", actions[0].text)
        texts = [cell["text"] for row in actions[0].markup["keyboard"] for cell in row]
        self.assertNotIn(BUTTON_ADMIN, texts)

    def test_admin_start_shows_cabinet_button(self) -> None:
        actions = self._handle("/start")
        texts = [cell["text"] for row in actions[0].markup["keyboard"] for cell in row]
        self.assertIn(BUTTON_ADMIN, texts)

    def test_guest_start_hides_cabinet(self) -> None:
        guest = ShopContext(
            store=self.store,
            plan=MONTH_PLAN,
            payment_mode="off",
            now=NOW,
            admin_ids=frozenset({1001}),
        )
        actions = handle_update(_update("/start", user_id=2002), guest)
        texts = [cell["text"] for row in actions[0].markup["keyboard"] for cell in row]
        self.assertNotIn(BUTTON_ADMIN, texts)

    def test_admin_menu_and_stats(self) -> None:
        self._handle("/start", user_id=7, name="Гость")
        self._handle(BUTTON_ANDROID, user_id=7, name="Гость")
        home = self._handle("/admin")
        self.assertIn("Кабинет", home[0].text)
        self.assertIn("1001", home[0].text)
        texts = [cell["text"] for row in home[0].markup["keyboard"] for cell in row]
        self.assertEqual(
            texts,
            [BUTTON_ADMIN_STATS, BUTTON_ADMIN_CLIENTS, BUTTON_ADMIN_HOUSE, BUTTON_SHOP],
        )
        stats = self._handle(BUTTON_ADMIN_STATS)
        self.assertIn("витрин", stats[0].text.lower())
        self.assertIn("Android", stats[0].text)

    def test_admin_clients_lists_bot_visitors(self) -> None:
        self._handle("/start", user_id=7, name="Гость")
        self._handle(BUTTON_ANDROID, user_id=7, name="Гость")
        self._handle("/admin")
        actions = self._handle(BUTTON_ADMIN_CLIENTS)
        self.assertIn("Гость", actions[0].text)
        self.assertIn("10.8.1.5", actions[0].text)

    def test_admin_house_shows_office_and_door(self) -> None:
        self._handle("/admin")
        actions = self._handle(BUTTON_ADMIN_HOUSE)
        self.assertIn("Офис", actions[0].text)
        self.assertIn("касса отвечает", actions[0].text)
        self.assertIn("Дверь", actions[0].text)

    def test_shop_button_returns_storefront(self) -> None:
        self._handle("/admin")
        actions = self._handle(BUTTON_SHOP)
        self.assertIn("С какого телефона", actions[0].text)
        texts = [cell["text"] for row in actions[0].markup["keyboard"] for cell in row]
        self.assertIn(BUTTON_ANDROID, texts)
        self.assertIn(BUTTON_ADMIN, texts)

    def test_stranger_cannot_open_stats_by_button_text(self) -> None:
        actions = self._handle(BUTTON_ADMIN_STATS, user_id=2002)
        self.assertIn("Нажмите кнопку", actions[0].text)


if __name__ == "__main__":
    unittest.main()
