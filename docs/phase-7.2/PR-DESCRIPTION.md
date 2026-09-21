# Phase 7.2 — Dashboard Redesign

**Branch:** `phase-7.2` · **Base:** `main` · **Status:** complete, pending owner acceptance.

## Summary

Rebuilds the Streamlit dashboard's presentation layer against the design mockup:
a design-token module and theme, a scoped-CSS owner, a shared component library,
the shell (sidebar + top bar), and all ten pages migrated to one layout contract.
The change is **presentation only** — nothing under `src/`, `alembic/` or
`airflow/` is touched.

## What landed

- **Tokens + theme** — `dashboard/components/tokens.py`, `.streamlit/config.toml`,
  the vendored Vazirmatn font (`dashboard/static/`).
- **Scoped CSS owner** — `dashboard/components/direction.py` (stable hooks only,
  version-named chrome block for Streamlit 1.61.1).
- **Shared components** — `render_page_header`, `render_callout(_stack)`,
  `render_kpi_band`, `render_section_header`, `render_filter_bar`,
  `render_status_chip/_dot`, `render_bar_list`, the `states` module, the typed-cell
  HTML table, the chart template and the export helpers.
- **Shell** — the sidebar brand/DB-status fallback, the top bar (breadcrumb +
  Jalali last-collection stamp), and the RTL/Jalali display policy
  (`Asia/Tehran`, storage unchanged).
- **All ten pages** migrated to the D11 layout contract across archetypes A1–A5
  (Overview, four generic domain pages, three emphasis pages, correlation, catalog).
- **Guards** — `test_layout_guard.py` (D11 contract) and `test_literal_guard.py`
  (no untranslated UI literal), both with completeness tests.
- **Wave H polish** — P1 catalog filter bar, P2 shell-level RTL caption, P3
  breadcrumb separator/bold crumb, P4 screenshot-script scroll fix + `--full-height`.

## Verification

- `make check` → **1468 passed, 3 skipped**, coverage **89.22%**.
- `poetry run mypy src dashboard` → **0 errors / 68 files**.
- Dashboard subset → **657 passed**; export smoke (PNG + SVG) → **1 passed**;
  ten-page router smoke green.
- Ten-page browser capture at commit `2c0977c` in
  `docs/phase-7.2/wave-h-assets/partA-all-pages/` with a pixel diff — **no defects**.

## Docs

- `docs/phase-7.2/README.md` — runbook + "How to add or change a page".
- `docs/phase-7.2/VALIDATION.md` — the verified / not-automated record.
- `docs/phase-7.2/design-system.md` — tokens, components, CSS ownership, contract.
- `docs/phase-7.2/execution-log.md` — per-task evidence and commit hashes.
- `AGENTS.md` — Dashboard UI conventions (Phase 7.2).

## Accepted deviations / deferred

F1 (content padding), F7 (coverage-column wrap), the D3 Gregorian/Jalali bidi
direction, and the unverified `<td title>` hover tooltip are recorded as accepted
deviations. The OPEC/CBI/TSETMC-extended scope, the cache-TTL item and Phase 7.1
Tasks 27–28 remain deferred. **No merge or push** is part of this change set.
