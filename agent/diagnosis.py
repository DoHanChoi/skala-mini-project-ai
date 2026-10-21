"""A-03 진단 입력·검증 결과 계약. A-04부터 v2 장애 그래프에서 사용한다."""
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .evidence import Metric


class DiagnosisModel(BaseModel):
    """알 수 없는 필드와 암묵적인 자료형 변환을 거부하는 공통 모델이다."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Observation(DiagnosisModel):
    """사용자 표시 문장을 담지 않고 원본과 비교할 항목만 명시한다."""

    system_name: str = Field(min_length=1)
    metric: Metric
    value: int | float | str
    unit: str | None
    evidence_id: str = Field(min_length=1)

    @field_validator("system_name", "evidence_id")
    @classmethod
    def reject_blank_identifier(cls, value: str) -> str:
        """빈 식별자를 거부하되 시스템명이나 ID를 임의로 수정하지 않는다."""
        if not value.strip():
            raise ValueError("blank identifier")
        return value

    @field_validator("value", mode="before")
    @classmethod
    def reject_nonfinite_number(cls, value: int | float | str) -> int | float | str:
        """JSON 스칼라 자료형과 유한 수치만 받고 bool·암묵적 수치 변환을 거부한다."""
        if type(value) not in (int, float, str):
            raise ValueError("unsupported observation value type")
        if type(value) is float and not isfinite(value):
            raise ValueError("nonfinite observation value")
        return value


class SourceLinkedText(DiagnosisModel):
    """가설·조치 문장과 출처 연결을 보관하며 의미의 참·거짓을 보증하지 않는다."""

    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """공백뿐인 가설이나 조치를 거부한다."""
        if not value.strip():
            raise ValueError("blank statement")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def require_distinct_nonblank_ids(cls, values: list[str]) -> list[str]:
        """문장마다 비어 있지 않은 출처 ID를 중복 없이 요구한다."""
        if any(not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError("blank or duplicate source id")
        return values


class DiagnosisDraft(DiagnosisModel):
    """최소 하나의 관측을 요구하고 가설·조치는 비어 있을 수 있도록 한다."""

    observations: list[Observation] = Field(min_length=1)
    hypotheses: list[SourceLinkedText]
    actions: list[SourceLinkedText]


class ValidationIssue(DiagnosisModel):
    """실패 코드·입력 경로·고정 안내문만 제공하며 실패 초안은 복사하지 않는다."""

    code: str
    path: str
    message: str


class ValidationResult(DiagnosisModel):
    """작성 시도와 관측·출처 연결 검사 범위를 명시한 순수 판정 결과다."""

    request_id: str
    attempt: int = Field(ge=1, le=3)
    passed: bool
    scope: Literal["observed_values_and_source_links"] = "observed_values_and_source_links"
    errors: list[ValidationIssue]


class DiagnosisOutput(DiagnosisModel):
    """검증 결과와 코드가 만든 표시 문자열을 함께 반환한다."""

    validation: ValidationResult
    reply: str
