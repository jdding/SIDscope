# SIDScope Linux matrix runbook

Status: executable runbook for the `linux_matrix` required gate. The cell
rules live in `tools/sidscope_linux_matrix_cells.py` and are applied
identically by the receipt builder and the delivery summary.

## Pieces

- `tools/sidscope_source_manifest.py` — the one rule for what counts as
  candidate source (excludes Git metadata, `.local_artifacts`, caches,
  virtualenvs, OS noise). Host and container compute the same digest.
- `tools/run_sidscope_linux_matrix_cell.sh` — runs inside the container; fixed
  command list, writes per-step outputs/exit codes, then invokes the assembler.
- `tools/sidscope_linux_matrix_cell.py` — pure assembler: computes the mounted
  tree manifest, builds the combined log with per-step unique markers (only for
  exit-0 steps), writes `cell-<version>.json`.
- `tools/build_sidscope_linux_matrix_receipt.py` — validates every cell with
  the shared rule, copies logs next to the receipt under `linux-cells/`, and
  re-binds the log paths relative to the receipt directory.

## Host procedure (from the repository root, clean candidate)

```bash
EXPECTED_MANIFEST=$(python3 tools/build_sidscope_linux_matrix_receipt.py --print-manifest)
SNAPSHOT=$(python3 -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'src'); \
  from tools.sidscope_local_release_record import source_snapshot; print(source_snapshot()['content_sha256'])")
HEAD=$(git rev-parse HEAD)
CELLS=.local_artifacts/releases/$HEAD/<attempt>/linux-cells   # fresh, must not exist
mkdir -p "$CELLS"
for v in 3.9 3.10 3.11 3.12; do
  docker run --rm -v "$(pwd)":/workspace:ro -v "$(cd "$CELLS" && pwd)":/out -w /workspace \
    "python:$v-slim" sh tools/run_sidscope_linux_matrix_cell.sh \
    /out "$v" "python:$v-slim" "$EXPECTED_MANIFEST" "$HEAD" "$SNAPSHOT"
done
python3 tools/build_sidscope_linux_matrix_receipt.py --cells-dir "$CELLS" \
  --output "$(dirname "$CELLS")/candidate/linux-matrix.json"
```

The receipt's logs live in `candidate/linux-cells/`, so the delivery summary
reads them through the same relative binding; nothing references the temporary
collection directory afterwards. Records the actual image tag, OS, arch,
in-container interpreter, per-step exit codes and the pytest pass count; no
private data enters the container.
