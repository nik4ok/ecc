#!/usr/bin/env python3
"""RED/GREEN: Bot API wrapper without a live Telegram token."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from handlers import Document, Invoice, PreCheckoutAnswer, Reply  # noqa: E402
from telegram_api import TelegramApi, TelegramApiError  # noqa: E402


class TelegramApiTest(unittest.TestCase):
    def test_empty_token_rejected(self) -> None:
        with self.assertRaises(TelegramApiError):
            TelegramApi("  ")

    def test_dispatch_routes_actions(self) -> None:
        api = TelegramApi("123:test")
        seen: list[tuple] = []
        api.send_message = lambda chat_id, text, keyboard=True: seen.append(
            ("message", chat_id, text, keyboard)
        )
        api.send_invoice = lambda chat_id, invoice: seen.append(("invoice", chat_id, invoice.payload))
        api.send_document = lambda chat_id, document: seen.append(("document", chat_id, document.path))
        api.answer_pre_checkout = lambda answer: seen.append(("pre", answer.query_id, answer.ok))
        invoice = Invoice(title="t", description="d", payload="nova:month:1:x", amount=1)
        document = Document(path="/tmp/x.apk", caption="c")
        api.dispatch(
            9,
            [
                Reply("hi"),
                invoice,
                document,
                PreCheckoutAnswer(query_id="q", ok=True),
            ],
        )
        self.assertEqual(
            seen,
            [
                ("message", 9, "hi", True),
                ("invoice", 9, "nova:month:1:x"),
                ("document", 9, "/tmp/x.apk"),
                ("pre", "q", True),
            ],
        )

    def test_send_document_missing_file_fails_fast(self) -> None:
        api = TelegramApi("123:test")
        with self.assertRaises(TelegramApiError):
            api.send_document(1, Document(path="/tmp/nova-no-such.apk", caption="x"))

    def test_http_error_redacts_token(self) -> None:
        import io
        from unittest.mock import patch
        from urllib.error import HTTPError

        token = "SECRETTOKEN"
        api = TelegramApi(token)

        def boom(_request, timeout=0):
            raise HTTPError(
                f"https://api.telegram.org/bot{token}/sendMessage",
                404,
                "Not Found",
                hdrs=None,
                fp=io.BytesIO(f"bot{token}".encode("utf-8")),
            )

        with patch("telegram_api.urlopen", boom):
            with self.assertRaises(TelegramApiError) as err:
                api.send_message(1, "hi")
        self.assertNotIn(token, str(err.exception))

    def test_multipart_includes_file_bytes(self) -> None:
        from telegram_api import _multipart

        tmp = tempfile.NamedTemporaryFile(suffix=".apk", delete=False)
        tmp.write(b"APKDATA")
        tmp.close()
        try:
            body = _multipart(
                "bnd",
                {"chat_id": "1", "caption": "hi", "filename": "NOVA.apk"},
                file_field="document",
                file_path=Path(tmp.name),
            )
        finally:
            os.unlink(tmp.name)
        self.assertIn(b"APKDATA", body)
        self.assertIn(b"NOVA.apk", body)
        self.assertIn(b'name="chat_id"', body)


if __name__ == "__main__":
    unittest.main()
