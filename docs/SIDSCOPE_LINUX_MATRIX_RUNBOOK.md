# SIDScope Linux matrix runbook

Status: deferred backlog reference under ADR-0027 (2026-10-08). Linux is
unsupported in 2.0 and this runbook is not a release prerequisite. It is
retained for a future feedback-driven support decision. The cell
rules live in `tools/sidscope_linux_matrix_cells.py` and are applied
identically by the receipt builder and the delivery summary.

## Pieces

- `tools/sidscope_source_manifest.py` — the one rule for what counts as
  candidate source: live bytes of Git-tracked files, not recursive ignored
  outputs or HEAD's historical bytes. Host and clone use the same file set.
- `tools/sidscope_linux_deps_install.sh` — offline per-cell dependency entry:
  installs the project wheel, its prepared runtime dependencies and pytest from
  the per-version wheelhouse. Cells never build from the mounted source.
- `tools/run_sidscope_linux_matrix_cell.sh` — runs inside the container; the
  seven fixed commands, per-step output directories, then the assembler.
- `tools/sidscope_linux_matrix_cell.py` — computes the mounted
  tree manifest, independently reads Git/source and runtime identity, builds the combined log
  with per-step unique markers, writes `cell-<version>.json`.
- `tools/build_sidscope_linux_matrix_receipt.py` — validates every cell with
  the shared rule, copies logs next to the receipt under `linux-cells/` and
  re-binds the log paths relative to the receipt directory.

## Preparation (host, once per candidate; network only where noted)

1. **A mountable candidate clone.** The repository is a Git worktree whose
   `.git` is a pointer file; mounting the worktree does not give the container
   a resolvable Git directory, and the full suite executes git identity
   checks. Prepare a real local clone of the frozen HEAD:

   ```bash
   set -eu
   REPO=$(pwd); HEAD=$(git rev-parse HEAD); BRANCH=$(git branch --show-current)
   test -z "$(git status --porcelain)" && test -n "$BRANCH"
   PREP=$(mktemp -d /tmp/sidscope-matrix.XXXXXX)
   git clone --no-hardlinks "$REPO" "$PREP/clone"
   git -C "$PREP/clone" checkout -B "$BRANCH" "$HEAD"
   test -z "$(git -C "$PREP/clone" status --porcelain)"
   ```

   Keep the branch as well as HEAD: both participate in source_snapshot.
   Never build a wheel in this verification clone. Nothing is written back to
   the worktree, the maintenance line or TOIS.

2. **Cell images with git.** The `python:<v>-slim` images do not include git.
   Pre-bake one image per version (network, once):

   ```bash
   for v in 3.9 3.10 3.11 3.12; do
     docker build -t sidscope-matrix:$v - <<EOF
FROM python:$v-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \\
    && rm -rf /var/lib/apt/lists/*
RUN git config --global --add safe.directory /workspace
EOF
   done
   ```

3. **Per-version wheelhouses (network, once).** Resolve dependencies inside
   each prepared Linux image, using its actual Python, ABI, architecture and
   environment markers. Host cross-download flags do not simulate all these
   markers. `requirements.txt` is a range file, not a lock. Build the project
   wheel once in a separate disposable build clone (never in the verification
   clone); include setuptools>=68 and wheel for Python 3.12 packaging checks:

   ```bash
   git clone --no-hardlinks "$PREP/clone" "$PREP/build"
   mkdir "$PREP/project-wheel"
   docker run --rm -v "$PREP/build:/build" -v "$PREP/project-wheel:/wheels" \
     sidscope-matrix:3.9 python3 -m pip wheel --no-deps -w /wheels /build
   for v in 3.9 3.10 3.11 3.12; do
     D="$PREP/deps-$v"; mkdir -p "$D"
     cp "$PREP"/project-wheel/sidinspector-*.whl "$D/"
     docker run --rm -v "$D:/deps" sidscope-matrix:$v sh -ec \
       'python3 -m pip download --only-binary :all: -d /deps /deps/sidinspector-*.whl pytest "setuptools>=68" wheel; cd /deps; sha256sum ./*.whl > SHA256SUMS'
     docker image inspect --format '{{.Id}}' sidscope-matrix:$v > "$D/image-id.txt"
   done
   ```

   Each loop iteration then mounts `deps-$v` — its own directory, matching the
   cell's Python/ABI. Preserve these wheelhouses, SHA256SUMS and image IDs with
   the private attempt evidence for replay. They are execution provenance,
   not a claim that upstream floating image tags or requirements are locked.

## Cell execution (host)

```bash
EXPECTED_MANIFEST=$(/usr/bin/python3 - <<PY
import sys
sys.path.insert(0, "$REPO"); sys.path.insert(0, "$REPO/src")
from pathlib import Path
from tools.sidscope_source_manifest import tree_manifest_digest
print(tree_manifest_digest(Path("$PREP/clone")))
PY
)
SNAPSHOT=$(/usr/bin/python3 - <<PY
import sys
sys.path.insert(0, "$REPO"); sys.path.insert(0, "$REPO/src")
from tools.sidscope_local_release_record import source_snapshot
print(source_snapshot()["content_sha256"])
PY
)
test "$EXPECTED_MANIFEST" = "$(python3 "$REPO/tools/build_sidscope_linux_matrix_receipt.py" --print-manifest)"
mkdir -p "$REPO/.local_artifacts/releases/$HEAD"
ATTEMPT=$(mktemp -d "$REPO/.local_artifacts/releases/$HEAD/linux-attempt.XXXXXX")
CELLS="$ATTEMPT/linux-cells"
mkdir "$CELLS"
for v in 3.9 3.10 3.11 3.12; do
  test "$(docker image inspect --format '{{.Id}}' sidscope-matrix:$v)" = "$(cat "$PREP/deps-$v/image-id.txt")"
  docker run --rm --network none -v "$PREP/deps-$v:/deps:ro" \
    sidscope-matrix:$v sh -ec 'cd /deps; sha256sum -c SHA256SUMS'
  docker run --rm --network none \
    -v "$PREP/clone:/workspace:ro" -v "$(cd "$CELLS" && pwd)":/out \
    -v "$PREP/deps-$v:/deps:ro" -e DEPS_DIR=/deps -w /workspace \
    sidscope-matrix:$v sh tools/run_sidscope_linux_matrix_cell.sh \
    /out "$v" "sidscope-matrix:$v" "$EXPECTED_MANIFEST" "$HEAD" "$SNAPSHOT"
done
cp -R "$PREP"/deps-* "$ATTEMPT/"
/usr/bin/python3 "$REPO/tools/build_sidscope_linux_matrix_receipt.py" \
  --cells-dir "$CELLS" --output "$(dirname "$CELLS")/candidate/linux-matrix.json"
```

Before execution compare the clone manifest with
`python3 tools/build_sidscope_linux_matrix_receipt.py --print-manifest` on the
host; they must match. Ignored build output cannot change the tracked manifest;
edits or deletions of tracked source do. Both checkouts must stay clean.
Each cell independently records actual HEAD and public snapshot digest rather
than copying the expected strings. Each cell
records its live `python_full` and `raw_platform` from inside the container;
the shared validator cross-checks them against the claimed version and OS.
The receipt's logs live in `candidate/linux-cells/`, so the delivery summary
reads them through the same relative binding; nothing references the
preparation or collection directories afterwards. No private data enters the
container; the resource gate runs its full verifier without skip flags.

Docker unavailable means NOT_RUN, never PASS. After any source change, rebuild
all same-source delivery evidence; old records remain historical and cannot
be combined with the new Linux receipt. The shell regression substitutes the
Python command boundary only to test dispatch; it is not Linux execution evidence.
