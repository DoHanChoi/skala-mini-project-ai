"""Test-only fixed inputs and network isolation; never load the user's .env."""
import asyncio
import copy
import json
import os
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

# Set before importing decorated production functions, even when a shell has
# tracing enabled. No test calls load_dotenv or the real MCP/LLM backends.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from agent.deps import SupervisorDeps
from agent.fake_llm import FastLLM, QualityLLM

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "diagnosis_cases.json"
REAL_SLEEP = asyncio.sleep


def load_fixture():
    """각 테스트에 독립적인 고정 입력 사본을 제공한다."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def collected_fixture():
    """기준 장애 경로가 수집하는 모니터링 두 건과 매뉴얼을 반환한다."""
    selected = {"mon-payments", "mon-web", "runbook-cpu"}
    return [{"source": e["source"], "data": e["data"]}
            for e in load_fixture()["evidence"] if e["id"] in selected]


async def no_delay(_seconds):
    """데모 지연을 없애되 비동기 태스크의 실행 양보는 유지한다."""
    # Preserve an actual scheduling point while removing demo/backoff delays.
    await REAL_SLEEP(0)


class FixtureMCP:
    """Strict in-process MCP double. Unknown calls fail instead of going online."""

    def __init__(self, transient_once=False):
        """선택적으로 한 번의 타임아웃을 주입하고 호출 기록을 초기화한다."""
        self.calls = []
        self.transient_pending = transient_once
        self.evidence = load_fixture()["evidence"]

    async def find_prompt(self, name):
        """허용된 진단 프롬프트의 테스트 서버만 반환한다."""
        assert name == "incident_analysis_prompt", name
        return "fixture-ops"

    async def get_prompt(self, name, arguments, server):
        """실제 MCP 연결 없이 대상과 증상을 담은 계획 입력을 만든다."""
        assert name == "incident_analysis_prompt" and server == "fixture-ops"
        return f"시스템: {arguments['system_name']}\n증상: {arguments['symptom']}"

    async def call_tool(self, name, arguments):
        """고정 모니터링을 조회하고 미설정 대상과 예상 밖 호출을 거부한다."""
        assert name == "get_monitoring_status", name
        self.calls.append((name, copy.deepcopy(arguments)))
        if self.transient_pending:
            self.transient_pending = False
            raise asyncio.TimeoutError("fixed transient failure")
        for e in self.evidence:
            if e["source"] == "monitoring" and e["request_id"] == "fixture-request-a":
                if e["data"]["system_name"] == arguments["system_name"]:
                    return copy.deepcopy(e["data"])
        raise AssertionError(f"Unconfigured monitoring target: {arguments}")

    async def find_resource_template(self, name):
        """매뉴얼 조회에 사용할 테스트 URI 템플릿을 반환한다."""
        assert name == "get_incident_runbook", name
        return "fixture-ops", "runbook://incident-response/{incident_type}"

    async def read_resource(self, uri, server):
        """고정 매뉴얼 본문을 반환하며 미설정 리소스는 실패시킨다."""
        assert server == "fixture-ops", server
        self.calls.append(("read_resource", uri))
        for e in self.evidence:
            if e["source"] == "runbook" and e["uri"] == uri:
                return e["data"]
        raise AssertionError(f"Unconfigured resource: {uri}")


def make_deps(store=None, quality=None, transient_once=False):
    """fake 모델·MCP 대역과 선택적인 임시 저장소로 의존성을 조립한다."""
    return SupervisorDeps(
        fast_llm=FastLLM("fixed-fast", 0.00015),
        quality_llm=quality if quality is not None else QualityLLM("fixed-quality", 0.005),
        mcp=FixtureMCP(transient_once), session_store=store, version="v2")


class OfflineAsyncCase(IsolatedAsyncioTestCase):
    def setUp(self):
        """테스트 동안 외부 연결·DNS 조회와 데모 지연을 차단한다."""
        super().setUp()
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo"):
            self.enterContext(patch(target, side_effect=AssertionError("External network forbidden in tests")))
        self.enterContext(patch("agent.graph.asyncio.sleep", side_effect=no_delay))
