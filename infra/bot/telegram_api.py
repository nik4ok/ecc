"""Thin Telegram Bot API client. Token never logged."""
from __future__ import annotations

import json
import mimetypes
import socket
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from handlers import Document, Invoice, PreCheckoutAnswer, Reply, reply_keyboard


class TelegramApiError(RuntimeError):
    pass


_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_IPV4_INSTALLED = False


def telegram_addr_family(host: object, family: int) -> int:
    if _is_telegram_host(host) and family in (0, socket.AF_UNSPEC):
        return socket.AF_INET
    return family


def prefer_ipv4_for_telegram() -> None:
    global _IPV4_INSTALLED
    if _IPV4_INSTALLED:
        return

    def wrapped(host, port, family=0, type=0, proto=0, flags=0):
        chosen = telegram_addr_family(host, family)
        return _ORIGINAL_GETADDRINFO(host, port, chosen, type, proto, flags)

    socket.getaddrinfo = wrapped  # type: ignore[assignment]
    _IPV4_INSTALLED = True


def _is_telegram_host(host: object) -> bool:
    if not isinstance(host, str):
        return False
    name = host.lower().rstrip(".")
    return name == "api.telegram.org" or name.endswith(".telegram.org")

class TelegramApi:
    def __init__(self, token: str, timeout: int = 15) -> None:
        cleaned = (token or "").strip()
        if not cleaned:
            raise TelegramApiError("bot token is empty")
        prefer_ipv4_for_telegram()
        self._token = cleaned
        self._timeout = timeout

    def delete_webhook(self) -> None:
        self._call("deleteWebhook", {"drop_pending_updates": False})

    def get_updates(self, offset: int | None, timeout: int = 10) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": [
                "message",
                "pre_checkout_query",
            ],
        }
        if offset is not None:
            payload["offset"] = offset
        data = self._call("getUpdates", payload, http_timeout=timeout + 10)
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def send_message(
        self,
        chat_id: int,
        text: str,
        keyboard: bool = True,
        markup: dict[str, Any] | None = None,
    ) -> None:
        body: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if markup is not None:
            body["reply_markup"] = markup
        elif keyboard:
            body["reply_markup"] = reply_keyboard()
        self._call("sendMessage", body)

    def send_invoice(self, chat_id: int, invoice: Invoice) -> None:
        self._call(
            "sendInvoice",
            {
                "chat_id": chat_id,
                "title": invoice.title,
                "description": invoice.description,
                "payload": invoice.payload,
                "provider_token": "",
                "currency": invoice.currency,
                "prices": [{"label": invoice.title, "amount": invoice.amount}],
            },
        )

    def send_document(self, chat_id: int, document: Document) -> None:
        path = Path(document.path)
        if not path.is_file():
            raise TelegramApiError(f"apk file is missing: {path}")
        boundary = uuid.uuid4().hex
        fields = {
            "chat_id": str(chat_id),
            "caption": document.caption,
            "filename": path.name,
        }
        body = _multipart(boundary, fields, file_field="document", file_path=path)
        request = Request(
            self._url("sendDocument"),
            data=body,
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        self._open(request)

    def answer_pre_checkout(self, answer: PreCheckoutAnswer) -> None:
        payload: dict[str, Any] = {
            "pre_checkout_query_id": answer.query_id,
            "ok": answer.ok,
        }
        if not answer.ok and answer.error_message:
            payload["error_message"] = answer.error_message
        self._call("answerPreCheckoutQuery", payload)

    def dispatch(self, chat_id: int, actions: list[object]) -> None:
        for action in actions:
            if isinstance(action, Reply):
                self.send_message(
                    chat_id,
                    action.text,
                    keyboard=action.keyboard,
                    markup=action.markup,
                )
            elif isinstance(action, Invoice):
                self.send_invoice(chat_id, action)
            elif isinstance(action, Document):
                self.send_document(chat_id, action)
            elif isinstance(action, PreCheckoutAnswer):
                self.answer_pre_checkout(action)

    def _call(self, method: str, payload: dict[str, Any], http_timeout: int | None = None) -> Any:
        request = Request(
            self._url(method),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        return self._open(request, timeout=http_timeout)

    def _open(self, request: Request, timeout: int | None = None) -> Any:
        seconds = self._timeout if timeout is None else timeout
        try:
            with urlopen(request, timeout=seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TelegramApiError(
                f"Telegram HTTP {exc.code}: {self._redact(detail[:200])}"
            ) from None
        except URLError as exc:
            raise TelegramApiError("Telegram is unreachable") from exc
        except json.JSONDecodeError as exc:
            raise TelegramApiError("Telegram returned invalid JSON") from exc
        except (TimeoutError, socket.timeout):
            raise TelegramApiError("Telegram timed out") from None
        if not isinstance(raw, dict) or not raw.get("ok"):
            raise TelegramApiError("Telegram rejected the request")
        return raw.get("result")

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "<token>")


def _multipart(
    boundary: str,
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
) -> bytes:
    chunks: list[bytes] = []
    for key, value in fields.items():
        if key == "filename":
            continue
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
        )
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")
    filename = fields.get("filename") or file_path.name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(file_path.read_bytes())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)
