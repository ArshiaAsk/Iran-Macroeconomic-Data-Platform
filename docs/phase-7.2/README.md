# Phase 7.2 — Dashboard Redesign

Runbook and validation records for Phase 7.2 (design system, shell, all pages).

Status: **Wave A complete** (foundation — Tasks 1–24). Wave 0 is recorded in
[`wave-0-spike.md`](wave-0-spike.md) (capabilities, pre-change baseline and the
per-wave gate rule). Per-task evidence lives in
[`execution-log.md`](execution-log.md); the Wave A visual review and gate are in
[`VALIDATION.md`](VALIDATION.md). Implementation waves B–H follow, starting at
Task 25 (Wave B — shell).

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
