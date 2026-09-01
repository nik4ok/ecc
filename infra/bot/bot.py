#!/usr/bin/env python3
"""NOVA Telegram shop: pay → APK → status. VPN stays in the Android app."""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from handlers import PreCheckoutAnswer, ShopContext, handle_update
from shop import EntitlementStore, plan_from_env
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
    mode = os.environ.get("NOVA_PAYMENTS", "stars").strip().lower() or "stars"
    if mode not in {"stars", "dev"}:
        raise SystemExit("NOVA_PAYMENTS must be 'stars' or 'dev'")
    if mode == "dev" and os.environ.get("NOVA_DEV_PAY", "") != "1":
        raise SystemExit("NOVA_PAYMENTS=dev requires NOVA_DEV_PAY=1")
    apk_path = Path(apk_raw) if apk_raw else None
    return ShopContext(
        store=EntitlementStore(db_path),
        plan=plan_from_env(os.environ.get("NOVA_STARS_PRICE")),
        apk_path=apk_path,
        payment_mode=mode,
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


def run_forever(api: TelegramApi, ctx: ShopContext) -> None:
    offset: int | None = None
    LOG.info("NOVA bot started, payments=%s", ctx.payment_mode)
    while True:
        try:
            updates = api.get_updates(offset)
        except TelegramApiError as err:
            LOG.error("getUpdates failed: %s", err)
            time.sleep(3)
            continue
        for update in updates:
            update_id = update.get("update_id")
            chat_id = chat_id_of(update)
            if chat_id is None:
                if isinstance(update_id, int):
                    offset = update_id + 1
                continue
            actions: list = []
            try:
                actions = handle_update(update, ctx)
                api.dispatch(chat_id, actions)
            except TelegramApiError as err:
                LOG.error("dispatch failed chat_id=%s: %s", chat_id, err)
                if any(isinstance(action, PreCheckoutAnswer) for action in actions):
                    continue
            except Exception:
                LOG.exception("handler crashed chat_id=%s", chat_id)
                continue
            if isinstance(update_id, int):
                offset = update_id + 1


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
