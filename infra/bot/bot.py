#!/usr/bin/env python3
"""NOVA Telegram shop: pay → APK → status. VPN stays in the Android app."""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from handlers import ShopContext, handle_update
from houses import CashierHouseProbe
from shop import EntitlementStore, parse_admin_ids, plan_from_env
from telegram_api import TelegramApi, TelegramApiError

LOG = logging.getLogger("nova.bot")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def load_context() -> ShopContext:
    db_path = os.environ.get("NOVA_BOT_DB", str(Path(__file__).resolve().parent / "shop.db"))
    apk_raw = os.environ.get("NOVA_APK_PATH", "").strip()
    mode = os.environ.get("NOVA_PAYMENTS", "off").strip().lower() or "off"
    if mode not in {"off", "stars", "dev"}:
        raise SystemExit("NOVA_PAYMENTS must be 'off', 'stars' or 'dev'")
    if mode == "dev" and os.environ.get("NOVA_DEV_PAY", "") != "1":
        raise SystemExit("NOVA_PAYMENTS=dev requires NOVA_DEV_PAY=1")
    apk_path = Path(apk_raw) if apk_raw else None
    raw_admins = os.environ.get("NOVA_BOT_ADMIN_IDS")
    admin_ids = parse_admin_ids(raw_admins)
    if (raw_admins or "").strip() and not admin_ids:
        LOG.warning("NOVA_BOT_ADMIN_IDS is set but no valid ids parsed")
    return ShopContext(
        store=EntitlementStore(db_path),
        plan=plan_from_env(os.environ.get("NOVA_STARS_PRICE")),
        apk_path=apk_path,
        payment_mode=mode,
        admin_ids=admin_ids,
        houses=CashierHouseProbe.from_env().snapshot,
    )


def chat_id_of(update: dict) -> int | None:
    pre = update.get("pre_checkout_query")
    if isinstance(pre, dict):
        user = pre.get("from") if isinstance(pre.get("from"), dict) else {}
        try:
            return int(user.get("id"))
        except (TypeError, ValueError):
            return None
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    try:
        return int(chat.get("id"))
    except (TypeError, ValueError):
        return None


def consume_update(api: TelegramApi, ctx: ShopContext | None, update: dict, offset: int | None) -> int | None:
    update_id = update.get("update_id")
    next_offset = update_id + 1 if isinstance(update_id, int) else offset
    chat_id = chat_id_of(update)
    if chat_id is None:
        return next_offset
    started = time.monotonic()
    try:
        if ctx is None:
            raise RuntimeError("shop context is missing")
        actions = handle_update(update, ctx)
        api.dispatch(chat_id, actions)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if elapsed_ms >= 800:
            LOG.warning("slow reply chat_id=%s ms=%s", chat_id, elapsed_ms)
        else:
            LOG.info("replied chat_id=%s ms=%s", chat_id, elapsed_ms)
    except TelegramApiError as err:
        LOG.error("dispatch failed chat_id=%s: %s", chat_id, err)
    except Exception:
        LOG.exception("handler crashed chat_id=%s", chat_id)
    return next_offset


def run_forever(api: TelegramApi, ctx: ShopContext) -> None:
    offset: int | None = None
    LOG.info("NOVA bot started, payments=%s admins=%s", ctx.payment_mode, len(ctx.admin_ids))
    try:
        api.delete_webhook()
    except TelegramApiError as err:
        LOG.warning("deleteWebhook skipped: %s", err)
    try:
        pending = api.get_updates(offset, timeout=0)
        if pending:
            last = pending[-1].get("update_id")
            if isinstance(last, int):
                offset = last + 1
                LOG.info("skipped %s pending updates", len(pending))
    except TelegramApiError as err:
        LOG.warning("startup getUpdates skipped: %s", err)
    while True:
        try:
            updates = api.get_updates(offset)
        except TelegramApiError as err:
            LOG.error("getUpdates failed: %s", err)
            if "409" in str(err):
                LOG.error("another poller is using this bot token")
            time.sleep(3)
            continue
        for update in updates:
            offset = consume_update(api, ctx, update, offset)


def main() -> int:
    configure_logging()
    token = os.environ.get("NOVA_BOT_TOKEN", "").strip()
    if not token:
        LOG.error("NOVA_BOT_TOKEN is missing")
        return 1
    ctx = load_context()
    api = TelegramApi(token)
    try:
        run_forever(api, ctx)
    finally:
        ctx.store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
