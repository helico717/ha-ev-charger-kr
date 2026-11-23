"""API client and response parser for Korea Environment Corporation EV Charger API."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any
from urllib.parse import unquote

from .const import (
    CHARGER_TYPE_LABELS,
    DEFAULT_DAILY_LIMIT,
    ENDPOINT_CHARGER_INFO,
    ENDPOINT_CHARGER_STATUS,
    FAST_CHARGER_TYPES,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    SLOW_CHARGER_TYPES,
    STAT_AVAILABLE,
    STAT_CHARGING,
    STAT_COMM_ERROR,
    STAT_INSPECTING,
    STAT_LABELS,
    STAT_RESERVED,
    STAT_SUSPENDED,
)


class EvChargerApiError(Exception):
    """Raised when the EV Charger API returns an error or invalid response."""


class EvChargerAuthError(EvChargerApiError):
    """Raised when the API key is invalid or unauthorized."""


class EvChargerNotFoundError(EvChargerApiError):
    """Raised when no chargers are found for the given station ID."""


@dataclass
class ChargerDetail:
    """Normalized state for a single EV charger."""

    charger_id: str
    stat: str
    stat_label: str
    charger_type: str | None = None
    charger_type_label: str | None = None
    output_kw: str | None = None
    stat_updated_at: str | None = None


@dataclass
class RateLimitInfo:
    """Rate limit metadata parsed from data.go.kr HTTP response headers."""

    remaining: int | None = None
    limit: int | None = None


def calculate_auto_scan_interval(
    station_count: int,
    daily_limit: int = DEFAULT_DAILY_LIMIT,
) -> int:
    """Calculate a safe polling interval (minutes) keeping daily calls within ~85% of limit."""
    count = max(1, station_count)
    limit = daily_limit if daily_limit and daily_limit > 0 else DEFAULT_DAILY_LIMIT
    safe_budget = max(1, int(limit * 0.85))
    minutes = math.ceil((1440 * count) / safe_budget)
    return max(max(2, MIN_SCAN_INTERVAL_MINUTES), min(MAX_SCAN_INTERVAL_MINUTES, minutes))


@dataclass
class StationSummary:
    """Summary of a charging station returned by station search."""

    stat_id: str
    station_name: str
    address: str | None = None
    busi_name: str | None = None
    charger_count: int = 0


@dataclass
class StationStatus:
    """Aggregated status for an EV charging station."""

    stat_id: str
    station_name: str
    address: str | None = None
    operator: str | None = None
    total_count: int = 0
    available_count: int = 0
    charging_count: int = 0
    unavailable_count: int = 0
    fast_available_count: int = 0
    slow_available_count: int = 0
    chargers: list[ChargerDetail] = field(default_factory=list)


def search_stations_from_items(
    items: list[dict[str, Any]],
    keyword: str,
) -> list[StationSummary]:
    """Filter and group raw charger info items into matching station summaries."""
    needle = keyword.strip().lower()
    if not needle:
        return []

    grouped: dict[str, StationSummary] = {}
    for item in items:
        stat_id = str(item.get("statId", "")).strip()
        if not stat_id:
            continue
        station_name = str(item.get("statNm") or stat_id).strip()
        address = str(item.get("addr") or "").strip() or None
        busi_name = str(item.get("busiNm") or item.get("bnm") or "").strip() or None

        haystack = " ".join(
            part for part in (station_name, address or "", busi_name or "", stat_id)
        ).lower()
        if needle not in haystack:
            continue

        if stat_id not in grouped:
            grouped[stat_id] = StationSummary(
                stat_id=stat_id,
                station_name=station_name,
                address=address,
                busi_name=busi_name,
                charger_count=1,
            )
        else:
            grouped[stat_id].charger_count += 1

    return sorted(grouped.values(), key=lambda s: (s.station_name, s.stat_id))


def normalize_service_key(api_key: str) -> str:
    """Decode URL-encoded service keys so aiohttp does not double-encode them."""
    return unquote(api_key.strip())


def extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract and validate charger item list from a data.go.kr JSON payload."""
    if not isinstance(payload, dict):
        raise EvChargerApiError("Invalid JSON response from API")

    # Handle OpenAPI_ServiceResponse error wrapper
    if "OpenAPI_ServiceResponse" in payload:
        header = payload["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {})
        msg = header.get("returnAuthMsg") or header.get("errMsg") or "API auth error"
        raise EvChargerAuthError(msg)

    result_code = str(payload.get("resultCode", ""))
    if result_code and result_code != "00":
        result_msg = payload.get("resultMsg", "Unknown API error")
        if result_code in {"20", "22", "30", "31", "32"}:
            raise EvChargerAuthError(f"[{result_code}] {result_msg}")
        raise EvChargerApiError(f"[{result_code}] {result_msg}")

    items_container = payload.get("items")
    if not items_container:
        return []

    if isinstance(items_container, dict):
        raw_items = items_container.get("item", [])
    elif isinstance(items_container, list):
        raw_items = items_container
    else:
        return []

    if isinstance(raw_items, dict):
        return [raw_items]
    if isinstance(raw_items, list):
        return [item for item in raw_items if isinstance(item, dict)]
    return []


def aggregate_station_status(
    stat_id: str,
    items: list[dict[str, Any]],
    fallback_station_name: str | None = None,
    charger_metadata: dict[str, dict[str, str | None]] | None = None,
) -> StationStatus:
    """Aggregate raw API charger items into a StationStatus summary."""
    if not items:
        raise EvChargerNotFoundError(f"No chargers found for station ID: {stat_id}")

    metadata_map = charger_metadata or {}
    station_name = fallback_station_name or stat_id
    address: str | None = None
    operator: str | None = None

    available_count = 0
    charging_count = 0
    unavailable_count = 0
    fast_available_count = 0
    slow_available_count = 0
    chargers: list[ChargerDetail] = []

    for item in items:
        if item.get("statNm"):
            station_name = str(item["statNm"])
        if item.get("addr") and not address:
            address = str(item["addr"])
        if (item.get("busiNm") or item.get("bnm")) and not operator:
            operator = str(item.get("busiNm") or item.get("bnm")).strip() or None

        chger_id = str(item.get("chgerId", "")).zfill(2)
        stat = str(item.get("stat", "0"))
        meta = metadata_map.get(chger_id, {})

        chger_type_raw = item.get("chgerType") or meta.get("chgerType")
        chger_type = str(chger_type_raw).zfill(2) if chger_type_raw else None
        output_kw = item.get("output") or meta.get("output")
        stat_upd_dt = item.get("statUpdDt")

        if stat == STAT_AVAILABLE:
            available_count += 1
            if chger_type in FAST_CHARGER_TYPES:
                fast_available_count += 1
            elif chger_type in SLOW_CHARGER_TYPES:
                slow_available_count += 1
        elif stat == STAT_CHARGING:
            charging_count += 1
        elif stat in {STAT_COMM_ERROR, STAT_SUSPENDED, STAT_INSPECTING, STAT_RESERVED}:
            unavailable_count += 1
        else:
            unavailable_count += 1

        chargers.append(
            ChargerDetail(
                charger_id=chger_id,
                stat=stat,
                stat_label=STAT_LABELS.get(stat, "알 수 없음"),
                charger_type=chger_type,
                charger_type_label=(
                    CHARGER_TYPE_LABELS.get(chger_type) if chger_type else None
                ),
                output_kw=str(output_kw) if output_kw is not None else None,
                stat_updated_at=str(stat_upd_dt) if stat_upd_dt else None,
            )
        )

    chargers.sort(key=lambda c: c.charger_id)

    return StationStatus(
        stat_id=stat_id,
        station_name=station_name,
        address=address,
        operator=operator,
        total_count=len(chargers),
        available_count=available_count,
        charging_count=charging_count,
        unavailable_count=unavailable_count,
        fast_available_count=fast_available_count,
        slow_available_count=slow_available_count,
        chargers=chargers,
    )


class EvChargerApiClient:
    """Async client for Korea Environment Corporation EV Charger Open API."""

    def __init__(self, session: Any, api_key: str) -> None:
        self._session = session
        self._service_key = normalize_service_key(api_key)
        self._charger_metadata_cache: dict[str, dict[str, dict[str, str | None]]] = {}
        self._station_name_cache: dict[str, str] = {}
        self.rate_limit = RateLimitInfo()

    def _update_rate_limit(self, headers: Any) -> None:
        """Extract X-RateLimit-Remaining and X-RateLimit-Limit from response headers."""
        if not headers:
            return
        rem_raw = headers.get("X-RateLimit-Remaining")
        lim_raw = headers.get("X-RateLimit-Limit")
        try:
            if rem_raw is not None:
                self.rate_limit.remaining = int(rem_raw)
            if lim_raw is not None:
                self.rate_limit.limit = int(lim_raw)
        except (TypeError, ValueError):
            pass

    async def _get_json(
        self, url: str, params: dict[str, Any], timeout: int = 20
    ) -> dict[str, Any]:
        query = {
            "serviceKey": self._service_key,
            "dataType": "JSON",
            "pageNo": 1,
            "numOfRows": 100,
            **params,
        }
        async with self._session.get(url, params=query, timeout=timeout) as response:
            self._update_rate_limit(getattr(response, "headers", None))
            if response.status in {401, 403}:
                raise EvChargerAuthError(f"HTTP {response.status}")
            if response.status != 200:
                raise EvChargerApiError(f"HTTP {response.status}")
            return await response.json(content_type=None)

    async def async_search_stations(
        self,
        zcode: str,
        keyword: str,
        max_pages: int = 10,
    ) -> list[StationSummary]:
        """Search stations in a region (zcode) matching a name/address keyword."""
        num_of_rows = 9999
        all_items: list[dict[str, Any]] = []

        for page in range(1, max_pages + 1):
            payload = await self._get_json(
                ENDPOINT_CHARGER_INFO,
                {"zcode": zcode, "pageNo": page, "numOfRows": num_of_rows},
                timeout=30,
            )
            items = extract_items(payload)
            if not items:
                break
            all_items.extend(items)

            try:
                total_count = int(payload.get("totalCount", 0))
            except (TypeError, ValueError):
                total_count = 0
            if total_count and page * num_of_rows >= total_count:
                break
            if len(items) < num_of_rows:
                break

        return search_stations_from_items(all_items, keyword)

    async def async_get_station_info(self, stat_id: str) -> StationStatus:
        """Fetch full station info (including station name and charger types)."""
        payload = await self._get_json(ENDPOINT_CHARGER_INFO, {"statId": stat_id})
        items = extract_items(payload)
        status = aggregate_station_status(stat_id=stat_id, items=items)

        self._station_name_cache[stat_id] = status.station_name
        self._charger_metadata_cache[stat_id] = {
            c.charger_id: {
                "chgerType": c.charger_type,
                "output": c.output_kw,
            }
            for c in status.chargers
        }
        return status

    async def async_get_station_status(
        self,
        stat_id: str,
        station_name: str | None = None,
    ) -> StationStatus:
        """Fetch current station and charger status via getChargerInfo.

        Note: getChargerStatus only returns chargers whose status changed
        within a short recent period, so getChargerInfo is used to retrieve
        every charger's current state reliably.
        """
        status = await self.async_get_station_info(stat_id)
        if station_name and status.station_name == stat_id:
            status.station_name = station_name
        return status
