#!/bin/sh
# In-container Linux matrix cell runner: fixed commands, then pure assembly.
# Usage (host, per version; see docs/SIDSCOPE_LINUX_MATRIX_RUNBOOK.md):
#   docker run --rm -v "$REPO:/workspace:ro" -v "$CELLS:/out" -v "$DEPS:/deps:ro" \
#     -e DEPS_DIR=/deps -w /workspace python:3.9-slim \
#     sh tools/run_sidscope_linux_matrix_cell.sh /out 3.9 python:3.9-slim \
#        "$EXPECTED_MANIFEST" "$HEAD" "$SNAPSHOT"
# DEPS_DIR (optional) is a prepared per-version Linux wheelhouse (the locked
# runtime dependencies plus the project wheel); when set, the cell installs
# the project and its locked dependencies from it before running pytest.
set -u
OUT="$1"; VERSION="$2"; IMAGE="$3"; EXPECTED_MANIFEST="$4"; HEAD="$5"; SNAPSHOT="$6"
WORK=/workspace
STEPS="$OUT/steps-$VERSION"
mkdir -p "$STEPS"

run_step() {
  NAME="$1"; shift
  mkdir -p "$STEPS/$NAME"
  ( cd "$WORK" && "$@" ) > "$STEPS/$NAME/output.log" 2>&1
  echo "$?" > "$STEPS/$NAME/exitcode"
}

# Dependency preparation (network-free): install the locked runtime deps and
# the project itself from the operator-provided Linux wheelhouse so pytest and
# imports run against a regular install, never a checkout.
if [ -n "${DEPS_DIR:-}" ] && [ -d "$DEPS_DIR" ]; then
  ( cd "$WORK" && python3 -m pip install --no-index --find-links "$DEPS" "$WORK" ) \
    > "$STEPS/deps-install.log" 2>&1 || { echo "dependency install failed; see $STEPS/deps-install.log"; exit 1; }
fi

run_step pytest      python3 -m pytest -q --no-header -x tests
run_step metadata    python3 tools/verify_sidscope_release_metadata.py
run_step architecture python3 tools/verify_sidscope_architecture_inventory.py
run_step sdlc_acceptance python3 tools/verify_sidscope_sdlc_acceptance.py
run_step sdlc_hardening python3 tools/verify_sidscope_sdlc_hardening.py --require-engineering-ready
run_step profiles    python3 tools/verify_sidscope_release_profiles.py
run_step resource    python3 tools/verify_sidscope_resource_package.py

python3 tools/sidscope_linux_matrix_cell.py \
  --workspace "$WORK" --steps-dir "$STEPS" --output-dir "$OUT" \
  --python-version "$VERSION" --image "$IMAGE" \
  --expected-manifest "$EXPECTED_MANIFEST" \
  --head "$HEAD" --public-snapshot-digest "$SNAPSHOT"
