# ReSOT Resource Walkthrough

This walkthrough follows one released tokenizer artifact from source discovery to a paper-facing SIDScope row. It also includes an invalid public fixture to show that promotion is conditional rather than automatic.

## Source Boundary

- Route: `ReSOT text-index / Instruments`
- Revision: `4531f4d31ae4a9a954995593eb8912289139c063`
- Artifact: `data/Instruments/Instruments.index_lemb.json`
- License status: `no_license_detected`
- Redistribution: `summary_only_no_archive_redistribution`

## Intake-to-Promotion Record

| Stage | Question | Recorded outcome |
| --- | --- | --- |
| discover | Does the upstream release expose an item-to-SID artifact? | 6250 four-level text-index rows found in the released archive. |
| normalize | Can the release be represented by the SIDScope table contract? | 6250 SID rows, 6250 metadata rows, and 136226 interaction rows normalized. |
| inspect | Do joins and bounded D1-D5 diagnostics execute? | C0-C5 pass; collision rate 0.000, depth-1 weighted D3 0.0629 versus 0.4056 for the same-dataset category-prefix control. |
| promote | May the route enter the paper-facing comparison matrix? | Promoted after matrix refresh; effective artifact n=10 and artifact-depth n=30. |
| reject-invalid | Does the contract reject an internally inconsistent SID export? | The public fixture fails C1 only because sid disagrees with sid_level_* columns. |

## Diagnostic Snapshot

The normalized row contains 6,250 items and 136,226 interactions. Its 4-level mapping has 6,250 unique full SIDs, full-code collision rate 0.000, depth-1 weighted D3 0.0629, and prefix counts `83;3645;5729;6250`. The deterministic same-dataset category-prefix control reaches D3 0.4056 under the same bounded protocol.

## Decision Boundary

- This is a released text-index artifact intake and matrix row.
- It is not trained-generator evidence or coverage of every ReSOT branch.
- The upstream archive is not redistributed because no upstream license was detected.
