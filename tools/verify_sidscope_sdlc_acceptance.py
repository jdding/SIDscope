#!/usr/bin/env python3
"""Requirement traceability and generated current-state consistency checks."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from sidinspector.version import PRODUCT_VERSION

LEDGER = ROOT / "docs/reproducibility/sidscope_sdlc_requirements.csv"
ROUTES = ROOT / "docs/reproducibility/generator_adapter_coverage.csv"
DOCUMENTS = ["README.md", "HANDOFF.md", "docs/COMPATIBILITY.md", "docs/VERSIONING.md", "docs/V1_2_TO_V2_ROADMAP.md", "docs/SIDSCOPE_1_7_STABILIZATION.md", "docs/SIDSCOPE_SDLC_HARDENING.md"]
# Hand-edited plan/RC/freeze documents are not generated blocks, but their
# current-state claims must agree with the acceptance scope policy.
SCOPE_SENTINEL_DOCUMENTS = ["docs/SIDSCOPE_NEXT_DEVELOPMENT_PLAN.md", "docs/SIDSCOPE_2_0_RC_PACKET.md", "docs/SIDSCOPE_2_0_CANDIDATE_FREEZE.md"]
SCOPE_SENTINEL = "independent_user_actual_use excluded from current gates"
BEGIN, END = "<!-- SIDSCOPE:CURRENT:BEGIN -->", "<!-- SIDSCOPE:CURRENT:END -->"


def rows():
    with LEDGER.open(newline="") as handle:
        return list(csv.DictReader(handle))


def acceptance_scope():
    from tools.sidscope_acceptance_scope import (
        SCOPE_RELATIVE_PATH,
        load_acceptance_scope,
        resolve_requirement_scope,
        scope_digest,
    )

    records = rows()
    policy = load_acceptance_scope(ROOT, records)
    resolution = resolve_requirement_scope(records, policy)
    return {
        "policy": policy,
        "policy_revision": policy["policy_revision"],
        "path": SCOPE_RELATIVE_PATH,
        "snapshot": scope_digest(ROOT),
        "excluded_acceptance": resolution["excluded_acceptance"],
        "pending_acceptance": required_pending_acceptance(records, policy),
        "unresolved_requirements": resolution["unresolved_requirements"],
        "adr": policy["decision"]["adr"],
        "decision_date": policy["decision"]["date"],
    }


def required_pending_acceptance(records, policy):
    from tools.sidscope_acceptance_scope import required_pending_acceptance as compute

    return compute(policy, user_acceptance_status(records))


def block():
    records = rows()
    pending = [row["id"] for row in records if row["id"].startswith("F") and row["state"] != "verified"]
    scope = acceptance_scope()
    accepted = user_acceptance_status(records) == "accepted"
    with ROUTES.open(newline="") as handle:
        routes = sorted(csv.DictReader(handle), key=lambda row: row["route_id"])
    history = "; ".join(row["route_id"]+"="+row["current_decision"] for row in routes)
    adoption_sentence = (
        "Independent user acceptance is recorded by traceable F09/N01 evidence. " if accepted else
        "Independent user actual use is excluded from current certification, RC and delivery gates by acceptance scope "
        f"policy revision {scope['policy_revision']}; it remains not verified and is not a current prerequisite. "
    )
    return "\n".join([BEGIN, f"Current package: `{PRODUCT_VERSION}`; GitHub main remains 1.1.x; 2.0 publication uses `codex/sidscope-v2` (ADR-0028).",
        "Current diagnostic admission and comparison require input-bound recomputation; declarations alone do not pass.",
        "Unclosed SDLC requirements: " + (", ".join(pending) if pending else "none") + ".",
        "Requirement snapshot: `"+hashlib.sha256(LEDGER.read_bytes()).hexdigest()+"`.",
        "Acceptance scope: `" + scope["path"] + "` revision " + str(scope["policy_revision"]) + " snapshot `"+scope["snapshot"]+"`.",
        "Acceptance scope decision: " + (", ".join(scope["excluded_acceptance"]) if scope["excluded_acceptance"] else "no excluded acceptance conditions") +
        " excluded from current gates (" + scope["decision_date"] + ", " + scope["adr"] + "); the adoption fact stays not_verified.",
        "Historical route decisions (not newly recomputed training): " + history + ".",
        "Historical route snapshot: `"+hashlib.sha256(ROUTES.read_bytes()).hexdigest()+"`.",
        adoption_sentence +
        "The project owner authorized the 2.0 RC-to-release sequence on 2026-10-08 (ADR-0028); automated checks do not grant publication authority. Main, origin and frozen TOIS mutations remain unauthorized.", END])


def render(document):
    value = block()
    if BEGIN in document:
        before, rest = document.split(BEGIN, 1)
        _, after = rest.split(END, 1)
        return before + value + after
    title, rest = document.split("\n", 1)
    return title + "\n\n" + value + "\n" + rest


def user_acceptance_status(records):
    """Check recorded state/traceability, never authenticate a human's use."""
    actual_use = [row for row in records if row["id"] in {"F09", "N01"}]
    assert len(actual_use) == 2
    states = {row["user_accepted"] for row in actual_use}
    assert len(states) == 1 and states <= {"pending_actual_use", "yes"}, "actual-use state mismatch"
    for row in actual_use:
        if row["user_accepted"] == "yes":
            assert row["state"] == "verified" and row["implemented"] == row["verified"] == "yes"
            evidence = Path(row.get("user_acceptance_evidence", ""))
            assert str(evidence) != "." and not evidence.is_absolute() and ".." not in evidence.parts, "actual-use evidence required"
            evidence_path = ROOT / evidence
            expected_sha256 = row.get("user_acceptance_sha256", "")
            assert (len(expected_sha256) == 64 and set(expected_sha256) <= set("0123456789abcdef")), "actual-use evidence hash required"
            assert evidence_path.is_file() and evidence_path.stat().st_size > 0, "actual-use evidence required"
            assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == expected_sha256, "actual-use evidence hash mismatch"
        else:
            assert row["state"] != "verified" and row["verified"] == "no", "pending actual use cannot be verified"
    return "accepted" if states == {"yes"} else "pending_actual_use"


def verify():
    records = rows()
    by_id = {row["id"]: row for row in records}
    assert len(by_id) == len(records) == 24
    required = {"persona", "journey", "accountable", "depends_on", "implementation", "tests", "evidence_command", "version_promise", "implemented", "verified", "user_accepted", "delivery_ready", "release_authorized", "disposition", "risk", "evidence_rule"}
    for row in records:
        assert required <= set(row), row["id"]
        assert all(row[key] for key in required), row["id"]
        assert row["accountable"] == "jdding", "do not invent external reviewers"
        assert row["release_authorized"] == "no"
        assert row["user_accepted"] in {"not_applicable", "pending_actual_use", "yes"}
        for column in ("verification", "implementation", "tests"):
            for path in row[column].split(";"):
                assert (ROOT / path).is_file(), (row["id"], column, path)
        if row["state"] == "verified":
            assert row["implemented"] == row["verified"] == "yes"
        for dependency in row["depends_on"].split(";"):
            assert dependency == "none" or dependency in by_id
    def visit(name, active):
        assert name not in active, "requirement dependency cycle"
        for dependency in by_id[name]["depends_on"].split(";"):
            if dependency != "none":
                visit(dependency, active | {name})
    for name in by_id:
        visit(name, set())
    user_acceptance = user_acceptance_status(records)
    scope = acceptance_scope()
    expected = block()
    for name in DOCUMENTS:
        assert expected in (ROOT / name).read_text(), "current status drift: " + name
    for name in SCOPE_SENTINEL_DOCUMENTS:
        assert SCOPE_SENTINEL in (ROOT / name).read_text(), "acceptance scope drift: " + name
    pending = [row["id"] for row in records if row["id"].startswith("F") and row["state"] != "verified"]
    return {"status": "pass", "requirement_count": len(records), "generated_documents": len(DOCUMENTS), "unclosed_requirements": pending, "user_acceptance": user_acceptance,
            "pending_acceptance": scope["pending_acceptance"], "excluded_acceptance": scope["excluded_acceptance"],
            "scope_unresolved_requirements": scope["unresolved_requirements"],
            "acceptance_scope": {"policy_revision": scope["policy_revision"], "path": scope["path"], "snapshot": scope["snapshot"], "adr": scope["adr"]},
            "release_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate only marked current-status blocks.")
    args = parser.parse_args()
    if args.write:
        for name in DOCUMENTS:
            path = ROOT / name
            path.write_text(render(path.read_text()))
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()
