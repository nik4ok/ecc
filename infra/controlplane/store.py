"""SQLite guest book for NOVA control plane. Private keys never stored."""
from __future__ import annotations

import base64
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from awg_status import handshake_is_fresh
from usage import UsageSnapshot, apply_observation, parse_transfer


class DuplicatePublicKeyError(ValueError):
    pass


class InvalidPublicKeyError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass


def validate_public_key(key: str) -> str:
    trimmed = (key or "").strip()
    if not trimmed:
        raise InvalidPublicKeyError("public key is empty")
    try:
        raw = base64.b64decode(trimmed, validate=True)
    except Exception as exc:
        raise InvalidPublicKeyError("public key is not valid Base64") from exc
    if len(raw) != 32:
        raise InvalidPublicKeyError("public key must decode to 32 bytes")
    return trimmed


class UserStore:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                display_name TEXT NOT NULL,
                public_key TEXT NOT NULL UNIQUE,
                client_address TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                source TEXT NOT NULL DEFAULT 'register',
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        self._migrate_usage_columns()

    def _migrate_usage_columns(self) -> None:
        existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(users)").fetchall()
        }
        additions = (
            ("connect_count", "INTEGER NOT NULL DEFAULT 0"),
            ("first_connected_at", "TEXT"),
            ("total_rx_bytes", "INTEGER NOT NULL DEFAULT 0"),
            ("total_tx_bytes", "INTEGER NOT NULL DEFAULT 0"),
            ("last_rx_bytes", "INTEGER NOT NULL DEFAULT 0"),
            ("last_tx_bytes", "INTEGER NOT NULL DEFAULT 0"),
            ("session_open", "INTEGER NOT NULL DEFAULT 0"),
        )
        for name, spec in additions:
            if name not in existing:
                self._conn.execute(f"ALTER TABLE users ADD COLUMN {name} {spec}")
        self._conn.commit()

    def seed_reserved(self, rows: list[dict[str, str]]) -> None:
        with self._lock:
            for row in rows:
                existing = self._conn.execute(
                    "SELECT id FROM users WHERE public_key = ?",
                    (row["public_key"],),
                ).fetchone()
                if existing:
                    continue
                self._conn.execute(
                    """
                    INSERT INTO users (id, email, display_name, public_key, client_address, status, source, created_at)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        row["email"],
                        row["display_name"],
                        validate_public_key(row["public_key"]),
                        row["client_address"],
                        row.get("source", "reserved"),
                        _now(),
                    ),
                )
            self._conn.commit()

    def next_address(self) -> str:
        with self._lock:
            return self._next_address_unlocked()

    def _next_address_unlocked(self) -> str:
        used = {
            row["client_address"]
            for row in self._conn.execute("SELECT client_address FROM users").fetchall()
        }
        reserved_hosts = {1, 2}
        for host in range(1, 255):
            if host in reserved_hosts:
                continue
            candidate = f"10.8.1.{host}/32"
            if candidate not in used:
                return candidate
        raise RuntimeError("no free addresses in 10.8.1.0/24")

    def register(self, email: str, display_name: str, public_key: str) -> dict[str, Any]:
        with self._lock:
            return self._register_unlocked(email, display_name, public_key)

    def _register_unlocked(self, email: str, display_name: str, public_key: str) -> dict[str, Any]:
        key = validate_public_key(public_key)
        mail = (email or "").strip().lower()
        name = (display_name or "").strip()
        if not mail or "@" not in mail:
            raise ValueError("email is required")
        if not name:
            raise ValueError("display name is required")
        dup = self._conn.execute(
            "SELECT id FROM users WHERE public_key = ?", (key,)
        ).fetchone()
        if dup:
            raise DuplicatePublicKeyError("this device badge is already in the book")
        address = self._next_address_unlocked()
        user_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO users (id, email, display_name, public_key, client_address, status, source, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', 'register', ?)
            """,
            (user_id, mail, name, key, address, _now()),
        )
        self._conn.commit()
        return self._get_unlocked(user_id)

    def get(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return self._get_unlocked(user_id)

    def _get_unlocked(self, user_id: str) -> dict[str, Any]:
        row = self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise UserNotFoundError(user_id)
        return _row_to_user(row)

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM users ORDER BY created_at ASC"
            ).fetchall()
            return [_row_to_user(row) for row in rows]

    def apply_tunnel_peers(
        self,
        peers: list[dict[str, Any]],
        now: str | None = None,
    ) -> None:
        stamp = now or _now()
        by_key = {peer.get("public_key"): peer for peer in peers}
        with self._lock:
            rows = self._conn.execute("SELECT * FROM users").fetchall()
            for row in rows:
                user = _row_to_user(row)
                peer = by_key.get(user["public_key"])
                rx_bytes: int | None = None
                tx_bytes: int | None = None
                online = False
                if peer:
                    online = (
                        handshake_is_fresh(peer.get("latest_handshake"))
                        and user.get("status") == "active"
                    )
                    if peer.get("transfer"):
                        rx_bytes, tx_bytes = parse_transfer(str(peer.get("transfer")))
                nxt = apply_observation(
                    UsageSnapshot(
                        connect_count=user["connect_count"],
                        first_connected_at=user["first_connected_at"],
                        total_rx_bytes=user["total_rx_bytes"],
                        total_tx_bytes=user["total_tx_bytes"],
                        last_rx_bytes=user["last_rx_bytes"],
                        last_tx_bytes=user["last_tx_bytes"],
                        session_open=user["session_open"],
                    ),
                    online=online,
                    rx_bytes=rx_bytes,
                    tx_bytes=tx_bytes,
                    now=stamp,
                )
                self._conn.execute(
                    """
                    UPDATE users SET
                        connect_count = ?,
                        first_connected_at = ?,
                        total_rx_bytes = ?,
                        total_tx_bytes = ?,
                        last_rx_bytes = ?,
                        last_tx_bytes = ?,
                        session_open = ?
                    WHERE id = ?
                    """,
                    (
                        nxt.connect_count,
                        nxt.first_connected_at,
                        nxt.total_rx_bytes,
                        nxt.total_tx_bytes,
                        nxt.last_rx_bytes,
                        nxt.last_tx_bytes,
                        1 if nxt.session_open else 0,
                        user["id"],
                    ),
                )
            self._conn.commit()

    def revoke(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._get_unlocked(user_id)
            self._conn.execute(
                "UPDATE users SET status = 'revoked' WHERE id = ?", (user_id,)
            )
            self._conn.commit()
            row["status"] = "revoked"
            return row

    def close(self) -> None:
        self._conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    user = dict(row)
    user["connect_count"] = int(user.get("connect_count") or 0)
    user["total_rx_bytes"] = int(user.get("total_rx_bytes") or 0)
    user["total_tx_bytes"] = int(user.get("total_tx_bytes") or 0)
    user["last_rx_bytes"] = int(user.get("last_rx_bytes") or 0)
    user["last_tx_bytes"] = int(user.get("last_tx_bytes") or 0)
    user["session_open"] = bool(int(user.get("session_open") or 0))
    return user
