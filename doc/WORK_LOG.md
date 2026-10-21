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
| 2026-10-21 | A-04 모델·그래프·API 통합 | A-03 완료 보고 후 사용자: “다음 이슈로 가자” | A-04 이슈·브랜치·구현·검증·문서·PR·리뷰·머지·종료·브랜치 정리 |
| 2026-10-21 | A-05 근거 확인 UI | A-04 완료 보고와 다음 이슈 승인 질문 후 사용자: “응” | A-05 이슈·브랜치·구현·검증·문서·PR·리뷰·머지·종료·브랜치 정리 |
| 2026-10-21 | A-06 전후 평가와 결과 문서 | A-05 완료 보고 후 사용자: “넘어가” | A-06 이슈·브랜치·평가 도구·검증·문서·PR·리뷰·머지·종료·브랜치 정리 |
| 2026-10-21 | A-07 빈 알림 생성 안내·피드백 | A-06 완료 보고와 다음 후보 제안 후 사용자: “넘어가” | A-07 이슈·브랜치·구현·검증·문서·PR·리뷰·머지·종료·브랜치 정리 |

**현재 승인된 개발 범위는 A-07이다. 그 밖의 후속 구현은 별도 승인 대상이다.**

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
- 산출물: Observation·DiagnosisDraft·검증 결과 계약, 순수 검증기·원본 기반 렌더링, [진단 검증 문서](VALIDATION.md), 검증·표시 테스트 24개.
- 검증 범위: 구조·시스템·측정 항목·원본 값·단위·요청별 출처 연결. 가설·조치의 의미나 실제 원인을 자동 판정하지 않는다.
- 검증 결과: 전체 56개와 기준 A-01 테스트 15개 통과. 고정 후보 초안 정상 6개 통과·오류 18개 거부, 파싱·중복 키·비정상 수치·타 요청/중복/훼손 근거, 입력 비변경·시도 상한·실패 초안 미노출을 확인했다. 중복 ID의 한 후보가 훼손된 경우도 입력 순서와 무관하게 대체 출력에서 제외한다.
- 첫 리뷰 지적: [CodeRabbit 의견](https://github.com/DoHanChoi/skala-mini-project-ai/pull/10#discussion_r4323537864)의 구조 검증 실패 사본에 대한 중복 ID 제외 요구를 재현했다. 추가 필드·타임존 없는 시각·bool 태스크 위치의 앞뒤 순서 6개 하위 사례가 수정 전 실패했고, 구조 검증 실패 시에도 주장한 문자열 ID를 제외 목록에 반영하도록 수정했다.
- 라이브 그래프·세 모델 백엔드·API·UI는 변경하지 않는다. 실제 응답 연결과 재작성·초안 차단은 A-04다.
- 실제 리뷰·검사·지적 처리와 머지·정리의 최종 상태는 해당 PR과 GitHub/Git에서 확인한다.
- 완료 확인: CodeRabbit 최신 HEAD 승인과 두 리뷰 스레드 해결 후 PR #10을 `697e63c0ef1a74eed1787d3a9f39d7e2089326a2`로 머지했다. 이슈 #9 completed 종료, 원격·로컬 브랜치 삭제, main 동기화를 확인했다. [완료 기록](https://github.com/DoHanChoi/skala-mini-project-ai/pull/10#issuecomment-6304525263).

### A-04: 모델·그래프·API 검증 통합

- 승인: A-03 완료 보고 후 사용자 “다음 이슈로 가자”(2026-10-21, Asia/Seoul). 첫 CodeRabbit 리뷰는 최소 10분 대기한다.
- 이슈: [#11](https://github.com/DoHanChoi/skala-mini-project-ai/issues/11).
- 작업 브랜치: `feat/issue-11-validation-integration`.
- PR: [#12](https://github.com/DoHanChoi/skala-mini-project-ai/pull/12).
- 산출물: 세 백엔드의 공통 `diagnose` 계약과 프롬프트, 그래프 검증·재작성·실패 종료, REST/SSE 진단·근거·검증 상태, 장애 초안·원시 프롬프트 공개 차단, [통합 계약](PIPELINE.md).
- 검증: 현재 코드 58개(근거 17 + 순수 검증 24 + 통합 17), 고정 기준 커밋 15개. 기준 특성 테스트는 내용 변경 없이 `pinned_*.py`로 분리해 기준 커밋에서만 실행한다.
- 브라우저: 실제 환경설정·사용자 DB·MCP 대신 임시 DB와 고정 fake 서버를 로컬 전용 포트에서 사용했다. 기존 Vue 화면의 진행 이벤트·재작성 후 최종 본문과 입력 재활성화를 확인했다. agent-browser CLI가 없어 내장 브라우저로 확인했다.
- 한계: 실모델 응답 품질·실제 MCP 프로토콜·운영 지연은 측정하지 않았다. OpenAI는 JSON 모드와 프롬프트 스키마이며 실제 내용은 코드 검증을 거친다. 가설·조치 의미 검증·자동 실행은 하지 않는다. 상세 UI는 A-05 범위다.
- PR, 실제 리뷰·최신 HEAD 검사·지적 처리와 머지·정리의 최종 상태는 해당 PR과 GitHub/Git에서 확인한다.
- 완료 확인: 최신 `d2bec55`의 실제 CodeRabbit 리뷰가 승인됐고 수정 요구 사항 없이 상태·사전 검사가 통과했다. PR #12를 `d303cd71ebacaf622634b625b2da4cbe3e065bf2`로 머지했다. 이슈 #11 completed 종료, 원격·로컬 브랜치 삭제와 main 동기화를 확인했다. [완료 기록](https://github.com/DoHanChoi/skala-mini-project-ai/pull/12#issuecomment-6304831912).

### A-05: 근거 확인 UI

- 승인: A-04 완료 보고 후 다음 이슈 질문에 사용자 “응”(2026-10-21, Asia/Seoul). 첫 CodeRabbit 리뷰는 최소 10분 대기한다.
- 이슈: [#13](https://github.com/DoHanChoi/skala-mini-project-ai/issues/13).
- 작업 브랜치: `feat/issue-13-evidence-ui`.
- PR: [#14](https://github.com/DoHanChoi/skala-mini-project-ai/pull/14).
- 산출물: 관측·가설·조치 구역, 검증 범위·횟수·실패/비대상/알 수 없음 표시, 답변별 근거 펼치기와 키보드 초점 연결, 원본 텍스트 표시와 좁은 화면 스타일, [UI 계약](UI.md).
- 자동 검증: Node 내장 UI 동작 검사 13개, 기존 Python 58개와 고정 기준 커밋 15개. Node 검사는 실제 화면 스크립트를 VM에서 실행하며 실제 Vue 렌더링을 대신하지 않는다.
- 브라우저 검증은 실제 모델·MCP·사용자 DB·환경설정 없이 요청마다 독립적인 fake 그래프를 쓰는 `tests/ui_fixture_server.py`로 수행한다. 이 fixture 서버는 운영 서버와 대화 저장 검증이 아니다.
- 화면 확인: 정상 복수 시스템·재작성, 3회 실패·unknown/없는 매뉴얼, 매뉴얼만 없는 정상 관측, 일반 대화·v1·정보 누락과 HTML 원문 시나리오를 확인했다. 근거 버튼의 답변별 연결·키보드 접기와 319px 화면의 가로 넘침 없음, 원문의 이미지·스크립트·링크 요소 미생성을 확인했다. v1 이벤트의 대상 누락 문구를 수정하고 재확인했다.
- 한계: 가설·조치 의미·실제 원인·출처 진위·실모델 품질은 검증하지 않는다. 백엔드 계약은 유지하며 전후 평가는 A-06 범위다.
- PR, 최신 HEAD 실제 리뷰·검사·지적 처리·머지·정리 결과는 해당 PR과 GitHub/Git에서 확인한다.
- 완료 확인: 최신 `5bbe602`의 실제 CodeRabbit 리뷰가 승인됐고 수정 요구 사항 없이 상태·사전 검사가 통과했다. PR #14를 `56a7b12e88976d97ce4dc02426f1aea342452b1d`로 머지했다. 이슈 #13 completed 종료, 원격·로컬 브랜치 삭제와 main 동기화를 확인했다. [완료 기록](https://github.com/DoHanChoi/skala-mini-project-ai/pull/14#issuecomment-6305133856).

### A-06: 전후 평가와 결과 문서

- 승인: A-05 완료 보고 후 사용자 “넘어가”(2026-10-21, Asia/Seoul). 첫 CodeRabbit 리뷰는 최소 10분 대기한다.
- 이슈: [#15](https://github.com/DoHanChoi/skala-mini-project-ai/issues/15).
- 작업 브랜치: `test/issue-15-evaluation-report`.
- PR: [#16](https://github.com/DoHanChoi/skala-mini-project-ai/pull/16).
- 산출물: Git 소스 격리 평가 러너, fixture·독립 관측 대조·집계·계약 검사, 원시 JSON/실행 보고서, [평가 결과와 재현 절차](EVALUATION.md).
- 오프라인: 정상 6개는 양쪽 통과, 대응 오류 18개의 검출은 기준 0/18·개선 18/18. 통제 파이프라인 36회에서 최초 성공·수정·3회 실패와 REST/SSE/저장 경계를 재현했다. 표현 계약이 다른 개발 fixture 결과이며 실모델 정확도로 보고하지 않는다.
- 실모델: 설치된 로컬 qwen3:8b, 질문 3개 × 버전별 1회. 같은 스냅샷·모델 digest·temperature/seed/token/context 예산, think=false·비스트리밍으로 통제했다. CPU는 2회 후 통과(관측 7/7 원본 일치), 메모리는 빈 알림 문자열 반복으로 3회 후 원본 대체 답변, unknown도 3회 후 실패 종료했다. 실제 운영 기본 설정·전체 라우팅·MCP·실모델 일반화를 주장하지 않는다.
- 비용·지연: 기준 품질 모델 1,160토큰·평균 6.18초, 개선 16,673토큰·평균 65.51초. 각 3요청의 통제 환경 기술 통계이며 가상 단가 추정은 실제 API 청구액이 아니다. 순서·캐시·로컬 작업 경합을 엄격히 통제하지 않아 운영 성능 우열로 일반화하지 않는다.
- 검증: Python 74개(기존 58 + 평가 16), 기준 15개, UI 13개 통과. raw JSON에 실행 조건·해시·예외·각 호출·토큰·최종 결과를 보존한다. 측정 원본·실행 코드 커밋 `59957ac`과 후속 CLI·사용량 누락 처리 보강을 구분하고 소스 해시·원본 보존·재집계를 검사했다. 모델을 내려 메모리를 정리하고 이번 평가를 위해 기동한 Ollama 서버를 종료했다.
- 한계와 후속: 빈 알림 생성/피드백, 원본 전부 인용 불가 시 조기 종료, 독립 질문·반복·검토 확대를 후보로 남겼다. 운영 코드는 평가 중 변경하지 않았고 후속 구현은 미착수다.
- PR, 최신 HEAD 실제 리뷰·검사·지적 처리와 머지·정리 결과는 해당 PR과 GitHub/Git에서 확인한다.

- 완료 확인: 최신 `aad2ad7`의 실제 CodeRabbit 승인·success·미해결 스레드 없음 확인 후 PR #16을 `dd918bd8b369bfdca280675ccb6c3a0939fccb3c`로 머지했다. 이슈 #15 completed 종료, 원격·로컬 브랜치 삭제와 main 동기화를 확인했다. [완료 기록](https://github.com/DoHanChoi/skala-mini-project-ai/pull/16#issuecomment-6305577941).

### A-07: 빈 알림 생성 안내·재작성 피드백

- 승인: A-06 완료와 빈 알림 개선 후보 제안 후 사용자 “넘어가”(2026-10-21 KST). 첫 CodeRabbit 리뷰는 최소 10분 대기한다.
- 이슈: [#17](https://github.com/DoHanChoi/skala-mini-project-ai/issues/17).
- 브랜치: `fix/issue-17-empty-alert-rewrite`.
- PR: [#18](https://github.com/DoHanChoi/skala-mini-project-ai/pull/18).
- 변경: 세 백엔드 공통 프롬프트에서 빈 알림은 관측 0개임을 명시하고, 기존 `value_mismatch`·위치를 유지하며 잘못된 알림 항목 삭제·다른 유효 관측 유지 피드백을 제공한다. [계약과 한계](ALERT_REWRITE.md).
- 검증: A-06 실제 메모리 실패 초안 3개 재생, 별도 시스템·수치의 경계, 원본 비변경과 오류 원문 미반사, 세 백엔드 프롬프트 전달, REST/SSE·임시 DB의 두 번째 성공과 3회 실패 종료를 새 테스트 5개로 확인했다. 기존 74개와 합쳐 Python 79개, 기준 15개·UI 13개 회귀가 통과했다. 문서 상대 링크·함수 설명과 diff 공백 검사도 확인했다.
- 한계: 결정론적 모델 대역이며 실모델 호출·수정 성공률·지연·토큰의 새 실측은 수행하지 않는다. A-06 수치·원시 결과는 수정하지 않고 역사적 결과로 유지한다. 검증 기준 완화·자동 관측 삭제·원본 부재 조기 종료는 구현하지 않는다.
- 첫 리뷰: [CodeRabbit 지적](https://github.com/DoHanChoi/skala-mini-project-ai/pull/18#discussion_r4332111939)의 결과 JSON 기본 인코딩 의존을 확인하고 새 회귀 테스트의 읽기를 UTF-8로 명시했다. 관련 5개 검사와 diff 공백 검사를 다시 통과했다.
- 실제 PR·최신 HEAD 리뷰·검사·머지·종료·브랜치 정리는 해당 PR과 GitHub/Git에서 확인한다.

## 다음 후보

- 초기 A안 6단계 완료 후 빈 알림 개선을 A-07로 승인받았다.
- 다음 후보는 유효 원본이 전혀 없을 때의 조기 종료 정책과 더 넓은 독립 평가다. 아직 착수하지 않았다.
- 현재 이슈의 머지·정리 후 **“다음 이슈로 넘어갈까요?”**에 대한 사용자 응답과 후속 범위 승인을 기다린다.

## 범위 밖 발견 사항

- 에이전트 실행 스크립트가 시작할 때 `session.db`를 삭제한다. 평가·테스트는 별도 임시 DB를 사용하며, 실행 스크립트 수정은 필요 시 별도 이슈로 논의한다.
- 미인식 시스템의 `auth-service` 폴백과 매뉴얼 키워드 선택 한계는 A안의 사실 인용 검증으로 해결되지 않는다.
- A-05까지 실모델 시험은 수행하지 않았으며, A-06에서 별도 질문의 로컬 모델 작성 비교를 수행했다. 통제 조건과 한계를 명시하고 fixture 검출률과 혼합하지 않는다.

## 2026-10-21: 공개 README 갱신

- 사용자 “깃허브 리드미도 업데이트해” 요청으로 이슈 [#19](https://github.com/DoHanChoi/skala-mini-project-ai/issues/19) 착수. `docs/issue-19-readme-update`에서 진행한다.
- README를 구현 완료 상태, 실제 기능·그래프·실행 방법·검사 명령·문서 탐색 중심으로 갱신했다. 공개 제목과 설명에는 내부 계획 명칭 대신 기능명을 사용한다.
- [최종 OpenAI 평가](FINAL_EVALUATION.md)와 [공개 측정 요약](../evaluation/results/openai-final-summary.json)을 추가했다. 저장된 최종 보고서 실측에서 필요한 필드만 추출했으며 모델을 재호출하지 않았다. 개인 경로·키·API 식별자·대화 원문·발표 파일은 추가하지 않는다.
- 기존 로컬 평가와 최종 비교의 버전·모델·조건을 구분하고 지연·토큰 증가, 6/7 사실 포함, 3질문 1회 측정 한계를 공개한다. 애플리케이션 동작은 변경하지 않는다.
- PR [#20](https://github.com/DoHanChoi/skala-mini-project-ai/pull/20)을 생성했다. 첫 리뷰 대기 10분 후 작업 기록 표현에 대한 지적 1건을 확인하고 수정했다. 이 기록 작성 시점에는 재리뷰·머지·이슈 종료·브랜치 정리가 대기 중이다. 사후 확인 결과는 이슈 #19의 완료 댓글에 남긴다.
- 문서 검증: 변경 Markdown의 상대 링크 존재 확인, 원시 실측과 공개 요약 대조, 고정 평가 fixture SHA-256 일치, 평균·토큰·호출 수 재집계, `git diff --check` 통과. 문서·측정 요약만 변경하여 모델 호출과 애플리케이션 회귀 테스트는 재실행하지 않았다.
