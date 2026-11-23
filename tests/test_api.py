"""Unit tests for EV Charger KR API parsing and aggregation logic."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

_PKG_NAME = "ev_charger_kr_test_pkg"
_COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent / "custom_components" / "ev_charger_kr"
)

if _PKG_NAME not in sys.modules:
    pkg = types.ModuleType(_PKG_NAME)
    pkg.__path__ = [str(_COMPONENT_DIR)]
    sys.modules[_PKG_NAME] = pkg

    for mod_name in ("const", "api"):
        spec = importlib.util.spec_from_file_location(
            f"{_PKG_NAME}.{mod_name}",
            _COMPONENT_DIR / f"{mod_name}.py",
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"{_PKG_NAME}.{mod_name}"] = mod
        spec.loader.exec_module(mod)

from ev_charger_kr_test_pkg.api import (  # noqa: E402
    EvChargerApiError,
    EvChargerAuthError,
    EvChargerNotFoundError,
    aggregate_station_status,
    extract_items,
    normalize_service_key,
)


class TestEvChargerApi(unittest.TestCase):
    """Tests for API response parsing and charger status aggregation."""

    def test_normalize_service_key(self) -> None:
        encoded = "abc%2Bdef%2Fghi%3D%3D"
        decoded = "abc+def/ghi=="
        self.assertEqual(normalize_service_key(encoded), decoded)
        self.assertEqual(normalize_service_key(f"  {decoded}  "), decoded)

    def test_extract_items_list_and_single_dict(self) -> None:
        list_payload = {
            "resultCode": "00",
            "resultMsg": "NORMAL SERVICE.",
            "items": {"item": [{"chgerId": "01", "stat": "2"}]},
        }
        self.assertEqual(len(extract_items(list_payload)), 1)

        single_payload = {
            "resultCode": "00",
            "items": {"item": {"chgerId": "01", "stat": "2"}},
        }
        self.assertEqual(extract_items(single_payload), [{"chgerId": "01", "stat": "2"}])

        empty_payload = {"resultCode": "00", "items": ""}
        self.assertEqual(extract_items(empty_payload), [])

    def test_extract_items_auth_and_api_errors(self) -> None:
        auth_payload = {
            "OpenAPI_ServiceResponse": {
                "cmmMsgHeader": {"returnAuthMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}
            }
        }
        with self.assertRaises(EvChargerAuthError):
            extract_items(auth_payload)

        code_auth_payload = {"resultCode": "30", "resultMsg": "SERVICE_KEY_ERROR"}
        with self.assertRaises(EvChargerAuthError):
            extract_items(code_auth_payload)

        api_err_payload = {"resultCode": "99", "resultMsg": "UNKNOWN_ERROR"}
        with self.assertRaises(EvChargerApiError):
            extract_items(api_err_payload)

    def test_aggregate_station_status(self) -> None:
        items = [
            {
                "statId": "ME000001",
                "statNm": "의왕시청 충전소",
                "addr": "경기도 의왕시 시청로 1",
                "chgerId": "2",
                "chgerType": "04",  # DC콤보 (급속)
                "output": "100",
                "stat": "2",  # 충전대기
                "statUpdDt": "20261123100000",
            },
            {
                "statId": "ME000001",
                "statNm": "의왕시청 충전소",
                "chgerId": "1",
                "chgerType": "02",  # AC완속
                "output": "7",
                "stat": "2",  # 충전대기
            },
            {
                "statId": "ME000001",
                "chgerId": "3",
                "chgerType": "04",
                "stat": "3",  # 충전중
            },
            {
                "statId": "ME000001",
                "chgerId": "4",
                "chgerType": "02",
                "stat": "5",  # 점검중
            },
        ]

        status = aggregate_station_status("ME000001", items)

        self.assertEqual(status.station_name, "의왕시청 충전소")
        self.assertEqual(status.address, "경기도 의왕시 시청로 1")
        self.assertEqual(status.total_count, 4)
        self.assertEqual(status.available_count, 2)
        self.assertEqual(status.charging_count, 1)
        self.assertEqual(status.unavailable_count, 1)
        self.assertEqual(status.fast_available_count, 1)
        self.assertEqual(status.slow_available_count, 1)
        self.assertEqual([c.charger_id for c in status.chargers], ["01", "02", "03", "04"])
        self.assertEqual(status.chargers[1].charger_type_label, "DC콤보")

    def test_aggregate_station_status_with_cached_metadata(self) -> None:
        status_items = [
            {"statId": "ME000001", "chgerId": "01", "stat": "2"},
            {"statId": "ME000001", "chgerId": "02", "stat": "3"},
        ]
        metadata = {
            "01": {"chgerType": "04", "output": "50"},
            "02": {"chgerType": "02", "output": "7"},
        }
        status = aggregate_station_status(
            "ME000001",
            status_items,
            fallback_station_name="테스트 충전소",
            charger_metadata=metadata,
        )
        self.assertEqual(status.station_name, "테스트 충전소")
        self.assertEqual(status.available_count, 1)
        self.assertEqual(status.fast_available_count, 1)
        self.assertEqual(status.slow_available_count, 0)
        self.assertEqual(status.chargers[0].output_kw, "50")

    def test_aggregate_station_status_empty_raises(self) -> None:
        with self.assertRaises(EvChargerNotFoundError):
            aggregate_station_status("ME000001", [])


if __name__ == "__main__":
    unittest.main()
