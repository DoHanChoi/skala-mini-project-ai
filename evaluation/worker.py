"""한 Git 스냅샷을 별도 프로세스에서 평가한다. .env·실제 MCP·사용자 DB를 읽지 않는다."""
import asyncio
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['LANGCHAIN_TRACING_V2'] = 'false'

import httpx
from agent.deps import SupervisorDeps
from agent import graph
from agent.session_store import SqliteSessionStore
from evaluation.common import REQUEST_ID, SETTINGS, digest, normalized_fixture

with patch('dotenv.load_dotenv', return_value=False):
    import server

REAL_SLEEP = asyncio.sleep


async def no_demo_sleep(seconds):
    """두 버전 모두 연구 노드의 0.35초 시연 지연만 제거한다."""
    await REAL_SLEEP(0 if seconds == .35 else seconds)


class FixedFast:
    """모델 작성 단계 비교를 위해 라우팅·태스크 선택을 두 버전에 동일하게 고정한다."""
    name = 'controlled-router'

    def __init__(self, case):
        """선택한 스냅샷의 조사 대상만 보관한다."""
        self.case = case

    def route(self, query):
        """평가 질문을 장애 경로로 고정하며 생성 모델을 호출하지 않는다."""
        return {'route': 'incident', 'needs_analysis': False}, {'usd': 0}

    def plan(self, query, procedure):
        """고정 모니터링과 매뉴얼 태스크를 한 번씩 만든다."""
        tasks = [{'id': f'task-{i}', 'agent': 'research', 'kind': 'monitoring',
                  'target': record['system_name'], 'status': 'pending'}
                 for i, record in enumerate(self.case['monitoring'])]
        tasks.append({'id': 'task-runbook', 'agent': 'research', 'kind': 'runbook',
                      'target': self.case['runbook_type'], 'status': 'pending'})
        return {'tasks': tasks, 'needs_analysis': False}, {'usd': 0}


class FixedMCP:
    """외부 프로토콜 대신 두 버전에 같은 원본 사본을 제공한다."""
    def __init__(self, case):
        """질문별 스냅샷 사본을 고정한다."""
        self.case = deepcopy(case)

    async def find_prompt(self, name):
        """연결을 만들지 않고 고정 프롬프트 서버를 반환한다."""
        assert name == 'incident_analysis_prompt'
        return 'evaluation-ops'

    async def get_prompt(self, name, arguments, server):
        """태스크 선택에 영향을 주지 않는 동일 절차를 제공한다."""
        return '고정 원본 스냅샷을 조회하고 사실·가설·조치를 구분한다.'

    async def find_resource_template(self, name):
        """실제 URI 생성 규칙은 동일하게 유지한다."""
        assert name == 'get_incident_runbook'
        return 'evaluation-ops', 'runbook://incident-response/{incident_type}'

    async def call_tool(self, name, arguments, server='ops'):
        """설정한 대상만 허용하고 매번 독립적인 원본을 반환한다."""
        assert name == 'get_monitoring_status' and server == 'ops'
        return deepcopy(next(r for r in self.case['monitoring'] if r['system_name'] == arguments['system_name']))

    async def read_resource(self, uri, server):
        """설정한 매뉴얼 본문만 반환하며 누락 안내도 원문 그대로 보존한다."""
        assert uri == f"runbook://incident-response/{self.case['runbook_type']}"
        assert server == 'evaluation-ops'
        return self.case['runbook']


def bounded_ollama(model):
    """실제 작성 프롬프트는 유지하고 양쪽 HTTP 전송·생성 예산을 동일하게 고정한다."""
    from agent.ollama_llm import OllamaQualityLLM
    delegate = OllamaQualityLLM(model, .005)
    transport_calls = []

    def chat(system, user, schema=None):
        """로컬 고정 주소만 호출하고 요청 해시·실측 토큰·종료 원인을 수집한다."""
        payload = {'model': model, 'messages': [{'role': 'system', 'content': system},
                   {'role': 'user', 'content': user}], 'stream': False, 'think': False,
                   'options': SETTINGS}
        if schema is not None:
            payload['format'] = schema
        record = {'request_sha256': digest(payload), 'prompt_sha256': digest(payload['messages'])}
        transport_calls.append(record)
        response = httpx.post('http://127.0.0.1:11434/api/chat', json=payload, timeout=120, trust_env=False)
        response.raise_for_status()
        data = response.json()
        record.update({key: data.get(key) for key in ('done', 'done_reason', 'prompt_eval_count', 'eval_count',
                       'total_duration', 'load_duration', 'prompt_eval_duration', 'eval_duration')})
        tokens = (data.get('prompt_eval_count') or 0) + (data.get('eval_count') or 0)
        return data['message']['content'], {'model': f'ollama:{model}', 'tokens': tokens,
                                           'usd': round(tokens / 1000 * .005, 6)}

    async def chat_stream(system, user, on_token=None):
        """REST 측정에서는 기준 writer도 같은 비스트리밍 전송을 쓰도록 통제한다."""
        content, usage = await asyncio.to_thread(chat, system, user)
        usage['prompt'] = f'[SYSTEM]\n{system}\n\n[USER]\n{user}'
        if on_token:
            on_token(content)
        return content, usage

    delegate._chat = chat
    delegate._chat_stream = chat_stream
    return delegate, transport_calls


class RecordingQuality:
    """결정론적 오류 주입 또는 실모델 호출을 계측하며 수동 정답을 모델 입력에 넣지 않는다."""
    def __init__(self, mode, scenario, model):
        """각 요청의 호출 기록과 선택적인 로컬 모델을 초기화한다."""
        self.mode, self.scenario, self.calls = mode, scenario, []
        self.delegate, self.transport_calls = bounded_ollama(model) if mode == 'ollama' else (None, [])

    async def write(self, query, collected, attempt, feedback, on_token=None):
        """기준 버전의 실제 writer 계약을 사용하거나 대응하는 오류 텍스트를 주입한다."""
        return await self.invoke('write', query, collected, [], attempt, feedback, on_token)

    async def diagnose(self, query, evidence, analysis, attempt, feedback):
        """개선 버전의 실제 JSON writer 계약을 사용하거나 구조화 오류를 주입한다."""
        return await self.invoke('diagnose', query, evidence, analysis, attempt, feedback, None)

    async def invoke(self, method, query, context, analysis, attempt, feedback, on_token):
        """실패한 호출도 기록하고 모델 원문·사용량·지연을 누락 없이 남긴다."""
        entry = {'attempt': attempt, 'feedback': feedback, 'usage': {}, 'output': None, 'error_type': None}
        self.calls.append(entry)
        started = time.perf_counter()
        try:
            if self.mode == 'ollama':
                if method == 'write':
                    content, usage = await self.delegate.write(query, context, attempt, feedback, on_token=on_token)
                else:
                    content, usage = await self.delegate.diagnose(query, context, analysis, attempt, feedback)
                entry['transport'] = deepcopy(self.transport_calls[-1])
            else:
                bad = self.scenario == 'exhausted' or (self.scenario == 'repair' and attempt == 1)
                if method == 'write':
                    facts = [f"{r['data']['system_name']} CPU {r['data']['cpu_percent']}%, 메모리 {r['data']['memory_percent']}%, 상태 {r['data']['status']}"
                             for r in context if r['source'] == 'monitoring']
                    content = 'BAD_DRAFT' if bad else '1) ' + '; '.join(facts) + '. 2) 매뉴얼을 검토하고 담당자와 후속 조치를 결정한다.'
                    if on_token:
                        on_token(content)
                else:
                    observations = []
                    for source in context:
                        if source['source'] != 'monitoring' or not source['available']:
                            continue
                        for metric in source['eligible_metrics']:
                            values = source['raw'][metric] if metric == 'alerts' else [source['raw'][metric]]
                            for value in values:
                                observations.append({'system_name': source['system_name'], 'metric': metric,
                                    'value': value, 'unit': '%' if metric in ('cpu_percent', 'memory_percent') else None,
                                    'evidence_id': source['id']})
                    if bad:
                        next(o for o in observations if o['metric'] == 'cpu_percent')['value'] = 99
                    content = json.dumps({'observations': observations,
                        'hypotheses': [{'text': 'BAD_DRAFT', 'evidence_ids': [context[0]['id']]}] if bad else [],
                        'actions': []}, ensure_ascii=False)
                usage = {'model': 'scripted-paired', 'tokens': 0, 'usd': 0, 'prompt': 'RAW_PROMPT_MARKER'}
            entry.update(output=content, usage={k: v for k, v in usage.items() if k != 'prompt'})
            return content, usage
        except Exception as exc:
            entry['error_type'] = type(exc).__name__
            raise
        finally:
            entry['elapsed_seconds'] = time.perf_counter() - started


async def validator_cases(fixture, variant):
    """A-01 수동 정답을 기준 자유 텍스트 또는 개선 구조 입력으로 평가한다."""
    results = []
    if variant == 'improved':
        from agent.validation import validate_diagnosis
        evidence, cases = normalized_fixture(fixture)
    else:
        cases = fixture['cases']
    for case in cases:
        if variant == 'baseline':
            result = await graph.validate_node({'draft': case['legacy_draft'], 'events': []}, None)
            passed, errors = result['validation_feedback'] is None, []
        else:
            result = validate_diagnosis(case['candidate_draft'], evidence, request_id=fixture['request_id'])
            passed, errors = result.passed, [e.model_dump() for e in result.errors]
        results.append({'case_id': case['id'], 'expected': case['expected_a_plan'], 'passed': passed, 'errors': errors})
    return results


async def pipeline(case, scenario, endpoint, repetition, options):
    """실제 REST/SSE·임시 저장 경계를 실행하고 공개 자료만 노출 지표로 집계한다."""
    quality = RecordingQuality(options['mode'], scenario, options['model'])
    row = {'case_id': case['id'], 'scenario': scenario, 'endpoint': endpoint, 'repetition': repetition,
           'input_sha256': digest({k: case[k] for k in ('query', 'monitoring', 'runbook', 'runbook_type')}),
           'operational_error': None, 'reply': None, 'diagnosis': None, 'reported_pass': None,
           'validation_attempts': 0, 'unvalidated_token_frames': 0, 'bad_draft_exposed': False,
           'raw_prompt_exposed': False, 'bad_draft_saved': False}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='skala-eval-db-') as tmp:
        store = SqliteSessionStore(Path(tmp) / 'session.db')
        deps = SupervisorDeps(FixedFast(case), quality, FixedMCP(case), store, 'v2')
        try:
            with patch.dict(server.app.state._state, {'deps': deps, 'graph': graph.build_graph(deps),
                            'llm_backend': options['mode'], 'instance_id': 1}, clear=True):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://test') as client:
                    if endpoint == 'rest':
                        response = await client.post('/chat', json={'message': case['query'], 'thread_id': 'eval'})
                        response.raise_for_status()
                        answer = response.json()
                        events = answer['events']
                    else:
                        response = await client.get('/chat/stream', params={'message': case['query'], 'thread_id': 'eval'})
                        response.raise_for_status()
                        frames = response.text.strip().split('\n\n')
                        assert frames[-1] == 'data: [DONE]' and frames.count('data: [DONE]') == 1
                        events = [json.loads(frame.removeprefix('data: ')) for frame in frames[:-1]]
                        answers = [e for e in events if e['type'] == 'FinalAnswer']
                        assert len(answers) == 1
                        answer = answers[0]
                    judgments = [e for e in events if e['type'] == 'Validation']
                    reported_pass = (answer['validation']['passed'] if 'validation' in answer
                                     else judgments[-1]['verdict'].startswith('합격'))
                    row.update(reply=answer['reply'], diagnosis=answer.get('diagnosis'), reported_pass=reported_pass,
                        validation=answer.get('validation'), validation_attempts=judgments[-1]['attempt'],
                        unvalidated_token_frames=sum(e['type'] == 'AnswerToken' for e in events),
                        bad_draft_exposed='BAD_DRAFT' in response.text,
                        raw_prompt_exposed=bool(answer.get('prompt')) or 'RAW_PROMPT_MARKER' in response.text,
                        bad_draft_saved=any('BAD_DRAFT' in m['content'] for m in store.load('eval') if m['role'] == 'assistant'),
                        evidence=answer.get('evidence', []))
        except Exception as exc:
            row['operational_error'] = type(exc).__name__
        finally:
            store.close()
    row.update(calls=quality.calls, write_calls=len(quality.calls), elapsed_seconds=time.perf_counter() - started)
    return row


async def run(options):
    """기준·개선 중 한쪽을 같은 고정 자료와 계측 조건으로 실행한다."""
    fixture = json.loads(Path('tests/fixtures/diagnosis_cases.json').read_text())
    heldout = json.loads(Path('evaluation/heldout.json').read_text())['cases']
    if options['mode'] == 'offline':
        selected = {e['id']: e for e in fixture['evidence']}
        cases = [{'id': 'controlled-a01', 'query': fixture['query'],
                  'monitoring': [selected[i]['data'] for i in ('mon-payments', 'mon-web')],
                  'runbook': selected['runbook-cpu']['data'], 'runbook_type': 'cpu-spike'}]
        scenarios, endpoints = ['first_valid', 'repair', 'exhausted'], ['rest', 'sse']
    else:
        cases, scenarios, endpoints = heldout, ['real_model'], ['rest']
    rows = []
    with patch('agent.graph.asyncio.sleep', new=no_demo_sleep), patch('agent.graph.uuid4', create=True) as uid, \
         patch('agent.graph.datetime', create=True) as clock:
        uid.return_value.hex = REQUEST_ID
        clock.now.return_value = datetime(2026, 10, 21, tzinfo=timezone.utc)
        for repetition in range(1, options['repetitions'] + 1):
            for case in cases:
                for scenario in scenarios:
                    for endpoint in endpoints:
                        print(f"{options['variant']} {options['mode']} {case['id']} {scenario} {endpoint} rep={repetition}", file=sys.stderr, flush=True)
                        rows.append(await pipeline(case, scenario, endpoint, repetition, options))
    return {'variant': options['variant'], 'mode': options['mode'],
            'validator_cases': await validator_cases(fixture, options['variant']) if options['mode'] == 'offline' else [],
            'rows': rows}


def main():
    """오프라인 모드는 소켓·DNS를 차단하고 결과 JSON만 표준 출력에 쓴다."""
    options = json.loads(sys.stdin.read())
    with ExitStack() as stack:
        if options['mode'] == 'offline':
            for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection', 'socket.getaddrinfo'):
                stack.enter_context(patch(name, side_effect=AssertionError('network forbidden')))
        result = asyncio.run(run(options))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
