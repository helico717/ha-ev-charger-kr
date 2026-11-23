# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT 라이선스 파일([LICENSE](LICENSE)) 추가 및 HACS 검증 통과를 위한 GitHub 저장소 Topics 설정

## [0.2.0] - 2026-11-23

### Added
- **시/도 및 키워드 기반 충전소 검색과 체크박스 다중 선택** (`ConfigFlow`, `OptionsFlow`)
  - 전국 17개 시/도 코드(`ZCODE_OPTIONS`) 및 `EvChargerApiClient.async_search_stations` 추가
  - `SelectSelector(multiple=True)`를 통해 검색 결과에서 여러 충전소를 체크박스로 일괄 등록 가능
  - 기존 API 키 자동 채움, `OptionsFlow` 메뉴에서 다른 시/도 충전소 추가 검색 및 등록 충전소 관리(삭제) 지원
- **등록 충전소 수 기반 조회 주기 자동 조절** (`calculate_auto_scan_interval`, `EvChargerCoordinator`)
  - 전체 등록 충전소 수와 일일 API 한도(85% 안전 여유 기준)에 맞춰 모든 코디네이터의 `update_interval` 자동 계산 및 동기화
  - 옵션에서 자동 조절 ON/OFF 및 수동 주기(1~60분) 설정 가능
- **API 일일 잔여 한도 센서** (`EvChargerApiRateLimitSensor`)
  - `X-RateLimit-Remaining`, `X-RateLimit-Limit` 응답 헤더를 파싱해 추가 트래픽 소모 없이 잔여 한도(`건`) 및 사용률 속성 제공
- **충전기 운영사(`operator`) 속성** (`StationStatus.operator`, `available_chargers` 센서 `operator` 속성)
- **통합 구성요소 브랜드 아이콘 및 로고** (`custom_components/ev_charger_kr/brand/`)
- **구역별 충전 가능 대수 모바일 알림 블루프린트** (`blueprints/automation/ev_charger_kr/zone_arrival_charger_notify.yaml`)
  - 최대 3개 구역별 1개 이상 충전소 센서 매핑, 알림 전 즉시 갱신, 만차 시 알림 생략 옵션 지원
  - 자동화 `실행` 버튼 수동 실행 시 설정된 모든 구역에 대한 테스트 알림 발송 지원
  - 사용자 지정 제목 및 간결한 모바일 알림 포맷(`▫️ N대 가능 — 운영사 (급속/완속)`) 적용
- **사용자 안내 문서 및 저장소 운영 가이드 강화** (`README.md`, `CHANGELOG.md`, `AGENTS.md`)

### Fixed
- **주기적 상태 조회 엔드포인트 수정** (`EvChargerApiClient.async_get_station_status`)
  - `getChargerStatus`가 최근 상태 변경이 없는 충전소를 빈 목록으로 반환하는 문제를 확인하고, 전체 충전기와 최신 `stat`을 안정적으로 반환하는 `getChargerInfo`를 사용하도록 수정
- **구성 옵션에서 충전소 추가·삭제 시 상위 항목 제목 자동 동기화** (`EV Charger KR (N개 충전소)`)
- **안내 문구 및 테스트 데이터 일반화** (`README.md`, `strings.json`, `ko.json`, `test_api.py` 예시를 범용 예시로 교체)

## [0.1.0] - 2026-11-23

### Added
- `ev_charger_kr` 커스텀 통합 구성요소 초기 골격 및 HACS 메타데이터(`hacs.json`, `manifest.json`) 생성
- 공공데이터포털 한국환경공단 전기차 충전소 Open API 비동기 클라이언트(`api.py`) 및 상태 집계 로직 구현
- `DataUpdateCoordinator` 기반 폴링 코디네이터(`coordinator.py`) 및 4종 충전소 센서(`available_chargers`, `charging_chargers`, `total_chargers`, `unavailable_chargers`) 구현
- 기본 `ConfigFlow` / `OptionsFlow` 및 다국어 번역(`strings.json`, `ko.json`, `en.json`) 추가
- Hassfest / HACS GitHub Actions 워크플로우(`.github/workflows/validate.yml`) 및 단위 테스트(`tests/test_api.py`) 추가
