# EV Charger KR (한국 전기차 충전소)

Home Assistant에서 **공공데이터포털(한국환경공단_전기자동차 충전소 정보)** API를 이용해 등록한 전기차 충전소의 **충전 가능 대수** 및 충전기 상태를 조회하는 HACS 커스텀 통합 구성요소입니다.

## 주요 기능
- UI(`Config Flow`)를 통한 API 키 및 충전소 ID(`statId`) 등록
- 충전소별 **충전 가능 대수** 센서 (`대`)
- **전체 충전기 수**, **충전 중 대수**, **고장/점검/통신이상 대수** 등 상태 집계
- 급속/완속 충전기별 가용 대수 및 개별 충전기 상세 상태(`extra_state_attributes`) 제공
- 옵션(`Options Flow`)을 통한 갱신 주기(분) 설정

## 사전 준비
1. [공공데이터포털](https://www.data.go.kr/)에서 **한국환경공단_전기자동차 충전소 정보** Open API 활용 신청
2. 발급받은 **일반 인증키(Decoding 또는 Encoding)** 준비
3. 조회할 충전소의 **충전소 ID (`statId`)** 확인 (예: `ME000001`, `28260005` 등)

## 설치 방법
### HACS (사용자 지정 저장소)
1. HACS → **통합 구성요소** → 우측 상단 메뉴 → **사용자 지정 저장소**
2. 이 저장소 URL 추가 (카테고리: `Integration`)
3. `EV Charger KR` 설치 후 Home Assistant 재시작
4. **설정 → 기기 및 서비스 → 통합 구성요소 추가 → EV Charger KR** 검색 후 등록

### 수동 설치
1. `custom_components/ev_charger_kr` 폴더를 Home Assistant의 `/config/custom_components/ev_charger_kr`로 복사
2. Home Assistant 재시작
