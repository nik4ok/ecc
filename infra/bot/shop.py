"""NOVA shop: 30-day entitlement and Stars invoice payload. No private keys here."""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import NamedTuple


class InvalidTelegramIdError(ValueError):
    pass


@dataclass(frozen=True)
class Plan:
    id: str
    title: str
    description: str
    stars: int
    days: int


DEFAULT_STARS = 250

MONTH_PLAN = Plan(
    id="month",
    title="NOVA — 30 дней",
    description="Доступ к приложению и защите на 30 дней.",
    stars=DEFAULT_STARS,
    days=30,
)


class InvoicePayload(NamedTuple):
    telegram_id: int
    plan_id: str
    nonce: str


_MONTHS_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def require_telegram_id(telegram_id: int) -> int:
    if not isinstance(telegram_id, int) or telegram_id <= 0:
        raise InvalidTelegramIdError("telegram id must be a positive integer")
    return telegram_id


def make_invoice_payload(telegram_id: int, plan_id: str, nonce: str) -> str:
    tid = require_telegram_id(telegram_id)
    plan = (plan_id or "").strip()
    token = (nonce or "").strip()
    if not plan or not token:
        raise ValueError("plan id and nonce are required")
    if ":" in plan or ":" in token:
        raise ValueError("plan id and nonce must not contain ':'")
    return f"nova:{plan}:{tid}:{token}"


def parse_invoice_payload(payload: str) -> InvoicePayload | None:
    parts = (payload or "").split(":")
    if len(parts) != 4 or parts[0] != "nova" or not parts[1] or not parts[3]:
        return None
    try:
        telegram_id = int(parts[2])
    except ValueError:
        return None
    try:
        require_telegram_id(telegram_id)
    except InvalidTelegramIdError:
        return None
    return InvoicePayload(telegram_id=telegram_id, plan_id=parts[1], nonce=parts[3])


def format_ru_date(value: datetime) -> str:
    stamp = value.astimezone(timezone.utc)
    return f"{stamp.day} {_MONTHS_GENITIVE[stamp.month]} {stamp.year}"


def plan_from_env(raw_stars: str | None) -> Plan:
    text = (raw_stars or str(DEFAULT_STARS)).strip()
    try:
        stars = int(text)
    except ValueError as exc:
        raise ValueError("NOVA_STARS_PRICE must be an integer") from exc
    if stars < 1:
        raise ValueError("NOVA_STARS_PRICE must be >= 1")
    return Plan(
        id=MONTH_PLAN.id,
        title=MONTH_PLAN.title,
        description=MONTH_PLAN.description,
        stars=stars,
        days=MONTH_PLAN.days,
    )


class EntitlementStore:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=5)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entitlements (
                telegram_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT '',
                paid_until TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                charge_id TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def has_access(self, telegram_id: int, now: datetime) -> bool:
        require_telegram_id(telegram_id)
        row = self.get(telegram_id)
        if row is None:
            return False
        until = datetime.fromisoformat(row["paid_until"])
        return until > now

    def get(self, telegram_id: int) -> dict | None:
        require_telegram_id(telegram_id)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM entitlements WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def apply_payment(
        self,
        telegram_id: int,
        days: int,
        now: datetime,
        display_name: str,
        charge_id: str,
    ) -> dict:
        require_telegram_id(telegram_id)
        charge = (charge_id or "").strip()
        if not charge:
            raise ValueError("charge id is required")
        if days < 1:
            raise ValueError("days must be >= 1")
        with self._lock:
            try:
                seen = self._conn.execute(
                    "SELECT telegram_id FROM payments WHERE charge_id = ?",
                    (charge,),
                ).fetchone()
                if seen is not None:
                    return self._get_unlocked(telegram_id)
                self._conn.execute(
                    """
                    INSERT INTO payments (charge_id, telegram_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (charge, telegram_id, now.isoformat()),
                )
                row = self._grant_unlocked(telegram_id, days, now, display_name)
                self._conn.commit()
                return row
            except Exception:
                self._conn.rollback()
                raise

    def grant(
        self,
        telegram_id: int,
        days: int,
        now: datetime,
        display_name: str = "",
    ) -> dict:
        require_telegram_id(telegram_id)
        if days < 1:
            raise ValueError("days must be >= 1")
        with self._lock:
            row = self._grant_unlocked(telegram_id, days, now, display_name)
            self._conn.commit()
            return row

    def _get_unlocked(self, telegram_id: int) -> dict:
        row = self._conn.execute(
            "SELECT * FROM entitlements WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("entitlement is missing after payment")
        return dict(row)

    def _grant_unlocked(
        self,
        telegram_id: int,
        days: int,
        now: datetime,
        display_name: str,
    ) -> dict:
        name = (display_name or "").strip()
        existing = self._conn.execute(
            "SELECT * FROM entitlements WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
        if existing is None:
            until = now + timedelta(days=days)
            created = now.isoformat()
            self._conn.execute(
                """
                INSERT INTO entitlements
                    (telegram_id, display_name, paid_until, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_id, name, until.isoformat(), created, created),
            )
        else:
            current = datetime.fromisoformat(existing["paid_until"])
            base = current if current > now else now
            until = base + timedelta(days=days)
            label = name or existing["display_name"]
            self._conn.execute(
                """
                UPDATE entitlements
                SET display_name = ?, paid_until = ?, updated_at = ?
                WHERE telegram_id = ?
                """,
                (label, until.isoformat(), now.isoformat(), telegram_id),
            )
        return self._get_unlocked(telegram_id)

    def close(self) -> None:
        self._conn.close()
