# CodeRabbit PR 리뷰

## 구성

- 설정 파일: [`.coderabbit.yaml`](../.coderabbit.yaml).
- 기본 브랜치 `main` 대상의 일반 PR을 한국어로 자동 리뷰한다. Draft PR은 준비 완료로 전환한 후 리뷰한다.
- 새 커밋을 push하면 증분 리뷰한다. 리뷰된 커밋 수에 따른 자동 일시 정지는 사용하지 않는다.
- 균형 잡힌 `chill` 프로필로 실제 오류·보안·회귀와 현재 이슈의 완료 기준을 우선한다.
- [AGENTS.md](../AGENTS.md)와 [PLAN_A.md](PLAN_A.md)를 리뷰 기준으로 사용한다. 미래 단계의 미구현 기능까지 현재 PR에 요구하지 않는다.
- 이미지·가상환경·캐시·DB·로그는 리뷰에서 제외한다. 이 설정은 Git 추적 제외를 대신하지 않는다.
- CodeRabbit의 자동 코드 수정·별도 수정 PR 생성 기능은 비활성화한다. 수정은 현재 이슈 브랜치에서 개발 에이전트가 검증 후 수행한다.

## GitHub App 연결

YAML만으로 GitHub App이 설치되지는 않는다. [공식 GitHub App](https://github.com/apps/coderabbitai)의 설치 대상에서 개인 계정 `DoHanChoi`와 `Only select repositories`를 선택하고 `skala-mini-project-ai`만 연결한다.

GitHub가 본인 인증이나 App 권한 승인을 요구하면 사용자가 확인한다. 설치 완료 여부는 해당 계정의 Installed GitHub Apps와 저장소 접근 목록으로 확인한다. 전체 저장소 접근이나 유료 플랜 구매를 기본값으로 선택하지 않는다.

## 이슈별 작업 흐름

`이슈 → 브랜치 → 구현·테스트 → PR → CodeRabbit 리뷰 → 지적 검토·수정·재검증 → 최신 커밋 리뷰 완료 확인 → 머지 → 이슈 종료 확인 → 브랜치 삭제 → 다음 이슈 진행 승인`

1. PR을 생성하고 연결된 이슈와 테스트 결과를 본문에 적는다.
2. CodeRabbit의 리뷰가 시작되었는지 확인한다. 미설치·리뷰 생략·오류·한도 도달·요약만 생성된 상태를 코드 리뷰 완료로 간주하지 않는다.
   사용자의 요청에 따라 첫 리뷰는 시작 후 최소 5분이 지난 뒤 결과를 확인한다. 그 전에 완료 여부를 반복 조회하거나 중복 리뷰를 요청하지 않는다.
3. 리뷰의 지적을 실제 코드와 대조한다. 유효한 문제는 수정하고, 오탐·범위 밖 의견은 이유와 근거를 PR에 기록한다. 일괄 수용하거나 근거 없이 무시하지 않는다.
4. 수정 후 관련 테스트를 재실행하고 같은 브랜치로 push한다. 최신 HEAD에 대한 재리뷰가 끝났는지 확인한다.
5. 리뷰 완료, 유효한 미해결 지적 없음, 필수 검사 통과, 충돌 없음이 확인된 뒤 머지한다.
6. 이슈 종료와 원격·로컬 브랜치 삭제를 확인하고 사용자에게 다음 이슈 진행 승인을 받는다.

`request_changes_workflow: true`는 CodeRabbit이 자신의 지적 해결과 최신 커밋 리뷰·검사 상태를 확인해 승인하도록 하는 설정이다. GitHub의 자동 머지나 브랜치 보호를 설정하는 옵션이 아니다. 이 작업에서는 브랜치 보호 규칙을 변경하지 않으며, 머지 전 리뷰 확인을 저장소 작업 규칙으로 적용한다.

`allow_author_approval: false`로 PR 작성자의 명령을 통한 승인 우회를 차단한다. 다른 사용자의 명령까지 차단하는 옵션은 아니므로 모든 작업자는 아래 우회 금지 규칙을 지킨다. [공식 승인 워크플로 문서](https://docs.coderabbit.ai/pr-reviews/request-changes-workflow)를 따른다.

머지·이슈 종료·브랜치 삭제는 리뷰 통과 후 수행하는 사후 확인 항목이다. 머지 전에는 설정·테스트·실제 리뷰·지적 처리와 최신 커밋 검토를 확인한다. 사후 정리를 미리 완료했다고 기록하지 않는다.

## 수동 명령

자동 리뷰가 시작되지 않거나 설정을 확인할 때 PR 댓글에서 다음 명령을 사용한다.

```text
@coderabbitai review
@coderabbitai full review
@coderabbitai configuration
```

이 저장소의 CodeRabbit 설정·리뷰 작업에는 해당 봇을 대상으로 하는 위 명령과 리뷰 지적 처리 답변이 포함된다. 다른 사람에게 리뷰를 요청하거나 별도 메시지를 보내는 것은 이 범위에 포함하지 않는다.

`@coderabbitai approve`, `@coderabbitai resolve` 등 검토를 건너뛰기 위한 명령은 사용하지 않는다. 리뷰가 이용 불가능한 경우 PR을 열린 상태로 두고 원인을 사용자에게 알린다. 사용자의 명시적 예외 승인 없이 리뷰 완료 규칙을 우회하지 않는다.

## 연결 검증과 한계

- 공식 JSON Schema로 YAML 문법·필드·자료형을 검증한다.
- 설정 PR에서 실제 `coderabbitai[bot]`의 리뷰, 적용 설정, 검토 커밋을 확인해야 연결 완료다.
- 설정 파일 검증 통과와 App 설치, 실제 리뷰 동작은 각각 별도의 확인 항목이다.
- CodeRabbit 리뷰는 테스트와 직접 검토를 보완한다. 리뷰 승인이 실제 진단 정확도나 코드의 무결함을 보장하지 않는다.

공식 문서: [GitHub 연동](https://docs.coderabbit.ai/platforms/github-com), [설정 항목](https://docs.coderabbit.ai/reference/configuration).
