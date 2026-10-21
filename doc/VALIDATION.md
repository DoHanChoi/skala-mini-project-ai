# A-03: 구조화된 진단 검증과 표시 계약

이 문서는 A-03의 [모델](../agent/diagnosis.py)과 [순수 검증·렌더링 함수](../agent/validation.py) 계약이다. A-03에서는 독립 구현했으며, A-04부터 라이브 v2 장애 흐름에 연결한다. 재작성·실패 종료와 공개 API는 [A-04 응답 통합](PIPELINE.md)을 따른다.

## 입력과 출력

```python
from agent.validation import validate_diagnosis, render_diagnosis

validation = validate_diagnosis(
    draft, evidence, request_id=request_id, attempt=1)
output = render_diagnosis(
    draft, evidence, request_id=request_id, attempt=1)
# output.validation: 검사 결과, output.reply: 코드가 만든 표시 문자열
```

`draft`는 단일 JSON 객체 문자열, 사전 또는 `DiagnosisDraft`다. `evidence`는 A-02 `Evidence` 모델 또는 직렬화 사전의 list/tuple이다. `request_id`는 서버의 현재 요청 ID이며 `attempt`는 초기 작성부터 센 1~3의 정수다. 잘못된 호출 제어값은 `ValueError`로 처리한다. 검증 자체는 시도 횟수와 관계없이 같은 입력에 같은 판정을 한다. 세 번째 실패를 강제로 통과시키지 않는다. 재작성 루프와 파싱 실패의 시도 횟수 누적은 A-04에서 연결한다.

| 모델 | 필드와 조건 |
|---|---|
| `Observation` | `system_name`, `metric`, `value`, `unit`, `evidence_id`. 자유 표시 문장을 받지 않음 |
| `SourceLinkedText` | `text`, `evidence_ids`. 비어 있지 않은 문장과 중복 없는 출처 ID 필요 |
| `DiagnosisDraft` | `observations` 최소 1개, `hypotheses`, `actions`. 세 목록 필수, 제안 목록은 빈 목록 허용 |
| `ValidationIssue` | `code`, `path`, 고정된 `message`. 실패 초안 값이나 알 수 없는 키를 되풀이하지 않음 |
| `ValidationResult` | `request_id`, `attempt`, `passed`, `scope`, `errors` |
| `DiagnosisOutput` | `validation`, `reply`. 실패 초안 객체를 반환하지 않음 |

모델은 추가 필드와 암묵적 자료형 변환을 거부한다. 관측값은 JSON의 int/float/string만 허용하고 bool·null·NaN/Infinity·비 JSON 수치 객체는 거부한다. 수치 문자열은 구조상 문자열로 남지만 수치 항목 비교에서는 실패한다. JSON 중복 키, 비표준 숫자 상수, 잘못된 루트 구조도 실패다.

## 검증 규칙

1. 근거 사본의 모델 구조와 요청·태스크 ID 일관성을 검사한다. 원본으로 A-02 정규화를 다시 계산해 활용 가능 항목·시스템·시각·제목·본문 해시 등과 비교한다. 오래되거나 훼손된 적격성 표시를 그대로 신뢰하지 않는다.
2. 현재 요청의 중복 ID는 실패이며 해당 ID의 모든 정상 후보를 대체 출력에서도 제외한다. 구조 검증에 실패한 사전이 같은 문자열 ID를 주장하는 경우에도 그 ID를 모호한 원본으로 취급해 양쪽 입력 순서에서 제외한다. 잘못된 근거 구조·메타데이터도 실패이고 해당 원본은 표시하지 않는다.
3. 다른 요청의 유효한 근거는 현재 요청 목록에서 제외한다. 목록에 존재한다는 이유만으로 현재 진단을 실패시키지는 않지만, 초안이 이를 인용하면 실패한다.
4. 관측은 현재 요청의 활용 가능한 `monitoring` 원본을 참조해야 한다. 실제 시스템명, 측정 항목과 값을 함께 비교한다. 매뉴얼이나 모델 해석으로 실측값을 증명할 수 없다.
5. CPU·메모리는 원본의 적격 int/float와 정확히 비교하고 단위는 `%`만 허용한다. `91`과 `91.0`은 동등하다. 숫자가 다른 시스템·다른 항목에 존재하는 것으로는 통과하지 못한다. 반올림·단위 변환·허용 오차를 임의 적용하지 않는다.
6. 상태는 원문 문자열, 알림은 원문 목록의 개별 문자열과 일치해야 한다. 두 항목의 `unit`은 null이다. 알림 문장에서 임의 숫자를 추출하거나 새로운 요약 문장을 사실로 허용하지 않는다.
7. 가설·조치는 출처 ID가 현재 요청에 존재하고 활용 가능한지만 검사한다. 원문의 의미가 문장을 지지하는지, 실제 원인인지, 조치가 효과적인지는 판정하지 않는다. 가설·조치에 임의 수치가 있어도 이를 관측 사실로 승격하지 않는다.

## 결과 표시와 실패 처리

`render_diagnosis`는 호출할 때마다 검증을 거치며 외부에서 전달한 ‘통과’ 플래그를 받지 않는다. 통과 시 관측 문장은 고정된 측정 항목명과 원본 값으로 생성한다. 예를 들어 int `91` 초안이 float `91.0` 원본과 일치하면 원본 값 `91.0%`를 표시한다. 알림은 일치한 원문 문자열을 표시한다.

관측 사실에는 값·시스템·단위·출처 연결 확인을 표시한다. 가설은 ‘추정·의미 검증 제외’, 조치는 ‘미실행·의미 검증 제외’ 구역에 둔다. 전체 검사 범위는 `observed_values_and_source_links`다. 출처 연결 확인을 문장 전체의 사실성·출처 진위 보장으로 표현하지 않는다.

실패하면 다음 내용만 코드에서 생성한다.

- 검증 실패와 작성 시도 횟수.
- 현재 요청의 정상 근거에서 확인되는 CPU·메모리·상태·알림. 누락·unknown·활용 불가·모호한 중복 근거는 제외한다.
- 원본 관측이 없으면 확인 가능한 사실이 없다는 안내.
- 실패한 초안의 가설·조치를 게시하지 않는다는 안내와 검사 범위.

잘못된 초안이나 가설·조치를 실패 답변의 대체 원본으로 사용하지 않는다. 오류에는 코드와 입력 경로만 남기며 임의의 입력 키는 `unknown_field`로 표시한다. 표시 문자열 속 개행·제어문자는 JSON 문자열 표현으로 이스케이프한다. **결과는 일반 텍스트이며 HTML이 아니다.** 화면 연결 시 `textContent`/텍스트 바인딩으로 표시해야 하며 HTML 안전성 검증은 아직 수행하지 않았다.

## 오류 코드

| 코드 | 의미 |
|---|---|
| `invalid_structure` | 초안 파싱·필수 항목·자료형·허용 필드 오류 |
| `invalid_evidence` | 근거 구조·식별·원본 메타데이터 오류 |
| `duplicate_evidence_id` | 현재 요청의 근거 ID 중복 |
| `foreign_evidence` | 다른 요청의 근거 인용 |
| `missing_evidence` | 현재 요청에 없는 출처 |
| `unavailable_evidence` | unknown·시스템 불일치·없는 매뉴얼 등 활용 불가 원본 |
| `wrong_source_type` | 실측 관측에 매뉴얼 등 다른 종류의 근거 사용 |
| `system_mismatch` | 관측 시스템과 원본 시스템 불일치 |
| `ineligible_metric` | 누락·비정상 측정 항목 인용 |
| `unit_mismatch` | 항목에 맞지 않는 단위 |
| `invalid_value_type` | 수치 문자열 등 항목과 다른 자료형 |
| `value_mismatch` | 원본 값·상태·알림 원문과 불일치 |

## 검증과 한계

```bash
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python tests/run_pinned_baseline.py
```

전체 56개(기존 32개 + 새 24개), 기준 커밋의 A-01 테스트 15개가 통과했다. A-01 고정 후보 초안 24개를 실제 Evidence ID로 대응시켜 정상 6개 통과·거부 18개 거부를 확인했다. 테스트 하위 사례는 별도 테스트 수에 더하지 않는다.

추가로 엄격한 JSON 파싱, 자료형·단위·원문 비교, 중복/타 요청/훼손 근거, 시도 상한, 입력 비변경, 실패 초안 미노출, 표시 구역 분리를 검사한다. 이는 사람이 정한 고정 데이터와 코드 규칙의 결과이며 실모델 정확도 개선 측정이 아니다.

근거는 서버 내부 수집자가 생성한 자료라는 전제다. 구조·메타데이터 재검사는 출처 인증이 아니고, 원본 값과 메타데이터를 함께 바꾸는 행위를 탐지하는 서명·외부 원장도 아니다. 임의 Evidence 입력을 외부 API에서 받아 권한이나 사실성의 증명으로 사용해서는 안 된다. 라이브 응답, 세 백엔드의 출력 계약, SSE 초안 차단, UI 및 재작성 통합은 A-04 이후에 검증한다.
