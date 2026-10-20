"""A-02 근거 스냅샷의 원본 격리와 수집 수명주기를 확인한다."""
import asyncio
from copy import deepcopy
from unittest.mock import patch

from tests.support import OfflineAsyncCase, load_fixture, make_deps
from agent.evidence import Evidence, monitoring_evidence, runbook_evidence
from agent.graph import analysis_node, build_graph, research_node, replan_check_node
from pydantic import ValidationError

FIXED_TIME = "2026-10-20T09:00:00+09:00"


def fixture_entry(identifier):
    """A-01의 수동 평가 근거를 매번 새 객체로 가져온다."""
    return next(e for e in load_fixture()["evidence"] if e["id"] == identifier)


def monitoring_snapshot(data=None, target="payments-service", **overrides):
    """고정 요청 정보와 지정 원본으로 모니터링 정규화를 실행한다."""
    args = dict(request_id="request-a", task_index=0, task_id="task-0",
                target=target, server="ops", retrieved_at=FIXED_TIME,
                data=fixture_entry("mon-payments")["data"] if data is None else data)
    args.update(overrides)
    return monitoring_evidence(**args)


def runbook_snapshot(body, **overrides):
    """고정 요청과 실제 URI 형식을 사용해 매뉴얼 스냅샷을 만든다."""
    args = dict(request_id="request-a", task_index=2, task_id="gap-runbook",
                target="cpu-spike", server="found-ops",
                uri="runbook://incident-response/cpu-spike", retrieved_at=FIXED_TIME, data=body)
    args.update(overrides)
    return runbook_evidence(**args)


def research_state(request_id="request-a"):
    """병렬 조사 순서 시험용 두 태스크와 독립 요청 상태를 제공한다."""
    return {"request_id": request_id, "events": [], "tasks": [
        {"id": "task-0", "agent": "research", "kind": "monitoring",
         "target": "payments-service", "status": "pending"},
        {"id": "task-1", "agent": "research", "kind": "monitoring",
         "target": "web-01", "status": "pending"}]}


class EvidenceNormalizationTests(OfflineAsyncCase):
    async def test_monitoring_preserves_raw_types_source_and_timestamps(self):
        """출처·조회 시각과 실측 시각을 구분하고 원본 수치 자료형을 유지한다."""
        original = fixture_entry("mon-payments")["data"]
        original["extra"] = {"sample": [1, 2]}
        result = monitoring_snapshot(original)
        self.assertEqual(result.id, "ev:request-a:0")
        self.assertEqual(result.raw, original)
        self.assertIs(type(result.raw["cpu_percent"]), float)
        self.assertEqual((result.target, result.system_name), ("payments-service", "payments-service"))
        self.assertEqual((result.server, result.locator), ("ops", "get_monitoring_status"))
        self.assertEqual(result.retrieved_at, FIXED_TIME)
        self.assertEqual(result.observed_at, original["last_checked"])
        self.assertEqual(set(result.eligible_metrics), {"cpu_percent", "memory_percent", "status", "alerts"})
        self.assertTrue(result.available)
        self.assertEqual(result.issues, [])
        self.assertEqual(Evidence.model_validate(result.model_dump()), result)

    async def test_mutating_original_snapshot_or_dump_does_not_change_other_copies(self):
        """입력·보존 스냅샷·직렬화 사본 사이에 중첩 리스트가 공유되지 않는다."""
        original = fixture_entry("mon-payments")["data"]
        snapshot = monitoring_snapshot(original)
        saved = snapshot.model_dump()
        original["alerts"].append("new source alert")
        snapshot.raw["alerts"].append("changed snapshot")
        saved["raw"]["alerts"].append("changed dump")
        self.assertNotIn("new source alert", snapshot.raw["alerts"])
        self.assertNotIn("changed snapshot", original["alerts"])
        self.assertNotIn("changed snapshot", saved["raw"]["alerts"])
        self.assertNotIn("changed dump", snapshot.raw["alerts"])

    async def test_missing_cpu_stays_missing_while_other_fields_remain_eligible(self):
        """없는 CPU를 0으로 채우지 않고 사용 가능한 나머지 항목만 표시한다."""
        original = fixture_entry("mon-missing")["data"]
        result = monitoring_snapshot(original, target="log-service")
        self.assertNotIn("cpu_percent", result.raw)
        self.assertNotIn("cpu_percent", result.eligible_metrics)
        self.assertIn("memory_percent", result.eligible_metrics)
        self.assertIn("missing_cpu_percent", result.issues)
        self.assertTrue(result.available)

    async def test_unknown_zeros_and_system_mismatch_are_not_observations(self):
        """unknown의 0과 다른 시스템의 값은 정상 실측 근거가 될 수 없다."""
        unknown = monitoring_snapshot(fixture_entry("mon-unknown")["data"], target="billing-service")
        mismatch = monitoring_snapshot(target="web-01")
        for result, reason in [(unknown, "unknown_system"), (mismatch, "system_mismatch")]:
            with self.subTest(reason=reason):
                self.assertFalse(result.available)
                self.assertEqual(result.eligible_metrics, [])
                self.assertIn(reason, result.issues)
        self.assertEqual(unknown.raw["cpu_percent"], 0.0)
        self.assertEqual(mismatch.system_name, "payments-service")
        self.assertEqual(mismatch.target, "web-01")

    async def test_invalid_numeric_values_are_preserved_but_excluded(self):
        """bool·문자열·누락·범위 밖·비유한 수치를 임의 변환하지 않는다."""
        for value in (True, "91", None, -1, 101, float("nan"), float("inf")):
            with self.subTest(value=value):
                original = fixture_entry("mon-payments")["data"]
                original["cpu_percent"] = value
                result = monitoring_snapshot(original)
                self.assertNotIn("cpu_percent", result.eligible_metrics)
                self.assertIn("invalid_cpu_percent", result.issues)
                self.assertIs(type(result.raw["cpu_percent"]), type(value))
                self.assertIn("memory_percent", result.eligible_metrics)

    async def test_zero_and_hundred_are_valid_for_known_systems(self):
        """정상 시스템의 0과 100을 unknown의 가짜 0과 혼동하지 않는다."""
        for value in (0, 100.0):
            with self.subTest(value=value):
                original = fixture_entry("mon-payments")["data"]
                original["cpu_percent"] = value
                result = monitoring_snapshot(original)
                self.assertIn("cpu_percent", result.eligible_metrics)
                self.assertEqual(result.raw["cpu_percent"], value)

    async def test_invalid_status_alerts_and_body_are_flagged(self):
        """잘못된 응답 형식과 상태·알림을 정상 데이터로 보충하지 않는다."""
        original = fixture_entry("mon-payments")["data"]
        original.update(status="not-a-status", alerts=[123])
        result = monitoring_snapshot(original)
        self.assertFalse(result.available)
        self.assertIn("invalid_status", result.issues)
        self.assertIn("invalid_alerts", result.issues)
        malformed = monitoring_snapshot(data="bad monitoring response")
        self.assertFalse(malformed.available)
        self.assertEqual(malformed.raw, "bad monitoring response")
        self.assertEqual(malformed.issues, ["invalid_monitoring_body"])

    async def test_observed_time_is_not_fabricated_or_reinterpreted(self):
        """누락·잘못된 시각을 표시하고 기존 naive 실측 시각은 그대로 보존한다."""
        original = fixture_entry("mon-payments")["data"]
        del original["last_checked"]
        result = monitoring_snapshot(original)
        self.assertIsNone(result.observed_at)
        self.assertNotIn("last_checked", result.raw)
        self.assertIn("missing_observed_at", result.issues)
        for value, expected_issues in [("bad timestamp", ["invalid_observed_at"]),
                                       ("2026-10-20T09:00:00", [])]:
            original["last_checked"] = value
            result = monitoring_snapshot(original)
            self.assertEqual(result.observed_at, value)
            self.assertEqual(result.issues, expected_issues)

    async def test_runbook_hashes_exact_body_and_retains_real_locator(self):
        """본문을 정리하지 않고 표준 SHA-256과 실제 서버·URI를 보존한다."""
        # SHA-256 'abc' is a published known-answer digest; no shared hash helper.
        result = runbook_snapshot("abc")
        self.assertEqual(result.content_sha256, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertEqual(result.raw, "abc")
        self.assertEqual((result.server, result.locator), ("found-ops", "runbook://incident-response/cpu-spike"))
        self.assertTrue(result.available)
        self.assertIn("missing_title", result.issues)
        titled = runbook_snapshot(fixture_entry("runbook-cpu")["data"])
        self.assertEqual(titled.title, "Runbook: CPU 급증 대응 절차")
        self.assertEqual(titled.retrieved_at, FIXED_TIME)
        self.assertEqual(titled.issues, [])
        self.assertNotEqual(runbook_snapshot("abc\n").content_sha256, result.content_sha256)

    async def test_empty_missing_and_malformed_runbooks_are_not_usable(self):
        """매뉴얼 없음 안내와 빈·비문자 본문은 보존하되 활용 대상에서 제외한다."""
        for body, reason in [(fixture_entry("runbook-missing")["data"], "runbook_not_found"),
                             ("  \n", "empty_runbook"), ({"error": "not found"}, "invalid_runbook_body")]:
            with self.subTest(reason=reason):
                result = runbook_snapshot(body)
                self.assertFalse(result.available)
                self.assertIn(reason, result.issues)
                self.assertEqual(result.raw, body)
                self.assertEqual(result.eligible_metrics, [])

    async def test_model_rejects_analysis_identity_mismatch_and_naive_collection_time(self):
        """모델 해석의 원본 승격과 잘못된 식별·수집 메타데이터를 거부한다."""
        valid = monitoring_snapshot().model_dump()
        for changes in ({"source": "analysis"}, {"id": "ev:another-request:0"},
                        {"task_index": True}, {"request_id": ""},
                        {"retrieved_at": "2026-10-20T09:00:00"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    Evidence.model_validate({**valid, **changes})


class EvidenceCollectionTests(OfflineAsyncCase):
    async def test_parallel_completion_does_not_change_task_order_or_ids(self):
        """두 번째 조회가 먼저 끝나도 원본과 ID가 태스크 순서로 대응한다."""
        deps = make_deps()
        second_done = asyncio.Event()
        completed = []

        async def reversed_tools(name, arguments, server):
            """첫 조회만 기다리게 해 실제 완료 순서를 뒤집는다."""
            self.assertEqual((name, server), ("get_monitoring_status", "ops"))
            target = arguments["system_name"]
            if target == "payments-service":
                await second_done.wait()
                entry = "mon-payments"
            else:
                second_done.set()
                entry = "mon-web"
            completed.append(target)
            return fixture_entry(entry)["data"]

        state = research_state()
        with patch.object(deps.mcp, "call_tool", side_effect=reversed_tools):
            result = await research_node(state, deps)
        self.assertEqual(completed, ["web-01", "payments-service"])
        self.assertEqual([e["id"] for e in result["evidence"]], ["ev:request-a:0", "ev:request-a:1"])
        self.assertEqual([e["target"] for e in result["evidence"]], ["payments-service", "web-01"])
        for collected, evidence in zip(result["collected"], result["evidence"]):
            self.assertEqual(collected["data"], evidence["raw"])
        result["collected"][0]["data"]["cpu_percent"] = 99
        self.assertEqual(result["evidence"][0]["raw"]["cpu_percent"], 91.0)
        self.assertTrue(all(t["status"] == "pending" for t in state["tasks"]))
        repeated = await research_node(research_state(), make_deps())
        self.assertEqual([e["id"] for e in repeated["evidence"]], [e["id"] for e in result["evidence"]])

    async def test_replan_appends_runbook_without_changing_existing_evidence(self):
        """재계획은 기존 스냅샷을 유지하며 실제 발견 서버의 매뉴얼을 누적한다."""
        deps = make_deps()
        state = research_state()
        state.update(await research_node(state, deps))
        first = deepcopy(state["evidence"])
        state.update(await replan_check_node(state, deps))
        state.update(await research_node(state, deps))
        self.assertEqual(state["evidence"][:2], first)
        runbook = state["evidence"][2]
        self.assertEqual(runbook["id"], "ev:request-a:2")
        self.assertEqual(runbook["task_id"], "task-gap-runbook")
        self.assertEqual((runbook["server"], runbook["locator"]),
                         ("fixture-ops", "runbook://incident-response/cpu-spike"))
        self.assertEqual(runbook["raw"], fixture_entry("runbook-cpu")["data"])
        self.assertTrue(runbook["available"])

    async def test_analysis_stays_in_collected_without_becoming_original_evidence(self):
        """분석 문장이 생성돼도 원본 근거 목록과 기존 스냅샷은 바뀌지 않는다."""
        deps = make_deps()
        state = research_state()
        state.update(await research_node(state, deps))
        before = deepcopy(state["evidence"])
        state["tasks"].append({"id": "analysis", "agent": "analysis", "status": "pending"})
        state.update(await analysis_node(state, deps))
        self.assertEqual(state["collected"][-1]["source"], "analysis")
        self.assertEqual(state["evidence"], before)

    async def test_retries_and_rewrites_preserve_evidence_identity_and_raw_values(self):
        """재시도 중복 없이 수집하고 여러 작성 시도 동안 근거가 고정된다."""
        deps = make_deps(transient_once=True)
        values = [deepcopy(value) async for value in build_graph(deps).astream(
            {"query": load_fixture()["query"], "events": []}, stream_mode="values")]
        final = values[-1]
        self.assertEqual(final["retry_count"], 1)
        self.assertEqual(final["validation_attempts"], 2)
        self.assertEqual(len(final["evidence"]), 3)
        self.assertEqual(len({e["id"] for e in final["evidence"]}), 3)
        for state in values:
            if any(e["type"] == "DraftWritten" for e in state.get("events", [])):
                self.assertEqual(state["evidence"], final["evidence"])

    async def test_each_request_in_same_thread_has_its_own_ids(self):
        """대화방을 재사용해도 요청별 근거 ID는 공유되지 않는다."""
        graph = build_graph(make_deps())
        query = {"query": load_fixture()["query"], "thread_id": "same-thread", "events": []}
        first = await graph.ainvoke(query)
        second = await graph.ainvoke(query)
        self.assertNotEqual(first["request_id"], second["request_id"])
        self.assertFalse({e["id"] for e in first["evidence"]} & {e["id"] for e in second["evidence"]})
        self.assertEqual([e["raw"] for e in first["evidence"]], [e["raw"] for e in second["evidence"]])
        chat = await graph.ainvoke({"query": "안녕", "events": []})
        self.assertNotIn("evidence", chat)

    async def test_skipped_research_and_missing_runbook_preserve_original_contract(self):
        """조사 생략은 근거를 보존하고 매뉴얼 없음 안내를 원본 그대로 남긴다."""
        state = research_state()
        deps = make_deps()
        state.update(await research_node(state, deps))
        before = deepcopy(state["evidence"])
        state.update(await research_node(state, deps))
        self.assertEqual(state["evidence"], before)
        self.assertEqual(state["events"][-1]["type"], "ResearchSkipped")
        state["tasks"].append({"id": "missing-runbook", "agent": "research", "kind": "runbook",
                               "target": "not-a-type", "status": "pending"})
        state.update(await research_node(state, deps))
        result = state["evidence"][-1]
        self.assertFalse(result["available"])
        self.assertIn("runbook_not_found", result["issues"])
        self.assertEqual(state["collected"][-1]["data"], result["raw"])
        self.assertEqual(state["tasks"][-1]["status"], "done")
