"""A-02 원본 근거 스냅샷. 답변 검증과 의미 판단은 후속 단계에서 수행한다."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from math import isfinite
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Metric = Literal["cpu_percent", "memory_percent", "status", "alerts"]


def evidence_id(request_id: str, task_index: int) -> str:
    """병렬 완료 순서와 무관하게 요청·전체 태스크 위치에서 ID를 결정한다."""
    return f"ev:{request_id}:{task_index}"


class Evidence(BaseModel):
    """원본과 출처를 보관하며 available은 답변 검증 성공을 의미하지 않는다."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    task_index: int = Field(ge=0)
    task_id: str = Field(min_length=1)
    source: Literal["monitoring", "runbook"]
    target: str = Field(min_length=1)
    server: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    retrieved_at: str
    observed_at: str | None = None
    system_name: str | None = None
    title: str | None = None
    content_sha256: str | None = None
    raw: Any
    available: bool
    eligible_metrics: list[Metric] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    @field_validator("retrieved_at")
    @classmethod
    def require_aware_timestamp(cls, value: str) -> str:
        """수집 시각은 타임존이 있는 ISO 8601 문자열로 저장한다."""
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        return value

    @model_validator(mode="after")
    def require_matching_id(self):
        """저장된 ID가 요청·태스크 위치와 모순되는 모델 입력을 거부한다."""
        if self.id != evidence_id(self.request_id, self.task_index):
            raise ValueError("evidence id does not match request and task index")
        return self


def monitoring_evidence(*, request_id: str, task_index: int, task_id: str,
                        target: str, server: str, retrieved_at: str, data: Any) -> Evidence:
    """원본 모니터링을 복사하고 인용 가능한 필드를 보수적으로 열거한다."""
    raw = deepcopy(data)
    issues = []
    eligible: list[Metric] = []
    system_name = None
    observed_at = None
    available = False
    if not isinstance(raw, dict):
        issues.append("invalid_monitoring_body")
    else:
        name = raw.get("system_name")
        system_name = name if isinstance(name, str) else None
        if system_name != target:
            issues.append("system_mismatch")
        status = raw.get("status")
        if status == "unknown":
            issues.append("unknown_system")
        elif status not in ("healthy", "degraded", "down"):
            issues.append("invalid_status")
        available = system_name == target and status in ("healthy", "degraded", "down")
        if available:
            eligible.append("status")
        for metric in ("cpu_percent", "memory_percent"):
            value = raw.get(metric)
            # bool is an int subclass; neither it nor NaN/Infinity is a measurement.
            valid = type(value) in (int, float) and 0 <= value <= 100 and isfinite(value)
            if not valid:
                issues.append(f"missing_{metric}" if metric not in raw else f"invalid_{metric}")
            elif available:
                eligible.append(metric)
        alerts = raw.get("alerts")
        if isinstance(alerts, list) and all(isinstance(a, str) for a in alerts):
            if available:
                eligible.append("alerts")
        else:
            issues.append("missing_alerts" if "alerts" not in raw else "invalid_alerts")
        checked = raw.get("last_checked")
        if isinstance(checked, str):
            observed_at = checked
            try:
                datetime.fromisoformat(checked)
            except ValueError:
                issues.append("invalid_observed_at")
        else:
            issues.append("missing_observed_at" if "last_checked" not in raw else "invalid_observed_at")
    return Evidence(
        id=evidence_id(request_id, task_index), request_id=request_id,
        task_index=task_index, task_id=task_id, source="monitoring", target=target,
        server=server, locator="get_monitoring_status", retrieved_at=retrieved_at,
        observed_at=observed_at, system_name=system_name, raw=raw,
        available=available, eligible_metrics=eligible, issues=issues)


def runbook_evidence(*, request_id: str, task_index: int, task_id: str,
                     target: str, server: str, uri: str, retrieved_at: str, data: Any) -> Evidence:
    """실제 요청 URI와 본문을 보존하고 없는 매뉴얼 안내는 사용 불가로 표시한다."""
    raw = deepcopy(data)
    title = None
    content_hash = None
    issues = []
    if not isinstance(raw, str):
        issues.append("invalid_runbook_body")
    else:
        content_hash = sha256(raw.encode("utf-8")).hexdigest()
        heading = re.search(r"^#{1,6}\s+(.+?)\s*$", raw, flags=re.MULTILINE)
        title = heading.group(1) if heading else None
        if not raw.strip():
            issues.append("empty_runbook")
        elif ((title is not None and title.casefold() == "runbook not found")
              or raw.lstrip().startswith("No runbook for incident type:")):
            issues.append("runbook_not_found")
        if title is None:
            issues.append("missing_title")
    unavailable = {"invalid_runbook_body", "empty_runbook", "runbook_not_found"}
    return Evidence(
        id=evidence_id(request_id, task_index), request_id=request_id,
        task_index=task_index, task_id=task_id, source="runbook", target=target,
        server=server, locator=uri, retrieved_at=retrieved_at,
        title=title, content_sha256=content_hash, raw=raw,
        available=not unavailable.intersection(issues), issues=issues)
