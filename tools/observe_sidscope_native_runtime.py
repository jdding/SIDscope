#!/usr/bin/env python3
"""Explicitly authorized CPU RPG/PSID observation in a fresh scratch copy.

Not a submission loader. The trusted spec contains private runtime paths and must
remain outside release resources. Keys are used only in memory for deidentification;
checkpoints are read-only, no training is invoked, and original assets are not written.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import resource
import re
import runpy
import shlex
import shutil
import sys
import tempfile
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, doc):
    with Path(path).open("x") as handle:
        json.dump(doc, handle, sort_keys=True, allow_nan=False)
        handle.write("\n")


def replace_arg(args, name, value):
    if args.count(name) > 1:
        raise ValueError("duplicate runtime argument")
    if name in args:
        args[args.index(name) + 1] = str(value)
    else:
        args.extend([name, str(value)])


def episode_selection(method, episodes):
    """Keep the frozen prefix / balanced-five-bucket selection semantics."""
    if type(episodes) is not int or episodes <= 0:
        raise ValueError("episode_count_must_be_positive_integer")
    if method == "rpg":
        return {"--episodes": episodes}
    if method == "psid":
        if episodes % 5:
            raise ValueError("psid_episode_count_requires_five_equal_buckets")
        per_bucket = episodes // 5
        return {"--eval-per-bucket-limit": per_bucket,
            "--trained-trace-split-id": f"amazon_vg/rigor_original_test/{per_bucket}_per_bucket/s2024"}
    raise ValueError("unsupported native runtime")


def validate_episode_counts(captured, measurements, native, episodes):
    ids = [row["trace_id"] for row in native["episodes"]]
    if len(captured) != 1 or len(measurements) != episodes or len(ids) != episodes or len(set(ids)) != episodes:
        raise ValueError("native_observations_incomplete_or_duplicate")


def source_snapshot(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in {".py", ".yaml", ".yml"}
        and not {".git", "__pycache__", "ckpt", "logs", "tensorboard", ".venv"}.intersection(p.relative_to(root).parts)}


def rpg_observation_anchors(text):
    """Support frozen inline-row and newer named-row exporters, fail closed."""
    lines = text.splitlines()
    starts = [i + 1 for i, line in enumerate(lines)
        if line.strip() == 'batch = {key: value.to(device) for key, value in raw_batch.items()}']
    stops = [i + 1 for i, line in enumerate(lines)
        if line.strip() in {'episodes.append(', 'episodes.append(episode_row)'}]
    if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
        raise ValueError("unsupported exporter observation anchors")
    return starts[0], stops[0]


def finish_measurement(timing, calls, propagation):
    # Python revisits a multi-line call's first line after evaluating arguments.
    # Consume the start once, rather than counting that as another episode.
    if not timing:
        return None
    started, before = timing["start"], timing["calls"]
    timing.clear()
    return {"forward_calls": calls - before, "nfe": calls - before,
        "candidate_count": sum(p["candidate_count"] for p in propagation),
        "latency_ms": (time.perf_counter() - started) * 1000}


def capture_inputs(pipeline, native, secret, method):
    raw = pipeline.raw_dataset
    def identity(value):
        return hmac.new(secret, (method + ":" + value).encode(), hashlib.sha256).hexdigest()[:32]
    universe = native["target_universe"]["rows"]
    sid_key = "semantic_codes" if method == "rpg" else "ordered_model_vocabulary_tokens"
    mapping = [{"item_id": r["normalized_item_id"], "sid": r[sid_key]} for r in universe]
    by_item = {r["item_id"]: r["sid"] for r in mapping}
    splits, targets, selected, interactions = [], [], [], []
    for split, rows in pipeline.split_datasets.items():
        name = "valid" if split == "val" else split
        for index in range(len(rows)):
            row = rows[index]
            items = [int(raw.item2id[item]) - 1 for item in row["item_seq"]]
            if not items:
                raise ValueError("empty native split sequence")
            cluster = identity("user:" + str(row["user"]))
            ep_id = identity(name + ":" + str(index) + ":" + str(row["user"]))
            if name == "test" and index < len(native["episodes"]):
                ep = native["episodes"][index]
                ep_id = ep["trace_id"]
                if method == "rpg":
                    if ep["target_normalized_item_id"] != items[-1]:
                        raise ValueError("native target/split mismatch")
                    context = ep["context_normalized_item_ids"]
                    if items[:-1][-len(context):] != context:
                        raise ValueError("native history/split mismatch")
                else:
                    from genrec.generation_audit import pseudonymous_trace_id
                    if pseudonymous_trace_id(secret, str(row["episode_id"])) != ep_id:
                        raise ValueError("native episode/split mismatch")
                selected.append({"episode_id": ep_id, "split_row_index": index,
                    "target_normalized_item_id": items[-1], "cluster_id": cluster,
                    "slice": ep.get("gap_bucket", "overall")})
                targets.append({"episode_id": ep_id, "split": name,
                    "target_item_id": items[-1], "sid": by_item[items[-1]]})
            splits.append({"episode_id": ep_id, "split": name,
                "target_item_id": items[-1], "history_item_ids": items[:-1]})
            if name == "train":
                interactions.extend({"normalized_user_id": int(raw.user2id[row["user"]]) - 1,
                    "item_id": item, "split": "train"} for item in items)
    return {"mapping": mapping, "catalog": [{"item_id": r["item_id"]} for r in mapping],
        "splits": splits, "targets": targets, "interactions": interactions}, selected


def checkpoint_metadata(spec):
    """Extract recorded best-checkpoint progress, not the final training budget.

    Reads bytes/logs only: no torch, key, training, inference or asset writes.
    These existing records are declarations, not independent training verification.
    """
    digest = sha(spec["checkpoint"])
    if digest != spec["checkpoint_sha256"]:
        raise ValueError("checkpoint identity mismatch")
    if spec["method"] == "rpg":
        payload = Path(spec["training_manifest"]).read_bytes()
        record = json.loads(payload)
        if record["best_model_sha256"] != digest:
            raise ValueError("best checkpoint/manifest mismatch")
        epoch = record["best_epoch"]
        rows = [row for row in record["epoch_records"] if row["epoch"] == epoch]
        if len(rows) != 1:
            raise ValueError("best epoch record missing or ambiguous")
        step, final_step = rows[0]["global_step"], record["global_step"]
        final_epoch = record["completed_epoch"]
        kind = "rpg_training_manifest"
    elif spec["method"] == "psid":
        name = Path(spec["checkpoint"]).stem
        log = Path(spec["source"]) / "logs/DormantVideoGames/PSID" / (name + ".log")
        payload = log.read_bytes()
        content = payload.decode()
        saved = re.findall(r'\[Epoch (\d+)\] Saved model checkpoint to (.+)', content)
        best = re.findall(r'Best epoch: (\d+),', content)
        progress = re.findall(r'\[Epoch (\d+)\] Train Loss: [^;]+; completed steps: (\d+)/(\d+)', content)
        if not saved or len(best) != 1 or not progress:
            raise ValueError("checkpoint training progress unavailable")
        epoch = int(best[0])
        if int(saved[-1][0]) != epoch or Path(saved[-1][1].strip()).name != Path(spec["checkpoint"]).name:
            raise ValueError("best checkpoint/log mismatch")
        rows = [row for row in progress if int(row[0]) == epoch]
        if len(rows) != 1:
            raise ValueError("best epoch progress missing or ambiguous")
        step = int(rows[0][1])
        final_epoch, final_step = map(int, progress[-1][:2])
        kind = "psid_training_log"
    else:
        raise ValueError("unsupported native runtime")
    return {"format": "sidscope.native_checkpoint_metadata.v1", "method": spec["method"],
        "checkpoint_sha256": digest, "completed_epoch": epoch, "global_step": step,
        "training_run_completed_epochs": final_epoch, "training_run_completed_steps": final_step,
        "records_sha256": hashlib.sha256(payload).hexdigest(), "records_kind": kind,
        "verification_scope": "existing_training_records_not_recomputed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trusted-runtime-spec", type=Path, required=True)
    parser.add_argument("--metadata-only", action="store_true", help="Read existing checkpoint/log bindings without importing the model or using a key")
    parser.add_argument("--output", type=Path, help="New metadata-only output path")
    parser.add_argument("--episodes", type=int, default=5, help="Authorized observation count; PSID requires five equal buckets")
    parser.add_argument("--scratch-parent", type=Path, help="Existing authorized workspace for fresh scratch copies")
    args = parser.parse_args(argv)
    spec = json.loads(args.trusted_runtime_spec.read_text())
    if args.metadata_only:
        if args.output is None:
            parser.error("--metadata-only requires --output")
        write(args.output, checkpoint_metadata(spec))
        print(json.dumps({"status": "pass", "scope": "existing_training_records_not_recomputed"}))
        return
    if args.output is not None:
        parser.error("--output is only for --metadata-only")
    method = spec["method"]
    selection_args = episode_selection(method, args.episodes)
    if sha(spec["checkpoint"]) != spec["checkpoint_sha256"]:
        raise ValueError("checkpoint identity mismatch")
    source = Path(spec["source"]).resolve()
    for relative, expected in spec["source_files"].items():
        path = source / relative
        if source not in path.resolve().parents or sha(path) != expected:
            raise ValueError("source identity mismatch: " + relative)
    secret = Path(spec["identity_key_file"]).read_bytes()
    if len(secret) < 32:
        raise ValueError("identity key too short")
    root = Path(tempfile.mkdtemp(prefix="sidscope-v2-native-", dir=args.scratch_parent)).resolve()
    print(json.dumps({"status": "started", "output": str(root), "method": method}), flush=True)
    os.environ.update(CUDA_VISIBLE_DEVICES="", ACCELERATE_USE_CPU="true",
        OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
    sys.dont_write_bytecode = True
    shutil.copytree(source, root / "source", ignore=shutil.ignore_patterns(".git", "__pycache__", "ckpt", "logs", "tensorboard", "asset", "assets", ".venv"))
    shutil.copytree(spec["cache"], root / "cache", ignore=shutil.ignore_patterns("__pycache__"))
    observed_source = source_snapshot(root / "source")
    original_cache = {str(p.relative_to(Path(spec["cache"]))): sha(p) for p in sorted(Path(spec["cache"]).rglob("*")) if p.is_file()}
    os.chdir(root)
    sys.path.insert(0, str(root / "source"))
    import torch
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        raise RuntimeError("CPU isolation failed")
    from genrec import pipeline as upstream
    original_pipeline = upstream.Pipeline
    captured, measurements, calls = [], [], [0]
    class ObservedPipeline(original_pipeline):
        def __init__(self, *args, **kwargs):
            config = kwargs.setdefault("config_dict", {})
            config.update(cache_dir=str(root / "cache") + "/", log_dir=str(root / "logs") + "/",
                tensorboard_log_dir=str(root / "tensorboard") + "/", ckpt_dir=str(root / "ckpt") + "/")
            super().__init__(*args, **kwargs)
            captured.append(self)
            if method == "rpg":
                forward = self.model.forward
                def observed_forward(*args, **kwargs):
                    calls[0] += 1
                    return forward(*args, **kwargs)
                self.model.forward = observed_forward
            else:
                original_generate = self.model.generate
                def count_forward(module, inputs, output):
                    calls[0] += 1
                self.model.t5.register_forward_hook(count_forward)
                def generate(*args, **kwargs):
                    before = calls[0]
                    started = time.perf_counter()
                    result = original_generate(*args, **kwargs)
                    elapsed = (time.perf_counter() - started) * 1000
                    traces = self.model.last_trained_generation_trace
                    if len(traces) != 1:
                        raise ValueError("per-episode measurement requires batch size one")
                    measurements.append({"forward_calls": calls[0] - before,
                        "nfe": calls[0] - before, "latency_ms": elapsed,
                        "candidate_count": sum(len(a["final_beams"]) for a in traces[0]["attempts"])})
                    return result
                self.model.generate = generate
    upstream.Pipeline = ObservedPipeline
    if method == "rpg":
        tools_dir = root / "tools"
        tools_dir.mkdir()
        for name in ("export_rpg_trained_trace.py", "run_rpg_resumable_training.py", "verify_rpg_trained_trace_bundle.py"):
            shutil.copyfile(Path(spec["exporter_dir"]) / name, tools_dir / name)
        script = tools_dir / "export_rpg_trained_trace.py"
        start_line, stop_line = rpg_observation_anchors(script.read_text())
        timing = {}
        def local_trace(frame, event, arg):
            if event == "line" and frame.f_lineno == start_line:
                timing.update(start=time.perf_counter(), calls=calls[0])
            if event == "line" and frame.f_lineno == stop_line:
                measurement = finish_measurement(timing, calls[0], frame.f_locals["propagation"])
                if measurement is not None:
                    measurements.append(measurement)
            return local_trace
        def global_trace(frame, event, arg):
            return local_trace if frame.f_code.co_filename == str(script) and frame.f_code.co_name == "main" else None
        sys.settrace(global_trace)
        sys.argv = [str(script), "--rpg-source", str(root / "source"), "--cache-dir", str(root / "cache"),
            "--checkpoint", spec["checkpoint"], "--training-manifest", spec["training_manifest"],
            "--formal-training-runner", spec["formal_training_runner"], "--output", str(root / "native.json"),
            "--episodes", str(selection_args["--episodes"]), "--target-universe-mode", "complete"]
    else:
        script = root / "source/run_dormant_baseline.py"
        native_args = shlex.split(Path(spec["launch_command"]).read_text())[2:]
        for name, value in {"--cache-dir": root / "cache", "--result-dir": root / "results",
            "--run-id": "sidscope-v2-psid-cpu", "--eval-batch-size": 1,
            **selection_args, "--workers": 0,
            "--trained-trace-output": root / "native.json",
            "--trained-trace-expected-failure-output": root / "native-negative.json",
            "--trained-trace-command-file": root / "command.txt"}.items():
            replace_arg(native_args, name, value)
        if native_args[native_args.index("--phase") + 1] != "trace":
            raise ValueError("only inference trace execution is permitted")
        if native_args[native_args.index("--replay-checkpoint") + 1] != spec["checkpoint"]:
            raise ValueError("command checkpoint differs from pinned checkpoint")
        sys.argv = [str(script), *native_args]
        with (root / "command.txt").open("x") as handle:
            handle.write(shlex.join(sys.argv))
    started = time.perf_counter()
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.settrace(None)
        upstream.Pipeline = original_pipeline
    native = json.loads((root / "native.json").read_text())
    validate_episode_counts(captured, measurements, native, args.episodes)
    preflight, selected = capture_inputs(captured[0], native, secret, method)
    preflight["dataset"] = "AmazonReviews2014/Beauty" if method == "rpg" else "VideoGames/rigor_original_test/selected"
    write(root / "preflight.json", preflight)
    write(root / "selection.json", {"format": "sidscope.native_selection.v1",
        "native_sha256": sha(root / "native.json"), "checkpoint_sha256": spec["checkpoint_sha256"],
        "split_id": native["evidence"]["split_id"], "target_universe_sha256": native["target_universe"]["sha256"],
        "rows": [{k: v for k, v in r.items() if k != "split_row_index"} for r in selected]})
    for relative, digest in original_cache.items():
        if sha(Path(spec["cache"]) / relative) != digest:
            raise ValueError("original cache changed during observation")
    if source_snapshot(source) != observed_source:
        raise ValueError("original source changed during observation")
    if sha(spec["checkpoint"]) != spec["checkpoint_sha256"]:
        raise ValueError("original checkpoint changed during observation")
    write(root / "observations.json", {"method": method, "selection": selected,
        "measurements": measurements, "native_sha256": sha(root / "native.json"),
        "preflight_sha256": sha(root / "preflight.json"), "checkpoint_sha256": spec["checkpoint_sha256"],
        "source_files": observed_source, "cache_files": original_cache,
        "seed_kind": "inference", "seed": 2024,
        "requested_episodes": args.episodes, "selection_arguments": selection_args,
        "compute_scope": "batch_one_native_generation_including_observation",
        "nfe_definition": "RPG model.forward or PSID T5 conditional-generation forward calls; not FLOPs",
        "elapsed_seconds": time.perf_counter() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "environment": {"python": platform.python_version(), "torch": torch.__version__, "device": "cpu", "threads": 2},
        "native_execution": "cpu_frozen_checkpoint_no_training"})
    print(json.dumps({"status": "pass", "output": str(root), "episodes": len(selected),
        "mapping_rows": len(preflight["mapping"]), "split_rows": len(preflight["splits"])}), flush=True)


if __name__ == "__main__":
    main()
