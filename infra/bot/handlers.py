"""Pure Telegram shop handlers. No HTTP, no Bot API."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Union

from houses import HouseSnapshot, HouseStatus
from messages import (
    ADMIN_HOME,
    ADMIN_HOUSE_UNSET,
    ANDROID_READY,
    APK_MISSING,
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
HouseProbe = Callable[[], HouseSnapshot]


@dataclass
class ShopContext:
    store: EntitlementStore
    plan: Plan = MONTH_PLAN
    apk_path: Path | None = None
    payment_mode: str = "off"
    now: datetime | None = None
    nonce_factory: Callable[[], str] = field(default=lambda: secrets.token_hex(8))
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    houses: HouseProbe | None = None

    def clock(self) -> datetime:
        return self.now or datetime.now(timezone.utc)


def picker_keyboard(*, admin: bool = False) -> dict[str, Any]:
    rows = [[BUTTON_ANDROID], [BUTTON_IOS], [BUTTON_REPORT]]
    if admin:
        rows.append([BUTTON_ADMIN])
    return _keyboard(rows)


def android_keyboard(*, admin: bool = False) -> dict[str, Any]:
    rows = [
        [BUTTON_DOWNLOAD],
        [BUTTON_PAY],
        [BUTTON_STATUS],
        [BUTTON_IOS],
        [BUTTON_REPORT],
    ]
    if admin:
        rows.append([BUTTON_ADMIN])
    return _keyboard(rows)


def ios_keyboard(*, admin: bool = False) -> dict[str, Any]:
    rows = [
        [BUTTON_DOWNLOAD],
        [BUTTON_PAY],
        [BUTTON_STATUS],
        [BUTTON_ANDROID],
        [BUTTON_REPORT],
    ]
    if admin:
        rows.append([BUTTON_ADMIN])
    return _keyboard(rows)


def admin_keyboard() -> dict[str, Any]:
    return _keyboard(
        [
            [BUTTON_ADMIN_STATS],
            [BUTTON_ADMIN_CLIENTS],
            [BUTTON_ADMIN_HOUSE],
            [BUTTON_SHOP],
        ]
    )


def reply_keyboard() -> dict[str, Any]:
    return picker_keyboard()


def keyboard_for(os_name: str | None, *, admin: bool = False) -> dict[str, Any]:
    if os_name == OS_ANDROID:
        return android_keyboard(admin=admin)
    if os_name == OS_IOS:
        return ios_keyboard(admin=admin)
    return picker_keyboard(admin=admin)


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
    admin = _is_admin(ctx, user_id)

    payment = message.get("successful_payment")
    if isinstance(payment, dict):
        actions = _successful_payment(user_id, name, payment, ctx)
        _track(ctx, user_id, user, "payment")
        return actions

    text = str(message.get("text") or "").strip()
    command = _command_name(text)
    os_name = _os_of(ctx, user_id)

    if admin and (command == "admin" or text == BUTTON_ADMIN):
        _track(ctx, user_id, user, "admin", os_name)
        return [_cabinet(user_id, ctx)]
    if admin and text == BUTTON_ADMIN_STATS:
        _track(ctx, user_id, user, "admin_stats", os_name)
        return [_admin_stats(ctx)]
    if admin and text == BUTTON_ADMIN_CLIENTS:
        _track(ctx, user_id, user, "admin_clients", os_name)
        return [_admin_clients(ctx)]
    if admin and text == BUTTON_ADMIN_HOUSE:
        _track(ctx, user_id, user, "admin_house", os_name)
        return [_admin_house(ctx)]
    if admin and text == BUTTON_SHOP:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        _track(ctx, user_id, user, "shop", os_name)
        return [_reply(start_text(name), None, admin=True)]

    if command in {"start", "help"} or text == "":
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        _track(ctx, user_id, user, "start", os_name)
        return [_reply(start_text(name), None, admin=admin)]
    if text == BUTTON_ANDROID:
        ctx.store.set_os(user_id, OS_ANDROID, now=ctx.clock(), display_name=name)
        _track(ctx, user_id, user, "android", OS_ANDROID)
        return [_reply(ANDROID_READY, OS_ANDROID, admin=admin)]
    if text == BUTTON_IOS:
        ctx.store.set_os(user_id, OS_IOS, now=ctx.clock(), display_name=name)
        _track(ctx, user_id, user, "ios", OS_IOS)
        return [_reply(IOS_WAIT, OS_IOS, admin=admin)]
    if command == "report" or text == BUTTON_REPORT:
        _track(ctx, user_id, user, "report", os_name)
        return _begin_report(user_id, name, os_name, ctx)
    if command == "pay" or text == BUTTON_PAY:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        _track(ctx, user_id, user, "pay", os_name)
        return _pay(user_id, name, os_name, ctx)
    if command == "download" or text == BUTTON_DOWNLOAD:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        _track(ctx, user_id, user, "download", os_name)
        return _download(user_id, os_name, ctx)
    if command == "status" or text == BUTTON_STATUS:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        _track(ctx, user_id, user, "status", os_name)
        return _status(user_id, os_name, ctx)
    if ctx.store.is_awaiting_report(user_id):
        _track(ctx, user_id, user, "report_saved", os_name)
        return _capture_report(user_id, name, os_name, text, ctx)
    _track(ctx, user_id, user, "unknown", os_name)
    return [_reply(UNKNOWN, os_name, admin=admin)]


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
    admin = _is_admin(ctx, user_id)
    day_ago = ctx.clock() - timedelta(days=1)
    if ctx.store.count_reports_since(user_id, day_ago) >= 5:
        ctx.store.set_awaiting_report(user_id, False, now=ctx.clock(), display_name=name)
        return [_reply(REPORT_LIMIT, os_name, admin=admin)]
    ctx.store.set_awaiting_report(user_id, True, now=ctx.clock(), display_name=name)
    return [_reply(REPORT_PROMPT, os_name, admin=admin)]


def _capture_report(
    user_id: int,
    name: str,
    os_name: str | None,
    text: str,
    ctx: ShopContext,
) -> list[Action]:
    admin = _is_admin(ctx, user_id)
    try:
        ctx.store.add_report(
            telegram_id=user_id,
            body=text,
            now=ctx.clock(),
            display_name=name,
            os_name=os_name,
        )
    except ValueError:
        return [_reply(REPORT_TOO_SHORT, os_name, admin=admin)]
    return [_reply(REPORT_THANKS, os_name, admin=admin)]


def _pay(user_id: int, name: str, os_name: str | None, ctx: ShopContext) -> list[Action]:
    admin = _is_admin(ctx, user_id)
    if os_name is None:
        return [_reply(DOWNLOAD_NEED_OS, None, admin=admin)]
    if os_name == OS_IOS:
        return [_reply(PAY_IOS, OS_IOS, admin=admin)]
    mode = (ctx.payment_mode or "off").strip().lower()
    if mode == "off":
        return [_reply(PAY_OFF, OS_ANDROID, admin=admin)]
    if mode == "dev":
        ctx.store.grant(user_id, days=ctx.plan.days, now=ctx.clock(), display_name=name)
        return [_reply(PAYMENT_OK, OS_ANDROID, admin=admin), *_apk_actions(ctx, user_id)]
    if mode != "stars":
        return [_reply(PAY_OFF, OS_ANDROID, admin=admin)]
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
    admin = _is_admin(ctx, user_id)
    if os_name is None:
        return [_reply(DOWNLOAD_NEED_OS, None, admin=admin)]
    if os_name == OS_IOS:
        return [_reply(DOWNLOAD_IOS, OS_IOS, admin=admin)]
    mode = (ctx.payment_mode or "off").strip().lower()
    if mode in {"stars", "dev"} and not ctx.store.has_access(user_id, now=ctx.clock()):
        return [_reply(PAY_FIRST, OS_ANDROID, admin=admin)]
    return _apk_actions(ctx, user_id)


def _apk_actions(ctx: ShopContext, user_id: int) -> list[Action]:
    path = ctx.apk_path
    admin = _is_admin(ctx, user_id)
    if path is None or not path.is_file():
        return [_reply(APK_MISSING, OS_ANDROID, admin=admin)]
    return [Document(path=str(path), caption=INSTALL_CAPTION)]


def _status(user_id: int, os_name: str | None, ctx: ShopContext) -> list[Action]:
    admin = _is_admin(ctx, user_id)
    if os_name is None:
        return [_reply(DOWNLOAD_NEED_OS, None, admin=admin)]
    row = ctx.store.get(user_id)
    if row is not None and ctx.store.has_access(user_id, now=ctx.clock()):
        until = datetime.fromisoformat(row["paid_until"])
        return [_reply(f"Подписка активна до {format_ru_date(until)}.", os_name, admin=admin)]
    mode = (ctx.payment_mode or "off").strip().lower()
    if mode == "off":
        return [_reply(STATUS_OFF, os_name, admin=admin)]
    return [_reply(NO_SUB, os_name, admin=admin)]


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
    admin = _is_admin(ctx, user_id)
    if os_name == OS_IOS:
        return [_reply(PAYMENT_OK, OS_IOS, admin=admin)]
    return [_reply(PAYMENT_OK, OS_ANDROID, admin=admin), *_apk_actions(ctx, user_id)]


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


def _cabinet(user_id: int, ctx: ShopContext) -> Reply:
    return Reply(
        text=ADMIN_HOME.format(telegram_id=user_id),
        keyboard=True,
        markup=admin_keyboard(),
    )


def _admin_stats(ctx: ShopContext) -> Reply:
    stats = ctx.store.shop_stats(now=ctx.clock())
    text = (
        "Витрина за сутки\n\n"
        f"Людей всего: {stats['visitors']}\n"
        f"Заходили за 24 ч: {stats['visitors_recent']}\n"
        f"Android: {stats['android']} · iPhone: {stats['ios']} · "
        f"телефон не выбрали: {stats['unknown_os']}\n"
        f"Скачиваний за сутки: {stats['downloads_recent']}\n"
        f"Жалоб всего: {stats['reports_total']}, за сутки: {stats['reports_recent']}"
    )
    return Reply(text=text, keyboard=True, markup=admin_keyboard())


def _admin_clients(ctx: ShopContext) -> Reply:
    visitors = ctx.store.list_recent_visitors(limit=10)
    lines = ["Кто писал боту"]
    if not visitors:
        lines.append("Пока никого.")
    else:
        for row in visitors:
            lines.append(_visitor_line(row))
    snapshot = _house_snapshot(ctx)
    lines.append("")
    lines.append("VPN на двери")
    if snapshot is None:
        lines.append("Касса не настроена — устройств не видно.")
    elif not snapshot.vpn_devices:
        if snapshot.office.ok:
            lines.append(
                f"В книге {snapshot.vpn_total}, онлайн {snapshot.vpn_online}. "
                "Список адресов пуст."
            )
        else:
            lines.append("Касса не ответила на книгу.")
    else:
        lines.append(f"В книге {snapshot.vpn_total}, онлайн {snapshot.vpn_online}.")
        for device in snapshot.vpn_devices[:12]:
            state = "онлайн" if device.online else "офлайн"
            lines.append(f"• {device.label} — {state}")
    return Reply(text="\n".join(lines), keyboard=True, markup=admin_keyboard())


def _admin_house(ctx: ShopContext) -> Reply:
    snapshot = _house_snapshot(ctx)
    if snapshot is None:
        return Reply(text=ADMIN_HOUSE_UNSET, keyboard=True, markup=admin_keyboard())
    lines = [
        snapshot.office.name,
        snapshot.office.detail,
        "",
    ]
    if not snapshot.doors:
        lines.append("Дверь: касса не отдала список нод.")
    else:
        for door in snapshot.doors:
            lines.append(door.name)
            lines.append(door.detail)
            lines.append("")
    return Reply(text="\n".join(lines).strip(), keyboard=True, markup=admin_keyboard())


def _house_snapshot(ctx: ShopContext) -> HouseSnapshot | None:
    probe = ctx.houses
    if probe is None:
        return None
    try:
        return probe()
    except Exception:
        return HouseSnapshot(
            office=HouseStatus(
                name="Офис",
                kind="office",
                ok=False,
                detail="не отвечает",
            ),
            doors=(),
            vpn_total=0,
            vpn_online=0,
            vpn_devices=(),
        )


def _visitor_line(row: dict[str, Any]) -> str:
    name = str(row.get("display_name") or "").strip() or "без имени"
    handle = str(row.get("username") or "").strip()
    nick = f" @{handle}" if handle else ""
    os_name = row.get("os")
    if os_name == OS_ANDROID:
        phone = "Android"
    elif os_name == OS_IOS:
        phone = "iPhone"
    else:
        phone = "телефон не выбрали"
    return f"• {name}{nick} — {phone}"


def _track(
    ctx: ShopContext,
    user_id: int,
    user: dict[str, Any],
    action: str,
    os_name: str | None = None,
) -> None:
    try:
        ctx.store.remember_visit(
            user_id,
            now=ctx.clock(),
            display_name=str(user.get("first_name") or ""),
            username=str(user.get("username") or ""),
            language_code=str(user.get("language_code") or ""),
            action=action,
            os_name=os_name,
        )
    except Exception:
        return


def _is_admin(ctx: ShopContext, user_id: int) -> bool:
    return user_id in ctx.admin_ids


def _os_of(ctx: ShopContext, user_id: int) -> str | None:
    profile = ctx.store.get_profile(user_id)
    if profile is None:
        return None
    os_name = profile.get("os")
    if os_name in {OS_ANDROID, OS_IOS}:
        return str(os_name)
    return None


def _reply(text: str, os_name: str | None, *, admin: bool = False) -> Reply:
    return Reply(text=text, keyboard=True, markup=keyboard_for(os_name, admin=admin))


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
