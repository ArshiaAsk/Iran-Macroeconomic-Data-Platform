# Phase 7.2 — Dashboard Redesign

Runbook and validation records for Phase 7.2 (design system, shell, all pages).

Status: **Wave C complete; Wave D awaiting owner review** (Overview reference
implementation — Step 0f, Tasks 29–33 and the P1–P5 polish are complete, and the
Task 34 AM-23 visual review was **signed off APPROVED on 2026-09-21** with the
deviations A1–A9 approved as recorded; see
[`validation/reference-overview.md`](validation/reference-overview.md) §6a and
the "Wave C part 2c" section of [`VALIDATION.md`](VALIDATION.md)). Wave D (the
four generic domain-explorer pages: GDP, Trade & Energy, FX & Gold, Labor) is
complete through Tasks 35–36; its owner review is
[`validation/archetype-domain.md`](validation/archetype-domain.md), where
**Owner sign-off is PENDING**. Wave 0 is
recorded in [`wave-0-spike.md`](wave-0-spike.md) (capabilities, pre-change
baseline and the per-wave gate rule). Per-task evidence lives in
[`execution-log.md`](execution-log.md); the Wave A, Wave B and Wave C visual
reviews and gates are in [`VALIDATION.md`](VALIDATION.md).

Sign-off carry items (2026-09-21): **F3** (chart legend title `label`) and **F4**
(English `Choose options` placeholder) were scheduled in Waves D–G and have
**landed in Wave D (Task 35)** on the shared chart builders and the shared filter
set; **F1, F2, F5, F7** and the Gregorian-vs-Jalali range-cell direction are
recorded as optional Wave H polish candidates and are **not scheduled**; the
Gregorian range font-size defect is **fixed** (Step 0a); two data-quality findings
(D1 TGJU coverage window, D2 SCI rows without Gold observations) are handed to the
ETL/catalog side and recorded in the plan's Deferred Scope.

Documents:

- [`design-system.md`](design-system.md) — tokens, theme table, component
  catalogue, CSS ownership and the hook pattern, the D1 table classification and
  typed cells, the D11 layout contract, and the do/don't list. First draft after
  Wave A; Task 47 extends it with the top bar, the sidebar shell and the
  screenshot script.
- [`wave-0-spike.md`](wave-0-spike.md) — Wave 0 capability probes and the
  pre-change baseline.
- [`VALIDATION.md`](VALIDATION.md) — verification record, separating "verified in
  this run" from "not automated".
- [`validation/reference-overview.md`](validation/reference-overview.md) — the
  Wave C AM-23 review of the shell and the Overview against the mockup (signed
  off APPROVED, 2026-09-21).
- [`validation/archetype-domain.md`](validation/archetype-domain.md) — the Wave D
  review of the four generic domain-explorer pages against the layout contract
  (**owner sign-off pending**).
- [`execution-log.md`](execution-log.md) — per-task execution log (files, Verify
  result, deviations, commit hash).
- `README.md` — this file, completed in Wave H.

Wave A left the shared components (`render_callout`, `render_page_header`,
`render_kpi_band`, `render_status_chip`, `render_status_dot`, `render_bar_list`,
`render_section_header`, `render_filter_bar`, the states module and the typed-cell
HTML table) **staged but not adopted by any page** — page composition is Waves
C–G, so the Wave A screenshots show only the global look and the chart template.

Local-development note (D14): the settings-menu theme toggle is already absent
because the app defines a custom `[theme]`; the toolbar can be restored for
development with `STREAMLIT_CLIENT_TOOLBAR_MODE=developer`.
