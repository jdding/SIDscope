#!/usr/bin/env python3
"""Versioned acceptance-scope policy: which acceptance conditions gate readiness.

The requirement ledger keeps original facts. This module loads and validates the
condition-scope mapping that decides which acceptance conditions participate in
certification, RC and delivery readiness predicates. Fail closed: a missing,
invalid or over-broad policy blocks; it never widens itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "sidscope.acceptance_scope.v1"
SCOPE_RELATIVE_PATH = "docs/reproducibility/sidscope_acceptance_scope.v1.json"
MIN_POLICY_REVISION = 2
VALID_CONDITION_TYPES = {"technical_chain", "independent_user_adoption"}
VALID_SCOPES = {"required", "excluded"}
# Only the named adoption condition may ever be excluded, and only an
# independent_user_adoption condition may carry scope=excluded. Technical
# conditions (F01/F02/F11 producer chains, admission, input safety, ...) are
# structurally required.
EXCLUDABLE_CONDITION_IDS = {"independent_user_actual_use"}
EXCLUDABLE_CONDITION_TYPES = {"independent_user_adoption"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AcceptanceScopeError(Exception):
    """Typed failure for missing, invalid or over-broad acceptance scope."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def load_acceptance_scope(root: Path, records: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Load, validate and return the scope policy. Raises AcceptanceScopeError."""
    path = root / SCOPE_RELATIVE_PATH
    if not path.is_file():
        raise AcceptanceScopeError("scope_policy_missing", str(SCOPE_RELATIVE_PATH))
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AcceptanceScopeError("scope_policy_invalid", f"unreadable policy: {error}") from error
    if not isinstance(policy, dict) or policy.get("schema") != SCHEMA:
        raise AcceptanceScopeError("scope_policy_invalid", f"schema must be {SCHEMA}")
    revision = policy.get("policy_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < MIN_POLICY_REVISION:
        raise AcceptanceScopeError("scope_policy_invalid", f"policy_revision must be an integer >= {MIN_POLICY_REVISION}")
    decision = policy.get("decision")
    if not isinstance(decision, dict):
        raise AcceptanceScopeError("scope_policy_invalid", "decision object required")
    if decision.get("decided_by") != "project_owner":
        raise AcceptanceScopeError("scope_policy_invalid", "decision.decided_by must be project_owner")
    if not isinstance(decision.get("date"), str) or not ISO_DATE.match(decision["date"]):
        raise AcceptanceScopeError("scope_policy_invalid", "decision.date must be YYYY-MM-DD")
    adr = decision.get("adr")
    if not isinstance(adr, str) or adr.startswith("/") or ".." in Path(adr).parts or not (root / adr).is_file():
        raise AcceptanceScopeError("scope_policy_invalid", f"decision.adr must point to a tracked document: {adr!r}")
    if not str(decision.get("statement", "")).strip():
        raise AcceptanceScopeError("scope_policy_invalid", "decision.statement required")

    known_ids = {row["id"] for row in records} if records is not None else None
    conditions = policy.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise AcceptanceScopeError("scope_policy_invalid", "conditions must be a non-empty list")
    seen: set[str] = set()
    for condition in conditions:
        if not isinstance(condition, dict):
            raise AcceptanceScopeError("scope_policy_invalid", "each condition must be an object")
        condition_id = condition.get("condition_id")
        requirement_ids = condition.get("requirement_ids")
        condition_type = condition.get("condition_type")
        scope = condition.get("scope")
        if not isinstance(condition_id, str) or not condition_id.strip():
            raise AcceptanceScopeError("scope_policy_invalid", "condition_id required")
        if condition_id in seen:
            raise AcceptanceScopeError("scope_policy_invalid", f"duplicate condition_id: {condition_id}")
        seen.add(condition_id)
        if not isinstance(requirement_ids, list) or not requirement_ids:
            raise AcceptanceScopeError("scope_policy_invalid", f"requirement_ids required for {condition_id}")
        if known_ids is not None:
            unknown = sorted(set(requirement_ids) - known_ids)
            if unknown:
                raise AcceptanceScopeError("scope_policy_unknown_requirement", f"{condition_id}: {unknown}")
        if condition_type not in VALID_CONDITION_TYPES:
            raise AcceptanceScopeError("scope_policy_invalid", f"unknown condition_type for {condition_id}: {condition_type!r}")
        if scope not in VALID_SCOPES:
            raise AcceptanceScopeError("scope_policy_invalid", f"unknown scope for {condition_id}: {scope!r}")
        if not str(condition.get("fact_status", "")).strip():
            raise AcceptanceScopeError("scope_policy_invalid", f"fact_status required for {condition_id}")
        if scope == "excluded":
            if condition_id not in EXCLUDABLE_CONDITION_IDS or condition_type not in EXCLUDABLE_CONDITION_TYPES:
                raise AcceptanceScopeError(
                    "scope_policy_forbidden_exclusion",
                    f"only {sorted(EXCLUDABLE_CONDITION_IDS)} may be excluded: {condition_id}",
                )
            if not str(condition.get("exclusion_reason", "")).strip():
                raise AcceptanceScopeError("scope_policy_invalid", f"exclusion_reason required for {condition_id}")
            if records is not None:
                by_id = {row["id"]: row for row in records}
                for requirement_id in requirement_ids:
                    row = by_id.get(requirement_id)
                    if row is None or row.get("user_accepted") == "not_applicable":
                        raise AcceptanceScopeError(
                            "scope_policy_forbidden_exclusion",
                            f"{condition_id}: {requirement_id} carries no user-acceptance fact and stays required",
                        )
    return policy


def resolve_requirement_scope(records: list[dict[str, str]], policy: dict[str, Any]) -> dict[str, Any]:
    """Map gating requirements to policy conditions and report unresolved gaps.

    A gating requirement (unclosed F finding, or unclosed approved-local N
    requirement) is resolved when every policy condition mapped to it is either
    excluded or required and covered by verified ledger requirements.
    """
    by_id = {row["id"]: row for row in records}
    conditions = policy["conditions"]
    conditions_for: dict[str, list[dict[str, Any]]] = {}
    for condition in conditions:
        for requirement_id in condition["requirement_ids"]:
            conditions_for.setdefault(requirement_id, []).append(condition)

    approved_local = {f"N{i:02d}" for i in range(1, 9)}
    gating = [
        row["id"]
        for row in records
        if row["state"] != "verified" and (row["id"].startswith("F") or row["id"] in approved_local)
    ]
    unmapped = [requirement_id for requirement_id in gating if not conditions_for.get(requirement_id)]
    if unmapped:
        raise AcceptanceScopeError("scope_requirement_unmapped", f"gating requirements without scope mapping: {unmapped}")

    def unresolved(requirement_id: str) -> bool:
        for condition in conditions_for[requirement_id]:
            if condition["scope"] == "excluded":
                continue
            covered_by = condition.get("covered_by_requirements", [])
            if not covered_by:
                return True
            if any(by_id[dependency]["state"] != "verified" for dependency in covered_by):
                return True
        return False

    unresolved_requirements = [requirement_id for requirement_id in gating if unresolved(requirement_id)]
    excluded_acceptance = [
        condition["condition_id"]
        for condition in conditions
        if condition["scope"] == "excluded" and condition["condition_type"] == "independent_user_adoption"
    ]
    return {
        "excluded_acceptance": excluded_acceptance,
        "unresolved_requirements": unresolved_requirements,
        "resolved_requirements": [requirement_id for requirement_id in gating if requirement_id not in unresolved_requirements],
    }


def acceptance_conditions(policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [condition for condition in policy["conditions"] if condition["condition_type"] == "independent_user_adoption"]


def required_pending_acceptance(policy: dict[str, Any], user_acceptance: str) -> list[str]:
    """Acceptance conditions that still gate readiness because they are required."""
    if user_acceptance == "accepted":
        return []
    return [
        condition["condition_id"]
        for condition in acceptance_conditions(policy)
        if condition["scope"] == "required"
    ]


def scope_digest(root: Path) -> str:
    import hashlib

    return hashlib.sha256((root / SCOPE_RELATIVE_PATH).read_bytes()).hexdigest()
