#!/usr/bin/env python3
"""Pure performance-gate policy: environment identity, comparability, timing validity.

The frozen baseline file is read-only. Observation status keeps its original
meaning; delivery disposition is computed separately and never relabels an
observation. Unknown or incomplete environment identity blocks instead of
being guessed into comparability.
"""
from __future__ import annotations

import math
import re
from typing import Any

# platform.platform() legacy format recorded by the 1.2 baseline campaign:
# {os_family}-{os_version}-{machine}-{processor_alias}-{bits}bit
LEGACY_PLATFORM = re.compile(
    r"^(?P<os_family>macOS|Windows|Linux)"
    r"-(?P<os_version>[0-9][^-]*)"
    r"-(?P<machine>[A-Za-z0-9_.]+)"
    r"-(?P<processor>[A-Za-z0-9_.]+)"
    r"-(?P<bitness>[0-9]+)bit$"
)
# Identity fields that must match for the narrow platform-version-only exception.
IDENTITY_FIELDS = ("os_family", "machine_architecture", "bitness", "platform_processor",
                   "python_version", "implementation", "processor")
ENVIRONMENT_KEYS = ("implementation", "platform", "processor", "python")
VERSION_PARTS = re.compile(r"^[0-9]+(\.[0-9]+)*$")


class PerformancePolicyError(Exception):
    """Typed rejection for environments or measurements that cannot be compared."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _parse_version(value: Any) -> str:
    text = str(value).strip()
    if not VERSION_PARTS.match(text):
        raise PerformancePolicyError("environment_unparseable_version", text)
    return text


def parse_legacy_platform(platform: Any) -> dict[str, Any]:
    """Strictly parse the recorded platform string; never guess."""
    if not isinstance(platform, str):
        raise PerformancePolicyError("environment_unparseable_platform", repr(platform))
    match = LEGACY_PLATFORM.match(platform.strip())
    if match is None:
        raise PerformancePolicyError("environment_unparseable_platform", platform)
    bitness = int(match.group("bitness"))
    if bitness not in (32, 64):
        raise PerformancePolicyError("environment_unparseable_platform", platform)
    return {
        "os_family": match.group("os_family"),
        "os_version": _parse_version(match.group("os_version")),
        "machine_architecture": match.group("machine"),
        "platform_processor": match.group("processor"),
        "bitness": bitness,
        "raw_platform": platform.strip(),
    }


def normalize_environment(environment: Any) -> dict[str, Any]:
    """Build the structured identity used for comparability decisions."""
    if not isinstance(environment, dict):
        raise PerformancePolicyError("environment_incomplete", "environment must be an object")
    missing = [key for key in ENVIRONMENT_KEYS if not str(environment.get(key, "")).strip()]
    if missing:
        raise PerformancePolicyError("environment_incomplete", ",".join(missing))
    identity = parse_legacy_platform(environment["platform"])
    identity["implementation"] = str(environment["implementation"]).strip()
    identity["python_version"] = _parse_version(environment["python"])
    identity["processor"] = str(environment["processor"]).strip()
    return identity


def environment_comparability(baseline_environment: Any, current_environment: Any) -> dict[str, Any]:
    """Decide whether two environments may share a delivery disposition.

    Returns a typed result. Only two outcomes permit a disposition:
    identical identity ("same") or the narrow platform-version-only variance.
    Every other difference or an unparseable/missing identity blocks.
    """
    changed = sorted(
        key for key in set(baseline_environment or {}) | set(current_environment or {})
        if (baseline_environment or {}).get(key) != (current_environment or {}).get(key)
    )
    detail: dict[str, Any] = {"changed_environment_fields": changed}
    try:
        baseline_identity = normalize_environment(baseline_environment)
    except PerformancePolicyError as error:
        detail["code"] = error.code
        detail["baseline_identity"] = None
        return {"comparable": False, **detail}
    try:
        current_identity = normalize_environment(current_environment)
    except PerformancePolicyError as error:
        detail["code"] = error.code
        detail["current_identity"] = None
        return {"comparable": False, **detail}
    detail["baseline_identity"] = baseline_identity
    detail["current_identity"] = current_identity
    if baseline_identity == current_identity:
        return {"comparable": True, "code": "same_environment", **detail}
    for field in IDENTITY_FIELDS:
        if baseline_identity[field] != current_identity[field]:
            return {"comparable": False, "code": f"environment_{field}_mismatch", **detail}
    # Only the OS version differs; that is the single narrow exception.
    return {"comparable": True, "code": "platform_version_only", **detail}


def explain_environment_extras(baseline_environment: Any, current_environment: Any) -> dict[str, Any]:
    """Record explanatory fields without letting them affect the frozen comparison.

    Fields the baseline never recorded are listed as current-only, never as matched.
    """
    baseline = baseline_environment if isinstance(baseline_environment, dict) else {}
    current = current_environment if isinstance(current_environment, dict) else {}
    known = set(ENVIRONMENT_KEYS)
    return {
        "baseline_only_fields": sorted(set(baseline) - known - set(current)),
        "current_only_fields": sorted(set(current) - known - set(baseline)),
    }


def _valid_median(value: Any) -> float:
    if isinstance(value, bool):
        raise PerformancePolicyError("measurement_boolean_median", repr(value))
    if not isinstance(value, (int, float)):
        raise PerformancePolicyError("measurement_nonnumeric_median", repr(value))
    number = float(value)
    if not math.isfinite(number):
        raise PerformancePolicyError("measurement_nonfinite_median", repr(value))
    if number <= 0:
        raise PerformancePolicyError("measurement_nonpositive_median", repr(value))
    return number


def measurement_validity(baseline_commands: Any, current_commands: Any) -> None:
    """Validate the workload set and every median before any ratio is formed."""
    if not isinstance(baseline_commands, dict) or not isinstance(current_commands, dict):
        raise PerformancePolicyError("workload_command_set_mismatch", "command maps required")
    if set(baseline_commands) != set(current_commands):
        raise PerformancePolicyError(
            "workload_command_set_mismatch",
            f"missing={sorted(set(baseline_commands) - set(current_commands))},"
            f" extra={sorted(set(current_commands) - set(baseline_commands))}",
        )
    for name, sample in sorted(current_commands.items()):
        if not isinstance(sample, dict) or "median_ms" not in sample:
            raise PerformancePolicyError("measurement_missing_median", name)
        _valid_median(sample["median_ms"])
        before = baseline_commands[name].get("median_ms")
        if before is None:
            raise PerformancePolicyError("measurement_missing_median", f"baseline:{name}")
        _valid_median(before)


def median_ratios(baseline_commands: dict, current_commands: dict) -> dict[str, float]:
    """Unrounded ratios; rounding is a display concern only."""
    return {
        name: float(current_commands[name]["median_ms"]) / float(baseline_commands[name]["median_ms"])
        for name in sorted(current_commands)
    }


def threshold_value(policy: dict) -> float:
    try:
        percent = policy["review_threshold_percent"]
    except (KeyError, TypeError) as error:
        raise PerformancePolicyError("policy_invalid", "review_threshold_percent required") from error
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not math.isfinite(percent) or percent <= 0:
        raise PerformancePolicyError("policy_invalid", repr(percent))
    return 1 + percent / 100
