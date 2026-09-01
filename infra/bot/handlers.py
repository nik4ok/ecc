"""Pure Telegram shop handlers. No HTTP, no Bot API."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Union

from messages import (
    ANDROID_READY,
    APK_MISSING,
    BUTTON_ANDROID,
    BUTTON_DOWNLOAD,
    BUTTON_IOS,
    BUTTON_PAY,
    BUTTON_REPORT,
    BUTTON_STATUS,
    DOWNLOAD_IOS,
    DOWNLOAD_NEED_OS,
    INSTALL_CAPTION,
    IOS_WAIT,
    NO_SUB,
    PAY_FIRST,
    PAY_IOS,
    PAY_OFF,
    PAYMENT_OK,
    PRECHECK_BAD_AMOUNT,
    PRECHECK_BAD_PAYLOAD,
    REPORT_LIMIT,
    REPORT_PROMPT,
    REPORT_THANKS,
    REPORT_TOO_SHORT,
    DOWNLOAD_IOS,
    DOWNLOAD_NEED_OS,
    INSTALL_CAPTION,
    IOS_WAIT,
    NO_SUB,
    PAY_FIRST,
    PAY_IOS,
    PAY_OFF,
    PAYMENT_OK,
    PRECHECK_BAD_AMOUNT,
    PRECHECK_BAD_PAYLOAD,
    START_ANON,
    START_NAMED,
    STATUS_OFF,
    UNKNOWN,
)
from shop import (
    MONTH_PLAN,
    OS_ANDROID,
    OS_IOS,
    EntitlementStore,
    Plan,
    format_ru_date,
    make_invoice_payload,
    parse_invoice_payload,
)


@dataclass(frozen=True)
class Reply:
    text: str
    keyboard: bool = True
    markup: dict[str, Any] | None = None


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
    payment_mode: str = "off"
    now: datetime | None = None
    nonce_factory: Callable[[], str] = field(default=lambda: secrets.token_hex(8))

    def clock(self) -> datetime:
        return self.now or datetime.now(timezone.utc)


def picker_keyboard() -> dict[str, Any]:
    return _keyboard([[BUTTON_ANDROID], [BUTTON_IOS], [BUTTON_REPORT]])


def android_keyboard() -> dict[str, Any]:
    return _keyboard(
        [
            [BUTTON_DOWNLOAD],
            [BUTTON_PAY],
            [BUTTON_STATUS],
            [BUTTON_IOS],
            [BUTTON_REPORT],
        ]
    )


def ios_keyboard() -> dict[str, Any]:
    return _keyboard(
        [
            [BUTTON_DOWNLOAD],
            [BUTTON_PAY],
            [BUTTON_STATUS],
            [BUTTON_ANDROID],
            [BUTTON_REPORT],
        ]
    )


def reply_keyboard() -> dict[str, Any]:
    return picker_keyboard()


def keyboard_for(os_name: str | None) -> dict[str, Any]:
    if os_name == OS_ANDROID:
        return android_keyboard()
    if os_name == OS_IOS:
        return ios_keyboard()
    return picker_keyboard()


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
    os_name = _os_of(ctx, user_id)
    if command in {"start", "help"} or text == "":
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        return [_reply(start_text(name), None)]
    if text == BUTTON_ANDROID:
        ctx.store.set_os(user_id, OS_ANDROID, now=ctx.clock(), display_name=name)
        return [_reply(ANDROID_READY, OS_ANDROID)]
    if text == BUTTON_IOS:
        ctx.store.set_os(user_id, OS_IOS, now=ctx.clock(), display_name=name)
        return [_reply(IOS_WAIT, OS_IOS)]
    if command == "report" or text == BUTTON_REPORT:
        return _begin_report(user_id, name, os_name, ctx)
    if command == "pay" or text == BUTTON_PAY:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        return _pay(user_id, name, os_name, ctx)
    if command == "download" or text == BUTTON_DOWNLOAD:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        return _download(user_id, os_name, ctx)
    if command == "status" or text == BUTTON_STATUS:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        return _status(user_id, os_name, ctx)
    if ctx.store.is_awaiting_report(user_id):
        return _capture_report(user_id, name, os_name, text, ctx)
    return [_reply(UNKNOWN, os_name)]


def start_text(name: str) -> str:
    cleaned = _safe_name(name)
    if cleaned:
        return START_NAMED.format(name=cleaned)
    return START_ANON


def _begin_report(
    user_id: int,
    name: str,
    os_name: str | None,
    ctx: ShopContext,
) -> list[Action]:
    day_ago = ctx.clock() - timedelta(days=1)
    if ctx.store.count_reports_since(user_id, day_ago) >= 5:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        return [_reply(REPORT_LIMIT, os_name)]
    ctx.store.set_awaiting_report(user_id, True, now=ctx.clock(), display_name=name)
    return [_reply(REPORT_PROMPT, os_name)]


def _capture_report(
    user_id: int,
    name: str,
    os_name: str | None,
    text: str,
    ctx: ShopContext,
) -> list[Action]:
    try:
        ctx.store.add_report(
            telegram_id=user_id,
            body=text,
            now=ctx.clock(),
            display_name=name,
            os_name=os_name,
        )
    except ValueError:
        return [_reply(REPORT_TOO_SHORT, os_name)]
    return [_reply(REPORT_THANKS, os_name)]


def _pay(user_id: int, name: str, os_name: str | None, ctx: ShopContext) -> list[Action]:
    if os_name is None:
        return [_reply(DOWNLOAD_NEED_OS, None)]
    if os_name == OS_IOS:
        return [_reply(PAY_IOS, OS_IOS)]
    mode = (ctx.payment_mode or "off").strip().lower()
    if mode == "off":
        return [_reply(PAY_OFF, OS_ANDROID)]
    if mode == "dev":
        ctx.store.grant(user_id, days=ctx.plan.days, now=ctx.clock(), display_name=name)
        return [_reply(PAYMENT_OK, OS_ANDROID), *_apk_actions(ctx)]
    if mode != "stars":
        return [_reply(PAY_OFF, OS_ANDROID)]
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


def _download(user_id: int, os_name: str | None, ctx: ShopContext) -> list[Action]:
    if os_name is None:
        return [_reply(DOWNLOAD_NEED_OS, None)]
    if os_name == OS_IOS:
        return [_reply(DOWNLOAD_IOS, OS_IOS)]
    mode = (ctx.payment_mode or "off").strip().lower()
    if mode in {"stars", "dev"} and not ctx.store.has_access(user_id, now=ctx.clock()):
        return [_reply(PAY_FIRST, OS_ANDROID)]
    return _apk_actions(ctx)


def _apk_actions(ctx: ShopContext) -> list[Action]:
    path = ctx.apk_path
    if path is None or not path.is_file():
        return [_reply(APK_MISSING, OS_ANDROID)]
    return [Document(path=str(path), caption=INSTALL_CAPTION)]


def _status(user_id: int, os_name: str | None, ctx: ShopContext) -> list[Action]:
    if os_name is None:
        return [_reply(DOWNLOAD_NEED_OS, None)]
    row = ctx.store.get(user_id)
    if row is not None and ctx.store.has_access(user_id, now=ctx.clock()):
        until = datetime.fromisoformat(row["paid_until"])
        return [_reply(f"Подписка активна до {format_ru_date(until)}.", os_name)]
    mode = (ctx.payment_mode or "off").strip().lower()
    if mode == "off":
        return [_reply(STATUS_OFF, os_name)]
    return [_reply(NO_SUB, os_name)]


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
    os_name = _os_of(ctx, user_id) or OS_ANDROID
    if os_name == OS_IOS:
        return [_reply(PAYMENT_OK, OS_IOS)]
    return [_reply(PAYMENT_OK, OS_ANDROID), *_apk_actions(ctx)]


def _pre_checkout(query: dict[str, Any], ctx: ShopContext) -> PreCheckoutAnswer:
    query_id = str(query.get("id") or "")
    user = query.get("from") if isinstance(query.get("from"), dict) else {}
    try:
        user_id = int(user.get("id"))
    except (TypeError, ValueError):
        return PreCheckoutAnswer(query_id=query_id, ok=False, error_message=PRECHECK_BAD_PAYLOAD)
    if _os_of(ctx, user_id) == OS_IOS:
        return PreCheckoutAnswer(query_id=query_id, ok=False, error_message=PAY_IOS)
    parsed = parse_invoice_payload(str(query.get("invoice_payload") or ""))
    if parsed is None or parsed.telegram_id != user_id or parsed.plan_id != ctx.plan.id:
        return PreCheckoutAnswer(query_id=query_id, ok=False, error_message=PRECHECK_BAD_PAYLOAD)
    amount = query.get("total_amount")
    currency = str(query.get("currency") or "")
    if amount != ctx.plan.stars or currency != "XTR":
        return PreCheckoutAnswer(query_id=query_id, ok=False, error_message=PRECHECK_BAD_AMOUNT)
    return PreCheckoutAnswer(query_id=query_id, ok=True)


def _os_of(ctx: ShopContext, user_id: int) -> str | None:
    profile = ctx.store.get_profile(user_id)
    if profile is None:
        return None
    os_name = profile.get("os")
    if os_name in {OS_ANDROID, OS_IOS}:
        return str(os_name)
    return None


def _reply(text: str, os_name: str | None) -> Reply:
    return Reply(text=text, keyboard=True, markup=keyboard_for(os_name))


def _safe_name(name: str) -> str:
    cleaned = "".join(ch for ch in (name or "").strip() if ch.isprintable())
    cleaned = cleaned.replace("\n", "").replace("\r", "")
    return cleaned[:32]


def _keyboard(rows: list) -> dict[str, Any]:
    normalized = []
    for row in rows:
        cells = []
        for cell in row:
            if isinstance(cell, str):
                cells.append({"text": cell})
            else:
                cells.append(cell)
        normalized.append(cells)
    return {"keyboard": normalized, "resize_keyboard": True}


def _command_name(text: str) -> str:
    if not text.startswith("/"):
        return ""
    token = text.split()[0][1:]
    return token.split("@", 1)[0].lower()
