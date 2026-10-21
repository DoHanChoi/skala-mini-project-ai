"""평가 집계·독립 대조·소스 격리와 실제 REST/SSE 계측의 재현성을 검증한다."""
from argparse import Namespace
import asyncio
from contextlib import redirect_stderr
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import subprocess
from unittest.mock import patch

import httpx

from tests.support import OfflineAsyncCase, load_fixture
from evaluation.common import REQUEST_ID, SETTINGS, digest, fraction, normalized_fixture, oracle_observations, summarize
from evaluation.run import ROOT, build_summary, functional_violations, main, model_environment, run_worker, source_info, validator_summary, fenced
from evaluation.worker import bounded_ollama


class EvaluationTests(OfflineAsyncCase):
    async def test_zero_denominator_is_unmeasured_and_errors_do_not_become_success(self):
        """실행 오류·미관측 사용량과 빈 분모를 0%·성공으로 치환하지 않는다."""
        self.assertEqual(fraction(0, 0), {'numerator': 0, 'denominator': 0, 'rate': None})
        row = {'operational_error': 'ReadTimeout', 'elapsed_seconds': 1,
               'calls': [{'usage': {}}]}
        summary = summarize([row])
        self.assertEqual((summary['completed'], summary['operational_errors']), (0, 1))
        self.assertIsNone(summary['reported_pass']['rate'])
        self.assertIsNone(summary['latency_seconds']['mean'])
        self.assertIsNone(summary['model_tokens'])
        self.assertIsNone(summary['estimated_usd_virtual'])
        self.assertEqual(summary['token_observation_coverage']['denominator'], 1)

    async def test_latency_nearest_rank_and_rewrite_denominators(self):
        """지연 분포와 초기 작성 포함 호출 수·재작성 횟수를 분리한다."""
        rows = [{'operational_error': None, 'elapsed_seconds': value, 'reported_pass': value < 3,
                 'unvalidated_token_frames': 0, 'bad_draft_exposed': False, 'raw_prompt_exposed': False,
                 'bad_draft_saved': False, 'write_calls': value, 'calls': [{'usage': {'tokens': 10, 'usd': .01}}]}
                for value in (1, 2, 3)]
        result = summarize(rows)
        self.assertEqual(result['latency_seconds'], {'n': 3, 'mean': 2, 'p50': 2, 'p95_nearest_rank': 3})
        self.assertEqual((result['mean_write_calls'], result['mean_rewrites']), (2, 1))
        self.assertEqual(result['reported_pass'], fraction(2, 3))
        self.assertEqual(result['model_tokens'], 30)

    async def test_oracle_checks_system_metric_unit_value_and_source_without_validator(self):
        """동일 숫자·다른 시스템/항목/단위/출처와 bool을 독립적인 수동 사실표로 거부한다."""
        case = {'expected_observations': [{'system_name': 'auth-service', 'metric': 'cpu_percent',
                                          'value': 86.5, 'unit': '%', 'source_index': 0}]}
        observation = {'system_name': 'auth-service', 'metric': 'cpu_percent', 'value': 86.5,
                       'unit': '%', 'evidence_id': f'ev:{REQUEST_ID}:0'}
        self.assertEqual(oracle_observations({'observations': [observation]}, case)['cited_match'], fraction(1, 1))
        for changes in ({'system_name': 'web-01'}, {'metric': 'memory_percent'}, {'unit': 'ratio'},
                        {'value': True}, {'value': 99}, {'evidence_id': f'ev:{REQUEST_ID}:1'}):
            with self.subTest(changes=changes):
                result = oracle_observations({'observations': [{**observation, **changes}]}, case)
                self.assertEqual(result['cited_match'], fraction(0, 1))
        repeated = oracle_observations({'observations': [observation, observation]}, case)
        self.assertEqual(repeated['fact_coverage'], fraction(1, 1))
        self.assertEqual(oracle_observations(None, {'expected_observations': []})['cited_match'], fraction(0, 0))

    async def test_fixture_adapter_preserves_labels_values_and_analysis_is_not_evidence(self):
        """ID 대조용 변환이 정답·값을 바꾸거나 모델 해석을 원본으로 승격하지 않는다."""
        fixture = load_fixture()
        original = deepcopy(fixture)
        evidence, cases = normalized_fixture(fixture)
        self.assertEqual(fixture, original)
        self.assertEqual(len(evidence), 8)
        self.assertEqual([c['expected_a_plan'] for c in cases], [c['expected_a_plan'] for c in fixture['cases']])
        wrong = next(c for c in cases if c['id'] == 'wrong-value')
        self.assertEqual(wrong['candidate_draft']['observations'][0]['value'], 99)
        analysis = next(c for c in cases if c['id'] == 'analysis-as-source')
        self.assertEqual(analysis['candidate_draft']['observations'][0]['evidence_id'], 'analysis-generated')
        self.assertEqual(evidence[0]['raw']['cpu_percent'], 91.0)

    async def test_confusion_matrix_and_content_hash_are_independent_of_order(self):
        """검출과 오탐의 분모를 구분하고 공백·키 순서에 의존하지 않는 해시를 쓴다."""
        summary = validator_summary([{'expected': 'accept', 'passed': False},
                                     {'expected': 'reject', 'passed': False}, {'expected': 'reject', 'passed': True}])
        self.assertEqual(summary['fault_detection'], fraction(1, 2))
        self.assertEqual(summary['false_rejection'], fraction(1, 1))
        self.assertEqual(digest({'a': 1, 'b': 2}), digest({'b': 2, 'a': 1}))
        self.assertNotEqual(digest({'a': 1}), digest({'a': 2}))

    async def test_existing_output_is_protected_without_explicit_overwrite(self):
        """기존 평가 파일을 소스 추출·모델 호출 전에 보호한다."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'existing.json'
            target.write_text('keep')
            with patch('evaluation.run.run_worker') as worker, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    main(['--output', str(target)])
            self.assertEqual(exc.exception.code, 2)
            self.assertEqual(target.read_text(), 'keep')
            worker.assert_not_called()

    async def test_json_output_path_cannot_collide_with_markdown_report(self):
        """비 JSON 경로는 원시 결과와 Markdown이 같은 파일을 덮어쓰기 전에 거부한다."""
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()), patch('evaluation.run.run_worker') as worker:
            with self.assertRaises(SystemExit):
                main(['--output', str(Path(tmp) / 'report.md')])
            worker.assert_not_called()
            self.assertFalse((Path(tmp) / 'report.md').exists())

    async def test_local_model_preflight_does_not_download_or_call_missing_model(self):
        """모델이 없으면 준비/생성 요청을 보내지 않고 측정을 중단한다."""
        requests = []

        def handle(request):
            """모델 목록만 허용하는 네트워크 대역이다."""
            requests.append(request)
            return httpx.Response(200, json={'models': []})

        client = httpx.Client(transport=httpx.MockTransport(handle), base_url='http://127.0.0.1:11434')
        with patch('httpx.Client', return_value=client):
            with self.assertRaisesRegex(RuntimeError, 'not installed locally'):
                model_environment('not-installed')
        self.assertEqual([r.url.path for r in requests], ['/api/tags'])

    async def test_cloud_or_unverified_model_tag_is_rejected_before_generation(self):
        """로컬 서버 주소여도 클라우드 태그나 검증되지 않은 형식은 생성하지 않는다."""
        for tag in ({'remote_host': 'https://example.invalid', 'details': {'format': 'gguf'}},
                    {'details': {'format': 'remote'}}):
            requests = []

            def handle(request):
                """클라우드 태그의 목록 응답만 제공하고 호출 경로를 기록한다."""
                requests.append(request)
                return httpx.Response(200, json={'models': [{'name': 'cloud-tag', 'digest': 'x', **tag}]})

            client = httpx.Client(transport=httpx.MockTransport(handle), base_url='http://127.0.0.1:11434')
            with patch('httpx.Client', return_value=client):
                with self.assertRaisesRegex(RuntimeError, 'cloud tags are forbidden'):
                    model_environment('cloud-tag')
            self.assertEqual([r.url.path for r in requests], ['/api/tags'])

    async def test_controlled_model_transport_keeps_same_budget_and_records_actual_usage(self):
        """평가 전송이 로컬 고정 주소·같은 생성 예산을 쓰고 토큰·종료 원인을 보존한다."""
        model, calls = bounded_ollama('qwen3:8b')
        response = httpx.Response(200, json={'message': {'content': 'answer'}, 'done': True, 'done_reason': 'stop',
            'prompt_eval_count': 12, 'eval_count': 8}, request=httpx.Request('POST', 'http://127.0.0.1:11434/api/chat'))
        with patch('httpx.post', return_value=response) as post:
            content, usage = model._chat('SECRET SYSTEM', 'fixed snapshot', schema={'type': 'object'})
        self.assertEqual(content, 'answer')
        self.assertEqual(usage['tokens'], 20)
        self.assertEqual(calls[0]['done_reason'], 'stop')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['options'], SETTINGS)
        self.assertFalse(payload['think'])
        self.assertFalse(payload['stream'])
        self.assertEqual(post.call_args.args[0], 'http://127.0.0.1:11434/api/chat')
        self.assertNotIn('SECRET SYSTEM', json.dumps(calls))

    async def test_transport_missing_or_invalid_token_counts_remain_unmeasured(self):
        """로컬 응답의 사용량 누락·잘못된 수를 실측 0토큰·0원으로 만들지 않는다."""
        for counts in ({}, {'prompt_eval_count': 12},
                       {'prompt_eval_count': True, 'eval_count': 8},
                       {'prompt_eval_count': 12, 'eval_count': -1}):
            model, _ = bounded_ollama('qwen3:8b')
            response = httpx.Response(200, json={'message': {'content': 'answer'}, **counts},
                request=httpx.Request('POST', 'http://127.0.0.1:11434/api/chat'))
            with patch('httpx.post', return_value=response):
                _, usage = model._chat('system', 'snapshot')
            self.assertNotIn('tokens', usage)
            self.assertNotIn('usd', usage)

    async def test_source_isolation_reproduces_both_validators_and_public_boundaries(self):
        """기준·개선을 별도 Git 추출 프로세스에서 실제 REST/SSE·임시 DB로 비교한다."""
        options = Namespace(mode='offline', model='unused', repetitions=1)
        sources = [source_info('447db631b079f6c8b5e67c3b2bfce4dbaf59169f'), source_info('HEAD')]
        studies = [await asyncio.to_thread(run_worker, source, variant, options)
                   for source, variant in zip(sources, ('baseline', 'improved'))]
        self.assertEqual(functional_violations(studies, 'offline'), [])
        baseline, improved = studies
        self.assertEqual(validator_summary(baseline['validator_cases'])['fault_detection'], fraction(0, 18))
        self.assertEqual(validator_summary(improved['validator_cases'])['fault_detection'], fraction(18, 18))
        self.assertEqual([r['input_sha256'] for r in baseline['rows']], [r['input_sha256'] for r in improved['rows']])
        for study in studies:
            self.assertEqual(len(study['rows']), 6)
        failed_old = next(r for r in baseline['rows'] if r['scenario'] == 'exhausted' and r['endpoint'] == 'rest')
        failed_new = next(r for r in improved['rows'] if r['scenario'] == 'exhausted' and r['endpoint'] == 'rest')
        self.assertTrue(failed_old['reported_pass'])
        self.assertTrue(failed_old['bad_draft_saved'])
        self.assertFalse(failed_new['reported_pass'])
        self.assertFalse(failed_new['bad_draft_saved'])
        sse_old = next(r for r in baseline['rows'] if r['scenario'] == 'repair' and r['endpoint'] == 'sse')
        self.assertTrue(sse_old['raw_prompt_exposed'])
        self.assertEqual(sse_old['unvalidated_token_frames'], 2)

    async def test_generated_report_fences_do_not_execute_model_markup(self):
        """원시 모델 응답의 HTML·펜스도 보고서의 코드 텍스트로 감싼다."""
        text = '<img src=x onerror=alert(1)>\n~~~\ntext'
        rendered = fenced(text)
        self.assertTrue(rendered.startswith('~~~~text\n'))
        self.assertTrue(rendered.endswith('\n~~~~'))
        self.assertIn(text, rendered)
        self.assertNotIn('text  \n', fenced('text  '))

    async def test_real_model_quality_failure_is_kept_separate_from_operational_failure(self):
        """실모델의 검증 실패는 측정 결과로 남기고 실행 오류와 혼동하지 않는다."""
        row = {'scenario': 'real_model', 'endpoint': 'rest', 'repetition': 1,
               'operational_error': None, 'reported_pass': False}
        study = {'variant': 'improved', 'rows': [row], 'validator_cases': []}
        self.assertEqual(functional_violations([study], 'ollama'), [])
        row['operational_error'] = 'ReadTimeout'
        self.assertEqual(len(functional_violations([study], 'ollama')), 1)

    async def test_recorded_results_match_their_pinned_runner_and_recomputed_aggregation(self):
        """실측 당시 소스 해시와 집계값을 현재 구현·결과 개선 여부와 독립적으로 확인한다."""
        for name in ('offline', 'ollama-qwen3-8b'):
            result = json.loads((ROOT / f'evaluation/results/{name}.json').read_text())
            commit = result['metadata'].get('runner_commit') or result['provenance_annotation']['runner_source_commit']
            for path, fingerprint in result['metadata']['runner_sha256'].items():
                source = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
                self.assertEqual(sha256(source).hexdigest(), fingerprint)
            if 'provenance_annotation' in result:
                original = subprocess.check_output(['git', 'show', f'{commit}:evaluation/results/{name}.json'], cwd=ROOT)
                self.assertEqual(sha256(original).hexdigest(), result['provenance_annotation']['original_result_sha256'])
                self.assertEqual(json.loads(original), {k: v for k, v in result.items() if k != 'provenance_annotation'})
            self.assertEqual(build_summary(result['studies'], result['metadata']['mode']), result['summary'])

    async def test_full_offline_cli_writes_json_and_markdown_without_real_model(self):
        """CLI 전체 경로의 소스·계측·집계·보고서 파일 생성을 외부 연결 없이 검증한다."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'result.json'
            with patch('evaluation.run.model_environment', side_effect=AssertionError('real model forbidden')):
                code = await asyncio.to_thread(main, ['--mode', 'offline', '--repetitions', '1',
                    '--improved-ref', '56a7b12e88976d97ce4dc02426f1aea342452b1d', '--output', str(target)])
            self.assertEqual(code, 0)
            result = json.loads(target.read_text())
            self.assertEqual(result['metadata']['mode'], 'offline')
            self.assertNotIn('local_model', result['metadata'])
            self.assertEqual(result['functional_violations'], [])
            self.assertEqual([len(s['rows']) for s in result['studies']], [6, 6])
            self.assertIn('실모델 일반화 평가가 아니다', target.with_suffix('.md').read_text())
