"""NOVA shop: 30-day entitlement and Stars invoice payload. No private keys here."""
from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import NamedTuple


class InvalidTelegramIdError(ValueError):
    pass


class InvalidOsError(ValueError):
    pass


OS_ANDROID = "android"
OS_IOS = "ios"
_ALLOWED_OS = {OS_ANDROID, OS_IOS}


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


def parse_admin_ids(raw: str | None) -> frozenset[int]:
    if raw is None or not str(raw).strip():
        return frozenset()
    found: set[int] = set()
    for chunk in str(raw).replace(";", ",").split(","):
        piece = chunk.strip()
        if not piece:
            continue
        try:
            telegram_id = int(piece)
        except ValueError:
            continue
        if telegram_id > 0:
            found.add(telegram_id)
    return frozenset(found)


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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                telegram_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT '',
                os TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                os TEXT,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visitors (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                language_code TEXT NOT NULL DEFAULT '',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                visit_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                os TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_visitors_last_seen ON visitors(last_seen)"
        )
        self._migrate_profile_columns()
        self._conn.commit()

    def _migrate_profile_columns(self) -> None:
        existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(profiles)").fetchall()
        }
        if "awaiting_report" not in existing:
            self._conn.execute(
                "ALTER TABLE profiles ADD COLUMN awaiting_report INTEGER NOT NULL DEFAULT 0"
            )

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

    def get_profile(self, telegram_id: int) -> dict | None:
        require_telegram_id(telegram_id)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM profiles WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def set_os(
        self,
        telegram_id: int,
        os_name: str,
        now: datetime,
        display_name: str = "",
    ) -> dict:
        require_telegram_id(telegram_id)
        os_key = (os_name or "").strip().lower()
        if os_key not in _ALLOWED_OS:
            raise InvalidOsError("os must be android or ios")
        name = (display_name or "").strip()
        stamp = now.isoformat()
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM profiles WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
            if existing is None:
                self._conn.execute(
                    """
                    INSERT INTO profiles
                        (telegram_id, display_name, os, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (telegram_id, name, os_key, stamp, stamp),
                )
            else:
                label = name or existing["display_name"]
                self._conn.execute(
                    """
                    UPDATE profiles
                    SET display_name = ?, os = ?, awaiting_report = 0, updated_at = ?
                    WHERE telegram_id = ?
                    """,
                    (label, os_key, stamp, telegram_id),
                )
            self._conn.commit()
        row = self.get_profile(telegram_id)
        if row is None:
            raise RuntimeError("profile did not persist")
        return row

    def is_awaiting_report(self, telegram_id: int) -> bool:
        profile = self.get_profile(telegram_id)
        if profile is None:
            return False
        return bool(int(profile.get("awaiting_report") or 0))

    def set_awaiting_report(
        self,
        telegram_id: int,
        waiting: bool,
        now: datetime,
        display_name: str = "",
    ) -> None:
        require_telegram_id(telegram_id)
        name = (display_name or "").strip()
        stamp = now.isoformat()
        flag = 1 if waiting else 0
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM profiles WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
            if existing is None:
                self._conn.execute(
                    """
                    INSERT INTO profiles
                        (telegram_id, display_name, os, awaiting_report, created_at, updated_at)
                    VALUES (?, ?, NULL, ?, ?, ?)
                    """,
                    (telegram_id, name, flag, stamp, stamp),
                )
            else:
                label = name or existing["display_name"]
                self._conn.execute(
                    """
                    UPDATE profiles
                    SET display_name = ?, awaiting_report = ?, updated_at = ?
                    WHERE telegram_id = ?
                    """,
                    (label, flag, stamp, telegram_id),
                )
            self._conn.commit()

    def add_report(
        self,
        telegram_id: int,
        body: str,
        now: datetime,
        display_name: str = "",
        os_name: str | None = None,
    ) -> dict:
        require_telegram_id(telegram_id)
        text = (body or "").strip()
        if len(text) < 8:
            raise ValueError("report is too short")
        if len(text) > 2000:
            text = text[:2000]
        profile = self.get_profile(telegram_id)
        os_value = os_name or (profile or {}).get("os")
        report_id = str(uuid.uuid4())
        name = (display_name or "").strip()
        if not name and profile:
            name = str(profile.get("display_name") or "")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO reports (id, telegram_id, display_name, os, body, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (report_id, telegram_id, name, os_value, text, now.isoformat()),
            )
            self._conn.execute(
                """
                UPDATE profiles SET awaiting_report = 0, updated_at = ?
                WHERE telegram_id = ?
                """,
                (now.isoformat(), telegram_id),
            )
            self._conn.commit()
        return {
            "id": report_id,
            "telegram_id": telegram_id,
            "display_name": name,
            "os": os_value,
            "body": text,
            "created_at": now.isoformat(),
        }

    def list_reports(self, telegram_id: int) -> list[dict]:
        require_telegram_id(telegram_id)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM reports
                WHERE telegram_id = ?
                ORDER BY created_at ASC
                """,
                (telegram_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_reports_since(self, telegram_id: int, since: datetime) -> int:
        require_telegram_id(telegram_id)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS n FROM reports
                WHERE telegram_id = ? AND created_at >= ?
                """,
                (telegram_id, since.isoformat()),
            ).fetchone()
        return int(row["n"] if row else 0)

    def get_visitor(self, telegram_id: int) -> dict | None:
        require_telegram_id(telegram_id)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM visitors WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def remember_visit(
        self,
        telegram_id: int,
        now: datetime,
        *,
        display_name: str = "",
        username: str = "",
        language_code: str = "",
        action: str,
        os_name: str | None = None,
    ) -> dict:
        require_telegram_id(telegram_id)
        verb = (action or "").strip().lower()
        if not verb or len(verb) > 32:
            raise ValueError("action is required")
        name = (display_name or "").strip()[:32]
        handle = (username or "").strip().lstrip("@")[:32]
        lang = (language_code or "").strip()[:16]
        os_key = (os_name or "").strip().lower() or None
        if os_key not in _ALLOWED_OS:
            os_key = None
        stamp = now.isoformat()
        with self._lock:
            try:
                existing = self._conn.execute(
                    "SELECT * FROM visitors WHERE telegram_id = ?",
                    (telegram_id,),
                ).fetchone()
                if existing is None:
                    self._conn.execute(
                        """
                        INSERT INTO visitors (
                            telegram_id, username, display_name, language_code,
                            first_seen, last_seen, visit_count
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                        """,
                        (telegram_id, handle, name, lang, stamp, stamp),
                    )
                else:
                    label = name or existing["display_name"]
                    nick = handle or existing["username"]
                    spoken = lang or existing["language_code"]
                    self._conn.execute(
                        """
                        UPDATE visitors
                        SET username = ?, display_name = ?, language_code = ?,
                            last_seen = ?, visit_count = visit_count + 1
                        WHERE telegram_id = ?
                        """,
                        (nick, label, spoken, stamp, telegram_id),
                    )
                self._conn.execute(
                    """
                    INSERT INTO events (telegram_id, action, os, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (telegram_id, verb, os_key, stamp),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        row = self.get_visitor(telegram_id)
        if row is None:
            raise RuntimeError("visitor did not persist")
        return row

    def list_events(self, telegram_id: int) -> list[dict]:
        require_telegram_id(telegram_id)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM events
                WHERE telegram_id = ?
                ORDER BY id ASC
                """,
                (telegram_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_recent_visitors(self, limit: int = 10) -> list[dict]:
        cap = 10 if limit < 1 else min(int(limit), 50)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT v.*, p.os AS os
                FROM visitors v
                LEFT JOIN profiles p ON p.telegram_id = v.telegram_id
                ORDER BY v.last_seen DESC
                LIMIT ?
                """,
                (cap,),
            ).fetchall()
            return [dict(row) for row in rows]

    def shop_stats(self, now: datetime, window: timedelta | None = None) -> dict:
        period = window or timedelta(hours=24)
        since = (now - period).isoformat()
        with self._lock:
            visitors = int(
                self._conn.execute("SELECT COUNT(*) AS n FROM visitors").fetchone()["n"]
            )
            visitors_recent = int(
                self._conn.execute(
                    "SELECT COUNT(*) AS n FROM visitors WHERE last_seen >= ?",
                    (since,),
                ).fetchone()["n"]
            )
            android = int(
                self._conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM visitors v
                    INNER JOIN profiles p ON p.telegram_id = v.telegram_id
                    WHERE p.os = ?
                    """,
                    (OS_ANDROID,),
                ).fetchone()["n"]
            )
            ios = int(
                self._conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM visitors v
                    INNER JOIN profiles p ON p.telegram_id = v.telegram_id
                    WHERE p.os = ?
                    """,
                    (OS_IOS,),
                ).fetchone()["n"]
            )
            unknown_os = int(
                self._conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM visitors v
                    LEFT JOIN profiles p ON p.telegram_id = v.telegram_id
                    WHERE p.os IS NULL OR p.os NOT IN (?, ?)
                    """,
                    (OS_ANDROID, OS_IOS),
                ).fetchone()["n"]
            )
            downloads_recent = int(
                self._conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM events
                    WHERE action = 'download' AND created_at >= ?
                    """,
                    (since,),
                ).fetchone()["n"]
            )
            reports_total = int(
                self._conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"]
            )
            reports_recent = int(
                self._conn.execute(
                    "SELECT COUNT(*) AS n FROM reports WHERE created_at >= ?",
                    (since,),
                ).fetchone()["n"]
            )
        return {
            "visitors": visitors,
            "visitors_recent": visitors_recent,
            "android": android,
            "ios": ios,
            "unknown_os": unknown_os,
            "downloads_recent": downloads_recent,
            "reports_total": reports_total,
            "reports_recent": reports_recent,
        }

    def close(self) -> None:
        self._conn.close()
