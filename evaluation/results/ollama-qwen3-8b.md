# A-06 ollama 실행 결과

생성 시각: 2026-10-21T00:52:47.047208+00:00

기준: `447db631b079f6c8b5e67c3b2bfce4dbaf59169f`
개선: `56a7b12e88976d97ce4dc02426f1aea342452b1d`

두 버전은 같은 질문·원본·태스크·인터프리터를 사용한다. 라우팅·계획은 고정 대역, MCP는 원본 사본이다. 시연용 0.35초 지연은 양쪽 모두 제거했다. 지연은 이 통제 환경의 요청 wall-clock이며 운영 지연이 아니다.

기준 자유 텍스트와 개선 JSON은 응답 계약·프롬프트가 다르다. 가설·조치의 의미와 인과관계는 채점하지 않는다.

## 실모델 조건

모델: `qwen3:8b`, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`, Ollama `0.33.0`.
설정: `{"temperature": 0, "seed": 42, "num_predict": 2048, "num_ctx": 8192}`, think=false, 비스트리밍. 준비 호출 1회는 제외했다. 각 질문은 버전별 1회다.

평가용 HTTP 전송은 두 버전 모두 같은 비스트리밍으로 통제했다. 실제 writer 프롬프트와 검증 흐름을 사용하지만 운영 기본 thinking/스트리밍 조건과 다르다. 기준→개선 순차 실행이므로 순서·캐시 영향이 남으며 작은 표본으로 우열을 일반화하지 않는다.

기준 자유 텍스트의 문장 전체 수치·출처 일치율은 자동 채점 미지원이다. 개선 관측은 별도 수동 작성 허용 사실 목록으로 대조한다. 아래의 자체 검사 통과율은 독립적인 전체 답변 정확도가 아니다.


## 파이프라인

| 버전/시나리오/경로 | 완료/전체 | 자체 검사 통과 | 실패 | 평균 작성/재작성 | 평균 지연(초) |
|---|---|---|---|---|---|
| baseline/real_model/rest | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 1/0 | 6.1849 |
| improved/real_model/rest | 3/3 | 1/3 (33.3%) | 2/3 (66.7%) | 2.6666666666666665/1.6666666666666667 | 65.5099 |

## 요청별 결과

### baseline · heldout-cpu · real_model · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 7.7625초

~~~text
1) auth-service와 web-01의 상태를 비교하면, auth-service는 degraded 상태이고 web-01는 healthy 상태이다.
2) auth-service의 CPU 사용률은 86.5%, 메모리 사용률은 61.25%로 높은 수치를 보이며, web-01의 CPU 사용률은 24.75%, 메모리 사용률은 38.5%로 정상 수준이다.
3) auth-service의 이상 원인으로는 CPU 사용률 상승이 주요 요인일 것으로 추정되며, 최근 배포와 요청량 증가 여부를 확인해야 하며, 조치는 담당자 검토 후 결정해야 한다.
~~~

### baseline · heldout-memory · real_model · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 6.3879초

~~~text
1) cache-service의 메모리 사용률이 92.75%로 급증하여 degraded 상태이며, web-01는 정상 상태(44.5% 메모리 사용)로 알림도 없어 비정상적인 차이가 있음.
2) 메모리 증가 추세와 프로세스별 사용량을 확인하여 과도한 메모리 소비 원인을 분석해야 함.
3) 최근 변경 사항과 메모리 누수 가능성에 대해 검토하여, 복구 명령은 실행 전에 조치 제안을 할 것.
~~~

### baseline · heldout-unknown · real_model · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 4.4044초

~~~text
1) 모니터링 시스템에서 billing-service의 상태가 unknown으로 확인되었으며, CPU와 메모리 사용률은 0%로 나타났습니다.
2) 알림 내역에는 "System 'billing-service' not found in monitoring"이라는 메시지가 1건 기록되어 있습니다.
3) 관련 runbook은 존재하지 않아, 장애 대응 절차를 확인할 수 없습니다.
~~~

### improved · heldout-cpu · real_model · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 57.6992초

인용 관측 원본 일치: 7/7 (100.0%); 허용 사실 포함: 7/7 (100.0%).

~~~text
관측 사실 (값·시스템·단위·출처 연결 확인):
- "auth-service" 상태: "degraded" [근거 "ev:evaluation-request:0"]
- "auth-service" CPU 사용률: 86.5% [근거 "ev:evaluation-request:0"]
- "auth-service" 메모리 사용률: 61.25% [근거 "ev:evaluation-request:0"]
- "auth-service" 알림: "CPU 사용률 86.5%로 상승" [근거 "ev:evaluation-request:0"]
- "web-01" 상태: "healthy" [근거 "ev:evaluation-request:1"]
- "web-01" CPU 사용률: 24.75% [근거 "ev:evaluation-request:1"]
- "web-01" 메모리 사용률: 38.5% [근거 "ev:evaluation-request:1"]
원인 가설 (추정·의미 검증 제외):
- "auth-service의 CPU 사용률이 높아 서비스가 저하되었을 수 있습니다." [근거 "ev:evaluation-request:0"]
- "auth-service의 메모리 사용률이 높아 서비스가 저하되었을 수 있습니다." [근거 "ev:evaluation-request:0"]
- "auth-service의 CPU 사용률이 높아 알림이 발생했을 수 있습니다." [근거 "ev:evaluation-request:0"]
권장 조치 (미실행·의미 검증 제외):
- "담당자에게 CPU 사용률이 높은 이유를 확인하고 조치를 요청하세요." [근거 "ev:evaluation-request:2"]
검사 범위: 관측값·시스템·단위·출처 연결. 가설·조치의 의미는 검증하지 않았습니다.
~~~

### improved · heldout-memory · real_model · rest · 1회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 92.7203초

인용 관측 원본 일치: 미측정 (0/0); 허용 사실 포함: 0/7 (0.0%).

~~~text
진단 검증 실패 (시도 3/3)
확인된 원본 관측:
- "cache-service" CPU 사용률: 27.25% [근거 "ev:evaluation-request:0"]
- "cache-service" 메모리 사용률: 92.75% [근거 "ev:evaluation-request:0"]
- "cache-service" 상태: "degraded" [근거 "ev:evaluation-request:0"]
- "cache-service" 알림: "메모리 사용률 92.75%로 지속 증가" [근거 "ev:evaluation-request:0"]
- "web-01" CPU 사용률: 18.25% [근거 "ev:evaluation-request:1"]
- "web-01" 메모리 사용률: 44.5% [근거 "ev:evaluation-request:1"]
- "web-01" 상태: "healthy" [근거 "ev:evaluation-request:1"]
실패한 초안의 가설·조치는 표시하지 않습니다.
검사 범위: 관측값·시스템·단위·출처 연결. 가설·조치의 의미는 검증하지 않았습니다.
~~~

### improved · heldout-unknown · real_model · rest · 1회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 46.1103초

인용 관측 원본 일치: 미측정 (0/0); 허용 사실 포함: 미측정 (0/0).

~~~text
진단 검증 실패 (시도 3/3)
확인된 원본 관측:
확인 가능한 원본 관측이 없습니다.
실패한 초안의 가설·조치는 표시하지 않습니다.
검사 범위: 관측값·시스템·단위·출처 연결. 가설·조치의 의미는 검증하지 않았습니다.
~~~

## 해석과 제한

- 생성 모델이 오류를 낼 확률을 오류 주입 검출률로 해석하지 않는다. 개발 fixture이며 외부 독립 평가 집합이 아니다.
- 실모델 질문·수치는 A-06에서 새로 고정했지만 독립 인간 평가나 미공개 벤치마크가 아니다. 인용 정밀도와 사실 포함률은 별개다.
- unknown 원본밖에 없는 질문의 검증 실패는 확인 불가능한 진단을 성공으로 바꾸지 않는 동작이다.
- 로컬 토큰은 실제 응답 사용량이며 usd는 1천 토큰당 가상 단가 $0.005 추정이다. 실제 API 청구액이 아니다.
- 실패·미측정·미지원 수치는 성공이나 0%로 치환하지 않았다. 원시 JSON에 각 호출·응답·종료 원인·오류·해시를 남겼다.
- 실제 MCP 네트워크·라우팅 품질·운영 지연·가설 의미·출처 진위를 측정하지 않는다.

계약 검사 위반: 0개
