# Phase 7.2 — Dashboard Redesign

Runbook and validation records for Phase 7.2 (design system, shell, all pages).

Status: **Waves F and G approved; Wave H in progress** (Overview reference
implementation — Step 0f, Tasks 29–33 and the P1–P5 polish are complete, and the
Task 34 AM-23 visual review was **signed off APPROVED on 2026-09-21** with the
deviations A1–A9 approved as recorded; see
[`validation/reference-overview.md`](validation/reference-overview.md) §6a and
the "Wave C part 2c" section of [`VALIDATION.md`](VALIDATION.md)). Wave D (the
four generic domain-explorer pages: GDP, Trade & Energy, FX & Gold, Labor) is
complete through Tasks 35–36 and its owner review is
[`validation/archetype-domain.md`](validation/archetype-domain.md), **signed off
APPROVED on 2026-09-21**. Wave E (the emphasis-domain pages: Inflation Task 38,
Welfare Task 39, Market Task 40, plus Step 0a/0b) is **complete through Task 41**;
the emphasis owner review is
[`validation/archetype-emphasis.md`](validation/archetype-emphasis.md),
**signed off APPROVED on 2026-09-22** (the 15 MATCH rows accepted; the three
approved deviations are recorded in its §10). Wave F (the comparison /
correlation page, Task 42) is **complete through Task 43**; its owner review is
[`validation/archetype-correlation.md`](validation/archetype-correlation.md),
**signed off APPROVED on 2026-09-22** (14 MATCH rows; the shared `render_filters`
deviation accepted). Wave G (the data catalog page, Task 44) is **complete through
Task 45**; its owner review is
[`validation/archetype-catalog.md`](validation/archetype-catalog.md),
**signed off APPROVED on 2026-09-22, conditional on P1** (the tall narrow filter
column is a defect, fixed in Wave H P1). Wave H (the final polish, the consistency
guard, the validation record and the cross-page audit) is **in progress**. Wave 0
is recorded in [`wave-0-spike.md`](wave-0-spike.md) (capabilities, pre-change
baseline and the per-wave gate rule). Per-task evidence lives in
[`execution-log.md`](execution-log.md); the Wave A, Wave B and Wave C visual
reviews and gates are in [`VALIDATION.md`](VALIDATION.md).

Sign-off carry items (2026-09-22): **F3** (chart legend title `label`) and **F4**
(English `Choose options` placeholder) were scheduled in Waves D–G and have
**landed in Wave D (Task 35)** on the shared chart builders and the shared filter
set; the Gregorian range font-size defect is **fixed** (Step 0a). The filter-set
shapes are **not unified** — recorded as an **accepted deviation**: the Overview
uses `render_filter_bar` of selects, the domain/emphasis/correlation pages use
`render_filters`, and the catalog uses a bar of simple controls plus a full-width
`render_filters`. **Not done, accepted deviations (with reasons):** **F1** content
padding 70 px vs the mockup's 40 px (owner did not request; it is a global change);
**F7** no-wrap of the short categorical coverage columns (owner did not request);
the Gregorian ranges read LTR while the Jalali ranges read RTL (the D3 bidi
decision); the `<td title>` hover tooltip is **unverified in a real browser** (an
owner checklist item); and the ETL/catalog findings **D1** (TGJU snapshot coverage
window) and **D2** (SCI rows without Gold observations) are handed to the
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
  (**owner sign-off APPROVED, 2026-09-21**).
- [`validation/archetype-emphasis.md`](validation/archetype-emphasis.md) — the
  Wave E review of the three emphasis-domain pages (Inflation, Welfare, Market)
  against the layout contract (**owner sign-off APPROVED, 2026-09-22**).
- [`validation/archetype-correlation.md`](validation/archetype-correlation.md) —
  the Wave F review of the comparison / correlation page against the layout
  contract (**owner sign-off APPROVED, 2026-09-22**).
- [`validation/archetype-catalog.md`](validation/archetype-catalog.md) — the
  Wave G review of the data catalog page against the layout contract
  (**owner sign-off APPROVED, 2026-09-22, conditional on Wave H P1**).
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

Screenshot capture (dev-only): `scripts/dashboard_screenshots.py` writes one PNG
per registered page. The default run captures the shipped **1440x900** viewport;
`--full-height` captures each page at its own content height (bounded to 12000 px)
for a whole-page view. Restart the dev server before a capture set and record the
commit under capture; see
[`design-system.md`](design-system.md) §16 and
[`wave-h-assets/p4/heights.txt`](wave-h-assets/p4/heights.txt).
