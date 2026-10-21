"""외부 호출 없이 v2 작성·검증·전송·저장과 세 모델 계약을 검증한다."""
import copy
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from tests.support import OfflineAsyncCase, load_fixture, make_deps
from agent.diagnosis import DiagnosisDraft
from agent.graph import build_graph
from agent.session_store import SqliteSessionStore

with patch("dotenv.load_dotenv", return_value=False):
    import server


def parse_sse(response):
    """종료 센티널이 한 번만 나타나는지 검사하고 JSON 이벤트를 반환한다."""
    frames = response.text.strip().split("\n\n")
    assert frames[-1] == "data: [DONE]"
    assert frames.count("data: [DONE]") == 1
    return [json.loads(frame.removeprefix("data: ")) for frame in frames[:-1]]


class PipelineTests(OfflineAsyncCase):
    async def test_valid_first_output_finishes_without_unnecessary_rewrite(self):
        """최초 초안이 정확하면 한 번만 작성하고 종료한다."""
        deps = make_deps()
        original = deps.quality_llm.diagnose

        async def valid(query, evidence, analysis, attempt, feedback):
            """fake의 의도적 첫 실패만 건너뛰어 정상 최초 출력을 주입한다."""
            return await original(query, evidence, analysis, 2, feedback)

        with patch.object(deps.quality_llm, "diagnose", side_effect=valid) as model:
            result = await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})
        self.assertEqual(model.await_count, 1)
        self.assertEqual(result["validation_attempts"], 1)
        self.assertTrue(result["validation"]["passed"])

    async def test_unknown_monitoring_cannot_become_confirmed_measurements(self):
        """unknown의 0 수치는 세 번 작성 후에도 검증된 관측으로 승격하지 않는다."""
        deps = make_deps()
        for record in deps.mcp.evidence:
            if record["source"] == "monitoring":
                record["data"].update(status="unknown", cpu_percent=0, memory_percent=0, alerts=[])
        with patch.object(deps.mcp, "read_resource", return_value="# Runbook Not Found"):
            result = await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})
        self.assertFalse(result["validation"]["passed"])
        self.assertEqual(result["validation_attempts"], 3)
        self.assertIsNone(result["diagnosis"])
        self.assertIn("확인 가능한 원본 관측이 없습니다", result["final"])

    async def test_fixed_incident_rewrites_then_confirms_original_values(self):
        """고정 장애가 게이트·재계획·재시도 후 두 번째 원본 일치 초안으로 끝난다."""
        deps = make_deps(transient_once=True)
        result = await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})
        self.assertEqual((result["gate_removed"], result["replan_rounds"], result["retry_count"]), (1, 1, 1))
        self.assertEqual(result["validation_attempts"], 2)
        self.assertTrue(result["validation"]["passed"])
        self.assertIn('"payments-service" CPU 사용률: 91.0%', result["final"])
        self.assertIn('"web-01" CPU 사용률: 34.0%', result["final"])
        self.assertIn("가설·조치의 의미는 검증하지 않았습니다", result["final"])
        ids = {e["id"] for e in result["evidence"]}
        self.assertTrue(all(o["evidence_id"] in ids for o in result["diagnosis"]["observations"]))
        self.assertTrue(all(t["status"] == "done" for t in result["tasks"]))
        self.assertEqual([e["will_retry"] for e in result["events"] if e["type"] == "Validation"], [True, False])

    async def test_wrong_value_feedback_and_same_evidence_reach_rewrite(self):
        """수치 오류 위치를 재작성에 전달하고 근거 ID·원본은 변경하지 않는다."""
        deps = make_deps()
        original = deps.quality_llm.diagnose
        calls = []

        async def response(query, evidence, analysis, attempt, feedback):
            """첫 관측값만 변조하고 두 번째에는 원본과 일치하는 JSON을 반환한다."""
            calls.append(copy.deepcopy((evidence, attempt, feedback)))
            content, usage = await original(query, evidence, analysis, 2, feedback)
            if attempt == 1:
                draft = json.loads(content)
                observation = next(o for o in draft["observations"] if o["metric"] == "cpu_percent")
                observation["value"] = 99
                content = json.dumps(draft)
            return content, usage

        with patch.object(deps.quality_llm, "diagnose", side_effect=response):
            result = await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})
        self.assertTrue(result["validation"]["passed"])
        self.assertEqual(calls[0][0], calls[1][0])
        self.assertIn("value_mismatch", calls[1][2])
        self.assertIn("observations.1.value", calls[1][2])
        self.assertEqual(result["validation_attempts"], 2)

    async def test_three_invalid_outputs_fail_without_releasing_draft(self):
        """잘못된 JSON·거부 응답·없는 출처 모두 총 세 번 뒤 원본 대체 결과로 끝난다."""
        for bad in ("FAILED DRAFT SECRET", None,
                    json.dumps({"observations": [{"system_name": "payments-service", "metric": "cpu_percent",
                                                  "value": 99, "unit": "%", "evidence_id": "missing"}],
                                "hypotheses": [], "actions": []})):
            with self.subTest(bad=bad):
                deps = make_deps()
                with patch.object(deps.quality_llm, "diagnose", return_value=(bad, {"usd": 0, "prompt": "RAW PROMPT SECRET"})) as model:
                    result = await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})
                self.assertEqual(model.await_count, 3)
                self.assertEqual(result["validation_attempts"], 3)
                self.assertFalse(result["validation"]["passed"])
                self.assertIsNone(result["diagnosis"])
                self.assertIn("진단 검증 실패 (시도 3/3)", result["final"])
                self.assertIn("91.0%", result["final"])
                public = json.dumps({k: result[k] for k in ("final", "events", "validation", "diagnosis")})
                self.assertNotIn("SECRET", public)
                self.assertNotIn("last_prompt", result)
                self.assertFalse([e for e in result["events"] if e["type"] == "Validation"][-1]["will_retry"])

    async def test_incident_has_progress_but_no_custom_answer_tokens(self):
        """장애 경로는 내부 초안을 custom 스트림으로 내보내지 않는다."""
        stream = [item async for item in build_graph(make_deps()).astream(
            {"query": load_fixture()["query"], "events": []}, stream_mode=["updates", "custom"])]
        self.assertFalse([payload for mode, payload in stream if mode == "custom"])
        self.assertTrue(any("validate" in p for mode, p in stream if mode == "updates"))

    async def test_model_and_resource_exceptions_propagate(self):
        """운영상 예외를 검증 실패나 정상 답변으로 숨기지 않는다."""
        for target, method in (("quality_llm", "diagnose"), ("mcp", "read_resource")):
            with self.subTest(target=target):
                deps = make_deps()
                with patch.object(getattr(deps, target), method, side_effect=RuntimeError("offline failure")):
                    with self.assertRaisesRegex(RuntimeError, "offline failure"):
                        await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})

    async def test_general_chat_preserves_history_and_streams_without_validation(self):
        """일반 대화는 이력을 사용하고 MCP·진단 검증 없이 토큰을 전송한다."""
        deps = make_deps()
        values = [item async for item in build_graph(deps).astream(
            {"query": "제 이름이 뭐였죠?", "history": [{"role": "user", "content": "제 이름은 민수입니다"}],
             "events": []}, stream_mode=["updates", "custom"])]
        tokens = [p for mode, p in values if mode == "custom"]
        self.assertEqual(len(tokens), 1)
        self.assertIn("민수님", tokens[0]["delta"])
        self.assertEqual(deps.mcp.calls, [])
        self.assertFalse(any("validate" in p for mode, p in values if mode == "updates"))


class ApiIntegrationTests(OfflineAsyncCase):
    async def asyncSetUp(self):
        """임시 DB·메모리 ASGI만 사용하고 실제 lifespan·MCP 시작을 금지한다."""
        tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.db_path = Path(tmp) / "sessions.db"
        self.store = SqliteSessionStore(self.db_path)
        self.addCleanup(self.store.close)
        self.deps = make_deps(store=self.store)
        self.enterContext(patch("server.MCPClient", side_effect=AssertionError("Real MCP forbidden")))
        self.enterContext(patch("server.SqliteSessionStore", side_effect=AssertionError("Real DB forbidden")))
        self.enterContext(patch.dict(server.app.state._state, {
            "deps": self.deps, "graph": build_graph(self.deps), "llm_backend": "fake", "instance_id": 12345}, clear=True))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_rest_sse_public_contract_and_persistence_are_equivalent(self):
        """같은 근거·시각에서 REST/SSE 진단·검증·출처와 저장 본문이 일치한다."""
        query = load_fixture()["query"]
        with patch("agent.graph.uuid4") as uid, patch("agent.graph.datetime") as clock:
            uid.return_value.hex = "fixed-request"
            clock.now.return_value = datetime(2026, 10, 21, tzinfo=timezone.utc)
            rest = await self.client.post("/chat", json={"message": query, "thread_id": "rest"})
            stream = await self.client.get("/chat/stream", params={"message": query, "thread_id": "stream"})
        self.assertEqual((rest.status_code, stream.status_code), (200, 200))
        self.assertTrue(stream.headers["content-type"].startswith("text/event-stream"))
        body = rest.json()
        events = parse_sse(stream)
        finals = [e for e in events if e["type"] == "FinalAnswer"]
        self.assertEqual(len(finals), 1)
        final = finals[0]
        self.assertEqual(set(body), {"reply", "events", "metadata", "diagnosis", "evidence", "validation"})
        self.assertEqual(set(final), {"type", "reply", "metadata", "diagnosis", "evidence", "validation"})
        for key in ("reply", "diagnosis", "evidence", "validation"):
            self.assertEqual(body[key], final[key])
        self.assertEqual(final["validation"]["status"], "passed")
        self.assertFalse([e for e in events if e["type"] == "AnswerToken"])
        domain = [{k: v for k, v in e.items() if k != "node"} for e in events if e["type"] != "FinalAnswer"]
        self.assertEqual(domain, body["events"])
        for thread in ("rest", "stream"):
            self.assertEqual(self.store.load(thread), [{"role": "user", "content": query},
                                                       {"role": "assistant", "content": body["reply"]}])

    async def test_failure_draft_and_prompt_are_absent_from_all_public_data_and_history(self):
        """세 번 실패해도 비공개 초안·프롬프트가 전송·저장되지 않는다."""
        with patch.object(self.deps.quality_llm, "diagnose", return_value=(
                'FAILED DRAFT SECRET', {"usd": 0, "prompt": "RAW PROMPT SECRET"})) as model:
            rest = await self.client.post("/chat", json={"message": load_fixture()["query"], "thread_id": "bad-rest"})
            stream = await self.client.get("/chat/stream", params={"message": load_fixture()["query"], "thread_id": "bad-stream"})
        self.assertEqual(model.await_count, 6)
        final = next(e for e in parse_sse(stream) if e["type"] == "FinalAnswer")
        for data in (rest.json(), final):
            self.assertEqual(data["validation"]["status"], "failed")
            self.assertFalse(data["validation"]["passed"])
            self.assertEqual(data["validation"]["attempt"], 3)
            self.assertIsNone(data["diagnosis"])
            self.assertIn("91.0%", data["reply"])
        for content in (rest.text, stream.text, json.dumps(self.store.load("bad-rest")), json.dumps(self.store.load("bad-stream"))):
            self.assertNotIn("SECRET", content)
            self.assertNotIn('"prompt"', content)

    async def test_general_chat_tokens_not_applicable_and_session_isolation(self):
        """일반 대화 토큰·이력 회상·세션 격리·DB 재연결과 비대상 표시를 유지한다."""
        await self.client.post("/chat", json={"message": "제 이름은 민수입니다", "thread_id": "a"})
        response = await self.client.get("/chat/stream", params={"message": "제 이름이 뭐였죠?", "thread_id": "a"})
        events = parse_sse(response)
        self.assertTrue(any(e["type"] == "AnswerToken" for e in events))
        final = next(e for e in events if e["type"] == "FinalAnswer")
        self.assertIn("민수님", final["reply"])
        self.assertEqual(final["validation"]["status"], "not_applicable")
        self.assertIsNone(final["validation"]["passed"])
        self.assertEqual(final["validation"]["reason"], "general_chat")
        self.assertIsNone(final["diagnosis"])
        self.assertEqual(final["evidence"], [])
        other = await self.client.post("/chat", json={"message": "제 이름이 뭐였죠?", "thread_id": "b"})
        self.assertNotIn("민수", other.json()["reply"])
        reopened = SqliteSessionStore(self.db_path)
        try:
            self.assertEqual(reopened.load("a"), self.store.load("a"))
            self.assertEqual(len(reopened.load("a")), 4)
        finally:
            reopened.close()
        self.assertEqual(self.deps.mcp.calls, [])

    async def test_v1_preserves_reply_and_marks_validation_not_applicable(self):
        """v1의 기존 응답과 이벤트를 유지하며 검증 적용으로 오인시키지 않는다."""
        self.deps.version = "v1"
        with patch.object(self.deps.mcp, "call_tool", new=AsyncMock(return_value={
                "system_name": "auth-service", "status": "degraded", "cpu_percent": 78.0})):
            rest = await self.client.post("/chat", json={"message": load_fixture()["query"]})
            stream = await self.client.get("/chat/stream", params={"message": load_fixture()["query"]})
        final = next(e for e in parse_sse(stream) if e["type"] == "FinalAnswer")
        self.assertEqual(final["reply"], rest.json()["reply"])
        self.assertIn("auth-service 상태=degraded, CPU 78.0%", final["reply"])
        for body in (rest.json(), final):
            self.assertEqual(body["validation"]["reason"], "legacy_v1")
            self.assertEqual(body["validation"]["status"], "not_applicable")
            self.assertIsNone(body["validation"]["passed"])
            self.assertEqual(body["metadata"]["validation_attempts"], 0)
        self.assertEqual([e["type"] for e in rest.json()["events"]], ["Legacy", "TaskCompleted", "Finalize"])

    async def test_nonfinite_source_is_not_a_measurement_and_has_explicit_json_representation(self):
        """비유한 원본 수치를 인용하지 않고 JSON 전송에만 태그를 사용한다."""
        for record in self.deps.mcp.evidence:
            if record["id"] == "mon-payments":
                record["data"]["cpu_percent"] = float("nan")
        rest = await self.client.post("/chat", json={"message": load_fixture()["query"]})
        stream = await self.client.get("/chat/stream", params={"message": load_fixture()["query"]})
        final = next(e for e in parse_sse(stream) if e["type"] == "FinalAnswer")
        for body in (rest.json(), final):
            source = next(e for e in body["evidence"] if e["system_name"] == "payments-service")
            self.assertEqual(source["raw"]["cpu_percent"], {"nonfinite_number": "nan"})
            self.assertIn("invalid_cpu_percent", source["issues"])
            self.assertNotIn("cpu_percent", source["eligible_metrics"])
            self.assertFalse(any(o["system_name"] == "payments-service" and o["metric"] == "cpu_percent"
                                 for o in body["diagnosis"]["observations"]))

    async def test_missing_message_and_operational_failure_do_not_save_assistant(self):
        """요청 오류와 모델 장애 시 거짓 성공 답변을 저장하지 않는다."""
        bad = await self.client.post("/chat", json={"thread_id": "missing"})
        self.assertEqual(bad.status_code, 422)
        with patch.object(self.deps.quality_llm, "diagnose", side_effect=RuntimeError("model offline")):
            with self.assertRaisesRegex(RuntimeError, "model offline"):
                await self.client.post("/chat", json={"message": load_fixture()["query"], "thread_id": "error"})
        self.assertEqual(self.store.load("error"), [])
        self.assertEqual(self.store.load("missing"), [])


class ModelAdapterTests(OfflineAsyncCase):
    async def test_each_remote_adapter_integrates_with_graph_rewrite_and_evidence_ids(self):
        """두 실모델 어댑터도 HTTP 대역으로 같은 그래프의 오류·재작성·성공 경로를 따른다."""
        from agent.ollama_llm import OllamaQualityLLM
        from agent.openai_llm import OpenAIQualityLLM
        for model_type in (OllamaQualityLLM, OpenAIQualityLLM):
            with self.subTest(model=model_type.__name__):
                model = model_type("test-only", 0)
                inputs = []

                def remote(_system, user, **_kwargs):
                    """근거 ID를 실제 요청에서 읽고 최초 파싱 오류 다음 원본 일치 JSON을 만든다."""
                    payload = json.loads(user)
                    inputs.append(payload)
                    if payload["attempt"] == 1:
                        return "malformed", {"usd": 0}
                    source = next(e for e in payload["evidence"] if e["source"] == "monitoring")
                    return json.dumps({"observations": [{"system_name": source["system_name"],
                        "metric": "cpu_percent", "value": source["raw"]["cpu_percent"],
                        "unit": "%", "evidence_id": source["id"]}], "hypotheses": [], "actions": []}), {"usd": 0}

                with patch.object(model, "_chat", side_effect=remote):
                    result = await build_graph(make_deps(quality=model)).ainvoke(
                        {"query": load_fixture()["query"], "events": []})
                self.assertTrue(result["validation"]["passed"])
                self.assertEqual(result["validation_attempts"], 2)
                self.assertEqual(inputs[0]["evidence"], inputs[1]["evidence"])
                self.assertIn("invalid_structure", inputs[1]["validation_feedback"])

    async def test_remote_backends_request_json_without_streaming_and_preserve_bad_output(self):
        """실제 네트워크 없이 두 HTTP 요청의 JSON 계약·오류 원문·사용량을 확인한다."""
        from agent.ollama_llm import OllamaQualityLLM
        from agent.openai_llm import OpenAIQualityLLM
        for backend in ("ollama", "openai"):
            with self.subTest(backend=backend), patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}):
                model = OllamaQualityLLM("test", 0.005) if backend == "ollama" else OpenAIQualityLLM("test", 0.005)
                data = ({"message": {"content": "MALFORMED"}, "prompt_eval_count": 4, "eval_count": 6}
                        if backend == "ollama" else {"choices": [{"message": {"content": "MALFORMED"}}], "usage": {"total_tokens": 10}})
                response = httpx.Response(200, json=data, request=httpx.Request("POST", "http://test"))
                with patch("httpx.post", return_value=response) as post:
                    content, usage = await model.diagnose("진단", [], ["해석은 관측 근거가 아님"], 2, "value_mismatch")
                self.assertEqual(content, "MALFORMED")
                self.assertEqual(usage["tokens"], 10)
                payload = post.call_args.kwargs["json"]
                self.assertFalse(payload.get("stream", False))
                system, user = [m["content"] for m in payload["messages"]]
                self.assertIn("observations", system)
                self.assertIn("evidence_ids", system)
                parsed = json.loads(user)
                self.assertEqual(parsed["attempt"], 2)
                self.assertEqual(parsed["validation_feedback"], "value_mismatch")
                self.assertEqual(parsed["model_analysis"], ["해석은 관측 근거가 아님"])
                if backend == "ollama":
                    self.assertEqual(payload["format"], DiagnosisDraft.model_json_schema())
                else:
                    self.assertEqual(payload["response_format"], {"type": "json_object"})

    async def test_remote_transport_error_is_not_rewritten_as_valid_json(self):
        """연결 실패를 모델 구조 오류로 바꾸거나 임의 초안으로 덮어쓰지 않는다."""
        from agent.ollama_llm import OllamaQualityLLM
        with patch("httpx.post", side_effect=httpx.ConnectError("offline")):
            with self.assertRaises(httpx.ConnectError):
                await OllamaQualityLLM("test", 0).diagnose("진단", [], [], 1, None)
