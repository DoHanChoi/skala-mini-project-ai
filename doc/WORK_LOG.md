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

**현재 승인된 개발 범위는 A-01이다. A-02의 착수 승인은 아직 받지 않았다.**

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

## 다음 후보

- A-02: 근거 모델과 출처 보존.
- 요청별 근거 모델·수집 결과 정규화·원본 보존·누락/unknown 처리·결정적인 ID 테스트를 마련한다.
- A-01이 끝나도 자동 착수하지 않는다. **“다음 이슈로 넘어갈까요?”**에 대한 사용자 응답을 기다린다.

## 범위 밖 발견 사항

- 에이전트 실행 스크립트가 시작할 때 `session.db`를 삭제한다. 평가·테스트는 별도 임시 DB를 사용하며, 실행 스크립트 수정은 필요 시 별도 이슈로 논의한다.
- 미인식 시스템의 `auth-service` 폴백과 매뉴얼 키워드 선택 한계는 A안의 사실 인용 검증으로 해결되지 않는다.
- 실모델 시험은 아직 수행하지 않았다. 예시·fixture 결과를 실모델 개선 실측으로 보고하지 않는다.
