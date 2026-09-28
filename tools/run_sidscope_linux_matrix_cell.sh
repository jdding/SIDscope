#!/bin/sh
# In-container Linux matrix cell runner: fixed commands, then pure assembly.
# Usage (host, per version; see docs/SIDSCOPE_LINUX_MATRIX_RUNBOOK.md):
#   docker run --rm -v "$CLONE:/workspace:ro" -v "$CELLS:/out" \
#     -v "$DEPS_VERSION_DIR:/deps:ro" -e DEPS_DIR=/deps -w /workspace \
#     sidscope-matrix:<version> sh tools/run_sidscope_linux_matrix_cell.sh \
#       /out <version> sidscope-matrix:<version> "$EXPECTED_MANIFEST" "$HEAD" "$SNAPSHOT"
# The mount at /workspace must be a real local clone (not the worktree): the
# full suite exercises git identity checks and the worktree .git pointer does
# not resolve inside the container. DEPS_DIR is a per-version wheelhouse with
# the project wheel, the locked runtime dependencies and pytest; cells never
# build from the read-only source and never reach the network.
set -u
OUT="$1"; VERSION="$2"; IMAGE="$3"; EXPECTED_MANIFEST="$4"; HEAD="$5"; SNAPSHOT="$6"
WORK=/workspace
STEPS="$OUT/steps-$VERSION"
mkdir -p "$STEPS"

# The full suite runs git-based source identity checks; a missing git is a
# preparation error, not a test failure.
if ! command -v git >/dev/null 2>&1; then
  echo "git_missing: the cell image must include git (see runbook image prep)" >&2
  exit 1
fi

if [ -z "${DEPS_DIR:-}" ]; then
  echo "DEPS_DIR not set: mount the per-version wheelhouse and export DEPS_DIR (see runbook)" >&2
  exit 1
fi
if [ ! -d "$DEPS_DIR" ]; then
  echo "DEPS_DIR not a directory: $DEPS_DIR" >&2
  exit 1
fi
mkdir -p "$STEPS/deps-install"
if ! sh tools/sidscope_linux_deps_install.sh "$DEPS_DIR" "$STEPS/deps-install/output.log"; then
  echo "dependency install failed; see $STEPS/deps-install/output.log" >&2
  exit 1
fi

run_step() {
  NAME="$1"; shift
  mkdir -p "$STEPS/$NAME"
  ( cd "$WORK" && "$@" ) > "$STEPS/$NAME/output.log" 2>&1
  echo "$?" > "$STEPS/$NAME/exitcode"
}

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
