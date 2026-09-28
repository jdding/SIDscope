"""T02 preparation regressions; shell dispatch is not Linux gate evidence."""
from __future__ import annotations

import re
import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sidscope_source_manifest import tree_manifest_digest
from tools.sidscope_linux_matrix_cells import IMAGES, REQUIRED_STEPS
from tools import sidscope_linux_matrix_cell as collector

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "run_sidscope_linux_matrix_cell.sh"
DEPS = ROOT / "tools" / "sidscope_linux_deps_install.sh"
RUNBOOK = ROOT / "docs" / "SIDSCOPE_LINUX_MATRIX_RUNBOOK.md"


class LinuxMatrixReadinessTest(unittest.TestCase):
    def test_runner_uses_deps_dir_consistently(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        without_dir = text.replace("$DEPS_DIR", "").replace("${DEPS_DIR", "")
        bare = re.findall(r"\$\{?DEPS[\}\s/:]", without_dir)
        self.assertEqual(bare, [], f"bare $DEPS references remain: {bare}")
        self.assertIn('"${DEPS_DIR:-}"', text)
        self.assertIn("sidscope_linux_deps_install.sh", text)
        # The runner installs via the deps entry from the prepared wheelhouse;
        # it never pip-installs the mounted read-only source tree.
        self.assertNotIn("pip install", text)
        self.assertIn("command -v git", text)

    def test_deps_entry_installs_wheel_and_pytest_from_wheelhouse(self) -> None:
        text = DEPS.read_text(encoding="utf-8")
        self.assertIn("sidinspector-*.whl", text)
        self.assertIn("--no-index", text)
        self.assertIn("--find-links \"$DEPS_DIR\"", text.replace("${DEPS_DIR}", "$DEPS_DIR"))
        self.assertIn("pytest", text)
        self.assertIn("project wheel missing", text)
        self.assertNotIn("$WORK", text)
        bare = re.findall(r"\$\{?DEPS[\}\s/:]", text.replace("$DEPS_DIR", ""))
        self.assertEqual(bare, [])

    def test_runbook_covers_clone_identity_and_per_version_deps(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("git clone --no-hardlinks", text)
        self.assertIn("worktree", text.lower())
        self.assertIn("deps-$v", text)
        self.assertIn("pytest", text)
        self.assertIn("sidscope-matrix", text)
        self.assertIn("DEPS_DIR", text)
        self.assertIn("--network none", text)
        self.assertIn("pip download", text)
        self.assertIn("setuptools>=68", text)
        # The manifest is computed over the mounted clone, not the worktree.
        self.assertIn('tree_manifest_digest(Path("$PREP/clone"))', text)
        self.assertNotIn("--skip-sampled-regeneration", text)
        # Per-version images must carry git; cells never apt-get on the fly.
        self.assertIn("apt-get", text)

    def test_deps_shell_success_missing_ambiguous_and_pip_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deps = root / "deps with spaces"
            deps.mkdir()
            binary = root / "bin"
            binary.mkdir()
            python = binary / "python3"
            # Only the pip boundary is substituted; /bin/sh executes the real entry.
            python.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nexit "${PIP_EXIT:-0}"\n')
            python.chmod(0o755)
            env = dict(os.environ, PATH=f"{binary}:{os.environ['PATH']}")
            log = root / "install.log"
            def run():
                return subprocess.run(["sh", str(DEPS), str(deps), str(log)],
                                      env=env, capture_output=True, text=True)
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("project wheel missing", result.stderr)
            first = deps / "sidinspector-1-py3-none-any.whl"
            first.touch()
            self.assertEqual(run().returncode, 0)
            args = log.read_text().splitlines()
            self.assertEqual(args, ["-m", "pip", "install", "--no-index", "--find-links",
                                    str(deps), str(first), "pytest", "setuptools>=68", "wheel"])
            env["PIP_EXIT"] = "7"
            self.assertEqual(run().returncode, 7)
            (deps / "sidinspector-2-py3-none-any.whl").touch()
            self.assertIn("ambiguous project wheels", run().stderr)

    def test_tracked_manifest_matches_clone_and_worktree_not_ignored_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source"
            source.mkdir()
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=source, stderr=subprocess.DEVNULL)
            git("init", "-b", "codex/test")
            (source / ".gitignore").write_text("build/\n*.egg-info/\n.local_artifacts/\n")
            tracked = source / "source.txt"
            tracked.write_text("controlled bytes")
            git("add", ".")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
            clone = base / "clone"
            git("clone", "--no-hardlinks", str(source), str(clone))
            linked = base / "linked"
            git("worktree", "add", "--detach", str(linked))
            for name in ("build", "package.egg-info", ".local_artifacts"):
                (source / name).mkdir()
                (source / name / "noise").write_text("not candidate source")
            expected = tree_manifest_digest(clone)
            self.assertEqual(expected, tree_manifest_digest(source))
            self.assertEqual(expected, tree_manifest_digest(linked))
            tracked.write_text("modified live bytes")
            self.assertNotEqual(expected, tree_manifest_digest(source))
            tracked.unlink()
            with self.assertRaises(FileNotFoundError):
                tree_manifest_digest(source)

    def test_real_shell_runner_dispatch_and_failed_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            (source / "tools").mkdir(parents=True)
            for script in (RUNNER, DEPS):
                shutil.copyfile(script, source / "tools" / script.name)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=source, stderr=subprocess.DEVNULL).decode().strip()
            git("init", "-b", "codex/test")
            git("add", ".")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
            head = git("rev-parse", "HEAD")
            binary = root / "bin"
            binary.mkdir()
            python = binary / "python3"
            python.write_text('''#!/bin/sh
printf '%s|%s\\n' "$PYTEST_ADDOPTS" "$*" >> "$CALL_LOG"
case "$*" in
  *verify_sidscope_resource_package.py*) exit "${RESOURCE_EXIT:-0}" ;;
esac
exit 0
''')
            python.chmod(0o755)
            deps = root / "deps"
            deps.mkdir()
            (deps / "sidinspector-1-py3-none-any.whl").touch()
            calls = root / "calls"
            env = dict(os.environ, PATH=f"{binary}:{os.environ['PATH']}", DEPS_DIR=str(deps),
                       CALL_LOG=str(calls), PYTEST_ADDOPTS="-k nonexistent", RESOURCE_EXIT="7")
            out = root / "out"
            out.mkdir()
            argv = ["sh", str(source / "tools" / RUNNER.name), str(out), "3.9",
                    IMAGES["3.9"], "manifest", head, "snapshot"]
            result = subprocess.run(argv, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            steps = out / "steps-3.9"
            for name in REQUIRED_STEPS:
                self.assertTrue((steps / name / "output.log").is_file(), name)
                self.assertEqual((steps / name / "exitcode").read_text().strip(),
                                 "7" if name == "resource" else "0")
            self.assertNotIn("nonexistent", calls.read_text())
            self.assertIn("|-m pytest -q\n", calls.read_text())
            self.assertIn("sidscope_linux_matrix_cell.py", calls.read_text())
            # Reuse refuses to overwrite a step directory, including a symlink.
            self.assertNotEqual(subprocess.run(argv, env=env, capture_output=True).returncode, 0)
            other = root / "other"
            other.mkdir()
            (other / "steps-3.9").symlink_to(steps)
            argv[2] = str(other)
            self.assertNotEqual(subprocess.run(argv, env=env, capture_output=True).returncode, 0)

    def test_collector_records_actual_identity_and_rejects_expected_string_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in REQUIRED_STEPS:
                step = root / name
                step.mkdir()
                (step / "exitcode").write_text("0")
                (step / "output.log").write_text("2 passed in 0.01s\n")
            argv = ["collector", "--workspace", str(collector.ROOT), "--steps-dir", str(root),
                    "--output-dir", str(root), "--python-version", "3.9", "--image", IMAGES["3.9"],
                    "--expected-manifest", "manifest", "--head", "expected-head",
                    "--public-snapshot-digest", "expected-snapshot"]
            actual = {"head": "actual-head", "content_sha256": "actual-snapshot", "dirty": False}
            with patch.object(sys, "argv", argv), patch.object(collector, "source_snapshot", return_value=actual), \
                 patch.object(collector, "tree_manifest_digest", return_value="manifest"):
                self.assertEqual(collector.main(), 2)
            cell = json.loads((root / "cell-3.9.json").read_text())
            self.assertEqual(cell["source_check"]["head"], "actual-head")
            self.assertEqual(cell["source_check"]["public_snapshot_digest"], "actual-snapshot")
            self.assertEqual(cell["status"], "failed")


if __name__ == "__main__":
    unittest.main()
