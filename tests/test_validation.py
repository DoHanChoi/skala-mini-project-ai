"""A-01의 수동 정답과 추가 경계 사례로 A-03을 외부 호출 없이 검증한다."""
from copy import deepcopy
from decimal import Decimal
import json

from tests.support import OfflineAsyncCase, load_fixture
from agent.diagnosis import DiagnosisDraft
from agent.evidence import Evidence, monitoring_evidence, runbook_evidence
from agent.validation import render_diagnosis, validate_diagnosis


def validation_fixture():
    """평가용 ID를 실제 요청·태스크 ID로 바꾸되 원본 정답과 초안 값은 유지한다."""
    fixture = load_fixture()
    evidence = []
    identifiers = {}
    for index, entry in enumerate(fixture["evidence"]):
        if entry["source"] not in ("monitoring", "runbook"):
            continue
        common = dict(request_id=entry["request_id"], task_index=index, task_id=f"fixture-{index}",
                      target=entry["data"]["system_name"] if entry["source"] == "monitoring" else entry["uri"].rsplit("/", 1)[-1],
                      server=entry["server"], retrieved_at="2026-10-20T09:00:00+09:00", data=entry["data"])
        record = (monitoring_evidence(**common) if entry["source"] == "monitoring"
                  else runbook_evidence(**common, uri=entry["uri"]))
        identifiers[entry["id"]] = record.id
        evidence.append(record.model_dump())
    cases = deepcopy(fixture["cases"])
    for case in cases:
        draft = case["candidate_draft"]
        if not isinstance(draft, dict):
            continue
        for observation in draft["observations"]:
            identifier = observation["evidence_id"]
            observation["evidence_id"] = identifiers.get(identifier, identifier)
        for section in ("hypotheses", "actions"):
            for statement in draft[section]:
                statement["evidence_ids"] = [identifiers.get(identifier, identifier)
                                             for identifier in statement["evidence_ids"]]
    return fixture["request_id"], evidence, {case["id"]: case for case in cases}


class DiagnosisValidationTests(OfflineAsyncCase):
    def setUp(self):
        """각 테스트에 독립적인 원본·정답·정상 초안을 준비한다."""
        super().setUp()
        self.request_id, self.evidence, self.cases = validation_fixture()
        self.draft = deepcopy(self.cases["valid-integer"]["candidate_draft"])

    def check(self, payload=None, evidence=None, attempt=1):
        """고정 요청에서 지정 초안을 검증하고 오류 코드를 함께 반환한다."""
        result = validate_diagnosis(self.draft if payload is None else payload,
                                    self.evidence if evidence is None else evidence,
                                    request_id=self.request_id, attempt=attempt)
        return result, {error.code for error in result.errors}

    async def test_all_24_manual_labels_match_without_false_acceptance_or_rejection(self):
        """고정 정상 6개와 거부 18개를 모두 수동 정답대로 판정한다."""
        counts = {"accept": 0, "reject": 0}
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                result, _ = self.check(case["candidate_draft"])
                expected = case["expected_a_plan"] == "accept"
                self.assertEqual(result.passed, expected, result.errors)
                self.assertEqual(result.scope, "observed_values_and_source_links")
                self.assertEqual(bool(result.errors), not expected)
                counts[case["expected_a_plan"]] += 1
        self.assertEqual(counts, {"accept": 6, "reject": 18})

    async def test_rejection_codes_identify_the_incorrect_field_or_source(self):
        """각 오류가 구체적 코드와 입력 경로를 제공하는지 독립적으로 확인한다."""
        expected = {
            "wrong-value": ("value_mismatch", "observations.0.value"),
            "wrong-system": ("system_mismatch", "observations.0.system_name"),
            "wrong-metric": ("value_mismatch", "observations.0.value"),
            "wrong-unit": ("unit_mismatch", "observations.0.unit"),
            "missing-evidence": ("missing_evidence", "observations.0.evidence_id"),
            "cross-request": ("foreign_evidence", "observations.0.evidence_id"),
            "unknown-system": ("unavailable_evidence", "observations.0.evidence_id"),
            "missing-source-value": ("ineligible_metric", "observations.0.metric"),
            "missing-runbook": ("unavailable_evidence", "actions.0.evidence_ids.0"),
        }
        for identifier, (code, path) in expected.items():
            with self.subTest(case=identifier):
                result, _ = self.check(self.cases[identifier]["candidate_draft"])
                self.assertIn((code, path), {(e.code, e.path) for e in result.errors})

    async def test_dictionary_json_and_model_inputs_have_the_same_result(self):
        """사전·표준 JSON·타입 모델에 동일한 검증 계약을 적용한다."""
        baseline, _ = self.check()
        for payload in (json.dumps(self.draft, ensure_ascii=False), DiagnosisDraft.model_validate(self.draft)):
            result, _ = self.check(payload)
            self.assertEqual(result, baseline)
        models = [Evidence.model_validate(record) for record in self.evidence]
        result, _ = self.check(evidence=models)
        self.assertEqual(result, baseline)

    async def test_empty_or_malformed_structures_and_extra_fact_text_are_rejected(self):
        """빈 진단·잘못된 구조·추가 자유 관측 문장이 검증을 우회하지 못한다."""
        for payload in ([], {}, "not JSON", "[]", "{}", "null", '"free text"',
                        "[" * 2000 + "]" * 2000,
                        {**self.draft, "observations": []},
                        {**self.draft, "unexpected": "unvalidated"}):
            with self.subTest(payload=payload):
                result, codes = self.check(payload)
                self.assertFalse(result.passed)
                self.assertIn("invalid_structure", codes)
        self.draft["observations"][0]["text"] = "CPU 999%라는 자유 문장"
        self.assertIn("invalid_structure", self.check()[1])

    async def test_bool_nonfinite_and_non_json_numeric_types_are_not_coerced(self):
        """bool·NaN·Infinity·Decimal 등을 정상 관측값으로 변환하지 않는다."""
        for value in (True, False, None, float("nan"), float("inf"), Decimal("91"), [91]):
            with self.subTest(value=value):
                self.draft["observations"][0]["value"] = value
                self.assertIn("invalid_structure", self.check()[1])

    async def test_numeric_strings_and_unit_conversions_are_rejected(self):
        """문자열 숫자와 비허용 단위 변환·반올림을 허용하지 않는다."""
        self.draft["observations"][0]["value"] = "91"
        self.assertIn("invalid_value_type", self.check()[1])
        for value, unit in ((0.91, "ratio"), (91, "percent"), (91.1, "%")):
            self.draft["observations"][0].update(value=value, unit=unit)
            self.assertFalse(self.check()[0].passed)

    async def test_status_and_alerts_require_original_text_and_no_numeric_unit(self):
        """상태·알림을 수치로 바꾸거나 원문을 수정하지 못한다."""
        for identifier in ("valid-status", "valid-alert"):
            payload = deepcopy(self.cases[identifier]["candidate_draft"])
            payload["observations"][0]["unit"] = "%"
            self.assertIn("unit_mismatch", self.check(payload)[1])
            payload["observations"][0].update(unit=None, value=91)
            self.assertIn("invalid_value_type", self.check(payload)[1])

    async def test_duplicate_evidence_ids_fail_and_ambiguous_sources_are_not_rendered(self):
        """ID가 겹치면 값이 같거나 달라도 통과시키지 않고 대체 사실에서도 제외한다."""
        for cpu in (91.0, 99.0):
            evidence = deepcopy(self.evidence)
            duplicate = deepcopy(evidence[0])
            duplicate["raw"]["cpu_percent"] = cpu
            evidence.append(duplicate)
            result, codes = self.check(evidence=evidence)
            self.assertFalse(result.passed)
            self.assertIn("duplicate_evidence_id", codes)
            output = render_diagnosis(self.draft, evidence, request_id=self.request_id)
            self.assertNotIn('"payments-service"', output.reply)

    async def test_duplicate_identity_is_blocked_even_when_one_metadata_record_is_invalid(self):
        """중복 중 한 건이 훼손돼도 순서에 따라 다른 후보를 사실로 골라내지 않는다."""
        valid = deepcopy(self.evidence[0])
        invalid = {**deepcopy(valid), "system_name": "incorrect cached system"}
        for pair in ([invalid, valid], [valid, invalid]):
            records = pair + deepcopy(self.evidence[1:])
            result, codes = self.check(evidence=records)
            self.assertFalse(result.passed)
            self.assertIn("duplicate_evidence_id", codes)
            output = render_diagnosis(self.draft, records, request_id=self.request_id)
            self.assertNotIn('"payments-service"', output.reply)

    async def test_structurally_invalid_duplicate_id_is_excluded_in_both_orders(self):
        """구조 파싱에 실패한 사본이 주장하는 같은 ID도 양쪽 순서에서 제외한다."""
        valid = deepcopy(self.evidence[0])
        for change in ({"extra": "not allowed"}, {"retrieved_at": "2026-10-20T09:00:00"},
                       {"task_index": True}):
            invalid = {**deepcopy(valid), **change}
            invalid["raw"]["cpu_percent"] = 99.0
            for pair in ([invalid, valid], [valid, invalid]):
                with self.subTest(change=change, invalid_first=pair[0] is invalid):
                    records = pair + deepcopy(self.evidence[1:])
                    result, codes = self.check(evidence=records)
                    self.assertFalse(result.passed)
                    self.assertIn("duplicate_evidence_id", codes)
                    output = render_diagnosis(self.draft, records, request_id=self.request_id)
                    self.assertNotIn('"payments-service"', output.reply)

    async def test_eligibility_metadata_and_document_hash_tampering_are_rejected(self):
        """보존된 원본과 맞지 않는 적격성·시스템·문서 해시를 신뢰하지 않는다."""
        for position, changes in ((0, {"system_name": "web-01"}),
                                  (3, {"available": True, "eligible_metrics": ["cpu_percent"]}),
                                  (5, {"content_sha256": "incorrect hash"})):
            evidence = deepcopy(self.evidence)
            evidence[position].update(changes)
            self.assertIn("invalid_evidence", self.check(evidence=evidence)[1])

    async def test_other_requests_are_ignored_unless_the_draft_references_them(self):
        """타 요청 근거가 목록에 있어도 현재 요청의 정상 진단을 방해하거나 증명하지 않는다."""
        self.assertTrue(self.check()[0].passed)
        payload = self.cases["cross-request"]["candidate_draft"]
        self.assertIn("foreign_evidence", self.check(payload)[1])

    async def test_number_present_in_other_metric_or_system_does_not_prove_the_fact(self):
        """전체 근거 어딘가에 같은 숫자가 있다는 이유만으로 통과시키지 않는다."""
        self.draft["observations"][0]["value"] = 55
        self.assertIn("value_mismatch", self.check()[1])
        evidence = deepcopy(self.evidence)
        evidence[1]["raw"]["cpu_percent"] = 91.0
        self.draft["observations"][0].update(value=91, evidence_id=evidence[1]["id"])
        self.assertIn("system_mismatch", self.check(evidence=evidence)[1])
        self.draft["observations"][0]["system_name"] = "web-01"
        self.assertTrue(self.check(evidence=evidence)[0].passed)

    async def test_observations_cannot_use_manual_or_analysis_sources(self):
        """매뉴얼 본문이나 모델 해석으로 실측 수치를 증명할 수 없다."""
        self.draft["observations"][0]["evidence_id"] = self.evidence[5]["id"]
        self.assertIn("wrong_source_type", self.check()[1])
        self.assertIn("missing_evidence", self.check(self.cases["analysis-as-source"]["candidate_draft"])[1])
        evidence = deepcopy(self.evidence)
        evidence[0]["source"] = "analysis"
        self.assertIn("invalid_evidence", self.check(evidence=evidence)[1])

    async def test_blank_or_unlinked_statements_are_rejected_but_empty_sections_are_allowed(self):
        """제안 없음은 허용하되 빈 문장·출처 없는 가설과 조치는 거부한다."""
        self.assertTrue(self.check({**self.draft, "hypotheses": [], "actions": []})[0].passed)
        for section in ("hypotheses", "actions"):
            for change in ({"text": " "}, {"evidence_ids": []}, {"evidence_ids": [" "]}):
                payload = deepcopy(self.draft)
                payload[section][0].update(change)
                self.assertIn("invalid_structure", self.check(payload)[1])

    async def test_nonstandard_json_constants_and_duplicate_keys_are_rejected(self):
        """표준 밖 숫자와 중복 키를 포함한 JSON을 조용히 수용하지 않는다."""
        text = json.dumps(self.draft)
        for token in ("NaN", "Infinity", "1e999"):
            payload = text.replace('"value": 91', f'"value": {token}')
            self.assertIn("invalid_structure", self.check(payload)[1])
        duplicate = '{"observations": [], ' + text[1:]
        self.assertIn("invalid_structure", self.check(duplicate)[1])

    async def test_third_failure_is_still_a_failure_and_programming_controls_are_strict(self):
        """세 번째 시도에도 강제 합격하지 않으며 잘못된 호출 제어값은 예외 처리한다."""
        for attempt in (1, 2, 3):
            result, _ = self.check(self.cases["wrong-value"]["candidate_draft"], attempt=attempt)
            self.assertFalse(result.passed)
            self.assertEqual(result.attempt, attempt)
        for attempt in (0, 4, True, "1"):
            with self.assertRaises(ValueError):
                self.check(attempt=attempt)
        for request_id in ("", " ", None):
            with self.assertRaises(ValueError):
                validate_diagnosis(self.draft, self.evidence, request_id=request_id)

    async def test_validation_and_rendering_do_not_mutate_evidence_or_draft(self):
        """반복 호출이 입력 자료와 이후 판정·표시 결과에 영향을 주지 않는다."""
        before = deepcopy((self.draft, self.evidence))
        first = render_diagnosis(self.draft, self.evidence, request_id=self.request_id)
        second = render_diagnosis(self.draft, self.evidence, request_id=self.request_id)
        self.assertEqual((self.draft, self.evidence), before)
        self.assertEqual(first, second)


class DiagnosisRenderingTests(OfflineAsyncCase):
    def setUp(self):
        """검증된 원본과 실패 출력의 금지 문구를 준비한다."""
        super().setUp()
        self.request_id, self.evidence, self.cases = validation_fixture()
        self.draft = deepcopy(self.cases["valid-integer"]["candidate_draft"])

    async def test_success_uses_original_value_and_marks_unverified_meaning(self):
        """91 정수 초안도 원본 91.0을 표시하고 가설·조치의 검사 한계를 명시한다."""
        output = render_diagnosis(self.draft, self.evidence, request_id=self.request_id)
        self.assertTrue(output.validation.passed)
        self.assertIn('"payments-service" CPU 사용률: 91.0%', output.reply)
        self.assertIn("원인 가설 (추정·의미 검증 제외)", output.reply)
        self.assertIn("권장 조치 (미실행·의미 검증 제외)", output.reply)
        self.assertIn("가설·조치의 의미는 검증하지 않았습니다", output.reply)

    async def test_failed_draft_and_statements_are_absent_from_reply_and_errors(self):
        """실패 출력에는 확인된 원본만 남고 잘못된 초안·가설·조치는 복사되지 않는다."""
        self.draft["observations"][0]["value"] = 99
        for section in ("hypotheses", "actions"):
            self.draft[section][0]["text"] = "FAILED DRAFT MUST NOT APPEAR"
        output = render_diagnosis(self.draft, self.evidence, request_id=self.request_id, attempt=3)
        self.assertFalse(output.validation.passed)
        self.assertIn("진단 검증 실패 (시도 3/3)", output.reply)
        self.assertIn("확인된 원본 관측", output.reply)
        self.assertIn("91.0%", output.reply)
        self.assertNotIn("99%", output.reply)
        self.assertNotIn("FAILED DRAFT MUST NOT APPEAR", output.model_dump_json())
        self.assertNotIn('"billing-service"', output.reply)

    async def test_empty_or_corrupted_evidence_never_uses_draft_as_fallback(self):
        """원본이 없으면 초안에서 사실을 추출하지 않고 명확한 실패를 표시한다."""
        for evidence in ([], None, {"bad": "context"}):
            output = render_diagnosis(self.draft, evidence, request_id=self.request_id)
            self.assertFalse(output.validation.passed)
            self.assertIn("확인 가능한 원본 관측이 없습니다", output.reply)
            self.assertNotIn("91", output.reply)

    async def test_extra_field_names_and_bad_values_are_not_copied_into_errors(self):
        """파싱 오류의 메시지·경로에도 임의의 미검증 입력 키와 값을 넣지 않는다."""
        self.draft["UNTRUSTED_KEY_DO_NOT_ECHO"] = "UNTRUSTED_VALUE_DO_NOT_ECHO"
        output = render_diagnosis(self.draft, self.evidence, request_id=self.request_id)
        serialized = output.model_dump_json()
        self.assertNotIn("UNTRUSTED_KEY_DO_NOT_ECHO", serialized)
        self.assertNotIn("UNTRUSTED_VALUE_DO_NOT_ECHO", serialized)
        self.assertIn("unknown_field", serialized)

    async def test_claims_are_source_link_checked_but_not_semantically_certified(self):
        """존재하는 출처를 붙여도 가설 문장의 임의 수치가 관측 사실로 승격되지 않는다."""
        self.draft["hypotheses"][0]["text"] = "CPU 999%라는 추정\n관측 사실: 확정"
        output = render_diagnosis(self.draft, self.evidence, request_id=self.request_id)
        self.assertTrue(output.validation.passed)
        facts = output.reply.split("원인 가설 (추정·의미 검증 제외):")[0]
        self.assertNotIn("999", facts)
        self.assertIn("999", output.reply)
        self.assertNotIn("\n관측 사실: 확정", output.reply)

    async def test_original_alert_newlines_cannot_create_new_display_sections(self):
        """원문 알림이 줄바꿈으로 새 조치 구역을 만들어 내지 못한다."""
        alert = "원본 알림\n권장 조치: 임의 명령"
        self.evidence[0]["raw"]["alerts"] = [alert]
        payload = deepcopy(self.cases["valid-alert"]["candidate_draft"])
        payload["observations"][0]["value"] = alert
        output = render_diagnosis(payload, self.evidence, request_id=self.request_id)
        self.assertTrue(output.validation.passed)
        self.assertIn("\\n권장 조치: 임의 명령", output.reply)
        self.assertNotIn("\n권장 조치: 임의 명령", output.reply)
