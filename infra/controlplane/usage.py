"""Lifetime session and traffic counters derived from `awg show` snapshots."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_UNITS = {
    "B": 1,
    "KIB": 1024,
    "MIB": 1024 ** 2,
    "GIB": 1024 ** 3,
    "TIB": 1024 ** 4,
}

_TRANSFER_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*(B|KiB|MiB|GiB|TiB)\s+received"
    r".*?([0-9]+(?:\.[0-9]+)?)\s*(B|KiB|MiB|GiB|TiB)\s+sent",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UsageSnapshot:
    connect_count: int = 0
    first_connected_at: Optional[str] = None
    total_rx_bytes: int = 0
    total_tx_bytes: int = 0
    last_rx_bytes: int = 0
    last_tx_bytes: int = 0
    session_open: bool = False


def parse_transfer(text: Optional[str]) -> tuple[int, int]:
    if not text:
        return 0, 0
    match = _TRANSFER_RE.search(text)
    if not match:
        return 0, 0
    rx = _to_bytes(match.group(1), match.group(2))
    tx = _to_bytes(match.group(3), match.group(4))
    return rx, tx


def format_bytes(n: int) -> str:
    value = max(0, int(n))
    if value < 1024:
        return f"{value} B"
    amount = float(value)
    for unit in ("KiB", "MiB", "GiB"):
        amount /= 1024
        if amount < 1024:
            return f"{amount:.2f} {unit}"
    return f"{amount / 1024:.2f} TiB"


def apply_observation(
    prev: UsageSnapshot,
    *,
    online: bool,
    rx_bytes: Optional[int],
    tx_bytes: Optional[int],
    now: str,
) -> UsageSnapshot:
    connect_count = prev.connect_count
    first_connected_at = prev.first_connected_at
    if online and not prev.session_open:
        connect_count += 1
        if first_connected_at is None:
            first_connected_at = now

    total_rx, last_rx = _accumulate(prev.total_rx_bytes, prev.last_rx_bytes, rx_bytes)
    total_tx, last_tx = _accumulate(prev.total_tx_bytes, prev.last_tx_bytes, tx_bytes)
    return UsageSnapshot(
        connect_count=connect_count,
        first_connected_at=first_connected_at,
        total_rx_bytes=total_rx,
        total_tx_bytes=total_tx,
        last_rx_bytes=last_rx,
        last_tx_bytes=last_tx,
        session_open=online,
    )


HIDDEN_USAGE_FIELDS = {"session_open", "last_rx_bytes", "last_tx_bytes"}


def usage_source_is_usable(source: str) -> bool:
    return source != "empty"


def present_user(user: dict) -> dict:
    total = int(user.get("total_rx_bytes") or 0) + int(user.get("total_tx_bytes") or 0)
    public = {key: value for key, value in user.items() if key not in HIDDEN_USAGE_FIELDS}
    public["total_bytes"] = total
    public["total_transfer"] = format_bytes(total)
    return public


def _to_bytes(amount: str, unit: str) -> int:
    return int(float(amount) * _UNITS[unit.upper()])


def _accumulate(total: int, last: int, current: Optional[int]) -> tuple[int, int]:
    if current is None:
        return total, last
    if current >= last:
        return total + (current - last), current
    # Overlapping polls can apply a slightly stale snapshot. A real wg
    # restart drops the counter close to zero, not by a fraction of a percent.
    if last > 0 and current * 100 >= last * 99:
        return total, last
    return total + current, current
