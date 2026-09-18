# Phase 7.1 Implementation Notes

**Status:** ✅ Implemented (Tasks 1–25) — recorded 2026-09-19.
**Plan:** [phase-7.1-dashboard-refresh.md](../plans/phase-7.1-dashboard-refresh.md)
**Runbook:** [README.md](README.md) · **Validation:** [VALIDATION.md](VALIDATION.md)

These notes describe **what shipped**, module by module, and why the design is
the way it is. Where the shipped behavior differs from the plan's wording, the
difference is called out explicitly.

The Phase 7 data contract is unchanged: the dashboard reads Gold only, keeps
timezone-aware UTC / Gregorian storage, and never interpolates, forward-fills or
resamples. **No file under `src/`, `alembic/` or `airflow/` changed** in this
phase (`git diff --name-only origin/development...HEAD -- src/` is empty).

---

## Architecture

The Phase 7 layering is preserved — repository → components → composition →
pages — with a router added on top and three presentation modules inserted
beneath it:

```text
dashboard/
├── app.py                    # shell + st.navigation router (entrypoint)
├── navigation.py             # page registry: PageSpec rows, GROUPS, PAGES, page_for_domain()
├── i18n.py                   # Persian UI string catalog + t()
├── labels.py                 # indicator/domain/source/frequency display names, cadence, derived suffix map
├── formatting.py             # Persian digits/separators, Jalali + Tehran display, digit mode
├── repository.py             # read-only SQL (LEFT JOIN catalog + parent provenance)
├── queries.py                # st.cache_data wrappers
├── connection.py             # one st.cache_resource connection pool
├── page_view.py              # page composition (filters, Gold load, sections)
├── components/
│   ├── direction.py          # scoped RTL CSS + Plotly typography template
│   ├── filters.py            # shared filters + Jalali presets + range echo
│   ├── charts.py             # pure Plotly builders + bounded/scaled modes + correlation bundle
│   ├── tables.py             # row cap + Persian header/value localization
│   ├── exports.py            # CSV/Excel/HTML + lazy PNG/SVG + Chromium probe
│   └── quality.py            # calendar-aware expectations + quality summary
└── pages/                    # 10 thin delegates (render_* from page_view)
```

**Boundary:** page modules are thin delegates; composition lives in
`page_view.py`; SQL lives only in `repository.py`; no page calls
`st.set_page_config` (the router owns it).

---

## Task-by-Task Notes

### Task 1 — Wave-0 spike

See [wave-0-spike.md](wave-0-spike.md) for the full evidence. Key outcomes that
shaped the implementation:

- `st.navigation` works, but a registry must be **plain data** (`PageSpec`
  rows), with `st.Page` objects built inside the running entrypoint — outside a
  script run `st.Page(...)` silently returns a stub.
- Page paths are entrypoint-relative (`pages/...`).
- `AppTest` cannot see nav chrome, so nav/ownership assertions are data-level
  against the registry.
- The Streamlit floor was bumped to `^1.36`; only a `poetry lock` refresh was
  needed (the lock already pinned 1.61.1).

### Task 2 — Router and page registry

- `dashboard/navigation.py` declares `PageSpec(key, path, icon, group, domains,
  is_default)` in `PAGES`, plus `GROUPS` and `page_for_domain()`.
- `dashboard/app.py` builds `st.Page`s from the registry inside `main()` and
  calls `st.navigation(build_navigation(), position="sidebar")`.
- Nav labels and in-page titles both resolve from the string catalog
  (`nav.<key>` / `page.<key>`) so the two cannot drift; `url_path` is left
  unset (the spike showed it is invisible to `AppTest.switch_page`).
- Exactly one page is `default=True` (`overview`).

### Task 3 — Persian UI string catalog (`dashboard/i18n.py`)

- One locale (`LOCALE = "fa"`); `STRING_CATALOG` is a `MappingProxyType`; `t()`
  fills `{placeholder}` fields and **raises `TranslationError` on a missing key**
  rather than falling back to English (a silent fallback would hide exactly the
  literals the untranslated-literal guard exists to find).
- `KEY_PREFIXES` constrains key namespaces; `has_string()`/`string_keys()` serve
  coverage tests.
- No runtime locale switcher and no second catalog; keys are stable so an `en`
  catalog can be added later without touching call sites.

### Task 4 — Presentation-name layer (`dashboard/labels.py`)

- `DOMAIN_LABELS` (+ `DOMAIN_ORDER`, `UNCLASSIFIED_DOMAIN`), `SOURCE_LABELS`,
  `FREQUENCY_LABELS`, `DERIVED_SUFFIX_LABELS`, and `INDICATOR_LABELS` (all 54
  catalog ids, including the four inactive SCI base-year segments).
- `SOURCE_EXPECTED_CADENCE` is the presentation cadence map used by the Overview
  staleness verdict (daily TGJU/TSETMC, weekly SCI, monthly World Bank/IMF/EIA,
  annual HBSIR).
- `indicator_label()` composes a derived row as *parent display name + derivation*
  and falls back, in order, to the catalog `name` and then the raw id, so an
  unmapped indicator is displayed rather than hidden.
- `is_derived()` reads `record_metadata["derived_from"]` — never an id shape.

### Task 5 — Display formatters (`dashboard/formatting.py`)

- Persian/Latin digit modes, Persian thousands/decimal separators, and Persian
  percent sign; `MISSING_VALUE` (`—`) for `None`/NaN — an unknown value is shown
  as unknown, never as zero.
- Jalali labels for date/year/month/period, a Tehran-local timestamp label, and
  the `tehran_day_bounds` / `jalali_day_bounds` round-trip constructors.
- Digit tables and the ingestion-direction helpers are shared with
  `src.utils.persian`, so the display direction cannot drift from the ingestion
  contract.

### Task 6 — RTL and Persian typography

- `.streamlit/config.toml` sets a light theme baseline.
- `dashboard/components/direction.py` injects a scoped stylesheet (sidebar,
  headings, markdown, metric blocks, form labels) and exposes
  `plotly_template()` / `apply_plotly_typography()`.
- Dataframe and Plotly canvases are explicitly pinned LTR; the selector map is
  declared once (`CSS_SELECTORS`). No webfont, no CDN, no vendored asset.

### Task 7 — Repository hardening (derived/orphan visibility, parent provenance)

- `load_series` is now a Gold-driven query with **two LEFT JOINs** on
  `indicator_catalog`: one for the observation's own row, one for the parent
  named by `record_metadata ->> 'derived_from'`. Parent `name`/`source_name`/
  `source_url` are folded in only when the observation has no catalog row, and
  helper columns are dropped so the frame contract stays stable.
- New frame columns: `series_kind` (`base`/`derived`), `derived_from`,
  `has_catalog_metadata` (orphan flag).
- `list_derived_ids(parent_ids)` and `series_inventory()` discover derived and
  orphan Gold series from metadata alone — no catalog row, no hardcoded id list,
  no id parsing.
- **Deviation:** the plan named the series kinds `level`/`derived`; the shipped
  constants are `base`/`derived` (`SERIES_KIND_BASE`/`SERIES_KIND_DERIVED`).
- **Not shipped:** Task 7(d) also required adding `ttl=` to every `st.cache_data`
  wrapper and a `clear_dashboard_cache()`. Neither is present; see
  [Remaining Gaps](VALIDATION.md#remaining-gaps).

### Task 8 — Lazy, failure-tolerant chart image export

- HTML download stays eager; PNG/SVG render **on demand** behind a button and
  are cached per figure content (`cached_figure_image`, `max_entries=32`).
- `detect_chromium_capability()` probes without raising; when Chromium is
  absent the image buttons are disabled with the actionable
  `DASHBOARD_CHROME_PATH` / `plotly_get_chrome` message. `find_chromium_executable()`
  still raises for the on-demand path, which is caught and surfaced as an error.

### Task 9 — Calendar-aware expected periods

- `expected_periods()` returns either enumerated period keys or an estimated
  count. Month/quarter/year expectations count the storage calendar exactly;
  `daily` has two rules: **calendar** (every Tehran day) for snapshot sources and
  **trading** (session-rate estimate) for exchange sources.
- `TRADING_SESSIONS_PER_YEAR = 241.0`, calibrated against the observed TSETMC
  live run (4,285 sessions across 2008-12-04 … 2026-09-15). The estimate carries
  no session dates and is never expanded into a calendar.
- `MISSING_PERIOD_WARNING_RATIO = 0.05` gates the gap warning so the session-rate
  residual does not raise a spurious warning for every TSETMC series.

### Task 10 — Market (TSETMC) page

- `render_market_page()` shows the catalog level series (domain `market`) plus
  the platform-computed `RET1D` / `MA30` and the `.ME` month-end downsample.
- Groups are metadata-driven: `series_kind` separates level from derived, and the
  Gold `frequency` separates daily derived from the monthly downsample.
- Each series gets its own labelled panel (parent name + derivation), so a rate
  never shares an axis with a level. Caveats cover derived-not-official, absent
  (not zero) sessions, MA30 warm-up, and the deferred trading-value / P/E /
  market-cap metrics.

### Task 11 — Labor page

- `render_labor_page()` reads the whole `labor` domain, defaults the selection to
  it, and renders through the shared Gold path. The single published quarter is
  presented as one observation with its quality row and an explicit SCI
  quarterly-publication caveat, not as an implied trend.

### Task 12 — Welfare & Survey page

- `render_welfare_page()` owns the whole `welfare` domain: HBSIR Gini/relative
  poverty on a Jalali survey-year axis, the ten income-decile shares, a
  survey-year metadata panel, and the remaining welfare members (World Bank
  population, IMF `LUR`). Relative-poverty and computed-value caveats are shown.
- The Trade/Welfare/Energy page was reduced to `trade` + `energy`.

### Task 13 — CPI decile view

- The Inflation page renders the ten SCI expenditure-decile CPI series as one
  unit-safe comparison (small-multiples mode), because they share a unit and a
  base year. The canonical chain-linked national/urban/rural series render in
  their own section. The ids come from the connector registry
  (`SCI_INDICATOR_REGISTRY`), not a dashboard-invented list.

### Task 14 — Derived series exposed end-to-end

- Derived Gold ids are discovered from `record_metadata["derived_from"]` through
  the repository (`derived_series_ids`), and a per-page "include derived" toggle
  appends them to the selection.
- Derived rows inherit their parent's `name`/`source_name`/`source_url` from the
  parent join, so the observations table and the exports attribute them to the
  parent source. Labels read as *parent name – derivation*.

### Task 15 — Bounded chart and table scaling (additive)

- Facets remain the default and unchanged. Overlay is opt-in and only honoured
  for a shared unit; small multiples are opt-in and capped at 12 series. Chart
  heights are bounded to `[420, 1200]` px. The observations grid is capped at 500
  rows with a truncation hint; exports keep every row.

### Task 16 — Overview refresh and domain ownership

- The Overview reports counts, a derived/orphan inventory
  (`series_inventory`), per-domain counts that `st.page_link` into the owning
  page (`page_for_domain`), per-source freshness with a staleness verdict, and
  the observed coverage table. An unowned domain is shown as plain text rather
  than dropped.
- `economy` is no longer claimed by any page.

### Tasks 17–22 — Localization

- Navigation, page chrome, filters, charts, tables and exports all render
  through `t()`, the label layer and the formatters. Chart axes/legends/hover and
  facet titles are Persian; the date axis uses bounded Jalali ticks with a
  Gregorian echo. Table headers come from one shared registry that also backs the
  exports, so grid and export cannot drift. Exports keep ISO-8601 Gregorian
  timestamps and add a Jalali display column.

### Task 23 — Chain-linking transparency

- The Inflation page adds `chain_linking_provenance()` (base-year flag, nominal
  years, registry segment ancestry), `build_chain_linking_chart()` (stored
  `original_value` vs chain-linked `value` for `is_chain_linked` rows), and the
  observations grid with confidence and `record_metadata`. Nothing is recomputed.

### Task 24 — Correlation guardrails

- `build_correlation_chart()` returns a `CorrelationBundle` with the masked
  heatmap, the raw correlation frame, the join-count matrix, a matched-observation
  summary, and the suppressed pairs. Cells with fewer than
  `MIN_CORRELATION_OVERLAP = 3` exact matches are masked; the page warns with the
  count. Axis labels are Persian display names.

### Task 25 — Catalog search

- Search matches catalog values and the Persian label layer (id, display name,
  English name, unit, source, domain, derived suffix). The needle is normalized
  (digits, `ي`/`ك`, case); stored data is untouched. A match count and a
  clear-filters button are provided; the inactive-segment toggle re-queries with
  `active_only=False`. Domain-page search is deferred.

### Task 26 — This documentation

- `docs/phase-7.1/{README,IMPLEMENTATION,VALIDATION}.md` plus corrections to the
  stale Phase 7 claims and the dashboard sections of `README.md` / `AGENTS.md` /
  `docs/phase-2/data_dictionary.md`.

---

## Ownership Decisions

- **`welfare` is owned by the Welfare & Survey page** in full (HBSIR plus World
  Bank population and IMF `LUR`). Excluding non-HBSIR ids would leave population
  and `LUR` homeless and break the ownership test.
- **`labor` is owned by the Labor page** (SCI quarterly unemployment).
- **`market` is owned by the Market page** (TSETMC).
- **`economy` is dropped** from the GDP page: no source emits it.
- The all-domain views (Overview, Comparison & Correlation, Data Catalog) own no
  domain and link out to owners.

Ownership is declared once in `PAGES` and read by both `st.navigation` and the
domain-coverage test, so a dead domain or a split cannot recur silently.

---

## Localization Approach

- One locale (Persian); every UI chrome string lives in `dashboard/i18n.py`.
- Indicator/domain/source/frequency names live in `dashboard/labels.py`; the
  catalog `name` stays the canonical English/auditable value and is preserved in
  exports.
- The "no untranslated literal remains" rule is scoped to UI chrome; data-level
  English (catalog names, slugs, `DataCollectionLog.status`) is displayed as data.
- Ruff `RUF001`/`RUF002`/`RUF003` are whitelisted only for the two presentation
  modules and the Persian-fixture test files.

---

## Deviations From The Plan (Shipped Reality)

| Plan wording | Shipped reality | Reason |
|---|---|---|
| `series_kind` values `level`/`derived` | `base`/`derived` | Naming chosen during implementation; documented in `repository.py`. |
| `clear_dashboard_cache()` + `ttl=` on every cache wrapper | **Not implemented** | Recorded as a remaining gap; a pipeline run needs an app restart. |
| Forecast labeling | Deferred with an in-UI disclaimer | Requires an `src/` ETL change (out of phase boundary). |
| `build_coverage_chart` | **Deleted** | The plan allowed wire-or-delete; the Overview uses metrics/tables instead. |
| `available_domains()` | **Wired** | Used by the Overview per-domain counts. |
