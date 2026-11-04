"""Bounded UTF-8 JSON encoding and loading for saved puzzle examples."""

import json
from math import isfinite
from pathlib import Path
from typing import Any

MAX_BYTES = 65536


def encode_json(data: Any, *, label: str = "Puzzle") -> bytes:
    """Return checked bytes so writing cannot change the validated size."""
    raw = (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError(f"{label} file must be at most {MAX_BYTES} bytes")
    return raw


def read_array(value: Any, name: str) -> list[Any]:
    """Require a JSON array before iterating or converting a saved field."""
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"Non-finite JSON number: {value}")
    return number


def load_json(path: Path, *, label: str = "Puzzle") -> Any:
    """Check byte/JSON boundaries; format-specific readers validate the schema."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError(f"{label} file must be at most 65536 bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                          parse_constant=_constant, parse_float=_finite_float)
    except RecursionError as exc:
        raise ValueError(f"{label} JSON is nested too deeply") from exc
