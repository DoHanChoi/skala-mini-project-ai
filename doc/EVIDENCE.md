# A-02: 요청별 근거와 출처 보존

v2 수집 단계에서 기존 `collected`의 `source`·`data`를 유지하고 별도 `evidence` 목록을 만든다. [근거 모델](../agent/evidence.py)은 원본을 깊은 복사해 보존한다. 모델 답변 검증과 공개 API·UI 연결은 후속 단계다.

## 모델 계약

`Evidence`는 Pydantic 모델이며 그래프 상태에는 `model_dump()`한 사전을 저장한다. 문자열 숫자·bool을 실측 숫자로 바꾸거나 누락을 0으로 채우지 않는다.

| 필드 | 의미 |
|---|---|
| `id` | `ev:<request_id>:<task_index>` |
| `request_id` | v2 장애 요청마다 생성하는 UUID hex. `thread_id`와 별개 |
| `task_index`, `task_id` | 게이트 적용 후 전체 태스크 목록에서의 위치와 원래 태스크 ID |
| `source` | `monitoring` 또는 `runbook`. `analysis`는 허용하지 않음 |
| `target` | 요청한 시스템 또는 매뉴얼 유형 |
| `server`, `locator` | 실제 MCP 서버 이름과 도구명 또는 실제 요청 URI |
| `retrieved_at` | 조회 성공 직후 코드에서 기록한 타임존 포함 ISO 8601 시각 |
| `observed_at` | 모니터링 원본 `last_checked`. 없으면 null, 원본 시각을 추정하지 않음 |
| `system_name` | 모니터링 응답에 실제 들어 있던 시스템명. 요청 대상과 별도로 보존 |
| `title`, `content_sha256` | 매뉴얼의 첫 Markdown 제목과 정확한 UTF-8 본문 SHA-256 |
| `raw` | 조회 결과 전체 사본. 추가 필드·원본 자료형·본문 공백도 유지 |
| `available` | 원본 근거로 활용할 기본 조건 충족 여부. 답변 검증 성공 표시가 아님 |
| `eligible_metrics` | 모니터링에서 인용 가능한 항목 목록. 매뉴얼은 빈 목록 |
| `issues` | 누락·비정상·불일치 사유 코드. 경고가 있어도 다른 정상 항목은 활용 가능 |

수집 상태는 `request_id`와 `evidence`를 추가한다. 태스크를 `asyncio.gather`로 실행해도 ID와 목록 순서는 태스크 위치로 정한다. 성공 전 타임아웃 재시도에는 새 ID를 만들지 않는다. 재계획은 끝에 gap task를 추가하고 기존 근거를 유지한다. 작성·검증 노드는 이 목록을 다시 생성하지 않는다.

모니터링은 기존 호출 대상 `ops`를 명시해 조회하고 그 서버명을 보존한다. 매뉴얼은 `find_resource_template`이 찾은 서버와 템플릿에서 실제 구성한 URI를 보존한다. 매뉴얼 파일에 버전이 없으므로 본문 해시로 수집한 문서를 구별한다. 제목 추출 외에 본문을 정리하거나 매뉴얼의 의미를 판단하지 않는다.

## 활용 가능 범위

- 모니터링 시스템명이 요청과 같고 상태가 `healthy`, `degraded`, `down` 중 하나여야 `available=True`다. `unknown`과 시스템 불일치는 원본을 남기되 모든 관측 항목을 제외한다.
- CPU·메모리는 bool이 아닌 Python int/float이며 유한한 0~100 값만 적격이다. 항목 누락, null, 문자열, bool, NaN/Infinity, 범위 밖 값은 원본에 그대로 남고 해당 항목만 제외한다.
- 상태는 위 기본 조건을 만족할 때 적격이다. 알림은 문자열 목록일 때만 적격이며 빈 목록은 정상적인 ‘알림 없음’이다. 알림 숫자를 추출·변환하지 않는다.
- 실측 시각이 없거나 잘못된 경우 `issues`에 표시한다. 조회 시각은 별도로 있으므로 이 경고만으로 정상 관측값을 제거하지 않는다. 기존 MCP의 타임존 없는 시각은 문자열 그대로 보존하며 지역이나 UTC를 추정하지 않는다.
- 매뉴얼 없음 안내(`# Runbook Not Found`), 빈 본문, 문자열이 아닌 본문은 사용 불가다. 문서에 제목만 없으면 본문과 해시를 남기고 `missing_title` 경고를 표시한다. 원문이 있는 일반 문서까지 자동으로 없다고 판단하지 않는다.
- `analysis`는 기존 `collected`에만 유지한다. 모델이 해석한 수치를 독립적인 관측 근거로 추가하지 않는다.

대표 `issues`: `unknown_system`, `system_mismatch`, `invalid_status`, `missing_cpu_percent`, `invalid_cpu_percent`, `missing_memory_percent`, `invalid_memory_percent`, `missing_alerts`, `invalid_alerts`, `missing_observed_at`, `invalid_observed_at`, `invalid_monitoring_body`, `runbook_not_found`, `empty_runbook`, `invalid_runbook_body`, `missing_title`.

## 보존과 호환성

수집 결과를 변형하지 않고 별도 `raw`를 깊은 복사하므로 `collected`의 중첩 데이터 변경이 근거에 전파되지 않는다. 모델 직렬화 사본도 원래 스냅샷과 중첩 데이터를 공유하지 않는다. Pydantic `frozen`은 모델 필드 재할당을 막지만 내부 dict/list까지 읽기 전용으로 만들지는 않는다. 그래프 상태도 일반 사전이므로 소비자는 보존된 근거를 수정하지 않아야 한다. 검증용 값이 필요하면 원본을 참조하거나 별도 사본에서 계산한다.

태스크 위치는 한 요청 안에서 고정하고, 새 조사는 새 태스크로 추가한다. 이미 완료된 태스크는 재실행하지 않는다. 원본을 다시 조회해야 한다면 이전 스냅샷을 덮어쓰지 말고 새 태스크를 추가한다. 같은 ID로 수정한 원본을 교체하는 저장 기능은 제공하지 않는다.

기존 LLM에는 기존 `collected`만 전달하므로 세 백엔드의 프롬프트 입력·답변 형식은 바뀌지 않는다. REST/SSE 응답과 이벤트, 저장 대화, 일반 대화, v1도 유지한다. **활용 가능 표시가 아직 답변을 차단하거나 검증하는 것은 아니다.** 매뉴얼 없음·unknown 원본이 기존 모델 입력에 남는 것도 기존 동작이며, 후속 통합에서 이 표시를 사용한다. 3회 강제 합격과 검증 전 초안 노출은 A-04에서 변경한다.

## 검증과 fixture 대응

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python tests/run_pinned_baseline.py
```

현재 전체 32개(기존 15개 + 근거 17개), 기준 커밋의 A-01 테스트 15개를 실행한다. 기준 실행기는 `tests.test_baseline`과 `tests.test_api_baseline`만 명시적으로 선택한다. 과거 코드에 존재하지 않는 A-02 근거 모듈의 테스트는 기준 재현에 포함하지 않는다.

검사 항목은 원본·사본 격리, 누락·unknown·시스템 불일치, 비정상 수치·상태·알림·시각, 본문 해시·출처, analysis 제외, 역전된 병렬 완료 순서, 요청 분리, 재계획 누적, 재시도·재작성 중 ID 유지, 기존 API·대화·v1 회귀다. 외부 모델·실제 MCP 프로토콜·화면·운영 지연은 측정하지 않는다.

A-01 fixture의 `mon-payments`, `mon-web`, `runbook-cpu`는 사람이 붙인 평가용 이름이다. 기본 장애 경로에서 각각 태스크 위치 0, 1, 2의 실제 `ev:<request_id>:<index>`로 대응한다. fixture의 다른 요청·unknown·누락 사례는 각 정규화 단위 테스트에서 따로 사용한다. fixture의 후보 초안 형식과 수동 판정을 이번 단계의 답변 검증 결과로 사용하지 않는다.
