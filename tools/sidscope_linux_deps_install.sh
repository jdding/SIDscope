#!/bin/sh
# Offline per-cell dependency install: the project wheel plus its runtime
# dependencies and pytest, all resolved from the prepared per-version
# wheelhouse at DEPS_DIR. Never builds from the mounted read-only source.
# Usage: sidscope_linux_deps_install.sh <DEPS_DIR> <LOG>
set -u
DEPS_DIR="${1:?usage: deps_install.sh <DEPS_DIR> <LOG>}"
LOG="${2:?usage: deps_install.sh <DEPS_DIR> <LOG>}"

WHEEL=$(ls "$DEPS_DIR"/sidinspector-*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL" ]; then
  echo "project wheel missing: no sidinspector-*.whl in $DEPS_DIR (prepare the wheelhouse per docs/SIDSCOPE_LINUX_MATRIX_RUNBOOK.md)" >> "$LOG" 2>&1
  echo "project wheel missing: no sidinspector-*.whl in $DEPS_DIR" >&2
  exit 1
fi

python3 -m pip install --no-index --find-links "$DEPS_DIR" "$WHEEL" pytest > "$LOG" 2>&1
code=$?
if [ "$code" -ne 0 ]; then
  echo "dependency install failed (exit $code); see $LOG" >&2
  exit "$code"
fi
exit 0
