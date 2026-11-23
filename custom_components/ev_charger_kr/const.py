"""Constants for the EV Charger KR integration."""

from datetime import timedelta

DOMAIN = "ev_charger_kr"

CONF_API_KEY = "api_key"
CONF_STATION_ID = "stat_id"
CONF_STATION_NAME = "station_name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_MINUTES = 3
MIN_SCAN_INTERVAL_MINUTES = 1
MAX_SCAN_INTERVAL_MINUTES = 60

DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)

BASE_URL = "https://apis.data.go.kr/B552584/EvCharger"
ENDPOINT_CHARGER_INFO = f"{BASE_URL}/getChargerInfo"
ENDPOINT_CHARGER_STATUS = f"{BASE_URL}/getChargerStatus"

# 한국환경공단 충전기 상태 코드 (stat)
STAT_UNKNOWN = "0"
STAT_COMM_ERROR = "1"
STAT_AVAILABLE = "2"  # 충전대기 (사용가능)
STAT_CHARGING = "3"
STAT_SUSPENDED = "4"
STAT_INSPECTING = "5"
STAT_RESERVED = "6"
STAT_UNCONFIRMED = "9"

STAT_LABELS: dict[str, str] = {
    STAT_UNKNOWN: "알 수 없음",
    STAT_COMM_ERROR: "통신이상",
    STAT_AVAILABLE: "충전대기",
    STAT_CHARGING: "충전중",
    STAT_SUSPENDED: "운영중지",
    STAT_INSPECTING: "점검중",
    STAT_RESERVED: "예약중",
    STAT_UNCONFIRMED: "상태미확인",
}

# 충전기 타입 코드 (chgerType)
CHARGER_TYPE_LABELS: dict[str, str] = {
    "01": "DC차데모",
    "02": "AC완속",
    "03": "DC차데모+AC3상",
    "04": "DC콤보",
    "05": "DC차데모+DC콤보",
    "06": "DC차데모+AC3상+DC콤보",
    "07": "AC3상",
    "08": "DC콤보(완속)",
}

# 급속 충전기 타입 코드
FAST_CHARGER_TYPES = {"01", "03", "04", "05", "06", "07"}
SLOW_CHARGER_TYPES = {"02", "08"}

# 공공데이터포털 시도 코드 (zcode)
ZCODE_OPTIONS: dict[str, str] = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "43": "충청북도",
    "44": "충청남도",
    "46": "전라남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
    "51": "강원특별자치도",
    "52": "전북특별자치도",
}
