"""T02 round-4 regressions: the Linux execution preparation surface stays real.

Static consistency checks for the committed shell entry points and the
runbook. The real-shell dependency-entry validation (success and
missing-wheel directions) is executed by the operator chain and its
transcript is stored beside the attempt evidence; these tests keep the
documented surface from drifting back to unbound variables, source-tree
installs or a single shared dependency directory.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

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
        self.assertIn("--python-version", text)
        # The manifest is computed over the mounted clone, not the worktree.
        self.assertIn('tree_manifest_digest(Path("$PREP/clone"))', text)
        self.assertNotIn("--skip-sampled-regeneration", text)
        # Per-version images must carry git; cells never apt-get on the fly.
        self.assertIn("apt-get", text)


if __name__ == "__main__":
    unittest.main()
