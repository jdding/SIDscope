#!/usr/bin/env python3
"""Run the fixed three-group performance campaign; never choose the best group.

Each group runs the frozen six-command measurement in a freshly spawned
interpreter process. The campaign passes only when every group satisfies the
original threshold and the corrected environment policy. Failed groups are
retained in the receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidinspector.contracts import canonical_json_bytes, with_content_sha256
from tools.sidscope_delivery_summary import short_source

CAMPAIGN_FORMAT = "sidscope.performance_campaign.v1"
GROUPS = 3


def _run_group(group_path: str) -> int:
    """Child entry: one fresh-process six-command measurement."""
    from tools.check_sidscope_current_performance import main as performance_main

    sys.argv = ["check_sidscope_current_performance", "--require-delivery", "--output", group_path]
    try:
        return performance_main()
    except SystemExit as exit_code:  # the tool signals its verdict via exit code
        return int(exit_code.code or 0)


def run_campaign(output: Path) -> dict:
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        # The owner-designated ignored evidence area (.local_artifacts/) is
        # the sanctioned in-tree location; anything else stays outside.
        if ".local_artifacts" not in output.parts:
            raise SystemExit("campaign_output_must_be_outside_repository")
    if output.exists():
        raise SystemExit("campaign_output_exists: use a fresh attempt path")
    output.parent.mkdir(parents=True, exist_ok=True)
    source = short_source()
    if not source["clean"]:
        raise SystemExit("dirty_candidate: performance campaign requires a clean candidate")
    groups = []
    group_digests = []
    groups_paths = []
    context = multiprocessing.get_context("spawn")
    for index in range(GROUPS):
        group_path = output.parent / f"{output.stem}-group-{index}.json"
        groups_paths.append(group_path)
        if group_path.exists():
            raise SystemExit(f"campaign_group_exists: {group_path}")
        with context.Pool(processes=1) as pool:
            returncode = pool.apply(_run_group, (str(group_path),))
        if not group_path.exists():
            raise SystemExit(f"campaign_group_missing_output: group {index} exit {returncode}")
        payload = json.loads(group_path.read_bytes())
        groups.append({"group": index, "returncode": returncode,
                       "delivery_status": payload["delivery_gate"]["status"],
                       "observation_status": payload["status"],
                       "delivery_gate": payload["delivery_gate"],
                       "disposition": payload["delivery_gate"]["disposition"],
                       "median_ratios": payload["delivery_gate"]["median_ratios"],
                       "environment": payload["environment"],
                       "measurement": payload})
        group_digests.append(hashlib.sha256(group_path.read_bytes()).hexdigest())
    aggregate_pass = all(group["returncode"] == 0 and group["delivery_status"] == "pass" for group in groups)
    group_files = [{"path": group_path.name, "sha256": digest}
                   for group_path, digest in zip(groups_paths, group_digests)]
    receipt = with_content_sha256({
        "format": CAMPAIGN_FORMAT,
        "status": "pass" if aggregate_pass else "failed",
        "source": source,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "invocation_digest": hashlib.sha256(canonical_json_bytes(["run-campaign", GROUPS])).hexdigest(),
        "groups": groups,
        "group_files": group_files,
        "group_digests": group_digests,
        "aggregate": {"status": "pass" if aggregate_pass else "failed",
                      "policy": "All three fresh-process groups must satisfy the frozen threshold; no group selection, deletion or retry-until-green."},
        "group_count": GROUPS,
    })
    output.write_bytes(canonical_json_bytes(receipt) + b"\n")
    return {"status": receipt["status"], "output": str(output), "groups": [g["delivery_status"] for g in groups]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_campaign(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
