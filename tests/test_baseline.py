"""Assert what the legacy validator does, including its known unsafe behavior.

These are characterization assertions, not the desired A-plan acceptance rules.
"""
import copy
from unittest.mock import patch

from tests.support import OfflineAsyncCase, collected_fixture, load_fixture, make_deps
from agent.graph import (
    _after_validate, _classify_incident_type, _extract_system_name,
    build_graph, finalize_node, validate_node,
)


class ValidatorBaselineTests(OfflineAsyncCase):
    async def test_boundary_requires_30_characters_and_literal_number(self):
        """현재 검증기의 30자 경계와 정확한 번호 문자열 조건을 고정한다."""
        for draft, accepted in [("1)" + "가" * 27, False),
                                ("1)" + "가" * 28, True),
                                ("가" * 40, False),
                                ("1." + "가" * 40, False)]:
            with self.subTest(length=len(draft), prefix=draft[:2]):
                result = await validate_node({"draft": draft, "events": []}, make_deps())
                self.assertEqual(result["validation_feedback"] is None, accepted)
                self.assertEqual(result["validation_attempts"], 1)
                self.assertEqual(_after_validate(result), "finalize" if accepted else "write")

    async def test_all_labeled_texts_pass_even_when_future_expectation_is_reject(self):
        """수동 거부 유형을 포함한 텍스트 24개가 모두 통과하는 한계를 재현한다."""
        fixture = load_fixture()
        self.assertEqual(sum(c["expected_a_plan"] == "accept" for c in fixture["cases"]), 6)
        self.assertEqual(sum(c["expected_a_plan"] == "reject" for c in fixture["cases"]), 18)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"], desired=case["expected_a_plan"]):
                result = await validate_node({"draft": case["legacy_draft"],
                                              "collected": collected_fixture(), "events": []}, make_deps())
                self.assertIsNone(result["validation_feedback"])
                self.assertEqual(result["events"][-1]["verdict"], "합격")

    async def test_three_invalid_drafts_are_forced_to_pass_then_finalized(self):
        """세 번째 실패가 강제 합격으로 바뀌고 같은 본문이 반환됨을 확인한다."""
        state = {"draft": "재시작", "events": []}
        for attempt in range(1, 4):
            result = await validate_node(state, make_deps())
            self.assertEqual(result["validation_attempts"], attempt)
            self.assertEqual(result["validation_feedback"] is None, attempt == 3)
            state.update(result)
        self.assertEqual(state["events"][-1]["verdict"], "합격(최대 시도 도달 — 통과 처리)")
        self.assertEqual((await finalize_node(state, make_deps()))["final"], "재시작")

    async def test_fixed_fixture_has_independent_labels_and_source_edge_cases(self):
        """핵심 관측값과 누락·unknown·타 요청 등 평가 데이터 경계를 점검한다."""
        fixture = load_fixture()
        evidence = {e["id"]: e for e in fixture["evidence"]}
        cases = {c["id"]: c for c in fixture["cases"]}
        self.assertEqual(len(evidence), len(fixture["evidence"]))
        self.assertEqual(len(cases), len(fixture["cases"]))
        self.assertEqual(evidence["mon-payments"]["data"]["cpu_percent"], 91.0)
        self.assertEqual(evidence["mon-payments"]["data"]["memory_percent"], 55.0)
        self.assertEqual(evidence["mon-web"]["data"]["cpu_percent"], 34.0)
        self.assertEqual(evidence["mon-unknown"]["data"]["status"], "unknown")
        self.assertNotIn("cpu_percent", evidence["mon-missing"]["data"])
        self.assertNotEqual(evidence["mon-other-request"]["request_id"], fixture["request_id"])
        self.assertTrue(evidence["runbook-missing"]["data"].startswith("# Runbook Not Found"))
        self.assertEqual(cases["wrong-value"]["candidate_draft"]["observations"][0]["value"], 99)
        self.assertEqual(cases["valid-float"]["candidate_draft"]["observations"][0]["value"], 91.0)
        self.assertIsInstance(cases["malformed-output"]["candidate_draft"], str)
        for case in cases.values():
            self.assertIn(case["expected_a_plan"], {"accept", "reject"})
            self.assertTrue(case["reason"])


class GraphBaselineTests(OfflineAsyncCase):
    async def test_incident_fixed_values_gate_replan_and_two_writes(self):
        """고정 장애 입력에서 수집·게이트·재계획·재시도·재작성을 함께 재현한다."""
        deps = make_deps(transient_once=True)
        result = await build_graph(deps).ainvoke(
            {"query": load_fixture()["query"], "history": [], "events": [], "cost_usd": 0.0})
        self.assertEqual(result["route"], "incident")
        self.assertEqual(result["gate_removed"], 1)
        self.assertEqual(result["replan_rounds"], 1)
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["validation_attempts"], 2)
        self.assertEqual(result["collected"], collected_fixture())
        self.assertIn("payments-service 상태=degraded, CPU 91.0%", result["final"])
        self.assertIn("web-01 상태=healthy, CPU 34.0%", result["final"])
        self.assertIn("CPU 급증 대응 절차", result["final"])
        self.assertEqual([e["verdict"] for e in result["events"] if e["type"] == "Validation"],
                         ["불합격", "합격"])
        self.assertEqual(sum(e["type"] == "DraftWritten" for e in result["events"]), 2)
        self.assertTrue(all(t["status"] == "done" for t in result["tasks"]))
        self.assertEqual(sum(name == "get_monitoring_status" for name, _ in deps.mcp.calls), 3)
        self.assertGreater(result["cost_usd"], 0)

    async def test_first_invalid_draft_is_streamed_before_validation(self):
        """첫 부적합 초안 토큰이 검증 이벤트보다 먼저 공개되는 순서를 확인한다."""
        stream = [item async for item in build_graph(make_deps()).astream(
            {"query": load_fixture()["query"], "events": []}, stream_mode=["updates", "custom"])]
        tokens = [(i, p) for i, (mode, p) in enumerate(stream) if mode == "custom"]
        self.assertEqual(tokens[0][1], {"type": "AnswerToken", "attempt": 1, "delta": "재시작하면 됩니다."})
        first_validation = next(i for i, (mode, p) in enumerate(stream)
                                if mode == "updates" and "validate" in p)
        self.assertLess(tokens[0][0], first_validation)
        self.assertEqual([p["attempt"] for _, p in tokens], [1, 2])

    async def test_repeated_short_outputs_are_forced_through_entire_graph(self):
        """실제 그래프에서도 짧은 초안 세 번 뒤 강제 종료되는 동작을 고정한다."""
        deps = make_deps()
        with patch.object(deps.quality_llm, "write", return_value=("실패", {"usd": 0})) as write:
            result = await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})
        self.assertEqual(write.await_count, 3)
        self.assertEqual(result["validation_attempts"], 3)
        self.assertEqual(result["final"], "실패")
        self.assertEqual(result["events"][-1], {"type": "Finalize", "pipeline": "incident-v2"})

    async def test_general_chat_preserves_history_without_mcp_or_validation(self):
        """일반 대화가 히스토리를 사용하며 장애 조사와 검증을 건너뜀을 확인한다."""
        deps = make_deps()
        result = await build_graph(deps).ainvoke({"query": "제 이름이 뭐였죠?", "events": [],
            "history": [{"role": "user", "content": "제 이름은 민수입니다"}]})
        self.assertEqual(result["route"], "chat")
        self.assertEqual(result["final"], "민수님이라고 말씀하셨어요. 무엇을 도와드릴까요?")
        self.assertEqual(deps.mcp.calls, [])
        self.assertNotIn("validation_attempts", result)

    async def test_resource_failure_propagates(self):
        """매뉴얼 조회의 영구 오류가 정상 응답으로 숨겨지지 않음을 확인한다."""
        deps = make_deps()
        with patch.object(deps.mcp, "read_resource", side_effect=ValueError("fixed resource failure")):
            with self.assertRaisesRegex(ValueError, "fixed resource failure"):
                await build_graph(deps).ainvoke({"query": load_fixture()["query"], "events": []})

    async def test_keyword_selection_and_unknown_target_fallback_are_current_behavior(self):
        """시스템 폴백과 매뉴얼 키워드 우선순위를 현재 특성으로 기록한다."""
        self.assertEqual(_extract_system_name("없는 시스템 장애"), "auth-service")
        self.assertEqual(_extract_system_name("web-01 뒤에 payments-service 장애"), "web-01")
        collected = copy.deepcopy(collected_fixture())
        collected[0]["data"]["alerts"].append("latency is high")
        self.assertEqual(_classify_incident_type(collected), "high-latency")
        self.assertEqual(_classify_incident_type([]), "db-down")
