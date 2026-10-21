# A-06 offline 실행 결과

생성 시각: 2026-10-21T00:54:56.894352+00:00

기준: `447db631b079f6c8b5e67c3b2bfce4dbaf59169f`
개선: `56a7b12e88976d97ce4dc02426f1aea342452b1d`

두 버전은 같은 질문·원본·태스크·인터프리터를 사용한다. 라우팅·계획은 고정 대역, MCP는 원본 사본이다. 시연용 0.35초 지연은 양쪽 모두 제거했다. 지연은 이 통제 환경의 요청 wall-clock이며 운영 지연이 아니다.

기준 자유 텍스트와 개선 JSON은 응답 계약·프롬프트가 다르다. 가설·조치의 의미와 인과관계는 채점하지 않는다.

## 검증기 오류 주입

A-01 개발 fixture에 대응하는 표현 두 가지를 사용했다. 동일한 출력 문자열이나 실모델 일반화 평가가 아니다.

| 버전 | 정상 통과 | 오류 검출 | 잘못된 통과 | 정상 오탐 |
|---|---|---|---|---|
| baseline | 6/6 (100.0%) | 0/18 (0.0%) | 18/18 (100.0%) | 0/6 (0.0%) |
| improved | 6/6 (100.0%) | 18/18 (100.0%) | 0/18 (0.0%) | 0/6 (0.0%) |

## 파이프라인

| 버전/시나리오/경로 | 완료/전체 | 자체 검사 통과 | 실패 | 평균 작성/재작성 | 평균 지연(초) |
|---|---|---|---|---|---|
| baseline/first_valid/rest | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 1/0 | 0.0073 |
| baseline/first_valid/sse | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 1/0 | 0.0079 |
| baseline/repair/rest | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 2/1 | 0.0070 |
| baseline/repair/sse | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 2/1 | 0.0160 |
| baseline/exhausted/rest | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 3/2 | 0.0075 |
| baseline/exhausted/sse | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 3/2 | 0.0082 |
| improved/first_valid/rest | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 1/0 | 0.0078 |
| improved/first_valid/sse | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 1/0 | 0.0161 |
| improved/repair/rest | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 2/1 | 0.0081 |
| improved/repair/sse | 3/3 | 3/3 (100.0%) | 0/3 (0.0%) | 2/1 | 0.0079 |
| improved/exhausted/rest | 3/3 | 0/3 (0.0%) | 3/3 (100.0%) | 3/2 | 0.0081 |
| improved/exhausted/sse | 3/3 | 0/3 (0.0%) | 3/3 (100.0%) | 3/2 | 0.0090 |

## 공개·저장 경계

| 버전/시나리오/경로 | 검증 전 토큰 전송 요청 | 오류 초안 노출 | 원시 프롬프트 노출 | 오류 초안 저장 |
|---|---|---|---|---|
| baseline/first_valid/rest | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| baseline/first_valid/sse | 3/3 (100.0%) | 0/3 (0.0%) | 3/3 (100.0%) | 0/3 (0.0%) |
| baseline/repair/rest | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| baseline/repair/sse | 3/3 (100.0%) | 3/3 (100.0%) | 3/3 (100.0%) | 0/3 (0.0%) |
| baseline/exhausted/rest | 0/3 (0.0%) | 3/3 (100.0%) | 0/3 (0.0%) | 3/3 (100.0%) |
| baseline/exhausted/sse | 3/3 (100.0%) | 3/3 (100.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| improved/first_valid/rest | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| improved/first_valid/sse | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| improved/repair/rest | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| improved/repair/sse | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| improved/exhausted/rest | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| improved/exhausted/sse | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |

REST의 토큰 전송 0은 스트리밍을 시험했다는 뜻이 아니다. SSE 경로의 토큰·프롬프트 노출을 별도로 읽어야 한다. 오류 초안 노출은 주입한 BAD_DRAFT 표식의 실제 응답/저장 포함 여부다. fake 토큰 0·가상 비용 0은 실모델 비용 측정이 아니다.

## 요청별 결과

### baseline · controlled-a01 · first_valid · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0092초

### baseline · controlled-a01 · first_valid · sse · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0101초

### baseline · controlled-a01 · repair · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0071초

### baseline · controlled-a01 · repair · sse · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0075초

### baseline · controlled-a01 · exhausted · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 3회 / 지연: 0.0076초

### baseline · controlled-a01 · exhausted · sse · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 3회 / 지연: 0.0085초

### baseline · controlled-a01 · first_valid · rest · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0060초

### baseline · controlled-a01 · first_valid · sse · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0066초

### baseline · controlled-a01 · repair · rest · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0064초

### baseline · controlled-a01 · repair · sse · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0072초

### baseline · controlled-a01 · exhausted · rest · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 3회 / 지연: 0.0074초

### baseline · controlled-a01 · exhausted · sse · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 3회 / 지연: 0.0081초

### baseline · controlled-a01 · first_valid · rest · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0067초

### baseline · controlled-a01 · first_valid · sse · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0071초

### baseline · controlled-a01 · repair · rest · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0076초

### baseline · controlled-a01 · repair · sse · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0332초

### baseline · controlled-a01 · exhausted · rest · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 3회 / 지연: 0.0076초

### baseline · controlled-a01 · exhausted · sse · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 3회 / 지연: 0.0081초

### improved · controlled-a01 · first_valid · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0098초

### improved · controlled-a01 · first_valid · sse · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0114초

### improved · controlled-a01 · repair · rest · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0078초

### improved · controlled-a01 · repair · sse · 1회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0079초

### improved · controlled-a01 · exhausted · rest · 1회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 0.0081초

### improved · controlled-a01 · exhausted · sse · 1회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 0.0090초

### improved · controlled-a01 · first_valid · rest · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0064초

### improved · controlled-a01 · first_valid · sse · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0084초

### improved · controlled-a01 · repair · rest · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0080초

### improved · controlled-a01 · repair · sse · 2회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0080초

### improved · controlled-a01 · exhausted · rest · 2회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 0.0082초

### improved · controlled-a01 · exhausted · sse · 2회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 0.0089초

### improved · controlled-a01 · first_valid · rest · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0071초

### improved · controlled-a01 · first_valid · sse · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 1회 / 지연: 0.0287초

### improved · controlled-a01 · repair · rest · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0084초

### improved · controlled-a01 · repair · sse · 3회

작업 오류: `None` / 자체 검사: `True` / 작성: 2회 / 지연: 0.0078초

### improved · controlled-a01 · exhausted · rest · 3회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 0.0081초

### improved · controlled-a01 · exhausted · sse · 3회

작업 오류: `None` / 자체 검사: `False` / 작성: 3회 / 지연: 0.0091초

## 해석과 제한

- 생성 모델이 오류를 낼 확률을 오류 주입 검출률로 해석하지 않는다. 개발 fixture이며 외부 독립 평가 집합이 아니다.
- 실모델 질문·수치는 A-06에서 새로 고정했지만 독립 인간 평가나 미공개 벤치마크가 아니다. 인용 정밀도와 사실 포함률은 별개다.
- unknown 원본밖에 없는 질문의 검증 실패는 확인 불가능한 진단을 성공으로 바꾸지 않는 동작이다.
- 로컬 토큰은 실제 응답 사용량이며 usd는 1천 토큰당 가상 단가 $0.005 추정이다. 실제 API 청구액이 아니다.
- 실패·미측정·미지원 수치는 성공이나 0%로 치환하지 않았다. 원시 JSON에 각 호출·응답·종료 원인·오류·해시를 남겼다.
- 실제 MCP 네트워크·라우팅 품질·운영 지연·가설 의미·출처 진위를 측정하지 않는다.

계약 검사 위반: 0개
