#!/usr/bin/env python3
"""RED/GREEN: запуск бота без токена и разбор chat_id."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot as bot_mod  # noqa: E402


class BotMainTest(unittest.TestCase):
    def setUp(self) -> None:
        self._token = os.environ.pop("NOVA_BOT_TOKEN", None)
        self._payments = os.environ.pop("NOVA_PAYMENTS", None)
        self._admins = os.environ.pop("NOVA_BOT_ADMIN_IDS", None)

    def tearDown(self) -> None:
        if self._token is not None:
            os.environ["NOVA_BOT_TOKEN"] = self._token
        else:
            os.environ.pop("NOVA_BOT_TOKEN", None)
        if self._payments is not None:
            os.environ["NOVA_PAYMENTS"] = self._payments
        else:
            os.environ.pop("NOVA_PAYMENTS", None)
        if self._admins is not None:
            os.environ["NOVA_BOT_ADMIN_IDS"] = self._admins
        else:
            os.environ.pop("NOVA_BOT_ADMIN_IDS", None)

    def test_main_without_token_exits_1(self) -> None:
        self.assertEqual(bot_mod.main(), 1)

    def test_load_context_rejects_unknown_payments(self) -> None:
        os.environ["NOVA_PAYMENTS"] = "yookassa"
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        os.environ["NOVA_BOT_DB"] = tmp.name
        try:
            with self.assertRaises(SystemExit):
                bot_mod.load_context()
        finally:
            os.unlink(tmp.name)
            os.environ.pop("NOVA_BOT_DB", None)

    def test_default_payments_is_off(self) -> None:
        os.environ.pop("NOVA_PAYMENTS", None)
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        os.environ["NOVA_BOT_DB"] = tmp.name
        try:
            ctx = bot_mod.load_context()
            self.assertEqual(ctx.payment_mode, "off")
            ctx.store.close()
        finally:
            os.unlink(tmp.name)
            os.environ.pop("NOVA_BOT_DB", None)

    def test_dev_payments_require_explicit_flag(self) -> None:
        os.environ["NOVA_PAYMENTS"] = "dev"
        os.environ.pop("NOVA_DEV_PAY", None)
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        os.environ["NOVA_BOT_DB"] = tmp.name
        try:
            with self.assertRaises(SystemExit):
                bot_mod.load_context()
        finally:
            os.unlink(tmp.name)
            os.environ.pop("NOVA_BOT_DB", None)

    def test_load_context_reads_admin_ids(self) -> None:
        os.environ["NOVA_BOT_ADMIN_IDS"] = "1001, 2002"
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        os.environ["NOVA_BOT_DB"] = tmp.name
        try:
            ctx = bot_mod.load_context()
            self.assertEqual(ctx.admin_ids, frozenset({1001, 2002}))
            ctx.store.close()
        finally:
            os.unlink(tmp.name)
            os.environ.pop("NOVA_BOT_DB", None)


class ChatIdTest(unittest.TestCase):
    def test_from_message(self) -> None:
        self.assertEqual(
            bot_mod.chat_id_of({"message": {"chat": {"id": 44}}}),
            44,
        )

    def test_from_pre_checkout(self) -> None:
        self.assertEqual(
            bot_mod.chat_id_of({"pre_checkout_query": {"from": {"id": 7}}}),
            7,
        )

    def test_empty_update(self) -> None:
        self.assertIsNone(bot_mod.chat_id_of({}))


class ConsumeUpdateTest(unittest.TestCase):
    def test_poison_update_still_advances_offset(self) -> None:
        class BoomApi:
            def dispatch(self, chat_id, actions):
                raise RuntimeError("handler exploded")

        offset = bot_mod.consume_update(
            BoomApi(),
            None,
            {
                "update_id": 50,
                "message": {
                    "from": {"id": 1, "first_name": "A"},
                    "chat": {"id": 1, "type": "private"},
                    "text": "/start",
                },
            },
            offset=10,
        )
        self.assertEqual(offset, 51)

    def test_missing_chat_still_advances_offset(self) -> None:
        class QuietApi:
            def dispatch(self, chat_id, actions):
                raise AssertionError("should not dispatch")

        offset = bot_mod.consume_update(
            QuietApi(),
            None,
            {"update_id": 7, "edited_message": {}},
            offset=1,
        )
        self.assertEqual(offset, 8)


if __name__ == "__main__":
    unittest.main()
