"""고정 Git 기준과 개선 스냅샷을 격리 실행해 원시 결과·보고서를 만든다.

예: ./.venv/bin/python -m evaluation.run --mode offline --output evaluation/results/offline.json
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

from evaluation.common import BASELINE, SETTINGS, digest, fraction, oracle_observations, summarize

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    """셸 보간 없이 로컬 Git의 고정 소스 정보를 읽는다."""
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def source_info(ref):
    """전체 커밋과 실제 평가에 쓴 agent·server·data 해시를 함께 고정한다."""
    commit = git('rev-parse', '--verify', f'{ref}^{{commit}}')
    return {'commit': commit, 'agent_tree': git('rev-parse', f'{commit}:agent'),
            'server_blob': git('rev-parse', f'{commit}:server.py'), 'data_tree': git('rev-parse', f'{commit}:data')}


def runner_matches_commit(commit, fingerprints):
    """미커밋 파일도 평가할 수 있도록 Git에 없는 소스는 불일치로 표시한다."""
    for path, fingerprint in fingerprints.items():
        blob = subprocess.run(['git', 'show', f'{commit}:{path}'], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if blob.returncode or sha256(blob.stdout).hexdigest() != fingerprint:
            return False
    return True


def run_worker(source, variant, options):
    """Git 소스를 임시 추출하고 같은 인터프리터·평가 코드·fixture로 실행한다."""
    archive = subprocess.check_output(['git', 'archive', source['commit'], 'agent', 'server.py', 'data'], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix=f'skala-eval-{variant}-') as tmp:
        target = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(target, filter='data')
        shutil.copytree(ROOT / 'evaluation', target / 'evaluation',
                        ignore=shutil.ignore_patterns('results', '__pycache__', '*.pyc'))
        (target / 'tests/fixtures').mkdir(parents=True)
        shutil.copy2(ROOT / 'tests/fixtures/diagnosis_cases.json', target / 'tests/fixtures/diagnosis_cases.json')
        request = {'variant': variant, 'mode': options.mode, 'model': options.model, 'repetitions': options.repetitions}
        result = subprocess.run([sys.executable, '-m', 'evaluation.worker'], cwd=target, input=json.dumps(request),
                                text=True, stdout=subprocess.PIPE, timeout=1800, check=True)
        return json.loads(result.stdout)


def model_environment(model):
    """이미 설치된 로컬 모델만 허용하고 동일 예산의 준비 호출은 측정에서 분리한다."""
    import httpx
    with httpx.Client(base_url='http://127.0.0.1:11434', timeout=120, trust_env=False) as client:
        tags = client.get('/api/tags')
        tags.raise_for_status()
        selected = next((m for m in tags.json()['models'] if model in (m.get('name'), m.get('model'))), None)
        if selected is None:
            raise RuntimeError('requested model is not installed locally; no model will be downloaded')
        if (selected.get('remote_host') or selected.get('remote_model')
                or selected.get('details', {}).get('format') != 'gguf'):
            raise RuntimeError('only verified local GGUF models are supported; cloud tags are forbidden')
        version = client.get('/api/version')
        version.raise_for_status()
        warmup = client.post('/api/chat', json={'model': model, 'messages': [{'role': 'user', 'content': 'OK라고만 답하세요.'}],
                                               'stream': False, 'think': False, 'options': SETTINGS})
        warmup.raise_for_status()
        data = warmup.json()
        return {'model': model, 'digest': selected['digest'], 'details': selected.get('details'),
                'ollama_version': version.json()['version'], 'settings': SETTINGS, 'think': False, 'stream': False,
                'warmup_excluded': {k: data.get(k) for k in ('done_reason', 'total_duration', 'load_duration',
                                                          'prompt_eval_count', 'eval_count')}}


def validator_summary(cases):
    """수동 정답 정상·거부 집합의 검출·오탐 분모를 분리한다."""
    good = [c for c in cases if c['expected'] == 'accept']
    bad = [c for c in cases if c['expected'] == 'reject']
    return {'normal_acceptance': fraction(sum(c['passed'] for c in good), len(good)),
            'fault_detection': fraction(sum(not c['passed'] for c in bad), len(bad)),
            'false_acceptance': fraction(sum(c['passed'] for c in bad), len(bad)),
            'false_rejection': fraction(sum(not c['passed'] for c in good), len(good))}


def build_summary(studies, mode):
    """통제 시험과 실모델을 혼합하지 않고 버전·시나리오·전송 경계별로 집계한다."""
    summary = {}
    for study in studies:
        groups = {}
        for row in study['rows']:
            key = f"{row['scenario']}/{row['endpoint']}"
            groups.setdefault(key, []).append(row)
        summary[study['variant']] = {'validator': validator_summary(study['validator_cases']) if mode == 'offline' else None,
                                     'groups': {key: summarize(rows) for key, rows in groups.items()}}
    return summary


def functional_violations(studies, mode):
    """자동 시험의 기대 계약만 검사하며 실모델의 불리한 품질 결과를 숨기지 않는다."""
    errors = []
    for study in studies:
        for row in study['rows']:
            prefix = f"{study['variant']}/{row['scenario']}/{row['endpoint']}/{row['repetition']}"
            if row['operational_error']:
                errors.append(f"{prefix}: operational_error={row['operational_error']}")
            elif mode == 'offline':
                expected_calls = {'first_valid': 1, 'repair': 2, 'exhausted': 3}[row['scenario']]
                if row['write_calls'] != expected_calls:
                    errors.append(f'{prefix}: unexpected write call count')
                expected_pass = not (study['variant'] == 'improved' and row['scenario'] == 'exhausted')
                if row['reported_pass'] is not expected_pass:
                    errors.append(f'{prefix}: unexpected reported verdict')
                if study['variant'] == 'improved' and any(row[k] for k in (
                        'unvalidated_token_frames', 'bad_draft_exposed', 'raw_prompt_exposed', 'bad_draft_saved')):
                    errors.append(f'{prefix}: public boundary violation')
        if mode == 'offline' and study['variant'] == 'improved':
            for case in study['validator_cases']:
                if case['passed'] != (case['expected'] == 'accept'):
                    errors.append(f"validator/{case['case_id']}: manual label mismatch")
    return errors


def ratio_text(value):
    """0개 분모는 미측정으로 표시하며 비율 옆에 원래 분모를 보존한다."""
    if value['rate'] is None:
        return f"미측정 ({value['numerator']}/{value['denominator']})"
    return f"{value['numerator']}/{value['denominator']} ({value['rate']:.1%})"


def fenced(text):
    """생성 문장의 Markdown·HTML을 보고서에서도 코드 텍스트로 취급한다."""
    import re
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    fence = '~' * max(3, max((len(m) + 1 for m in re.findall(r'~+', text)), default=3))
    return f'{fence}text\n{text}\n{fence}'


def report(result):
    """실행 조건·수치·모든 최종 응답과 실패를 빠짐없이 읽을 수 있게 렌더링한다."""
    meta = result['metadata']
    lines = [f"# A-06 {meta['mode']} 실행 결과", '', f"생성 시각: {meta['created_at']}", '',
             f"기준: `{meta['sources']['baseline']['commit']}`", f"개선: `{meta['sources']['improved']['commit']}`", '',
             '두 버전은 같은 질문·원본·태스크·인터프리터를 사용한다. 라우팅·계획은 고정 대역, MCP는 원본 사본이다. '
             '시연용 0.35초 지연은 양쪽 모두 제거했다. 지연은 이 통제 환경의 요청 wall-clock이며 운영 지연이 아니다.', '',
             '기준 자유 텍스트와 개선 JSON은 응답 계약·프롬프트가 다르다. 가설·조치의 의미와 인과관계는 채점하지 않는다.', '']
    if meta['mode'] == 'offline':
        lines += ['## 검증기 오류 주입', '', 'A-01 개발 fixture에 대응하는 표현 두 가지를 사용했다. 동일한 출력 문자열이나 실모델 일반화 평가가 아니다.', '',
                  '| 버전 | 정상 통과 | 오류 검출 | 잘못된 통과 | 정상 오탐 |', '|---|---|---|---|---|']
        for variant, summary in result['summary'].items():
            v = summary['validator']
            lines.append('| ' + variant + ' | ' + ' | '.join(ratio_text(v[k]) for k in ('normal_acceptance', 'fault_detection', 'false_acceptance', 'false_rejection')) + ' |')
    else:
        m = meta['local_model']
        lines += ['## 실모델 조건', '', f"모델: `{m['model']}`, digest `{m['digest']}`, Ollama `{m['ollama_version']}`.",
                  f"설정: `{json.dumps(SETTINGS)}`, think=false, 비스트리밍. 준비 호출 1회는 제외했다. 각 질문은 버전별 {meta['repetitions']}회다.", '',
                  '평가용 HTTP 전송은 두 버전 모두 같은 비스트리밍으로 통제했다. 실제 writer 프롬프트와 검증 흐름을 사용하지만 운영 기본 thinking/스트리밍 조건과 다르다. '
                  '기준→개선 순차 실행이므로 순서·캐시 영향이 남으며 작은 표본으로 우열을 일반화하지 않는다.', '',
                  '기준 자유 텍스트의 문장 전체 수치·출처 일치율은 자동 채점 미지원이다. 개선 관측은 별도 수동 작성 허용 사실 목록으로 대조한다. '
                  '아래의 자체 검사 통과율은 독립적인 전체 답변 정확도가 아니다.', '']
    lines += ['', '## 파이프라인', '', '| 버전/시나리오/경로 | 완료/전체 | 자체 검사 통과 | 실패 | 평균 작성/재작성 | 평균 지연(초) |', '|---|---|---|---|---|---|']
    for variant, summary in result['summary'].items():
        for name, group in summary['groups'].items():
            delay = group['latency_seconds']['mean']
            lines.append(f"| {variant}/{name} | {group['completed']}/{group['runs']} | {ratio_text(group['reported_pass'])} | "
                         f"{ratio_text(group['reported_failure'])} | {group['mean_write_calls']}/{group['mean_rewrites']} | {delay:.4f} |" if delay is not None
                         else f"| {variant}/{name} | {group['completed']}/{group['runs']} | 미측정 | 미측정 | 미측정 | 미측정 |")
    if meta['mode'] == 'offline':
        lines += ['', '## 공개·저장 경계', '', '| 버전/시나리오/경로 | 검증 전 토큰 전송 요청 | 오류 초안 노출 | 원시 프롬프트 노출 | 오류 초안 저장 |', '|---|---|---|---|---|']
        for variant, summary in result['summary'].items():
            for name, group in summary['groups'].items():
                lines.append('| ' + variant + '/' + name + ' | ' + ' | '.join(ratio_text(group[k]) for k in
                    ('unvalidated_token_runs', 'bad_draft_exposure', 'raw_prompt_exposure', 'bad_draft_saved')) + ' |')
        lines += ['', 'REST의 토큰 전송 0은 스트리밍을 시험했다는 뜻이 아니다. SSE 경로의 토큰·프롬프트 노출을 별도로 읽어야 한다. '
                  '오류 초안 노출은 주입한 BAD_DRAFT 표식의 실제 응답/저장 포함 여부다. fake 토큰 0·가상 비용 0은 실모델 비용 측정이 아니다.']
    lines += ['', '## 요청별 결과', '']
    for study in result['studies']:
        for row in study['rows']:
            lines += [f"### {study['variant']} · {row['case_id']} · {row['scenario']} · {row['endpoint']} · {row['repetition']}회", '',
                      f"작업 오류: `{row['operational_error']}` / 자체 검사: `{row['reported_pass']}` / 작성: {row['write_calls']}회 / 지연: {row['elapsed_seconds']:.4f}초", '']
            if 'oracle' in row:
                lines += [f"인용 관측 원본 일치: {ratio_text(row['oracle']['cited_match'])}; 허용 사실 포함: {ratio_text(row['oracle']['fact_coverage'])}.", '']
            if meta['mode'] == 'ollama':
                lines += [fenced(row['reply'] or '(응답 없음)'), '']
    lines += ['## 해석과 제한', '',
              '- 생성 모델이 오류를 낼 확률을 오류 주입 검출률로 해석하지 않는다. 개발 fixture이며 외부 독립 평가 집합이 아니다.',
              '- 실모델 질문·수치는 A-06에서 새로 고정했지만 독립 인간 평가나 미공개 벤치마크가 아니다. 인용 정밀도와 사실 포함률은 별개다.',
              '- unknown 원본밖에 없는 질문의 검증 실패는 확인 불가능한 진단을 성공으로 바꾸지 않는 동작이다.',
              '- 로컬 토큰은 실제 응답 사용량이며 usd는 1천 토큰당 가상 단가 $0.005 추정이다. 실제 API 청구액이 아니다.',
              '- 실패·미측정·미지원 수치는 성공이나 0%로 치환하지 않았다. 원시 JSON에 각 호출·응답·종료 원인·오류·해시를 남겼다.',
              '- 실제 MCP 네트워크·라우팅 품질·운영 지연·가설 의미·출처 진위를 측정하지 않는다.', '',
              f"계약 검사 위반: {len(result['functional_violations'])}개", *[f'- {e}' for e in result['functional_violations']], '']
    return '\n'.join(lines)


def main(argv=None):
    """평가를 실행하고 실패 기록도 저장하며 기존 결과는 명시적 덮어쓰기 때만 변경한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('offline', 'ollama'), default='offline')
    parser.add_argument('--improved-ref', default='HEAD')
    parser.add_argument('--model', default='qwen3:8b')
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--overwrite', action='store_true')
    options = parser.parse_args(argv)
    if options.output.suffix.lower() != '.json':
        parser.error('output must end in .json so the JSON and Markdown paths cannot collide')
    if not 1 <= options.repetitions <= 10:
        parser.error('repetitions must be between 1 and 10')
    if (options.output.exists() or options.output.with_suffix('.md').exists()) and not options.overwrite:
        parser.error('output already exists; choose a new path or explicitly use --overwrite')
    sources = {'baseline': source_info(BASELINE), 'improved': source_info(options.improved_ref)}
    runner_files = sorted(p for p in (ROOT / 'evaluation').rglob('*') if p.suffix in ('.py', '.json') and 'results' not in p.parts)
    metadata = {'created_at': datetime.now(timezone.utc).isoformat(), 'mode': options.mode,
                'repetitions': options.repetitions, 'sources': sources,
                'runner_commit': git('rev-parse', 'HEAD'),
                'python': platform.python_version(), 'system': platform.system(), 'machine': platform.machine(),
                'dependencies': {name: importlib.metadata.version(name) for name in ('langgraph', 'pydantic', 'fastapi', 'httpx')},
                'fixture_sha256': sha256((ROOT / 'tests/fixtures/diagnosis_cases.json').read_bytes()).hexdigest(),
                'heldout_sha256': sha256((ROOT / 'evaluation/heldout.json').read_bytes()).hexdigest(),
                'runner_sha256': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in runner_files},
                'conditions': {'routing': 'fixed', 'collection': 'fixed snapshots', 'demo_delay_seconds': 0,
                               'real_mcp': False, 'dotenv_loaded': False, 'user_db_used': False}}
    metadata['runner_matches_commit'] = runner_matches_commit(metadata['runner_commit'], metadata['runner_sha256'])
    if options.mode == 'ollama':
        metadata['local_model'] = model_environment(options.model)
    studies = [run_worker(sources[variant], variant, options) for variant in ('baseline', 'improved')]
    if options.mode == 'ollama':
        cases = {c['id']: c for c in json.loads((ROOT / 'evaluation/heldout.json').read_text())['cases']}
        for study in studies:
            if study['variant'] == 'improved':
                for row in study['rows']:
                    if not row['operational_error']:
                        row['oracle'] = oracle_observations(row['diagnosis'], cases[row['case_id']])
    result = {'schema_version': 1, 'metadata': metadata, 'studies': studies,
              'summary': build_summary(studies, options.mode), 'functional_violations': functional_violations(studies, options.mode)}
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    options.output.with_suffix('.md').write_text(report(result))
    print(f'Results: {options.output}; contract violations: {len(result["functional_violations"])}', flush=True)
    return 1 if result['functional_violations'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
