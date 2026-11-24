const runButton = document.getElementById("run");
const status = document.getElementById("status");
const results = document.getElementById("results");
const tabs = Array.from(document.querySelectorAll("[data-tab]"));
const panels = Array.from(document.querySelectorAll("[data-panel]"));

const byoRunBtn = document.getElementById("byo-run");
const byoStatus = document.getElementById("byo-status");
const byoResults = document.getElementById("byo-results");
const byoSidInput = document.getElementById("byo-sid-csv");
const byoInterInput = document.getElementById("byo-inter-csv");
const byoMetaInput = document.getElementById("byo-meta-csv");

const worker = new Worker("demo/python-worker.js", {type: "module"});
const fixed = (v, d = 3) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d));
const pct = v => (v === null || v === undefined ? "—" : (100 * Number(v)).toFixed(1) + "%");

const PRESETS = {
  cross_stratum: {
    sid: "item_id,sid_0,sid_1,sid_2\n1,1,1,1\n2,1,1,2\n3,1,2,1\n4,2,1,1\n5,2,1,2\n6,2,2,1\n7,1,1,1\n8,1,1,2\n9,3,1,1",
    inter: "user_id,item_id,split\nu1,1,train\nu2,1,train\nu3,1,train\nu4,1,train\nu1,2,train\nu2,2,train\nu3,2,train\nu1,3,train\nu2,3,train\nu3,3,train\nu1,4,train\nu2,4,train\nu3,5,train\nu4,5,train\nu5,6,train\nu6,6,train\nu7,7,train\nu8,8,train",
    meta: "item_id,category\n1,head\n2,head\n3,head\n4,mid\n5,mid\n6,mid\n7,tail\n8,tail\n9,tail",
  },
  clean: {
    sid: "item_id,sid_0,sid_1,sid_2\n1,10,1,1\n2,10,1,2\n3,10,2,1\n4,10,2,2\n5,20,1,1\n6,20,1,2\n7,20,2,1\n8,20,2,2",
    inter: "user_id,item_id,split\nu1,1,train\nu1,2,train\nu2,2,train\nu2,3,train\nu3,5,train\nu3,6,train\nu4,6,train\nu4,7,train",
    meta: "item_id,category\n1,catA\n2,catA\n3,catA\n4,catA\n5,catB\n6,catB\n7,catB\n8,catB",
  },
  heavy_collision: {
    sid: "item_id,sid_0,sid_1,sid_2\n1,1,1,1\n2,1,1,1\n3,1,1,1\n4,2,1,1\n5,2,1,1\n6,2,1,1\n7,3,1,1\n8,3,1,1",
    inter: "user_id,item_id,split\nu1,1,train\nu1,2,train\nu2,1,train\nu2,4,train\nu3,4,train\nu3,5,train\nu4,7,train\nu4,8,train",
    meta: "",
  },
};

function addRow(id, values) {
  const row = document.createElement("tr");
  for (const value of values) {
    const cell = document.createElement("td");
    cell.textContent = String(value);
    row.append(cell);
  }
  document.getElementById(id).append(row);
}

function setActiveTab(name) {
  for (const btn of tabs) {
    const active = btn.dataset.tab === name;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const panel of panels) {
    panel.hidden = panel.dataset.panel !== name;
  }
}

for (const btn of tabs) {
  btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
}

function renderAbSbBars(rows) {
  const box = document.getElementById("rq1-absb-bars");
  box.replaceChildren();
  for (const r of rows) {
    const row = document.createElement("div");
    row.className = "bar-row";
    const label = document.createElement("div");
    label.className = "bar-label";
    const gap = r.ab - r.sb;
    label.textContent = r.mapping + (gap > 0.5 ? ` (Δ ${gap.toFixed(1)} pp)` : "");
    const tracks = document.createElement("div");
    tracks.className = "bar-tracks";
    for (const [cls, tag, val] of [
      ["plum", "Tail allocation A_b", r.ab],
      ["amber", "Global singleton S_b", r.sb],
    ]) {
      const line = document.createElement("div");
      line.className = "bar-line";
      const fill = document.createElement("span");
      fill.className = `bar-fill ${cls}`;
      fill.style.width = `${Math.max(2, val).toFixed(1)}%`;
      const txt = document.createElement("span");
      txt.className = "bar-val";
      txt.textContent = `${tag}: ${val.toFixed(1)}%`;
      line.append(fill, txt);
      tracks.append(line);
    }
    row.append(label, tracks);
    box.append(row);
  }
}

function renderDecisions(containerId, cards) {
  const box = document.getElementById(containerId);
  box.replaceChildren();
  for (const c of cards) {
    const el = document.createElement("div");
    el.className = `triage-card ${c.status}`;
    const head = document.createElement("div");
    head.className = "probe-title";
    const t = document.createElement("span");
    t.textContent = c.question;
    const pill = document.createElement("span");
    pill.className = `pill ${c.status}`;
    pill.textContent = c.status;
    head.append(t, pill);
    const sig = document.createElement("p");
    sig.style.fontSize = "13px";
    sig.textContent = c.signal;
    const act = document.createElement("p");
    act.className = "note";
    act.textContent = "Action: " + c.action;
    el.append(head, sig, act);
    box.append(el);
  }
}

function render(result) {
  for (const id of [
    "rq1-t5", "rq1-live-d4",
    "rq2-d7-sim", "rq2-t5", "rq2-t6", "rq2-t7", "rq2-ladder", "rq2-d7-125k",
    "rq3-t8a", "rq3-t8b", "rq3-gate",
    "c-protocol", "c-inv", "steps",
  ]) {
    document.getElementById(id).replaceChildren();
  }

  // Tab 1: RQ1 Mapping Structure & A_b vs S_b
  for (const r of result.table5_profiles) {
    addRow("rq1-t5", [
      r.artifact,
      r.items,
      r.sid_depth,
      r.d1_level1_symbols,
      r.d2_collision_item_rate,
      r.d3_depth1_weighted,
      r.d4_tail_unique_ratio,
      r.d5_unique_full_codes,
    ]);
  }
  renderAbSbBars(result.published_ab_sb);

  for (const r of result.rq1_live_ab_sb.d4) {
    addRow("rq1-live-d4", [
      r.bucket,
      r.items,
      pct(r.allocation_ab),
      pct(r.global_singleton_sb),
      pct(r.ab_minus_sb),
      r.cross_stratum_shared,
    ]);
  }

  // Tab 2: RQ2 Exposure Controls & D7 Beam Resolvers
  const sim = result.d7_live_sim;
  addRow("rq2-d7-sim", ["Target-path survival (upper bound)", pct(sim.path_survival), "Target code appears anywhere in beam"]);
  addRow("rq2-d7-sim", ["Singleton credit (strict unambiguous)", pct(sim.singleton_credit), "Code resolves uniquely to target alone"]);
  addRow("rq2-d7-sim", ["Uniform within-leaf draw (1/m)", pct(sim.uniform_expected), "Expected hit under uniform tie-break"]);
  addRow("rq2-d7-sim", ["Deterministic popularity resolver", pct(sim.popularity_resolver), `Recovers +${pct(sim.popularity_gain_over_singleton)} over singleton`]);

  for (const r of result.fixed_budget_t5) {
    addRow("rq2-t5", [
      r.mapping,
      `${r.orig_r100.toFixed(2)}%`,
      `${r.perm_r100.toFixed(2)}%`,
      `${r.pop_r100.toFixed(2)}%`,
      r.orig_ndcg.toFixed(2),
      r.perm_ndcg.toFixed(2),
      r.pop_ndcg.toFixed(2),
    ]);
  }
  for (const r of result.table10_traces) {
    addRow("rq2-t6", [
      r.route,
      r.split,
      r.targets,
      Number(r.beam_rows).toLocaleString("en-US"),
      pct(r.ambiguous_beam_rate),
      pct(r.target_path_survival),
      pct(r.target_unique_item_hit),
      `+${(100 * Number(r.path_item_gap)).toFixed(1)} pp`,
    ]);
  }
  for (const r of result.resolver_t7) {
    addRow("rq2-t7", [r.case, `${r.path.toFixed(2)}%`, `${r.singleton.toFixed(2)}%`, `${r.uniform.toFixed(2)}%`, `${r.popularity.toFixed(2)}%`, r.gain_ci]);
  }
  for (const r of result.table6_ladder) {
    addRow("rq2-ladder", [r.group, r.evaluation_protocol, r.endpoint, r.unit, r.rho, r.uncertainty]);
  }
  for (const [caseName, info] of Object.entries(result.d7_release_cases)) {
    const pfc = info.primary_failure_counts || {};
    addRow("rq2-d7-125k", [
      caseName,
      info.traces,
      info.rows.toLocaleString("en-US"),
      (pfc.invalid_path || 0).toLocaleString("en-US"),
      (pfc.ambiguous_path || 0).toLocaleString("en-US"),
      (pfc.high_uncertainty || 0).toLocaleString("en-US"),
      (pfc.valid_hit || 0).toLocaleString("en-US"),
    ]);
  }

  // Tab 3: RQ3 Refresh & Handoff Gate
  for (const r of result.dact_handoff) {
    addRow("rq3-t8a", [
      r.mapping_model_state,
      r.catalog_gaps,
      r.d6_churn,
      `${r.common_ndcg_at_20} ${r.common_ndcg_at_20_ci}`,
      r.new_item_recall_at_20 === "--" ? "—" : `${r.new_item_recall_at_20} ${r.new_item_recall_at_20_ci}`,
      r.gate,
      r.gate_probability,
    ]);
  }
  const dg = result.dact_gate_live;
  document.getElementById("rq3-threshold").textContent =
    `Live-recomputed preregistered recovery threshold = ${dg.computed_threshold.toFixed(8)} ` +
    `(matches archived JSON: ${dg.threshold_match ? "exact" : "mismatch"}).`;
  for (const s of dg.seeds) {
    addRow("rq3-gate", [
      `Seed ${s.seed}`,
      (s.overall_ndcg * 1000).toFixed(2),
      (s.common_ndcg * 1000).toFixed(2),
      pct(s.new_item_recall),
      `${s.conditions_passed} / 4`,
      s.pass_all ? "PASS" : "FAIL",
    ]);
  }
  for (const row of dg.posthoc_stratification) {
    addRow("rq3-t8b", [
      row.group,
      row.targets.toLocaleString("en-US"),
      row.items.toLocaleString("en-US"),
      row.old.toFixed(2),
      row.map_only.toFixed(2),
      row.s2025.toFixed(2),
      row.s2026.toFixed(2),
      row.s2027.toFixed(2),
    ]);
  }

  // Tab 4: Conformance & Inventory
  const c1 = result.c1_failure_check;
  const mismatch = c1.mismatches[0];
  document.getElementById("c1-result").textContent =
    `PASS (expected fail-closed rejection): Checked ${c1.rows_checked} rows in ${c1.fixture}; ` +
    `caught C1 mismatch at row ${mismatch.row_index} (item_id=${mismatch.item_id}: declared sid="${mismatch.declared_sid}" vs reconstructed "${mismatch.reconstructed_sid}").`;

  for (const r of result.table4_conformance) {
    addRow("c-protocol", [r.level, r.question, r.required_evidence]);
  }
  for (const r of result.inventory) {
    addRow("c-inv", [
      r.route_id || r.method || "—",
      r.dataset || "—",
      r.evidence_role || r.role || "—",
      r.license_status || r.license_identifier || "—",
      r.redistribution_policy || "—",
    ]);
  }

  for (const s of result.steps) {
    const li = document.createElement("li");
    li.textContent = `${s.script} — ${s.output}`;
    document.getElementById("steps").append(li);
  }
  document.getElementById("runtime").textContent =
    `Python ${result.python} · SIDScope v${result.version} (${result.portal_revision}) · SHA-256 verified against PACKAGE_MANIFEST.json`;
  results.hidden = false;
}

function renderCustom(payload) {
  const r = payload.report;
  for (const id of ["byo-d1", "byo-d2", "byo-d3", "byo-d4"]) {
    document.getElementById(id).replaceChildren();
  }
  document.getElementById("byo-summary").textContent =
    `Validated ${r.d5.items} items (depth ${r.d5.sid_depth}) · ${r.d5.unique_sid} unique SIDs · ` +
    `D2 full aliasing = ${fixed(r.d2[0].full_collision_rate, 4)} · active prefixes = ${r.d5.prefix_counts}`;
  for (const row of r.d1) addRow("byo-d1", [row.level, row.unique_codes, fixed(row.entropy, 3), fixed(row.gini, 3)]);
  for (const row of r.d2) addRow("byo-d2", [row.prefix_depth, row.active_prefixes, fixed(row.prefix_collision_rate, 3), fixed(row.full_collision_rate, 3)]);
  for (const row of r.d3) addRow("byo-d3", [row.prefix_depth, row.retained_edges, fixed(row.edge_micro, 3), fixed(row.freq_weighted, 3)]);
  for (const row of r.d4) addRow("byo-d4", [row.bucket, row.items, pct(row.allocation_ab), pct(row.global_singleton_sb), pct(row.ab_minus_sb), row.cross_stratum_shared]);
  renderDecisions("byo-decisions", r.decisions);
  byoResults.hidden = false;
}

worker.onmessage = event => {
  const msg = event.data;
  if (msg.type === "progress") status.textContent = msg.message;
  if (msg.type === "result") {
    render(msg.result);
    if (document.querySelector('[data-tab="t5"].active')) setActiveTab("t1");
    status.className = "";
    status.textContent = "Complete. All 8 manuscript tables, RQ1–RQ3 workflows, and C1 rejection verified in your browser.";
    runButton.disabled = false;
    runButton.textContent = "Run all RQ1–RQ3 & conformance workflows";
    results.removeAttribute("aria-busy");
  }
  if (msg.type === "error") {
    status.className = "error";
    status.textContent = msg.message;
    runButton.disabled = false;
    runButton.textContent = "Run all RQ1–RQ3 & conformance workflows";
    results.removeAttribute("aria-busy");
  }
  if (msg.type === "custom_progress") byoStatus.textContent = msg.message;
  if (msg.type === "custom_result") {
    renderCustom(msg.result);
    byoStatus.className = "";
    byoStatus.textContent = "Audit complete (100% client-side in Pyodide).";
    byoRunBtn.disabled = false;
  }
  if (msg.type === "custom_error") {
    byoStatus.className = "error";
    byoStatus.textContent = msg.message;
    byoRunBtn.disabled = false;
  }
};

runButton.addEventListener("click", () => {
  runButton.disabled = true;
  runButton.textContent = "Running…";
  status.className = "";
  results.setAttribute("aria-busy", "true");
  worker.postMessage({type: "run"});
});

byoRunBtn.addEventListener("click", () => {
  byoRunBtn.disabled = true;
  byoStatus.className = "";
  byoStatus.textContent = "Running client-side Pyodide audit…";
  worker.postMessage({
    type: "audit_custom",
    sidCsv: byoSidInput.value,
    interactionsCsv: byoInterInput.value,
    metadataCsv: byoMetaInput.value,
  });
});

for (const btn of document.querySelectorAll("[data-preset]")) {
  btn.addEventListener("click", () => {
    const p = PRESETS[btn.dataset.preset];
    if (!p) return;
    byoSidInput.value = p.sid;
    byoInterInput.value = p.inter;
    byoMetaInput.value = p.meta;
    byoStatus.className = "";
    byoStatus.textContent = `Loaded preset "${btn.textContent}". Click "Audit my CSV in browser" to run.`;
  });
}

for (const [fileId, targetEl] of [
  ["byo-sid-file", byoSidInput],
  ["byo-inter-file", byoInterInput],
  ["byo-meta-file", byoMetaInput],
]) {
  const input = document.getElementById(fileId);
  if (input) {
    input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      targetEl.value = await file.text();
    });
  }
}

byoSidInput.value = PRESETS.cross_stratum.sid;
byoInterInput.value = PRESETS.cross_stratum.inter;
byoMetaInput.value = PRESETS.cross_stratum.meta;
