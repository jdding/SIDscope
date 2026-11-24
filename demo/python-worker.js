const PYODIDE_BASE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const FILES = [
  "RELEASE_STATUS.json",
  "demo/browser_example.py",
  "tools/build_sidscope_paper_tables.py",
  "examples/conformance_failure_fixture/sid_assignments.csv",
  "examples/conformance_failure_fixture/conformance_report.json",
  "docs/reproducibility/sidscope_source_license_config_inventory.csv",
  "docs/reproducibility/d7_labeled_trace_release.json",
  "docs/reproducibility/g22_diagnose_repair_handoff_summary.json",
  "docs/reproducibility/g22_handoff_uncertainty.json",
  "docs/reproducibility/paper_table_sources/table1_resource_delta_source.csv",
  "docs/reproducibility/paper_table_sources/table2_artifact_coverage_source.csv",
  "docs/reproducibility/paper_table_sources/table4_evidence_ladder_source.csv",
  "docs/reproducibility/paper_table_sources/table5_trace_accounting_source.csv",
  "docs/reproducibility/paper_table_sources/table6_resource_contract_source.csv",
  "docs/reproducibility/paper_table_sources/table10_g20_trained_trace_source.csv",
  "docs/reproducibility/paper_tables/table1_resource_delta.csv",
  "docs/reproducibility/paper_tables/table2_artifact_coverage.csv",
  "docs/reproducibility/paper_tables/table4_adapter_conformance.csv",
  "docs/reproducibility/paper_tables/table5_diagnostic_profile.csv",
  "docs/reproducibility/paper_tables/table6_evidence_ladder.csv",
  "docs/reproducibility/paper_tables/table8_resot_walkthrough.csv",
  "docs/reproducibility/paper_tables/table9_resource_contract.csv",
  "docs/reproducibility/paper_tables/table10_g20_trained_trace.csv",
  "docs/reproducibility/conformance/resid_gaoq_video_report.json",
  "docs/reproducibility/conformance/grid_p5_beauty_report.json",
  "docs/reproducibility/conformance/card_p5_beauty_report.json",
  "docs/reproducibility/conformance/diger_beauty_report.json",
  "docs/reproducibility/conformance/diger_yelp_report.json",
  "docs/reproducibility/conformance/resot_instruments_report.json",
  "docs/reproducibility/conformance/letter_instruments_report.json",
  "docs/reproducibility/conformance/lcrec_instruments_report.json",
];

let runtime;

async function initialize(base) {
  postMessage({type: "progress", message: "Loading pinned Pyodide Python 3.14 runtime in your browser…"});
  const {loadPyodide} = await import(PYODIDE_BASE + "pyodide.mjs");
  const python = await loadPyodide({indexURL: PYODIDE_BASE});
  const response = await fetch(new URL("PACKAGE_MANIFEST.json", base));
  if (!response.ok) throw new Error("PACKAGE_MANIFEST.json is unavailable.");
  const manifest = await response.json();
  const hashes = new Map(manifest.files.map(row => [row.path, row.sha256]));

  postMessage({type: "progress", message: `Verifying SHA-256 hashes for ${FILES.length} SIDScope release files…`});
  for (const path of FILES) {
    const resource = await fetch(new URL(path, base));
    if (!resource.ok) throw new Error("Could not load " + path);
    const bytes = new Uint8Array(await resource.arrayBuffer());
    const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
    const actual = Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("");
    if (hashes.get(path) !== actual) throw new Error("SHA-256 integrity check failed: " + path);
    const target = "/sidscope/" + path;
    python.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    python.FS.writeFile(target, bytes);
  }
  return python;
}

self.onmessage = async event => {
  try {
    const base = new URL("../", self.location.href);
    runtime ??= initialize(base);
    const python = await runtime;

    if (event.data.type === "audit_custom") {
      postMessage({type: "custom_progress", message: "Running client-side D1–D5 and A_b vs S_b audit…"});
      python.globals.set("_BYO_SID_CSV", event.data.sidCsv || "");
      python.globals.set("_BYO_INTER_CSV", event.data.interactionsCsv || "");
      python.globals.set("_BYO_META_CSV", event.data.metadataCsv || "");
      const out = await python.runPythonAsync(`
import json, runpy
mod = runpy.run_path('/sidscope/demo/browser_example.py')
json.dumps(mod['audit_custom_csv'](_BYO_SID_CSV, _BYO_INTER_CSV, _BYO_META_CSV))
`);
      postMessage({type: "custom_result", result: JSON.parse(out)});
      return;
    }

    postMessage({type: "progress", message: "Rebuilding 8 manuscript tables, testing C1 rejection, and running RQ1–RQ3…"});
    const result = await python.runPythonAsync(`
import json, runpy
mod = runpy.run_path('/sidscope/demo/browser_example.py')
json.dumps(mod['run_example']())
`);
    postMessage({type: "result", result: JSON.parse(result)});
  } catch (error) {
    if (event.data.type === "audit_custom") {
      postMessage({type: "custom_error", message: String(error.message || error)});
    } else {
      runtime = undefined;
      postMessage({type: "error", message: String(error.message || error)});
    }
  }
};
