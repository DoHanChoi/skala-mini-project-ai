"""In-process ASGI checks with a temporary DB; server lifespan is never started."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.support import OfflineAsyncCase, load_fixture, make_deps
import httpx
from agent.graph import build_graph
from agent.session_store import SqliteSessionStore

# server.py calls load_dotenv at import time. Block it before the import.
with patch("dotenv.load_dotenv", return_value=False):
    import server


def parse_sse(response):
    frames = response.text.strip().split("\n\n")
    assert frames[-1] == "data: [DONE]", frames[-1]
    assert frames.count("data: [DONE]") == 1
    return [json.loads(frame.removeprefix("data: ")) for frame in frames[:-1]]


class ApiBaselineTests(OfflineAsyncCase):
    async def asyncSetUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.db_path = Path(self.tmp) / "test-session.db"
        self.store = SqliteSessionStore(self.db_path)
        self.addCleanup(self.store.close)
        self.deps = make_deps(store=self.store)
        self.enterContext(patch("server.MCPClient", side_effect=AssertionError("Real MCP startup forbidden")))
        self.enterContext(patch("server.SqliteSessionStore", side_effect=AssertionError("Default DB forbidden")))
        self.enterContext(patch.dict(server.app.state._state, {
            "deps": self.deps, "graph": build_graph(self.deps),
            "llm_backend": "fake", "instance_id": 12345}, clear=True))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_rest_and_sse_return_same_final_and_save_only_final(self):
        query = load_fixture()["query"]
        rest = await self.client.post("/chat", json={"message": query, "thread_id": "rest"})
        stream = await self.client.get("/chat/stream", params={"message": query, "thread_id": "stream"})
        self.assertEqual((rest.status_code, stream.status_code), (200, 200))
        self.assertTrue(stream.headers["content-type"].startswith("text/event-stream"))
        body = rest.json()
        events = parse_sse(stream)
        final = [e for e in events if e["type"] == "FinalAnswer"]
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["reply"], body["reply"])
        self.assertEqual(set(body), {"reply", "events", "metadata"})
        self.assertEqual(body["metadata"]["validation_attempts"], 2)
        self.assertEqual(body["metadata"]["supervisor_version"], "v2")
        self.assertEqual(body["metadata"]["llm_backend"], "fake")
        self.assertEqual(body["metadata"]["gate_removed"], 1)
        self.assertEqual(body["metadata"]["replan_rounds"], 1)
        # SSE adds node names; the underlying domain events should be equivalent.
        streamed_events = [{k: v for k, v in e.items() if k != "node"}
                           for e in events if e["type"] not in {"AnswerToken", "FinalAnswer"}]
        self.assertEqual(streamed_events, body["events"])
        for thread in ("rest", "stream"):
            self.assertEqual(self.store.load(thread), [
                {"role": "user", "content": query}, {"role": "assistant", "content": body["reply"]}])
        token_index = next(i for i, e in enumerate(events) if e["type"] == "AnswerToken")
        validation_index = next(i for i, e in enumerate(events) if e["type"] == "Validation")
        self.assertEqual(events[token_index]["delta"], "재시작하면 됩니다.")
        self.assertLess(token_index, validation_index)

    async def test_sse_exposes_last_prompt_when_writer_supplies_it(self):
        # Fake normally supplies no prompt. A fake response exercises the current
        # transport contract without invoking either real model backend.
        reply = "1) 고정된 관측값을 확인하고 표준 매뉴얼의 대응 절차를 검토하여 진단합니다."
        with patch.object(self.deps.quality_llm, "write", return_value=(
                reply, {"usd": 0, "prompt": "TEST-ONLY RAW PROMPT"})):
            response = await self.client.get("/chat/stream", params={"message": load_fixture()["query"]})
        final = next(e for e in parse_sse(response) if e["type"] == "FinalAnswer")
        self.assertEqual(final["prompt"], "TEST-ONLY RAW PROMPT")

    async def test_general_chat_session_persistence_and_isolation(self):
        first = await self.client.post("/chat", json={"message": "제 이름은 민수입니다", "thread_id": "a"})
        self.assertEqual(first.json()["metadata"]["route"], "chat")
        response = await self.client.get("/chat/stream", params={"message": "제 이름이 뭐였죠?", "thread_id": "a"})
        final = next(e for e in parse_sse(response) if e["type"] == "FinalAnswer")
        self.assertEqual(final["reply"], "민수님이라고 말씀하셨어요. 무엇을 도와드릴까요?")
        other = await self.client.post("/chat", json={"message": "제 이름이 뭐였죠?", "thread_id": "b"})
        self.assertEqual(other.json()["reply"], "안녕하세요! 무엇을 도와드릴까요?")
        # Reopen the temporary DB with another connection, never the user's DB.
        reopened = SqliteSessionStore(self.db_path)
        try:
            self.assertEqual(reopened.load("a"), self.store.load("a"))
            self.assertEqual(len(reopened.load("a")), 4)
            self.assertEqual(len(reopened.load("b")), 2)
        finally:
            reopened.close()
        self.assertEqual(self.deps.mcp.calls, [])

    async def test_v1_basic_legacy_contract_has_no_validation(self):
        self.deps.version = "v1"
        query = load_fixture()["query"]
        # Legacy deliberately looks up auth-service regardless of requested target.
        from unittest.mock import AsyncMock
        with patch.object(self.deps.mcp, "call_tool", new=AsyncMock(return_value={
                "system_name": "auth-service", "status": "degraded", "cpu_percent": 78.0})) as tool:
            rest = await self.client.post("/chat", json={"message": query, "thread_id": "v1-rest"})
            stream = await self.client.get("/chat/stream", params={"message": query, "thread_id": "v1-stream"})
        body = rest.json()
        self.assertEqual(body["metadata"]["validation_attempts"], 0)
        self.assertEqual(body["metadata"]["route"], "legacy")
        self.assertEqual(body["metadata"]["supervisor_version"], "v1")
        self.assertEqual([e["type"] for e in body["events"]], ["Legacy", "TaskCompleted", "Finalize"])
        final = next(e for e in parse_sse(stream) if e["type"] == "FinalAnswer")
        self.assertEqual(final["reply"], body["reply"])
        self.assertIn("auth-service 상태=degraded, CPU 78.0%", body["reply"])
        self.assertEqual(tool.await_count, 2)
        self.assertEqual(tool.call_args.args[1], {"system_name": "auth-service"})

    async def test_missing_message_is_rejected_without_graph_or_storage(self):
        response = await self.client.post("/chat", json={"thread_id": "bad"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.store.load("bad"), [])
        self.assertEqual(self.deps.mcp.calls, [])
