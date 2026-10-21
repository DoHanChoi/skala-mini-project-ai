"""빈 알림의 실제 실패 재현과 작성 안내·재작성·공개 경계를 검증한다."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import httpx

from tests.support import OfflineAsyncCase, load_fixture, make_deps
from tests.test_pipeline import parse_sse
from agent.diagnosis_prompt import diagnosis_prompt
from agent.evidence import monitoring_evidence
from agent.graph import build_graph
from agent.session_store import SqliteSessionStore
from agent.validation import validate_diagnosis

with patch('dotenv.load_dotenv', return_value=False):
    import server


def sample(alerts):
    """A-06과 다른 시스템·수치의 독립적인 알림 경계 자료를 만든다."""
    source = monitoring_evidence(request_id='alert-test', task_index=0, task_id='monitor',
        target='queue-worker', server='ops', retrieved_at='2026-10-21T10:00:00+09:00',
        data={'system_name': 'queue-worker', 'status': 'degraded', 'cpu_percent': 23.75,
              'memory_percent': 88.25, 'alerts': alerts}).model_dump()
    draft = {'observations': [{'system_name': 'queue-worker', 'metric': 'memory_percent',
        'value': 88.25, 'unit': '%', 'evidence_id': source['id']}], 'hypotheses': [], 'actions': []}
    return source, draft


class AlertRewriteTests(OfflineAsyncCase):
    async def test_recorded_memory_failure_has_actionable_empty_array_feedback(self):
        """A-06 실모델 초안은 계속 거부하되 빈 배열 관측 삭제를 구체적으로 안내한다."""
        result = json.loads((Path(__file__).resolve().parents[1] /
                            'evaluation/results/ollama-qwen3-8b.json').read_text(encoding='utf-8'))
        row = next(r for s in result['studies'] if s['variant'] == 'improved'
                   for r in s['rows'] if r['case_id'] == 'heldout-memory')
        for call in row['calls']:
            verdict = validate_diagnosis(call['output'], row['evidence'], request_id='evaluation-request')
            self.assertFalse(verdict.passed)
            error = next(e for e in verdict.errors if e.path == 'observations.7.value')
            self.assertEqual(error.code, 'value_mismatch')
            self.assertIn('빈 배열', error.message)
            self.assertIn('삭제', error.message)
            self.assertIn('유지', error.message)

    async def test_empty_array_rejects_placeholders_without_mutation_or_reflection(self):
        """빈 문자열·없음·배열 표현·임의 문장은 인용되지 않고 오류에 원문도 복사하지 않는다."""
        for value in ('', '없음', '[]', 'FAILED_EMPTY_ALERT_DRAFT'):
            source, draft = sample([])
            draft['observations'].append({**draft['observations'][0], 'metric': 'alerts', 'unit': None, 'value': value})
            before = deepcopy((source, draft))
            verdict = validate_diagnosis(draft, [source], request_id='alert-test')
            self.assertFalse(verdict.passed)
            self.assertEqual((source, draft), before)
            self.assertEqual([(e.code, e.path) for e in verdict.errors], [('value_mismatch', 'observations.1.value')])
            self.assertIn('빈 배열', verdict.errors[0].message)
            self.assertNotIn('FAILED_EMPTY_ALERT_DRAFT', verdict.model_dump_json())
            draft['observations'].pop()
            self.assertTrue(validate_diagnosis(draft, [source], request_id='alert-test').passed)

    async def test_nonempty_alerts_keep_exact_membership_including_empty_string(self):
        """원본 배열 []와 실제 빈 문자열 항목이 있는 배열을 혼동해 검증 범위를 바꾸지 않는다."""
        for alerts in ([''], ['메모리 88.25%\n<script>원문</script>', '대기열 증가']):
            source, draft = sample(alerts)
            for value in alerts:
                draft['observations'] = [{**draft['observations'][0], 'metric': 'alerts', 'value': value, 'unit': None}]
                self.assertTrue(validate_diagnosis(draft, [source], request_id='alert-test').passed)
            draft['observations'][0]['value'] = '원문에 없는 알림'
            verdict = validate_diagnosis(draft, [source], request_id='alert-test')
            self.assertFalse(verdict.passed)
            self.assertNotIn('빈 배열', verdict.errors[0].message)

    async def test_three_backends_receive_common_empty_array_instruction(self):
        """fake·Ollama·OpenAI 모두 같은 작성 규칙을 사용하며 원본 입력을 유지한다."""
        from agent.fake_llm import QualityLLM
        from agent.ollama_llm import OllamaQualityLLM
        from agent.openai_llm import OpenAIQualityLLM
        source, _ = sample([])
        original = deepcopy(source)
        for backend in (QualityLLM, OllamaQualityLLM, OpenAIQualityLLM):
            model = backend('test', 0)
            with patch('agent.diagnosis_prompt.diagnosis_prompt', wraps=diagnosis_prompt) as common:
                if backend is QualityLLM:
                    await model.diagnose('메모리 진단', [source], [], 2, None)
                else:
                    with patch.object(model, '_chat', return_value=('{}', {'usd': 0})) as transport:
                        await model.diagnose('메모리 진단', [source], [], 2, None)
                    system, user = transport.call_args.args[:2]
                    self.assertIn('alerts=[]', system)
                    self.assertIn('관측을 만들지', system)
                    self.assertEqual(json.loads(user)['evidence'], [source])
                common.assert_called_once()
        self.assertEqual(source, original)

    async def test_empty_alert_rewrite_and_exhaustion_preserve_api_and_storage_boundary(self):
        """실제 REST/SSE에서 피드백 수신 후 수정 성공과 반복 실패의 상한·저장을 검사한다."""
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteSessionStore(Path(tmp) / 'session.db')
            self.addCleanup(store.close)
            deps = make_deps(store=store)
            original = deps.quality_llm.diagnose
            for repair in (True, False):
                for endpoint in ('rest', 'sse'):
                    calls = []
                    valid_observations = []

                    async def response(query, evidence, analysis, attempt, feedback):
                        """피드백의 삭제 안내를 받은 경우에만 오류 알림을 제거하는 모델 대역이다."""
                        calls.append(deepcopy((evidence, feedback)))
                        content, usage = await original(query, evidence, analysis, 2, feedback)
                        valid_observations.append(json.loads(content)['observations'])
                        errors = json.loads(feedback) if feedback else []
                        actionable = any('빈 배열' in e['message'] and '삭제' in e['message'] for e in errors)
                        if not (repair and actionable):
                            draft = json.loads(content)
                            source = next(e for e in evidence if e['source'] == 'monitoring' and e['raw']['alerts'] == [])
                            observation = next(o for o in draft['observations'] if o['evidence_id'] == source['id'])
                            draft['observations'].append({**observation, 'metric': 'alerts',
                                'unit': None, 'value': 'FAILED_EMPTY_ALERT_DRAFT'})
                            content = json.dumps(draft)
                        return content, {**usage, 'prompt': 'RAW_PROMPT_MARKER'}

                    thread = f'{endpoint}-{repair}'
                    with patch.object(deps.quality_llm, 'diagnose', side_effect=response), patch.dict(
                        server.app.state._state, {'deps': deps, 'graph': build_graph(deps),
                            'llm_backend': 'fake', 'instance_id': 1}, clear=True):
                        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://test') as client:
                            if endpoint == 'rest':
                                public = await client.post('/chat', json={'message': load_fixture()['query'], 'thread_id': thread})
                                body = public.json()
                            else:
                                public = await client.get('/chat/stream', params={'message': load_fixture()['query'], 'thread_id': thread})
                                frames = parse_sse(public)
                                self.assertFalse(any(e['type'] == 'AnswerToken' for e in frames))
                                body = next(e for e in frames if e['type'] == 'FinalAnswer')
                    self.assertEqual(public.status_code, 200)
                    self.assertEqual(body['validation']['passed'], repair)
                    self.assertEqual(body['validation']['attempt'], 2 if repair else 3)
                    self.assertEqual(len(calls), 2 if repair else 3)
                    self.assertTrue(all(evidence == calls[0][0] for evidence, _ in calls))
                    self.assertTrue(all(feedback for _, feedback in calls[1:]))
                    self.assertEqual(store.load(thread)[-1]['content'], body['reply'])
                    self.assertNotIn('FAILED_EMPTY_ALERT_DRAFT', public.text + json.dumps(store.load(thread)))
                    self.assertNotIn('RAW_PROMPT_MARKER', public.text)
                    if repair:
                        self.assertEqual(body['diagnosis']['observations'], valid_observations[0])
                        empty_ids = {e['id'] for e in body['evidence'] if e['source'] == 'monitoring' and e['raw']['alerts'] == []}
                        self.assertFalse(any(o['metric'] == 'alerts' and o['evidence_id'] in empty_ids
                                             for o in body['diagnosis']['observations']))
                    else:
                        self.assertIsNone(body['diagnosis'])
