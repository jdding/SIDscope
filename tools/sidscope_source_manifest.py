#!/usr/bin/env python3
"""Shared source-tree manifest: one rule for what counts as candidate source.

Used by the Linux matrix (host builder, in-container assembler) and available
to any verifier that must compare a mounted tree against the clean candidate.
Excludes everything that is not controlled source/docs: Git metadata, the
ignored private evidence area, caches, virtualenvs and OS noise. Including any
of those would let verification outputs change the verified input.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

EXCLUDED_DIR_NAMES = {".git", ".local_artifacts", "__pycache__", ".pytest_cache",
                      "venv", ".venv", "node_modules", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".DS_Store", ".egg-info")


def is_manifest_source(relative: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES for part in relative.parts[:-1]):
        return False
    if relative.parts[-1] == ".DS_Store":
        return False
    if relative.suffix in EXCLUDED_SUFFIXES:
        return False
    if relative.name.endswith(".egg-info"):
        return False
    return True


def tree_manifest_digest(root: Path) -> str:
    """Stable content manifest of the controlled source tree under root."""
    root = Path(root)
    digest = hashlib.sha256()
    if (root / ".git").exists():
        # Hash live tracked bytes, not HEAD bytes: edits must change the digest.
        # Git supplies the same file set in a worktree and a standalone clone.
        names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
        paths = [root / os.fsdecode(name) for name in names.split(b"\0") if name]
    else:
        paths = []
        for directory, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in EXCLUDED_DIR_NAMES
                       and not name.endswith(".egg-info")]
            paths.extend(Path(directory) / name for name in files)
    for path in sorted(paths):
        relative = path.relative_to(root)
        if not is_manifest_source(relative):
            continue
        digest.update(str(relative).encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()
