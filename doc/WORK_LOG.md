# A안 진행 기록

기준 커밋: `447db631b079f6c8b5e67c3b2bfce4dbaf59169f`

규칙: [AGENTS.md](../AGENTS.md) / 설계와 이슈 후보: [PLAN_A.md](PLAN_A.md)

## 승인 기록

| 날짜 (KST) | 대상 | 승인 근거 | 허용 범위 |
|---|---|---|---|
| 2026-10-20 | 기준 버전 업로드 | 사용자: 현재 상황부터 GitHub에 업로드 | 기준 버전 커밋·push 완료 |
| 2026-10-20 | 준비 문서 | 사용자: 개발 참조 md 작성 및 이슈 단위 작업 요청 | 준비 문서 이슈의 작성·검증·PR·머지·종료·브랜치 정리 |
| 2026-10-20 | CodeRabbit 설정 | 사용자: 코드래빗으로 코드리뷰를 하고 싶으니 GitHub에 설정 요청 | 설정 이슈·설정 파일·작업 규칙·PR, App 연결 및 실제 리뷰 확인. 추가 권한은 사용자 확인 |
| 2026-10-20 | A-01 기준 동작과 평가 데이터 | CodeRabbit 이슈 완료 보고 후 사용자: “넘어가자” | A-01 이슈·브랜치·테스트·문서·PR·리뷰·머지·종료·브랜치 정리 |
| 2026-10-20 | A-02 근거 모델과 출처 보존 | A-01 완료 보고 후 사용자: “넘어가사”, 첫 CodeRabbit 리뷰는 최소 5분 대기 요청 | A-02 이슈·브랜치·구현·검증·문서·PR·리뷰·머지·종료·브랜치 정리 |
| 2026-10-20 | A-03 구조화된 진단 검증기 | A-02 완료 보고 후 사용자: 다음 이슈 진행 승인, 리뷰 대기 시간을 10분으로 변경 | A-03 이슈·브랜치·구현·검증·문서·PR·리뷰·머지·종료·브랜치 정리 |

**현재 승인된 개발 범위는 A-03이다. A-04의 착수 승인은 아직 받지 않았다.**

## 작업 기록

### 준비: A안 개발 기준과 작업 흐름

- 이슈: [#1](https://github.com/DoHanChoi/skala-mini-project-ai/issues/1)
- 작업 브랜치: `docs/issue-1-plan-a-workflow`
- PR: [#2](https://github.com/DoHanChoi/skala-mini-project-ai/pull/2)
- 산출물: AGENTS.md, PLAN_A.md, WORK_LOG.md, README 개발 문서 링크.
- 코드 변경: 없음. 문서만 변경한다.
- 검증 결과: 상대 링크 18개 유효, 기준 커밋과 승인 경계 확인, 문서 간 범위·승인 규칙 검토, `git diff --check` 통과. 애플리케이션 변경이 없어 실행 테스트는 수행하지 않았다.
- 완료 확인: PR #2가 `82af0da6fb5878e87c8bd6abcac3255801270e0b`로 머지되었고 이슈 #1은 completed로 종료되었다. 원격·로컬 작업 브랜치 삭제와 main 동기화를 확인했다.

### 설정: CodeRabbit 자동 PR 리뷰

- 이슈: [#3](https://github.com/DoHanChoi/skala-mini-project-ai/issues/3)
- 브랜치: `chore/issue-3-coderabbit`
- PR: [#4](https://github.com/DoHanChoi/skala-mini-project-ai/pull/4)
- 산출물: `.coderabbit.yaml`, CodeRabbit 운영 문서, AGENTS·README의 리뷰 단계, 승인 기록.
- 앱 연결: 사용자가 본인 인증을 완료한 뒤, 개인 계정의 CodeRabbit 설치와 `Only select repositories`에서 `DoHanChoi/skala-mini-project-ai` 한 개만 연결된 상태를 확인했다.
- 로컬 검증: 공식 JSON Schema 검증과 Markdown 상대 링크 검사, `git diff --check` 통과. 실제 봇 리뷰는 설정 PR에서 확인한다.
- 실제 리뷰: [CodeRabbit 리뷰](https://github.com/DoHanChoi/skala-mini-project-ai/pull/4#pullrequestreview-5581216583)가 `a5f1be4` 커밋의 변경 파일 5개를 검토했고 한국어 수정 의견 1건을 제출했다. 저장소 설정 적용과 자동 리뷰 동작을 확인했다.
- 지적 처리: 공식 문서로 작성자 승인 우회 옵션의 기본값을 확인하고 `allow_author_approval: false`를 추가했다. 수정 커밋의 자동 재리뷰 완료를 머지 전에 확인한다.
- 사후 정리: 머지·이슈 종료·브랜치 삭제는 재리뷰 통과 후 수행한다. 실제 최종 상태는 PR #4와 이슈 #3 및 Git에서 확인하며, 완료 전에는 완료로 기록하지 않는다.
- 완료 기준: 공식 스키마 검증, 실제 CodeRabbit 리뷰 확인 및 지적 처리, 최신 커밋 리뷰 완료 후 머지·종료·브랜치 정리.
- 앱 설치나 리뷰가 완료되지 않으면 PR을 머지하지 않고 이슈를 열린 상태로 유지한다.
- 완료 확인: 최신 `3635e36` 커밋을 CodeRabbit이 재리뷰 후 승인했고 상태 검사가 성공했다. PR #4는 `300853f95c2a3059d6e163905936393f89a39648`로 머지, 이슈 #3은 completed로 종료되었다. 원격·로컬 작업 브랜치 삭제와 main 동기화를 확인했다. [완료 기록](https://github.com/DoHanChoi/skala-mini-project-ai/pull/4#issuecomment-6284461099).

### A-01: 기준 동작과 고정 평가 데이터

- 승인: 사용자 “넘어가자”.
- 이슈: [#5](https://github.com/DoHanChoi/skala-mini-project-ai/issues/5).
- 작업 브랜치: `test/issue-5-baseline-fixtures`.
- PR: [#6](https://github.com/DoHanChoi/skala-mini-project-ai/pull/6).
- 산출물: 고정 근거 9개·초안 24개 fixture, 오프라인 특성·회귀 테스트, 기준 커밋 임시 추출 실행기, [기준 평가 문서](BASELINE.md).
- 실행 코드 변경: 없음. A-02의 근거 모델과 A-03의 새 검증기는 구현하지 않는다.
- 검증: 현재 코드와 `447db63` 기준 코드에서 각각 15개 테스트 통과. 기준 실행기는 같은 테스트·fixture·인터프리터를 사용한다. 실제 모델·MCP 네트워크·사용자 DB를 사용하지 않는다.
- 결과: 현재 검사에서 오류 유형 대응 텍스트 18개가 모두 통과한다. 3회 강제 합격, 검증 전 SSE 초안 및 테스트용 프롬프트 노출을 재현했다. 개선 성공이나 실모델 품질 결과로 해석하지 않는다.
- PR과 최신 커밋의 실제 CodeRabbit 리뷰·지적 처리·머지 결과는 해당 PR 기록과 GitHub 상태로 확인한다. 리뷰 완료 후 머지·이슈 종료·브랜치 정리를 수행한다.
- 첫 리뷰: CodeRabbit이 `e8f7e9d` 커밋을 [승인](https://github.com/DoHanChoi/skala-mini-project-ai/pull/6#pullrequestreview-5582726593)했으며 기능 결함 지적은 없었다. 설명문 커버리지 경고를 처리하기 위해 테스트·지원 함수 29개의 목적을 docstring으로 보완했다. 보완 후 현재·기준 코드 각각 15개 테스트 통과 및 함수 설명문 29/29개를 확인했으며, 최신 커밋의 리뷰 완료 상태는 PR에 기록한다.
- 완료 확인: 최신 `82b6901` 증분 리뷰와 사전 검사 5개 통과 후 PR #6을 `4357e6af99dc65b8939117d3d373d2382e3acc92`로 머지했다. 이슈 #5 completed 종료, 원격·로컬 브랜치 삭제와 main 동기화를 확인했다. [완료 기록](https://github.com/DoHanChoi/skala-mini-project-ai/pull/6#issuecomment-6287136489).

### A-02: 요청별 근거 모델과 출처 보존

- 승인: 사용자 “넘어가사”. 첫 CodeRabbit 리뷰는 시작 후 최소 5분 뒤 결과를 확인한다.
- 이슈: [#7](https://github.com/DoHanChoi/skala-mini-project-ai/issues/7).
- 작업 브랜치: `feat/issue-7-evidence-provenance`.
- PR: [#8](https://github.com/DoHanChoi/skala-mini-project-ai/pull/8).
- 산출물: Evidence 모델·모니터링/매뉴얼 정규화, 요청별 근거 수집, [모델 계약 문서](EVIDENCE.md), 근거 테스트 17개.
- 보존 범위: 원본 전체 사본, 요청·태스크 ID, 실제 MCP 서버·도구/URI, 수집 시각·실측 시각, 매뉴얼 제목·본문 SHA-256.
- 활용 범위: missing·unknown·비정상·시스템 불일치와 없는 매뉴얼을 표시한다. 모델 analysis는 원본 근거로 추가하지 않는다. 현재 답변의 참·거짓 검증 성공을 의미하지 않는다.
- 검증: 전체 32개 테스트, 기준 커밋의 A-01 회귀 15개 통과. 병렬 역순 완료·요청 분리·재계획·재시도·재작성 보존, 원본/사본 격리, 정상 경계값·오류값, 출처·해시와 API 회귀를 확인했다.
- 기존 응답·모델 입력·저장 계약을 유지한다. A-03 검증기와 A-04 출력 차단은 아직 구현하지 않는다.
- PR, 실제 리뷰·지적 처리, 최신 HEAD 검사 및 머지·정리 결과는 해당 PR 기록과 GitHub/Git으로 확인한다.
- 완료 확인: 최신 `9788a0e` 전체 리뷰가 승인됐고 상태·사전 검사 5개가 통과했다. PR #8은 `b42ff2b29b2d65b9b173a96114fad1d6253bbad0`로 머지, 이슈 #7은 completed로 종료됐다. 원격·로컬 브랜치 삭제와 main 동기화를 확인했다. [완료 기록](https://github.com/DoHanChoi/skala-mini-project-ai/pull/8#issuecomment-6287649843).

### A-03: 구조화된 진단 검증과 표시

- 승인: 다음 이슈 진행 및 첫 CodeRabbit 리뷰 대기를 최소 10분으로 늘리라는 사용자 요청.
- 이슈: [#9](https://github.com/DoHanChoi/skala-mini-project-ai/issues/9).
- 작업 브랜치: `feat/issue-9-diagnosis-validation`.
- PR: [#10](https://github.com/DoHanChoi/skala-mini-project-ai/pull/10).
- 산출물: Observation·DiagnosisDraft·검증 결과 계약, 순수 검증기·원본 기반 렌더링, [진단 검증 문서](VALIDATION.md), 검증·표시 테스트 23개.
- 검증 범위: 구조·시스템·측정 항목·원본 값·단위·요청별 출처 연결. 가설·조치의 의미나 실제 원인을 자동 판정하지 않는다.
- 검증 결과: 전체 55개와 기준 A-01 테스트 15개 통과. 고정 후보 초안 정상 6개 통과·오류 18개 거부, 파싱·중복 키·비정상 수치·타 요청/중복/훼손 근거, 입력 비변경·시도 상한·실패 초안 미노출을 확인했다. 중복 ID의 한 후보가 훼손된 경우도 입력 순서와 무관하게 대체 출력에서 제외한다.
- 라이브 그래프·세 모델 백엔드·API·UI는 변경하지 않는다. 실제 응답 연결과 재작성·초안 차단은 A-04다.
- 실제 리뷰·검사·지적 처리와 머지·정리의 최종 상태는 해당 PR과 GitHub/Git에서 확인한다.

## 다음 후보

- A-04: 모델·그래프·API 통합.
- fake/ollama/openai 구조화된 출력, 재작성·반복 실패 종료, REST/SSE 최종 계약, 검증 전 장애 초안 차단을 함께 연결한다.
- A-03이 끝나도 자동 착수하지 않는다. **“다음 이슈로 넘어갈까요?”**에 대한 사용자 응답을 기다린다.

## 범위 밖 발견 사항

- 에이전트 실행 스크립트가 시작할 때 `session.db`를 삭제한다. 평가·테스트는 별도 임시 DB를 사용하며, 실행 스크립트 수정은 필요 시 별도 이슈로 논의한다.
- 미인식 시스템의 `auth-service` 폴백과 매뉴얼 키워드 선택 한계는 A안의 사실 인용 검증으로 해결되지 않는다.
- 실모델 시험은 아직 수행하지 않았다. 예시·fixture 결과를 실모델 개선 실측으로 보고하지 않는다.
