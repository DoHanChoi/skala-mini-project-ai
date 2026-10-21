"""JSON으로 표현할 수 없는 원본 수치의 명시적인 전송 표현."""
from math import isfinite
from typing import Any


def json_safe(value: Any) -> Any:
    """NaN·Infinity만 태그 객체로 표현하고 내부 원본이나 정상 JSON 값은 바꾸지 않는다."""
    if isinstance(value, float) and not isfinite(value):
        return {"nonfinite_number": str(value)}
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value
