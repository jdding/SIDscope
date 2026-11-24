# Expected Outputs

| Command | Primary Output | Expected Verdict |
| --- | --- | --- |
| `python3 tools/verify_sidscope_paper_tables.py` | Rebuilt CSVs for all 8 manuscript tables | Exact row-by-row match with frozen snapshots; exits `0` |
| `python3 tools/verify_adapter_conformance_assets.py` | 9-route inventory + 8 C0–C5 reports + C1 failure fixture | Inventory passes; failure fixture fails `C1` only; exits `0` |
| `python3 tools/validate_resource_portal.py` | SHA-256 portal manifest + pure-Python workbench payload | Final line: `PASS_SIDSCOPE_PORTAL_VALIDATION` |
| `python3 tools/verify_sidscope_resource_package.py` | Full package, quickstart, D7 trace labels & evidence gates | All package checks pass; exits `0` |
| `python3 tools/serve_demo.py --port 8765` | `DEMO_READY http://127.0.0.1:8765` | `/health` returns `status=ready`; browser run completes RQ1–RQ3 + C0–C5 |
