#!/usr/bin/env python3
"""Actual wheel/sdist, wide-resolution and hash-locked offline install matrix.

No supported environment is inferred from requires-python or a CI YAML file.
All build/install artifacts and private execution logs stay outside the repo.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, cwd, log):
    started = time.monotonic()
    result = subprocess.run(list(map(str, command)), cwd=cwd, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log}")
    return {"returncode": 0, "seconds": round(time.monotonic()-started, 3), "output_sha256": sha(log)}


def verify(output: Path, interpreters: list[str]):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("distribution_output_must_be_outside_repository")
    output.mkdir(parents=True, exist_ok=False)
    source, consumer = output / "build-source", output / "consumer"
    source.mkdir(); consumer.mkdir()
    for name in ("pyproject.toml", "setup.py", "README.md", "LICENSE"):
        shutil.copyfile(ROOT / name, source / name)
    shutil.copytree(ROOT / "src", source / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", ".DS_Store"))
    source_hashes = {p.relative_to(source).as_posix(): sha(p) for p in sorted(source.rglob("*")) if p.is_file()}
    shutil.copyfile(ROOT / "tools/sidscope_public_consumer.py", consumer / "consumer.py")
    shutil.copyfile(ROOT / "docs/reproducibility/sidscope_public_consumer_contract.v1.json", consumer / "contract.json")
    for folder in ("canonical_pipeline_fixture", "dataset_identity_fixture", "native_trace_payload_fixtures", "evidence_system_fixture", "conformance_ecosystem_fixture"):
        shutil.copytree(ROOT / "examples" / folder, consumer / "inputs" / folder)
    commands = []
    def execute(args, name, cwd=consumer):
        row = run(args, cwd, output / (name + ".log")); commands.append({"step": name, **row}); return row
    build_env = output / "build-env"
    execute([interpreters[0], "-m", "venv", build_env], "build-venv")
    builder = build_env / "bin/python"
    execute([builder, "-m", "pip", "install", "--upgrade", "pip", "build", "setuptools>=68", "wheel"], "build-tools")
    execute([builder, "-m", "pip", "freeze"], "build-environment")
    dist = output / "dist"
    execute([builder, "-m", "build", "--no-isolation", "--outdir", dist, source], "wheel-and-sdist")
    wheel = next(dist.glob("*.whl")); sdist = next(dist.glob("*.tar.gz"))
    roundtrip = output / "sdist-wheel"
    execute([builder, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", roundtrip, sdist], "sdist-roundtrip-wheel")
    sdist_wheel = next(roundtrip.glob("*.whl"))
    results = []
    for index, interpreter in enumerate(interpreters):
        name = f"python-{index}"
        normal, locked = output / (name + "-normal"), output / (name + "-locked")
        execute([interpreter, "-m", "venv", normal], name+"-normal-venv")
        py = normal / "bin/python"
        execute([py, "-m", "pip", "install", "--upgrade", "pip"], name+"-installer")
        report_path = output / (name+"-resolution.json")
        execute([py, "-m", "pip", "install", "--report", report_path, wheel], name+"-wide-install")
        consumer_args = ["-I", "consumer.py", "--inputs", "inputs", "--contract", "contract.json", "--installed"]
        execute([py, *consumer_args], name+"-wheel-consumer")
        resolution = json.loads(report_path.read_text())["install"]
        lock = output / (name+"-requirements.lock")
        lock.write_text("\n".join(sorted(f"{row['metadata']['name']}=={row['metadata']['version']} --hash=sha256:{row['download_info']['archive_info']['hashes']['sha256']}" for row in resolution)) + "\n")
        wheelhouse = output / (name+"-wheelhouse")
        execute([py, "-m", "pip", "download", "--require-hashes", "--only-binary=:all:", "--find-links", dist, "--dest", wheelhouse, "-r", lock], name+"-lock-download")
        execute([interpreter, "-m", "venv", locked], name+"-locked-venv")
        replay = locked / "bin/python"
        execute([replay, "-m", "pip", "install", "--no-index", "--find-links", wheelhouse, "--require-hashes", "-r", lock], name+"-offline-replay")
        execute([replay, *consumer_args], name+"-locked-consumer")
        execute([replay, "-m", "pip", "install", "--no-deps", "--force-reinstall", sdist_wheel], name+"-sdist-install")
        execute([replay, *consumer_args], name+"-sdist-consumer")
        execute([replay, "-I", "-c", "import json,platform,importlib.metadata as m; print(json.dumps({'python':platform.python_version(),'os':platform.system(),'machine':platform.machine(),'dependencies':{d.metadata['Name']:d.version for d in m.distributions()}},sort_keys=True))"], name+"-environment")
        environment = json.loads((output / (name+"-environment.log")).read_text())
        results.append({"status": "pass", "environment": environment, "requirements_sha256": sha(lock), "resolution_sha256": sha(report_path), "wheelhouse": {p.name: sha(p) for p in sorted(wheelhouse.glob("*"))}, "consumers": ["wheel-wide", "wheel-locked-offline", "sdist-roundtrip"]})
        # These are disposable venvs created in this new output directory.
        # Retain logs, exact environment records, locks and wheelhouse for replay.
        shutil.rmtree(normal)
        shutil.rmtree(locked)
    result = {"format": "sidscope.distribution_install_matrix.v1", "status": "pass", "source_files": source_hashes, "artifacts": {role: {"filename": p.name, "sha256": sha(p)} for role, p in (("wheel", wheel), ("sdist", sdist), ("sdist_roundtrip_wheel", sdist_wheel))}, "environments": results, "commands": commands, "boundary": "Only recorded interpreter/OS cells were run. No Linux, Windows, GPU, optional training extras or public release is implied."}
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python", action="append", default=[])
    args = parser.parse_args()
    result = verify(args.output_dir, args.python or [sys.executable])
    print(json.dumps({"status": result["status"], "environments": [row["environment"] for row in result["environments"]]}, sort_keys=True))


if __name__ == "__main__":
    main()
