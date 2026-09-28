# SIDScope Linux matrix runbook

Status: executable runbook for the `linux_matrix` required gate. The cell
rules live in `tools/sidscope_linux_matrix_cells.py` and are applied
identically by the receipt builder and the delivery summary.

## Pieces

- `tools/sidscope_source_manifest.py` — the one rule for what counts as
  candidate source; excludes Git metadata, the ignored evidence area, caches
  and virtualenvs. The host and the container compute the same digest.
- `tools/sidscope_linux_deps_install.sh` — offline per-cell dependency entry:
  installs the project wheel, its locked runtime dependencies and pytest from
  the per-version wheelhouse. Cells never build from the mounted source.
- `tools/run_sidscope_linux_matrix_cell.sh` — runs inside the container; the
  seven fixed commands, per-step output directories, then the assembler.
- `tools/sidscope_linux_matrix_cell.py` — pure assembler: computes the mounted
  tree manifest, records the live runtime identity, builds the combined log
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
   REPO=$(pwd); HEAD=$(git rev-parse HEAD)
   PREP=$(mktemp -d /tmp/sidscope-matrix.XXXXXX)
   git clone --no-hardlinks "$REPO" "$PREP/clone"
   git -C "$PREP/clone" checkout "$HEAD"
   git -C "$PREP/clone" status --porcelain   # must be empty
   ```

   The clone carries the candidate history; nothing is written back to the
   worktree, the maintenance line or TOIS.

2. **Cell images with git.** The `python:<v>-slim` images do not include git.
   Pre-bake one image per version (network, once):

   ```bash
   for v in 3.9 3.10 3.11 3.12; do
     docker build -t sidscope-matrix:$v - <<EOF
FROM python:$v-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \\
    && rm -rf /var/lib/apt/lists/*
EOF
   done
   ```

3. **Per-version wheelhouses (network, once).** `requirements.txt` is a range
   file, not a lock; do not treat it as one. Download the exact runtime set
   per target Python/ABI plus pytest, and build the pure-Python project wheel
   once with the host interpreter:

   ```bash
   PIP="/usr/bin/python3 -m pip"
   for v in 3.9 3.10 3.11 3.12; do
     D="$PREP/deps-$v"; mkdir -p "$D"
     $PIP download -r "$PREP/clone/requirements.txt" \
       --python-version "$v" --platform manylinux2014_aarch64 --only-binary :all: -d "$D"
     $PIP download pytest --python-version "$v" --only-binary :all: -d "$D"
   done
   $PIP wheel --no-deps --no-build-isolation -w "$PREP/deps-3.9" "$PREP/clone"
   for v in 3.10 3.11 3.12; do cp "$PREP"/deps-3.9/sidinspector-*.whl "$PREP/deps-$v/"; done
   ```

   Each loop iteration then mounts `deps-$v` — its own directory, matching the
   cell's Python/ABI. Record the wheelhouse digests with the attempt evidence
   so the offline installs are replayable.

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
CELLS="$REPO/.local_artifacts/releases/$HEAD/<attempt>/linux-cells"   # fresh
mkdir -p "$CELLS"
for v in 3.9 3.10 3.11 3.12; do
  docker run --rm \
    -v "$PREP/clone:/workspace:ro" -v "$(cd "$CELLS" && pwd)":/out \
    -v "$PREP/deps-$v:/deps:ro" -e DEPS_DIR=/deps -w /workspace \
    sidscope-matrix:$v sh tools/run_sidscope_linux_matrix_cell.sh \
    /out "$v" "sidscope-matrix:$v" "$EXPECTED_MANIFEST" "$HEAD" "$SNAPSHOT"
done
/usr/bin/python3 "$REPO/tools/build_sidscope_linux_matrix_receipt.py" \
  --cells-dir "$CELLS" --output "$(dirname "$CELLS")/candidate/linux-matrix.json"
```

The expected manifest is computed over the mounted clone, not the worktree,
so untracked host files cannot desynchronize the comparison. Each cell
records its live `python_full` and `raw_platform` from inside the container;
the shared validator cross-checks them against the claimed version and OS.
The receipt's logs live in `candidate/linux-cells/`, so the delivery summary
reads them through the same relative binding; nothing references the
preparation or collection directories afterwards. No private data enters the
container; the resource gate runs its full verifier without skip flags.
