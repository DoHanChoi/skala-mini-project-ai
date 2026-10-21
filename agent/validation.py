"""A-03 순수 진단 검증·표시 함수. 네트워크·모델 호출·상태 변경을 하지 않는다."""
import json
from typing import Any

from pydantic import ValidationError

from .diagnosis import (
    DiagnosisDraft, DiagnosisOutput, Observation, ValidationIssue, ValidationResult,
)
from .evidence import Evidence, monitoring_evidence, runbook_evidence

_NORMALIZED_FIELDS = (
    "available", "eligible_metrics", "issues", "system_name", "observed_at",
    "title", "content_sha256", "locator",
)
_METRIC_LABELS = {"cpu_percent": "CPU 사용률", "memory_percent": "메모리 사용률",
                  "status": "상태", "alerts": "알림"}
_SCOPE_NOTICE = "검사 범위: 관측값·시스템·단위·출처 연결. 가설·조치의 의미는 검증하지 않았습니다."
_PATH_FIELDS = {"observations", "hypotheses", "actions", "system_name", "metric", "value",
                "unit", "evidence_id", "text", "evidence_ids", "int", "float", "str"}


def _issue(errors: list[ValidationIssue], code: str, path: str, message: str) -> None:
    """초안 내용을 되풀이하지 않는 오류 항목을 누적한다."""
    errors.append(ValidationIssue(code=code, path=path, message=message))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    """중복 JSON 키를 마지막 값으로 조용히 덮어쓰지 않는다."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    """표준 JSON 숫자가 아닌 NaN·Infinity 상수를 거부한다."""
    raise ValueError("nonstandard JSON constant")


def _error_path(location: tuple) -> str:
    """알 수 없는 입력 키를 오류 응답에 복사하지 않고 스키마상의 위치만 남긴다."""
    return ".".join(str(part) if type(part) is int or part in _PATH_FIELDS else "unknown_field"
                    for part in location) or "draft"


def _parse_draft(payload: Any, errors: list[ValidationIssue]) -> DiagnosisDraft | None:
    """JSON 또는 사전·모델을 엄격히 파싱하고 오류의 위치만 외부에 남긴다."""
    try:
        if isinstance(payload, str):
            payload = json.loads(payload, object_pairs_hook=_unique_object,
                                 parse_constant=_reject_constant)
        elif isinstance(payload, DiagnosisDraft):
            payload = payload.model_dump()
        return DiagnosisDraft.model_validate(payload)
    except ValidationError as exc:
        for error in exc.errors(include_input=False, include_context=False, include_url=False):
            _issue(errors, "invalid_structure", _error_path(error["loc"]), "초안 구조·필수 항목·자료형이 올바르지 않습니다.")
    except (ValueError, TypeError, RecursionError):
        _issue(errors, "invalid_structure", "draft", "초안이 유효한 단일 JSON 객체가 아닙니다.")
    return None


def _load_evidence(records: Any, request_id: str, errors: list[ValidationIssue]) -> tuple[dict, set]:
    """요청의 근거를 복사·재검사하고 중복·훼손 근거는 비교와 대체 출력에서 제외한다."""
    indexed: dict[str, Evidence] = {}
    foreign_ids: set[str] = set()
    seen_ids: set[str] = set()
    if not isinstance(records, (list, tuple)):
        _issue(errors, "invalid_evidence", "evidence", "근거 목록 형식이 올바르지 않습니다.")
        return indexed, foreign_ids
    for index, entry in enumerate(records):
        path = f"evidence.{index}"
        raw_entry = entry
        try:
            raw_entry = entry.model_dump() if isinstance(entry, Evidence) else entry
            record = Evidence.model_validate(raw_entry)
        except (ValidationError, ValueError, TypeError):
            # A malformed candidate can still make an otherwise valid ID ambiguous.
            claimed_id = raw_entry.get("id") if isinstance(raw_entry, dict) else None
            if isinstance(claimed_id, str):
                if claimed_id in seen_ids:
                    _issue(errors, "duplicate_evidence_id", path, "같은 ID의 근거가 중복되어 원본을 선택할 수 없습니다.")
                seen_ids.add(claimed_id)
                indexed.pop(claimed_id, None)
            _issue(errors, "invalid_evidence", path, "근거 구조·식별 정보가 올바르지 않습니다.")
            continue
        if record.request_id != request_id:
            foreign_ids.add(record.id)
            continue
        if record.id in seen_ids:
            indexed.pop(record.id, None)
            _issue(errors, "duplicate_evidence_id", path, "같은 ID의 근거가 중복되어 원본을 선택할 수 없습니다.")
            continue
        seen_ids.add(record.id)
        try:
            common = dict(request_id=record.request_id, task_index=record.task_index,
                          task_id=record.task_id, target=record.target, server=record.server,
                          retrieved_at=record.retrieved_at, data=record.raw)
            normalized = (monitoring_evidence(**common) if record.source == "monitoring"
                          else runbook_evidence(**common, uri=record.locator))
            if any(getattr(record, field) != getattr(normalized, field) for field in _NORMALIZED_FIELDS):
                _issue(errors, "invalid_evidence", path, "근거 메타데이터가 보존된 원본과 일치하지 않습니다.")
                continue
            indexed[record.id] = normalized
        except (ValidationError, ValueError, TypeError):
            _issue(errors, "invalid_evidence", path, "근거 구조·식별 정보가 올바르지 않습니다.")
    return indexed, foreign_ids


def _lookup(identifier: str, path: str, records: dict[str, Evidence], foreign_ids: set[str],
            errors: list[ValidationIssue]) -> Evidence | None:
    """현재 요청에 속하며 활용 가능한 근거만 조회한다."""
    if identifier in foreign_ids:
        _issue(errors, "foreign_evidence", path, "다른 요청의 근거는 인용할 수 없습니다.")
        return None
    record = records.get(identifier)
    if record is None:
        _issue(errors, "missing_evidence", path, "참조한 근거가 현재 요청에 존재하지 않습니다.")
    elif not record.available:
        _issue(errors, "unavailable_evidence", path, "해당 원본은 관측·문서 근거로 사용할 수 없습니다.")
    else:
        return record
    return None


def _check_observation(observation: Observation, index: int, records: dict[str, Evidence],
                       foreign_ids: set[str], errors: list[ValidationIssue]) -> None:
    """항목의 출처·시스템·원본 값·단위를 한 묶음으로 비교한다."""
    path = f"observations.{index}"
    record = _lookup(observation.evidence_id, f"{path}.evidence_id", records, foreign_ids, errors)
    if record is None:
        return
    if record.source != "monitoring":
        _issue(errors, "wrong_source_type", f"{path}.evidence_id", "관측 사실은 원본 모니터링 근거를 참조해야 합니다.")
        return
    if observation.system_name != record.system_name:
        _issue(errors, "system_mismatch", f"{path}.system_name", "관측 시스템명이 원본과 일치하지 않습니다.")
    metric = observation.metric
    if metric not in record.eligible_metrics:
        _issue(errors, "ineligible_metric", f"{path}.metric", "해당 항목은 누락되었거나 유효한 원본 관측이 아닙니다.")
        return
    numeric = metric in ("cpu_percent", "memory_percent")
    expected_unit = "%" if numeric else None
    if observation.unit != expected_unit:
        _issue(errors, "unit_mismatch", f"{path}.unit", "원본 항목에 허용된 단위와 일치하지 않습니다.")
    value = observation.value
    if (numeric and type(value) not in (int, float)) or (not numeric and not isinstance(value, str)):
        _issue(errors, "invalid_value_type", f"{path}.value", "원본 항목에 맞는 값 자료형이 아닙니다.")
        return
    matches = value in record.raw[metric] if metric == "alerts" else value == record.raw[metric]
    if not matches:
        message = ("원본 alerts가 빈 배열이므로 인용할 알림은 0개입니다. "
                   "이 경로의 알림 관측 항목 전체를 삭제하고 다른 유효 관측은 유지하세요. "
                   "빈 문자열·없음·배열 문자열로 바꾸지 마세요."
                   if metric == "alerts" and not record.raw[metric]
                   else "원본 값 또는 알림 원문과 일치하지 않습니다.")
        _issue(errors, "value_mismatch", f"{path}.value", message)


def _evaluate(payload: Any, evidence: Any, request_id: str, attempt: int) -> tuple:
    """입력을 변경하지 않고 검사 결과와 렌더링에 필요한 검증된 사본을 만든다."""
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a nonblank string")
    if type(attempt) is not int or not 1 <= attempt <= 3:
        raise ValueError("attempt must be an integer from 1 to 3")
    errors: list[ValidationIssue] = []
    records, foreign_ids = _load_evidence(evidence, request_id, errors)
    draft = _parse_draft(payload, errors)
    if draft is not None:
        for index, observation in enumerate(draft.observations):
            _check_observation(observation, index, records, foreign_ids, errors)
        for section in ("hypotheses", "actions"):
            for index, statement in enumerate(getattr(draft, section)):
                for position, identifier in enumerate(statement.evidence_ids):
                    _lookup(identifier, f"{section}.{index}.evidence_ids.{position}", records, foreign_ids, errors)
    result = ValidationResult(request_id=request_id, attempt=attempt, passed=not errors, errors=errors)
    return result, draft, records


def validate_diagnosis(payload: Any, evidence: Any, *, request_id: str, attempt: int = 1) -> ValidationResult:
    """구조화된 관측과 출처 연결을 판정하며 시도 상한에서도 실패를 성공으로 바꾸지 않는다."""
    return _evaluate(payload, evidence, request_id, attempt)[0]


def _literal(value: Any) -> str:
    """문자열의 개행·제어문자를 이스케이프해 다른 표시 구역을 위조하지 못하게 한다."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _observation_line(record: Evidence, metric: str, value: Any) -> str:
    """초안의 자유 문장 대신 원본 값과 고정된 항목명으로 관측 한 줄을 만든다."""
    suffix = "%" if metric in ("cpu_percent", "memory_percent") else ""
    return (f"- {_literal(record.system_name)} {_METRIC_LABELS[metric]}: {_literal(value)}{suffix} "
            f"[근거 {_literal(record.id)}]")


def _confirmed_facts(records: dict[str, Evidence]) -> list[str]:
    """실패 초안 없이 현재 요청의 활용 가능한 원본 관측만 나열한다."""
    lines = []
    for record in sorted(records.values(), key=lambda item: item.task_index):
        if record.source != "monitoring" or not record.available:
            continue
        for metric in ("cpu_percent", "memory_percent", "status", "alerts"):
            if metric not in record.eligible_metrics:
                continue
            values = record.raw[metric] if metric == "alerts" else [record.raw[metric]]
            lines.extend(_observation_line(record, metric, value) for value in values)
    return lines


def render_diagnosis(payload: Any, evidence: Any, *, request_id: str, attempt: int = 1) -> DiagnosisOutput:
    """반드시 검증을 거쳐 관측·추정·조치 또는 실패와 확인된 사실만 렌더링한다."""
    result, draft, records = _evaluate(payload, evidence, request_id, attempt)
    if not result.passed:
        lines = [f"진단 검증 실패 (시도 {attempt}/3)", "확인된 원본 관측:"]
        lines.extend(_confirmed_facts(records) or ["확인 가능한 원본 관측이 없습니다."])
        lines.extend(["실패한 초안의 가설·조치는 표시하지 않습니다.", _SCOPE_NOTICE])
    else:
        lines = ["관측 사실 (값·시스템·단위·출처 연결 확인):"]
        for observation in draft.observations:
            record = records[observation.evidence_id]
            value = observation.value if observation.metric == "alerts" else record.raw[observation.metric]
            lines.append(_observation_line(record, observation.metric, value))
        for section, title in (("hypotheses", "원인 가설 (추정·의미 검증 제외):"),
                               ("actions", "권장 조치 (미실행·의미 검증 제외):")):
            lines.append(title)
            statements = getattr(draft, section)
            lines.extend(f"- {_literal(s.text)} [근거 {', '.join(_literal(i) for i in s.evidence_ids)}]"
                         for s in statements)
            if not statements:
                lines.append("- 제안 없음")
        lines.append(_SCOPE_NOTICE)
    return DiagnosisOutput(validation=result, reply="\n".join(lines))
