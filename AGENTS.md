# Agent Guidelines (`ha-ev-charger-kr`)

이 저장소에서 작업하는 모든 AI 에이전트는 아래 작업 플로우와 규칙을 반드시 준수해야 합니다.

## 1. 변경 사항 기록 의무 (`CHANGELOG.md`)
- 코드, 블루프린트, 번역, 설정, 문서 등 **모든 의미 있는 변경 사항은 반드시 [CHANGELOG.md](CHANGELOG.md)에 기록**합니다.
- 개발 중 변경 사항은 `## [Unreleased]` 섹션 아래(`Added`, `Changed`, `Fixed`, `Removed` 등)에 추가합니다.
- **예외 없이**, 커밋/푸시 전에 해당 작업 내역이 `CHANGELOG.md`에 누락되지 않았는지 확인합니다.

## 2. 버전 릴리즈 작업 플로우
새 버전을 발행할 때는 아래 순서를 반드시 따릅니다:
1. `CHANGELOG.md`의 `[Unreleased]` 내용을 새 버전 섹션(예: `## [0.3.0] - YYYY-MM-DD`)으로 정리하고, 상단에 빈 `## [Unreleased]` 섹션을 유지합니다.
2. `custom_components/ev_charger_kr/manifest.json`의 `"version"` 값을 새 버전과 일치시킵니다.
3. 검증 명령어를 실행해 모두 통과하는지 확인합니다:
   - `python3 -m unittest discover -s tests -v`
   - `python3 -m compileall -q custom_components/ev_charger_kr`
   - 모든 `.json` 파일 유효성 검사
4. 변경 사항을 커밋한 뒤 버전 태그(`git tag vX.Y.Z`)를 생성하고 브랜치와 태그를 함께 푸시합니다(`git push origin main && git push origin vX.Y.Z`).
5. GitHub Releases에 해당 태그(`vX.Y.Z`)와 `CHANGELOG.md`의 릴리즈 노트를 반영해 공식 릴리즈를 발행합니다.

## 3. 일반 예시 유지 규칙
- `README.md`, `strings.json`, `translations/*.json`, `tests/` 등의 공개 예시에는 특정 개인 거주지나 개인 식별 가능한 충전소 이름 대신 범용 예시(예: `서울시청`, `판교역`)를 사용합니다.
