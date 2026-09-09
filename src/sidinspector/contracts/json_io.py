"""Bounded untrusted JSON intake shared by public file consumers."""
from __future__ import annotations
import json
import math
from pathlib import Path

MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_JSON_DEPTH = 64


class JSONInputError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def _validate_byte_budget(max_bytes):
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 1):
        raise JSONInputError("invalid_json_budget", "max_bytes must be a positive integer or None")


def bounded_bytes(path: Path, *, max_bytes: int | None = MAX_JSON_BYTES) -> bytes:
    _validate_byte_budget(max_bytes)
    with Path(path).open("rb") as handle:
        payload = handle.read() if max_bytes is None else handle.read(max_bytes + 1)
    if max_bytes is not None and len(payload) > max_bytes:
        raise JSONInputError("json_size_exceeded", f"limit={max_bytes}")
    return payload


def loads_json(payload: bytes, *, max_bytes: int | None = MAX_JSON_BYTES):
    _validate_byte_budget(max_bytes)
    if max_bytes is not None and len(payload) > max_bytes:
        raise JSONInputError("json_size_exceeded", f"limit={max_bytes}")
    depth, quoted, escaped = 0, False, False
    for char in payload:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise JSONInputError("json_depth_exceeded", f"limit={MAX_JSON_DEPTH}")
        elif char in (93, 125):
            depth -= 1
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise JSONInputError("duplicate_json_key", "object keys must be unique")
            result[key] = value
        return result
    def reject_constant(value):
        raise JSONInputError("nonfinite_json_number", value)
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            reject_constant(value)
        return number
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=object_pairs, parse_constant=reject_constant, parse_float=finite_float)
    except JSONInputError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise JSONInputError("invalid_json_input", type(error).__name__) from error


def load_json(path: Path, *, max_bytes: int | None = MAX_JSON_BYTES):
    return loads_json(bounded_bytes(path, max_bytes=max_bytes), max_bytes=max_bytes)
