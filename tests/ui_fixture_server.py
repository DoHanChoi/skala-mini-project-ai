"""사용자 환경설정·DB·외부 모델 없이 A-05 화면 시나리오를 제공하는 임시 서버.

실행: ./.venv/bin/python tests/ui_fixture_server.py --port 18762
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
import uvicorn

from tests.support import make_deps, load_fixture
from agent.graph import build_graph
from agent.json_output import json_safe
from agent.supervisor_v1 import run_v1

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI()


@app.get('/')
async def index():
    """실제 개발 중인 Vue 화면 파일을 제공한다."""
    return FileResponse(ROOT / 'web_chat.html')


@app.get('/health')
async def health():
    """실모델로 오인하지 않도록 fixture 백엔드 이름을 반환한다."""
    return {'llm_backend': 'fake', 'fast_llm': 'fixture-fast', 'quality_llm': 'fixture-quality'}


async def scenario(message):
    """사용자 문구에 따라 요청마다 독립적인 fake 그래프·근거로 화면 데이터를 만든다."""
    deps = make_deps()
    query = load_fixture()['query'] if message != '안녕하세요' else message
    original = deps.quality_llm.diagnose

    async def diagnose(query, evidence, analysis, attempt, feedback):
        """실패 초안을 주입하거나 정상 진단에 출처 연결 가설을 추가한다."""
        if '실패' in message:
            return 'PRIVATE FAILED DRAFT', {'usd': 0, 'prompt': 'PRIVATE RAW PROMPT'}
        content, usage = await original(query, evidence, analysis, attempt, feedback)
        if attempt > 1:
            draft = json.loads(content)
            monitoring = next((e for e in evidence if e['source'] == 'monitoring' and e['available']), None)
            if monitoring:
                draft['hypotheses'] = [{'text': '부하 증가가 원인일 가능성이 있습니다.', 'evidence_ids': [monitoring['id']]}]
            content = json.dumps(draft, ensure_ascii=False)
        return content, usage

    deps.quality_llm.diagnose = diagnose
    if 'unknown' in message:
        for e in deps.mcp.evidence:
            if e['source'] == 'monitoring':
                e['data'].update(status='unknown', cpu_percent=0, memory_percent=0, alerts=['CPU 확인 불가'])
    if '매뉴얼없음' in message:
        async def no_runbook(uri, server):
            """없는 매뉴얼 안내를 정상 문서로 표시하지 않는지 확인한다."""
            return '# Runbook Not Found\nNo runbook for incident type: cpu-spike'
        deps.mcp.read_resource = no_runbook
    if 'HTML' in message:
        for e in deps.mcp.evidence:
            if e['id'] == 'runbook-cpu':
                e['data'] += '\n<img src=x onerror="alert(1)"><script>alert(2)</script>\n[실행](javascript:alert(3))'
    if 'v1' in message:
        async def legacy_monitor(name, arguments, server='ops'):
            """v1의 고정 조회 계약에 맞는 공개 샘플만 반환한다."""
            return {'system_name': 'auth-service', 'status': 'degraded', 'cpu_percent': 78.0}
        deps.mcp.call_tool = legacy_monitor
        result = await run_v1(deps, query, 'ui-fixture', [])
    else:
        result = await build_graph(deps).ainvoke({'query': query, 'events': [], 'history': []})
    validation = result.get('validation')
    if validation:
        validation = {**validation, 'status': 'passed' if validation['passed'] else 'failed'}
    else:
        validation = {'status': 'not_applicable', 'passed': None, 'attempt': 0, 'scope': None,
                      'errors': [], 'request_id': None, 'reason': 'legacy_v1' if 'v1' in message else 'general_chat'}
    answer = {'type': 'FinalAnswer', 'reply': result['final'], 'diagnosis': result.get('diagnosis'),
              'evidence': json_safe(result.get('evidence', [])), 'validation': validation}
    if '구버전' in message:
        answer = {'type': 'FinalAnswer', 'reply': '검증 정보가 없는 이전 서버의 응답입니다.'}
    return result, answer


@app.get('/chat/stream')
async def stream(message: str, thread_id: str = 'ui-fixture'):
    """확정 fixture와 진행 이벤트만 보내며 사용자 DB를 생성하거나 읽지 않는다."""
    async def gen():
        """일반 대화 토큰·최종 결과·정상 종료를 기존 SSE 모양으로 제공한다."""
        result, answer = await scenario(message)
        for event in result['events']:
            yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
        if result['route'] == 'chat':
            yield f'data: {json.dumps({"type": "AnswerToken", "delta": answer["reply"]}, ensure_ascii=False)}\n\n'
        yield f'data: {json.dumps(answer, ensure_ascii=False)}\n\n'
        yield 'data: [DONE]\n\n'
    return StreamingResponse(gen(), media_type='text/event-stream')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18762)
    args = parser.parse_args()
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
