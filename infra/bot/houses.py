"""Office and door snapshot for the bot admin cabinet. No secrets stored here."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FetchFn = Callable[..., bytes]


@dataclass(frozen=True)
class HouseStatus:
    name: str
    kind: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class VpnDevice:
    label: str
    online: bool


@dataclass(frozen=True)
class HouseSnapshot:
    office: HouseStatus
    doors: tuple[HouseStatus, ...]
    vpn_total: int
    vpn_online: int
    vpn_devices: tuple[VpnDevice, ...]


MAX_BODY = 65536


def parse_overview(payload: dict[str, Any], *, office_ok: bool) -> HouseSnapshot:
    if not office_ok:
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
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        data = {}
    kpis = data.get("kpis") if isinstance(data.get("kpis"), dict) else {}
    vpn_total = _as_int(kpis.get("total"))
    vpn_online = _as_int(kpis.get("online"))
    doors = tuple(_door_from_node(node) for node in _as_list(data.get("nodes")))
    devices = tuple(
        VpnDevice(label=_device_label(user), online=bool(user.get("online")))
        for user in _as_list(data.get("users"))
        if _device_label(user)
    )
    return HouseSnapshot(
        office=HouseStatus(
            name="Офис",
            kind="office",
            ok=True,
            detail="касса отвечает",
        ),
        doors=doors,
        vpn_total=vpn_total,
        vpn_online=vpn_online,
        vpn_devices=devices,
    )


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _door_from_node(node: dict[str, Any]) -> HouseStatus:
    ipv4 = str(node.get("ipv4") or "").strip()
    status = str(node.get("status") or "").strip() or "unknown"
    name = str(node.get("name") or "").strip() or "Дверь"
    peers = _as_int(node.get("peer_count"))
    online = _as_int(node.get("online_count"))
    if status == "active":
        detail = f"{ipv4} — active, пиров {peers}, онлайн {online}"
        return HouseStatus(name=name, kind="door", ok=True, detail=detail)
    if status == "inactive":
        return HouseStatus(
            name=name,
            kind="door",
            ok=False,
            detail=f"{ipv4} — не в работе",
        )
    return HouseStatus(
        name=name,
        kind="door",
        ok=False,
        detail=f"{ipv4} — {status}",
    )


def _device_label(user: dict[str, Any]) -> str:
    raw = str(user.get("address") or user.get("client_address") or "").strip()
    if not raw:
        return ""
    return raw.split("/", 1)[0]


class CashierHouseProbe:
    def __init__(
        self,
        base_url: str,
        username: str = "nova",
        password: str = "",
        timeout: float = 2.5,
        fetch: FetchFn | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._fetch = fetch or _http_get

    @classmethod
    def from_env(cls) -> "CashierHouseProbe":
        return cls(
            base_url=os.environ.get("NOVA_CASHIER_URL", "http://127.0.0.1:8090").strip()
            or "http://127.0.0.1:8090",
            username=os.environ.get("NOVA_DASHBOARD_USER", "nova").strip() or "nova",
            password=os.environ.get("NOVA_DASHBOARD_PASSWORD", "").strip(),
        )

    def snapshot(self) -> HouseSnapshot:
        try:
            return self._snapshot()
        except Exception:
            return parse_overview({}, office_ok=False)

    def _snapshot(self) -> HouseSnapshot:
        if not self.base_url:
            return parse_overview({}, office_ok=False)
        try:
            raw = self._fetch(
                f"{self.base_url}/api/v1/health",
                timeout=self.timeout,
                headers=self._headers(include_auth=False),
            )
            payload = json.loads(raw.decode("utf-8"))
            data = payload.get("data") if isinstance(payload, dict) else None
            health_ok = bool(isinstance(payload, dict) and payload.get("success"))
            if isinstance(data, dict) and "ok" in data:
                health_ok = health_ok and bool(data.get("ok"))
        except (URLError, HTTPError, TimeoutError, ValueError, OSError):
            return parse_overview({}, office_ok=False)
        if not health_ok:
            return parse_overview({}, office_ok=False)
        try:
            raw = self._fetch(
                f"{self.base_url}/api/v1/overview",
                timeout=self.timeout,
                headers=self._headers(include_auth=True),
            )
            overview = json.loads(raw.decode("utf-8"))
        except HTTPError as err:
            if err.code == 401:
                return HouseSnapshot(
                    office=HouseStatus(
                        name="Офис",
                        kind="office",
                        ok=True,
                        detail="касса жива, книга закрыта паролем",
                    ),
                    doors=(),
                    vpn_total=0,
                    vpn_online=0,
                    vpn_devices=(),
                )
            return HouseSnapshot(
                office=HouseStatus(
                    name="Офис",
                    kind="office",
                    ok=True,
                    detail="касса жива, книга не прочиталась",
                ),
                doors=(),
                vpn_total=0,
                vpn_online=0,
                vpn_devices=(),
            )
        except (URLError, TimeoutError, ValueError, OSError):
            return HouseSnapshot(
                office=HouseStatus(
                    name="Офис",
                    kind="office",
                    ok=True,
                    detail="касса жива, книга не прочиталась",
                ),
                doors=(),
                vpn_total=0,
                vpn_online=0,
                vpn_devices=(),
            )
        if not isinstance(overview, dict):
            return parse_overview({}, office_ok=True)
        return parse_overview(overview, office_ok=True)

    def _headers(self, *, include_auth: bool) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if include_auth and self.password:
            token = base64.b64encode(
                f"{self.username}:{self.password}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers


def _http_get(url: str, timeout: float, headers: dict | None = None) -> bytes:
    request = Request(url, headers=headers or {}, method="GET")
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_BODY + 1)
    if len(data) > MAX_BODY:
        raise ValueError("cashier body too large")
    return data
