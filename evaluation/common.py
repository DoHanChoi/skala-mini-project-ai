"""평가 fixture 변환과 분모를 보존하는 집계·독립 관측 대조."""
from copy import deepcopy
from hashlib import sha256
import json
from math import ceil, isfinite
from statistics import mean, median

BASELINE = '447db631b079f6c8b5e67c3b2bfce4dbaf59169f'
REQUEST_ID = 'evaluation-request'
SETTINGS = {'temperature': 0, 'seed': 42, 'num_predict': 2048, 'num_ctx': 8192}


def digest(value):
    """JSON 자료의 순서·공백 차이를 제거한 내용 해시를 반환한다."""
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def normalized_fixture(fixture):
    """A-01 이름을 실제 요청·태스크 ID로 바꾸고 수동 정답·원본 값은 보존한다."""
    from agent.evidence import monitoring_evidence, runbook_evidence
    evidence, identifiers = [], {}
    for index, entry in enumerate(fixture['evidence']):
        if entry['source'] not in ('monitoring', 'runbook'):
            continue
        common = dict(request_id=entry['request_id'], task_index=index, task_id=f'fixture-{index}',
                      target=entry['data']['system_name'] if entry['source'] == 'monitoring' else entry['uri'].rsplit('/', 1)[-1],
                      server=entry['server'], retrieved_at='2026-10-20T09:00:00+09:00', data=entry['data'])
        record = monitoring_evidence(**common) if entry['source'] == 'monitoring' else runbook_evidence(**common, uri=entry['uri'])
        identifiers[entry['id']] = record.id
        evidence.append(record.model_dump())
    cases = deepcopy(fixture['cases'])
    for case in cases:
        draft = case['candidate_draft']
        if not isinstance(draft, dict):
            continue
        for observation in draft['observations']:
            identifier = observation['evidence_id']
            observation['evidence_id'] = identifiers.get(identifier, identifier)
        for section in ('hypotheses', 'actions'):
            for statement in draft[section]:
                statement['evidence_ids'] = [identifiers.get(i, i) for i in statement['evidence_ids']]
    return evidence, cases


def fraction(numerator, denominator):
    """미측정·빈 분모를 0%로 바꾸지 않고 수와 비율을 함께 반환한다."""
    return {'numerator': numerator, 'denominator': denominator,
            'rate': numerator / denominator if denominator else None}


def oracle_observations(diagnosis, case):
    """운영 검증기 대신 별도로 작성한 허용 사실 목록과 출처 위치에 대조한다."""
    if diagnosis is None:
        return {'cited_match': fraction(0, 0), 'fact_coverage': fraction(0, len(case['expected_observations']))}
    expected = case['expected_observations']
    observations = diagnosis.get('observations', [])
    matched = set()
    correct = 0
    for observation in observations:
        for index, fact in enumerate(expected):
            actual_value, expected_value = observation.get('value'), fact['value']
            same_type = (type(actual_value) in (int, float) and type(expected_value) in (int, float)
                         and isfinite(actual_value)) or type(actual_value) is type(expected_value) is str
            source_id = f"ev:{REQUEST_ID}:{fact['source_index']}"
            if (same_type and actual_value == expected_value and observation.get('evidence_id') == source_id
                    and all(observation.get(k) == fact[k] for k in ('system_name', 'metric', 'unit'))):
                correct += 1
                matched.add(index)
                break
    return {'cited_match': fraction(correct, len(observations)),
            'fact_coverage': fraction(len(matched), len(expected))}


def summarize(rows):
    """작업 오류를 분리하고 같은 study·endpoint 집단의 분모와 지연 분포를 집계한다."""
    successful = [r for r in rows if r['operational_error'] is None]
    times = sorted(r['elapsed_seconds'] for r in successful)
    calls = [call for row in rows for call in row['calls']]
    observed = [call for call in calls if 'tokens' in call['usage']]
    return {
        'runs': len(rows), 'completed': len(successful), 'operational_errors': len(rows) - len(successful),
        'reported_pass': fraction(sum(r['reported_pass'] is True for r in successful), len(successful)),
        'reported_failure': fraction(sum(r['reported_pass'] is False for r in successful), len(successful)),
        'unvalidated_token_runs': fraction(sum(r['unvalidated_token_frames'] > 0 for r in successful), len(successful)),
        'bad_draft_exposure': fraction(sum(r['bad_draft_exposed'] for r in successful), len(successful)),
        'raw_prompt_exposure': fraction(sum(r['raw_prompt_exposed'] for r in successful), len(successful)),
        'bad_draft_saved': fraction(sum(r['bad_draft_saved'] for r in successful), len(successful)),
        'mean_write_calls': mean(r['write_calls'] for r in successful) if successful else None,
        'mean_rewrites': mean(max(0, r['write_calls'] - 1) for r in successful) if successful else None,
        'latency_seconds': {'n': len(times), 'mean': mean(times) if times else None,
                            'p50': median(times) if times else None,
                            'p95_nearest_rank': times[ceil(.95 * len(times)) - 1] if times else None},
        'token_observation_coverage': fraction(len(observed), len(calls)),
        'model_tokens_observed': sum(c['usage']['tokens'] for c in observed),
        'model_tokens': sum(c['usage']['tokens'] for c in observed) if len(observed) == len(calls) else None,
        'estimated_usd_virtual': sum(c['usage'].get('usd', 0) for c in observed) if len(observed) == len(calls) else None,
    }
