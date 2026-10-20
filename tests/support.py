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
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def collected_fixture():
    selected = {"mon-payments", "mon-web", "runbook-cpu"}
    return [{"source": e["source"], "data": e["data"]}
            for e in load_fixture()["evidence"] if e["id"] in selected]


async def no_delay(_seconds):
    # Preserve an actual scheduling point while removing demo/backoff delays.
    await REAL_SLEEP(0)


class FixtureMCP:
    """Strict in-process MCP double. Unknown calls fail instead of going online."""

    def __init__(self, transient_once=False):
        self.calls = []
        self.transient_pending = transient_once
        self.evidence = load_fixture()["evidence"]

    async def find_prompt(self, name):
        assert name == "incident_analysis_prompt", name
        return "fixture-ops"

    async def get_prompt(self, name, arguments, server):
        assert name == "incident_analysis_prompt" and server == "fixture-ops"
        return f"시스템: {arguments['system_name']}\n증상: {arguments['symptom']}"

    async def call_tool(self, name, arguments):
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
        assert name == "get_incident_runbook", name
        return "fixture-ops", "runbook://incident-response/{incident_type}"

    async def read_resource(self, uri, server):
        assert server == "fixture-ops", server
        self.calls.append(("read_resource", uri))
        for e in self.evidence:
            if e["source"] == "runbook" and e["uri"] == uri:
                return e["data"]
        raise AssertionError(f"Unconfigured resource: {uri}")


def make_deps(store=None, quality=None, transient_once=False):
    return SupervisorDeps(
        fast_llm=FastLLM("fixed-fast", 0.00015),
        quality_llm=quality if quality is not None else QualityLLM("fixed-quality", 0.005),
        mcp=FixtureMCP(transient_once), session_store=store, version="v2")


class OfflineAsyncCase(IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo"):
            self.enterContext(patch(target, side_effect=AssertionError("External network forbidden in tests")))
        self.enterContext(patch("agent.graph.asyncio.sleep", side_effect=no_delay))
