# Current architecture image generation prompt

Mode: built-in image generation. The interface does not expose a model version;
this artifact must not be described as verified output from "image 2.5".
Date: 2026-09-09. Generated from the current implementation, not a future feature list.

Visual review: six layers; five contract-binding arrows; upstream boundary;
Evidence-derived output branches; labels and local-development disclaimer checked.
The rejected draw.io rendition is retained privately, not used to render this image.

## Final prompt

Use case: infographic-diagram.
Create a polished, publication-quality software architecture overview for the SIDScope project. A new raster image, not a draw.io screenshot. Wide landscape 16:9, ideally 3840 x 2160. Audience: algorithm engineers and software architects. Editorial Swiss information design, precise typography, confident navy titles, warm white canvas, slate text, restrained teal/blue accents and a warm amber conformance gate. Thin crisp arrows, generous whitespace, careful alignment, delicate pale container backgrounds; small meaningful line icons only. No 3D, no decorative background, no status dashboard, no task checklist. Design clarity must be excellent at desktop reading size.

Exact main title, top left: "SIDScope · toward 2.0"
Exact subtitle: "Conformance & observability for Semantic-ID and generative recommendation"
Small top-right edition label: "LOCAL DEVELOPMENT · 1.7.0.dev0"

Architecture composition:
1. A separate narrow LEFT region titled "UPSTREAM SYSTEMS", outside the product boundary, with a small model/data schematic and exactly these three lines:
"Models & training"
"Data & checkpoints"
"Native generation"
At its bottom: "Owned upstream"
A single rightward arrow from this region into the Integration card crosses the product boundary, labelled "File / SDK exports". This depicts data intake, never SIDScope training or changing a model.

2. A large soft outlined central/right enclosure titled "SIDSCOPE · LOCAL-FIRST MODULAR MONOLITH". Five spacious horizontally aligned cards inside it, left to right, linked by short solid arrows. Exactly these cards with these contents:
"01 Integration" / "Adapter SDK" / "Selected producers"
"02 Observation" / "TraceEnvelope" / "Native payloads"
"03 Evaluation" / "Resolution · ranking" / "Mapping diagnostics"
"04 Conformance" / "Profiles & checks" / "Input-bound recomputation"
"05 Evidence" / "Immutable bundles" / "Content-addressed files"
The conformance card is amber-tinted, evidence teal-tinted; others muted blue. Do not make five standalone services. All five must be within one product boundary.

3. Directly beneath the five cards, within the same enclosure, a broad contrasting pale-blue horizontal foundation bar, visibly the sixth owned layer:
"06 Canonical contracts"
"Source · Dataset · SID space · Selection · Run · Checkpoint · Evaluation protocol"
Five thin dashed upward connections from this foundation to the five cards indicate shared identity/contract binding. Do not use downward or bidirectional arrows. Do not number any other layer.

4. A compact unnumbered workflow strip at the top inside the same enclosure, visually lighter than the six owned layers, labelled:
"LOCAL WORKFLOWS · CLI / PYTHON"
With four evenly separated short labels:
"Mapping audit"   "Paired comparison"   "Offline review"   "CPU measurement"
This strip consumes existing layers, it is not a seventh core layer. No task IDs.

5. Below the product enclosure, aligned with its Evidence end, show two understated document/index output groups reached by a branching solid arrow from Evidence:
"Offline review & export"
"Rebuildable SQLite / static indexes"
Visually differentiate authoritative evidence files in the Evidence card from derivative indexes here. No server, cloud, hosted dashboard or service icon.

Bottom legend with solid short arrow then "Artifact flow", dashed short line then "Shared contract binding". One concise footer sentence:
"Native semantics preserved · Fail-closed verification · No hosted service"
Small second footer: "Architecture view, not a public 2.0 compatibility claim."

Render all provided text verbatim with impeccable readable sans-serif type. Keep every arrow unobstructed and every label inside its region. Do not add task IDs, pending/verified badges, counts of tests, performance numbers, citations, source code, file paths, release claims, GPU symbols or project management annotations. This is the actual six-layer local architecture, not a road map. Use a coherent high-end technical publication aesthetic, not a generic flowchart template.
CRITICAL CONNECTOR GEOMETRY: Leave a generous blank vertical routing gutter at the RIGHT of the product enclosure. Evidence's solid output connector must exit the RIGHT EDGE of the Evidence card horizontally into that gutter, descend there entirely OUTSIDE the product enclosure and to the RIGHT of the Canonical contracts bar, then run left below the enclosure to branch into the two output boxes. Never route any solid arrow down through or behind the Canonical contracts bar. All five dashed contract-binding arrows remain upward from the bar. The output connector source must be visibly Evidence, not contracts.
