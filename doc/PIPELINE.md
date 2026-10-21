# A-04: 모델·그래프·API 검증 통합

v2 장애 경로에 [진단 검증기](VALIDATION.md)를 연결했다. 일반 대화와 v1은 A안 검증 비대상이다. 가설·조치의 의미나 실제 장애 원인, 조치 효과는 보장하지 않는다.

## 작성과 종료

- 세 quality 백엔드의 공통 메서드는 `diagnose(query, evidence, analysis, attempt, feedback)`이며 JSON 문자열과 사용량을 반환한다. 기존 `write`는 기준 예제용으로 남지만 v2 장애 그래프에서 호출하지 않는다.
- 공통 프롬프트는 `DiagnosisDraft` JSON Schema, 활용 가능한 원본 항목·출처 ID, 별도로 구분한 모델 해석, 작성 시도와 이전 오류 목록을 제공한다. `collected`의 analysis는 원본 근거로 승격하지 않는다.
- fake는 최초 빈 관측으로 구조 오류를 재현하고 다음 시도부터 인용 가능한 원본 값으로 작성한다. Ollama는 기존 `format=JSON Schema`, OpenAI는 기존 `response_format=json_object`와 스키마 프롬프트를 사용한다. OpenAI JSON 모드는 스키마 자체를 강제하지 않는다. 어느 백엔드든 실제 출력은 동일한 코드 검증을 거친다.
- 실모델 작성은 기존 동기 HTTP 호출을 worker thread에서 수행한다. 장애 초안은 스트리밍하지 않으며 JSON 파싱 오류·거부 응답도 검증 시도로 계산한다. 연결 오류나 HTTP 오류는 검증 실패로 숨기지 않고 전파한다.
- 관측값·시스템·항목·단위·출처를 대조하고, 오류의 코드·위치·고정 안내문만 재작성에 전달한다. 초기 작성 포함 최대 3회다. 성공은 즉시 종료하고, 세 번 실패해도 `passed=false`를 유지한다.
- 실패한 초안은 최종 본문과 구조화 진단에 복사하지 않는다. 확인 가능한 원본 사실과 실패 안내만 코드로 표시한다. 같은 요청의 재작성 중 근거와 ID는 유지된다.

## 공개 API 계약

`POST /chat`의 기존 `reply`, `events`, `metadata`를 유지하고 아래 필드를 추가했다. SSE `FinalAnswer`에도 같은 필드와 `metadata`가 있다. 별도 요청끼리는 요청 ID·조회 시각·시간/비용·trace 정보가 달라질 수 있다.

| 필드 | v2 장애 | 일반 대화·v1 |
|---|---|---|
| `diagnosis` | 성공한 `DiagnosisDraft` 객체, 실패 시 `null` | `null` |
| `evidence` | 요청별 Evidence 목록 | `[]` |
| `validation.status` | `passed` 또는 `failed` | `not_applicable` |
| `validation.passed` | `true` 또는 `false` | `null` |
| `validation.attempt` | 실제 작성 횟수 1~3 | `0` |
| `validation.scope` | `observed_values_and_source_links` | `null` |
| `validation.errors` | 오류 코드·위치·고정 안내문 목록 | `[]` |
| `validation.request_id` | 현재 요청 ID | `null` |
| `validation.reason` | 제공하지 않음 | `general_chat` 또는 `legacy_v1` |

Evidence의 정상 JSON 원본 값은 그대로 전달한다. JSON 숫자로 표현할 수 없는 원본 NaN·Infinity는 모델 입력과 공개 응답에 한해 `{"nonfinite_number": "nan"}` / `"inf"` / `"-inf"` 태그로 표시한다. 내부 원본은 바꾸지 않고 해당 수치는 인용 가능 항목에서 제외한다. 태그는 원본 숫자가 아닌 전송 표현이며 공개 Evidence를 검증기 내부 입력으로 다시 사용하는 계약은 제공하지 않는다.

### 스트리밍·저장

- 장애 경로는 `DraftWritten`의 시도·길이와 `Validation`의 판정·오류 등 단계 진행 이벤트만 공개한다. `Validation.will_retry`로 재작성과 최종 실패를 구분한다.
- 검증 전 장애 `AnswerToken`은 생성하지 않는다. 전송 계층도 일반 대화 경로의 `AnswerToken.delta`만 허용한다.
- 최종 본문은 검증기가 렌더링한 결과이며 그래프 종료 후 한 번 `FinalAnswer`로 전송한다. 정상 종료 센티널 `[DONE]`은 한 번이다.
- REST/SSE 공개 응답에서 원시 `prompt`, `draft`, `validation_feedback`, `last_prompt`, `collected`를 반환하지 않는다. 내부 그래프 상태와 LangSmith trace는 사용자 공개 응답과 구분되며 내부 초안이 포함될 수 있다.
- v2는 사용자 질문과 확정 답변만 SQLite에 저장한다. 실패 초안과 원시 프롬프트를 저장하지 않는다. 기존 일반 대화 토큰·세션은 유지한다. v1의 기존 저장 동작은 변경하지 않았다.
- A-04의 기본 Vue 화면은 `FinalAnswer.reply`로 장애 본문을 표시했다. A-05부터 구조화된 구역·출처 패널·검증 비대상 표시를 연결하며 화면 계약은 [근거 확인 UI](UI.md)를 따른다.

## 재현과 검증

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python tests/run_pinned_baseline.py
```

- 현재 코드: 근거 17개·순수 검증 24개·통합 17개, 총 58개 테스트. fake/MCP 대역, 네트워크 차단, 임시 DB를 사용한다.
- 최초 성공, 수치 변조 후 수정, 구조 파싱 실패·거부 응답·없는 출처 3회 종료, unknown·비유한 수치, 근거 보존, REST/SSE 최종 동등성, 초안·프롬프트 전송/저장 차단, 일반 대화·v1·운영상 예외를 검사한다.
- Ollama/OpenAI HTTP 요청을 mock하여 schema/JSON 모드, 비스트리밍, 프롬프트·피드백·사용량·잘못된 출력의 원문 전달을 확인한다. 실제 API·모델 품질을 측정한 결과가 아니다.
- 개선 전 15개 특성 테스트는 내용 변경 없이 `pinned_baseline.py`, `pinned_api_baseline.py`로 분리했다. 현재 테스트 자동 탐색에서는 제외하고 고정 기준 커밋에서 실행한다. 테스트 수 감소/증가를 품질 지표로 해석하지 않는다.

실제 모델·실제 MCP 프로토콜·운영 지연은 이 자동 검증의 범위가 아니다. 라우팅·시스템 폴백·매뉴얼 선택과 출처의 실제 신뢰성 한계는 그대로다. UI 상세 표시는 [A-05](UI.md), 전후 평가는 A-06에서 별도로 다룬다.
