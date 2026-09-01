"""Pure Telegram shop handlers. No HTTP, no Bot API."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Union

from shop import (
    MONTH_PLAN,
    EntitlementStore,
    Plan,
    format_ru_date,
    make_invoice_payload,
    parse_invoice_payload,
)

BUTTON_PAY = "Оплатить"
BUTTON_DOWNLOAD = "Скачать NOVA"
BUTTON_STATUS = "Мой статус"

START_TEXT = (
    "NOVA — защита телефона без Google Play.\n\n"
    "Как это работает:\n"
    "1. Оплатите 30 дней\n"
    "2. Скачайте приложение\n"
    "3. Установите файл. Кнопка в чате VPN не включает — его включает NOVA "
    "на телефоне.\n\n"
    "Android спросит разрешение VPN при первом включении."
)

PAY_FIRST_TEXT = "Сначала оплатите 30 дней. После оплаты откроется скачивание приложения."
NO_SUB_TEXT = "Подписки нет. Нажмите «Оплатить»."
APK_MISSING_TEXT = (
    "Подписка активна, но сборка ещё не лежит на сервере. "
    "Напишите нам — загрузим APK."
)
INSTALL_CAPTION = (
    "Разрешите установку из Telegram → откройте файл → при первом включении "
    "Android спросит разрешение VPN."
)
UNKNOWN_TEXT = "Нажмите кнопку ниже: оплатить, скачать приложение или посмотреть статус."
PRECHECK_BAD_AMOUNT = "Счёт не совпал. Нажмите «Оплатить» ещё раз."
PRECHECK_BAD_PAYLOAD = "Этот счёт вам не принадлежит. Нажмите «Оплатить» ещё раз."
PAYMENT_OK_TEXT = "Оплата прошла. Дальше установите NOVA с телефона."


@dataclass(frozen=True)
class Reply:
    text: str
    keyboard: bool = True


@dataclass(frozen=True)
class Invoice:
    title: str
    description: str
    payload: str
    amount: int
    currency: str = "XTR"


@dataclass(frozen=True)
class Document:
    path: str
    caption: str


@dataclass(frozen=True)
class PreCheckoutAnswer:
    query_id: str
    ok: bool
    error_message: str | None = None


Action = Union[Reply, Invoice, Document, PreCheckoutAnswer]


@dataclass
class ShopContext:
    store: EntitlementStore
    plan: Plan = MONTH_PLAN
    apk_path: Path | None = None
    payment_mode: str = "stars"
    now: datetime | None = None
    nonce_factory: Callable[[], str] = field(default=lambda: secrets.token_hex(8))

    def clock(self) -> datetime:
        return self.now or datetime.now(timezone.utc)


def reply_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [
            [{"text": BUTTON_PAY}],
            [{"text": BUTTON_DOWNLOAD}],
            [{"text": BUTTON_STATUS}],
        ],
        "resize_keyboard": True,
    }


def handle_update(update: dict[str, Any], ctx: ShopContext) -> list[Action]:
    pre = update.get("pre_checkout_query")
    if isinstance(pre, dict):
        return [_pre_checkout(pre, ctx)]

    message = update.get("message")
    if not isinstance(message, dict):
        return []

    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_type = str(chat.get("type") or "private")
    if chat_type != "private":
        return []

    user = message.get("from") if isinstance(message.get("from"), dict) else {}
    try:
        user_id = int(user.get("id"))
    except (TypeError, ValueError):
        return []
    name = str(user.get("first_name") or "")

    payment = message.get("successful_payment")
    if isinstance(payment, dict):
        return _successful_payment(user_id, name, payment, ctx)

    text = str(message.get("text") or "").strip()
    command = _command_name(text)
    if command in {"start", "help"} or text == "":
        return [Reply(START_TEXT)]
    if command == "pay" or text == BUTTON_PAY:
        return _pay(user_id, name, ctx)
    if command == "download" or text == BUTTON_DOWNLOAD:
        return _download(user_id, ctx)
    if command == "status" or text == BUTTON_STATUS:
        return _status(user_id, ctx)
    return [Reply(UNKNOWN_TEXT)]


def _pay(user_id: int, name: str, ctx: ShopContext) -> list[Action]:
    mode = (ctx.payment_mode or "stars").strip().lower()
    if mode == "dev":
        ctx.store.grant(user_id, days=ctx.plan.days, now=ctx.clock(), display_name=name)
        return [Reply(PAYMENT_OK_TEXT), *_apk_actions(ctx)]
    if mode != "stars":
        return [Reply("Оплата временно недоступна. Напишите нам.")]
    payload = make_invoice_payload(
        telegram_id=user_id,
        plan_id=ctx.plan.id,
        nonce=ctx.nonce_factory(),
    )
    return [
        Invoice(
            title=ctx.plan.title,
            description=ctx.plan.description,
            payload=payload,
            amount=ctx.plan.stars,
        )
    ]


def _download(user_id: int, ctx: ShopContext) -> list[Action]:
    if not ctx.store.has_access(user_id, now=ctx.clock()):
        return [Reply(PAY_FIRST_TEXT)]
    return _apk_actions(ctx)


def _apk_actions(ctx: ShopContext) -> list[Action]:
    path = ctx.apk_path
    if path is None or not path.is_file():
        return [Reply(APK_MISSING_TEXT)]
    return [Document(path=str(path), caption=INSTALL_CAPTION)]


def _status(user_id: int, ctx: ShopContext) -> list[Action]:
    row = ctx.store.get(user_id)
    if row is None or not ctx.store.has_access(user_id, now=ctx.clock()):
        return [Reply(NO_SUB_TEXT)]
    until = datetime.fromisoformat(row["paid_until"])
    return [Reply(f"Подписка активна до {format_ru_date(until)}.")]


def _successful_payment(
    user_id: int,
    name: str,
    payment: dict[str, Any],
    ctx: ShopContext,
) -> list[Action]:
    charge_id = str(payment.get("telegram_payment_charge_id") or "").strip()
    if not charge_id:
        charge_id = f"payload:{payment.get('invoice_payload') or ''}"
    ctx.store.apply_payment(
        telegram_id=user_id,
        days=ctx.plan.days,
        now=ctx.clock(),
        display_name=name,
        charge_id=charge_id,
    )
    return [Reply(PAYMENT_OK_TEXT), *_apk_actions(ctx)]


def _pre_checkout(query: dict[str, Any], ctx: ShopContext) -> PreCheckoutAnswer:
    query_id = str(query.get("id") or "")
    user = query.get("from") if isinstance(query.get("from"), dict) else {}
    try:
        user_id = int(user.get("id"))
    except (TypeError, ValueError):
        return PreCheckoutAnswer(query_id=query_id, ok=False, error_message=PRECHECK_BAD_PAYLOAD)
    parsed = parse_invoice_payload(str(query.get("invoice_payload") or ""))
    if parsed is None or parsed.telegram_id != user_id or parsed.plan_id != ctx.plan.id:
        return PreCheckoutAnswer(query_id=query_id, ok=False, error_message=PRECHECK_BAD_PAYLOAD)
    amount = query.get("total_amount")
    currency = str(query.get("currency") or "")
    if amount != ctx.plan.stars or currency != "XTR":
        return PreCheckoutAnswer(query_id=query_id, ok=False, error_message=PRECHECK_BAD_AMOUNT)
    return PreCheckoutAnswer(query_id=query_id, ok=True)


def _command_name(text: str) -> str:
    if not text.startswith("/"):
        return ""
    token = text.split()[0][1:]
    return token.split("@", 1)[0].lower()
