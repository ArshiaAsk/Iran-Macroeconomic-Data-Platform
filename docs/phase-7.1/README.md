# Phase 7.1 — Dashboard Refresh Runbook (Coverage, Catalog-Driven IA, Persian Localization)

**Status:** ✅ Implemented (Tasks 1–25) — documentation recorded 2026-09-19.
Tasks 27 (extended test suite) and 28 (analyst acceptance pass) are **not yet
executed**; see [Remaining Gaps](VALIDATION.md#remaining-gaps).

**Plan:** [phase-7.1-dashboard-refresh.md](../plans/phase-7.1-dashboard-refresh.md)

This runbook describes the dashboard **as it actually shipped** in Phase 7.1. It
supersedes the Phase 7 runbook ([docs/phase-7/README.md](../phase-7/README.md))
for navigation, page structure, localization and data-quality behavior. The
Phase 7 data contract is unchanged: the dashboard reads the validated Gold
analytical layer only, and it never interpolates, forward-fills or resamples.

---

## Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | What was built: architecture, modules, ownership, localization, derived discovery, quality, chart modes | Developers |
| **[VALIDATION.md](VALIDATION.md)** | Validation record, Wave-0 spike outcome, accepted deviations, remaining gaps | QA, Maintainers |
| **[wave-0-spike.md](wave-0-spike.md)** | Task 1 router/`AppTest`/dependency spike evidence | QA |
| **[Deferred Scope](#deferred-scope-phase-72-candidates)** | Phase 7.2 candidates recorded verbatim from the plan | Everyone |
| **[docs/phase-7/README.md](../phase-7/README.md)** | Phase 7 runbook (structure/localization superseded here) | Historians |

---

## Prerequisites

1. Install project dependencies:

   ```bash
   poetry install
   ```

2. Start PostgreSQL/TimescaleDB and apply migrations:

   ```bash
   make db-up
   poetry run alembic upgrade head
   ```

3. Populate Gold with the pipelines whose data you want to explore. For example:

   ```bash
   poetry run python -m src.connectors.world_bank
   poetry run python -m src.connectors.imf
   poetry run python -m src.connectors.eia
   poetry run python -m src.connectors.sci_scraper
   poetry run python -m src.connectors.tsetmc   # requires `poetry install -E tsetmc`
   poetry run python -m src.connectors.hbsir    # requires `poetry install -E hbsir`
   ```

4. Confirm connectivity:

   ```bash
   make db-check
   ```

## Launch

```bash
make dashboard
```

Streamlit starts in the foreground at `http://localhost:8501`. Press `Ctrl+C`
to stop it. The equivalent direct command is:

```bash
poetry run streamlit run dashboard/app.py
```

The entrypoint (`dashboard/app.py`) is a **router**: it configures the shell,
injects the RTL/Persian stylesheet, renders the database-status banner, and hands
off to `st.navigation`. Page modules under `dashboard/pages/` remain
standalone-runnable (they render their own title) so `AppTest` can still drive
them directly.

---

## Navigation And Domain Ownership

The information architecture is a **single declarative registry**
(`dashboard/navigation.py`) consumed by both `st.navigation` and the
domain-ownership tests. Sidebar labels, in-page titles and section names all
resolve from the Persian string catalog (`nav.<key>` / `page.<key>` /
`group.<key>`), so a page cannot render a literal that drifts from its label.

Two sidebar groups are declared:

- **مرور و تحلیل** (`overview_analysis`) — Overview, Comparison & Correlation, Data Catalog
- **حوزه‌ها** (`domains`) — Inflation, GDP & Economy, Trade & Energy, Welfare & Survey, FX & Gold, Market, Labor

Each domain page owns exactly the domains it renders; the all-domain views
(Overview, Comparison & Correlation, Data Catalog) own none. `economy` is a
**dead domain** (no source emits it) and is never claimed.

| Page (Persian) | Registry key | Group | Owned domains |
|---|---|---|---|
| مرور کلی | `overview` | overview_analysis | — (default page) |
| مقایسه و همبستگی | `correlation` | overview_analysis | — |
| فهرست داده‌ها | `catalog` | overview_analysis | — |
| تورم | `inflation` | domains | `inflation` |
| تولید ناخالص داخلی و اقتصاد | `gdp` | domains | `gdp` |
| تجارت و انرژی | `trade_energy` | domains | `trade`, `energy` |
| رفاه و آمارگیری خانوار | `welfare` | domains | `welfare` |
| ارز و طلا | `fx_gold` | domains | `fx`, `gold` |
| بازار سرمایه | `market` | domains | `market` |
| بازار کار | `labor` | domains | `labor` |

The **Welfare & Survey** page owns the whole `welfare` domain — HBSIR's Gini,
relative poverty and decile shares *plus* the World Bank population series and
IMF `LUR`. The old "Trade, Welfare & Energy" page shrank to `trade` + `energy`.
The **Market** page owns `market` (TSETMC) and the **Labor** page owns `labor`
(SCI quarterly unemployment).

---

## Persian Page Guide

Every page is Persian and right-to-left, with Persian digits and Jalali dates.
Charts label their axes/legends in Persian and use a Jalali date axis with a
Gregorian echo in the hover.

- **مرور کلی (Overview)** — platform-wide counts (active indicators, Gold
  observations, domains, sources), a derived/orphan Gold series inventory, a
  per-domain indicator count that links into the owning page, per-source
  freshness with a staleness verdict, and the observed coverage table. It also
  carries the IMF **forecast-indistinguishability** disclaimer (see below).
- **تورم (Inflation)** — owns `inflation`. Shows the ten SCI expenditure-decile
  CPI series as one unit-safe comparison, the canonical chain-linked
  national/urban/rural CPI comparison, the **chain-linking transparency** panel,
  and the generic inflation composition (World Bank/IMF headline CPIs).
- **تولید ناخالص داخلی و اقتصاد (GDP & Economy)** — owns `gdp` only; derived
  annual growth series are reachable through the "include derived" toggle.
- **تجارت و انرژی (Trade & Energy)** — owns `trade` + `energy`; mixed-unit
  series render one panel per indicator.
- **رفاه و آمارگیری خانوار (Welfare & Survey)** — owns `welfare`. HBSIR Gini and
  relative poverty on a Jalali survey-year axis, the ten income-decile shares,
  a survey-year metadata panel, and the remaining welfare members (World Bank
  population, IMF `LUR`). Relative-poverty and computed-value caveats are shown.
- **ارز و طلا (FX & Gold)** — owns `fx` + `gold`; renders the title once and
  warns that TGJU publishes only current prices, so history accumulates through
  daily collection.
- **بازار سرمایه (Market)** — owns `market`. Shows TEDPIX daily level, the
  platform-computed `RET1D` / `MA30` derived series, and the `.ME` month-end
  downsample, each in its own panel. Caveats cover derived-not-official,
  absent (not zero) trading sessions, MA30 warm-up, and the deferred
  trading-value / P/E / market-cap metrics.
- **بازار کار (Labor)** — owns `labor`. Presents the single published quarterly
  unemployment observation honestly (one marker, no implied trend), with the
  SCI quarterly-publication caveat.
- **مقایسه و همبستگی (Comparison & Correlation)** — exact-timestamp correlation
  heatmap with overlap guardrails (see below), a matched-observation summary,
  quality diagnostics and a CSV/Excel export.
- **فهرست داده‌ها (Data Catalog)** — searchable catalog across id, Persian
  display name, English catalog name, unit, source and domain, with a match
  count, a clear-filters button, and an inactive-base-year-segment toggle.

---

## Filters, Search And Date Selection

Domain pages expose domain, frequency, source, indicator and date filters.
Default date bounds come from observed catalog coverage, not hardcoded years.

- **Jalali presets.** An expander offers a Jalali year, a Jalali month, and a
  numeric Jalali day (`YYYY/MM/DD`, Persian or ASCII digits). The most specific
  preset wins and takes over the range; the Gregorian `st.date_input` controls
  are disabled while a preset is active.
- **Round-trippable bounds.** A selected day is interpreted as a **Tehran** day.
  The applied range is echoed as a Jalali label *and* the inclusive UTC
  Gregorian bounds, so the analyst can always see what the query used.
- **Catalog search (catalog page only).** Matches catalog values (id, English
  name, description) *and* the Persian label layer (display name, unit, source,
  domain, derived suffix). The needle is digit- and character-normalized
  (Persian/Arabic-Indic digits → ASCII, `ي`→`ی`, `ك`→`ک`, case-folded); stored
  data is never rewritten. Domain-page search is deferred.

## Chart Modes

Every multi-indicator chart defaults to **per-indicator facets** (one y-axis per
panel), which is the only mode safe for mixed units. A chart-mode selector adds
two opt-in modes:

- **Overlay** — all series on one shared axis. Honoured only when every series
  shares one unit; a mixed or unknown-unit selection falls back to facets with a
  visible notice instead of sharing a misleading axis.
- **Small multiples** — a 3-column grid of per-indicator panels, capped at
  **12 series**; a larger selection keeps the first 12 and shows a truncation
  notice. The full selection is still exported.

Chart heights are bounded: a floor of 420 px, a 230 px-per-row heuristic, and a
hard ceiling of 1200 px, so a 50-indicator selection cannot produce an enormous
figure.

## Tables And Exports

- The observations grid is a **bounded preview** capped at **500 rows**; a
  truncation hint names shown vs. total. The downloads always carry the full
  selection, and the quality summary describes the full selection.
- Table headers are Persian (one shared header registry), values use Persian
  digits, and timestamps render as Jalali dates. The dataframe grid itself stays
  **LTR** (a known limitation; see below).
- **CSV** is UTF-8 with a BOM so spreadsheet tooling decodes Persian headers.
  **Excel** exports use a Persian sheet name and a right-to-left sheet view.
- Exports keep the ISO-8601 Gregorian `timestamp` and add a Jalali display
  column beside it. Numbers default to **Latin digits** so downstream tooling
  stays machine-readable; a toggle switches to Persian digits for a human-facing
  copy. File names stay ASCII.
- Charts download as standalone interactive **HTML** (eager) and **PNG/SVG**
  (on demand). PNG/SVG need Chromium: the page only probes for it, renders the
  bytes when the matching button is pressed, caches per figure content, and
  **disables** the controls with an actionable message when Chromium is absent —
  a missing browser never fails the page.

## Chain-Linking Transparency

The Inflation page surfaces the stored chain-linking provenance:

- a per-indicator table with the catalog's `has_base_year_changes` flag, the
  nominal `base_years`, and the registry's segment ancestry;
- a chart drawing the stored `original_value` against the chain-linked `value`
  for rows with `is_chain_linked` set;
- the observations grid with `chain_linking_confidence` and `record_metadata`
  unchanged.

Nothing is recomputed, interpolated or normalized. Captions state that the
linked and original values are stored fields and that the splice is derived from
base-year-segment overlap.

## Correlation Guardrails

The Comparison & Correlation page uses **exact-timestamp** matches only.

- A correlation cell whose exact-timestamp join holds fewer than **3** paired
  observations is masked (left blank) rather than drawn, and the page warns with
  the count of suppressed pairs.
- The matched-observation summary reports the actual overlap per indicator pair
  and whether it meets the minimum.
- A mixed-frequency selection warns that no forward-fill or interpolation is
  performed; a blank cell means insufficient overlap, not zero.
- Axis labels are the Persian display names, never raw indicator ids.

## Forecast Disclosure

IMF WEO forecasts are stored as future-dated Gold rows, but Gold carries no
`observation_type` (that label lives only in Silver metadata). Phase 7.1
therefore **does not distinguish forecasts from actuals** in the UI. The
Overview shows an explicit disclaimer; a forecast row renders like any other
observation. Forecast labeling is deferred to Phase 7.2 because it requires an
ETL change under `src/`.

## Data Quality And Freshness

- Quality panels report rows returned, expected observations, missing periods,
  observed start/end, chain-linked rows and average confidence.
- Expectations are **calendar-aware**. Period-end frequencies count calendar
  months/quarters/years exactly. Daily **snapshot** sources (TGJU) expect every
  Tehran day; daily **trading** sources (TSETMC) use an empirical session rate
  (~241 sessions/year, calibrated against the observed live run) reported as an
  **estimate** with no enumerable session dates. The gap warning only fires when
  the missing share is material (≥5%), so the session-rate estimate does not
  raise a spurious "missing periods" warning for every TSETMC series.
- A single-observation series triggers the sparse-history warning; TGJU's
  snapshot nature is stated explicitly.
- Source freshness on the Overview is the latest `DataCollectionLog` run per
  source, with a staleness verdict against the presentation cadence map in
  `dashboard/labels.py` (daily for TGJU/TSETMC, weekly for SCI, monthly for the
  API sources, annual for HBSIR). An unknown source cadence reports "unknown"
  rather than guessing fresh or stale.

## RTL And Persian Typography

Streamlit has no RTL mode, so `dashboard/components/direction.py` owns the one
place the DOM is touched: a small scoped stylesheet (sidebar, headings, markdown,
metric blocks, form labels) plus a Plotly typography template. The dataframe grid
and Plotly canvases are **pinned LTR** on purpose. There is no `@font-face`, no
CDN and no vendored font file — the app works fully offline with an OS font
stack (`Vazirmatn`, `IRANSans`, `Tahoma`, `Segoe UI`, `sans-serif`).

## Jalali / Tehran Display Policy

- Storage is unchanged: timezone-aware **UTC** and ISO-8601 **Gregorian**.
- `Asia/Tehran` is applied **only** when a value is rendered or when a selected
  day is interpreted.
- Period ends (annual/monthly/quarterly) are stored at UTC midnight; Tehran is
  ahead of UTC, so the Tehran-local Gregorian date — and therefore the Jalali
  day — is stable.
- Daily snapshot sources (TGJU) store a scrape instant that may be late evening
  UTC, so the Jalali day is determined **after** converting to Tehran.
  `tehran_day_bounds` / `jalali_day_bounds` produce the inclusive UTC bounds that
  round-trip back to the same Jalali day.
- HBSIR survey years are labelled by the Jalali year **containing** the stored
  period end (the true Esfand 29/30 year end), so the label round-trips without a
  Silver read.

## Cache Behavior

`dashboard/queries.py` wraps every query in `st.cache_data` keyed on the query
arguments, and the connection is one `st.cache_resource` pool. **A TTL and an
explicit refresh control were specified in the plan but are not implemented** in
this phase, so a pipeline run is not visible until the cache is cleared or the
app restarts. This is recorded as a remaining gap in
[VALIDATION.md](VALIDATION.md#remaining-gaps).

## Troubleshooting

### Database unavailable

```bash
make db-up
poetry run alembic upgrade head
make db-check
```

If Docker cannot connect, try `DOCKER_CONTEXT=default make db-up`.

### No indicators or observations

Run a pipeline first. The dashboard intentionally does not invent catalog rows
or observations.

### PNG/SVG downloads are disabled

The buttons disable themselves when no Chromium executable is found. Set
`DASHBOARD_CHROME_PATH` to a working Chrome/Chromium binary, or run
`poetry run plotly_get_chrome`. HTML export needs no browser.

### Mixed-frequency correlation looks empty

Expected when timestamps do not match exactly. Inspect the matched-observation
summary; the dashboard does not forward-fill annual or daily values.

### A pipeline run is not reflected in the UI

The cache has no TTL (see [Cache Behavior](#cache-behavior)). Restart the app
(`Ctrl+C`, then `make dashboard`) to pick up new data.

---

## Known Limitations

- The dataframe grid is LTR-only; localized headers/digits/dates are applied but
  column order and the grid layout stay left-to-right.
- IMF forecasts are indistinguishable from actuals in the UI (explicit
  disclaimer only).
- The cache has no TTL or refresh control; a pipeline run needs an app restart.
- RTL depends on Streamlit `data-testid` selectors that can change across
  releases.
- TGJU is a current-price snapshot source; history accumulates through daily
  collection.
- SCI publishes one labour-force quarter per release, so the Labor series is
  legitimately sparse.
- The dashboard is local and single-user; no authentication, cloud deployment or
  real-time updates.

## Deferred Scope (Phase 7.2 candidates)

Recorded verbatim from the plan so a deferral cannot be mistaken for a missing
feature:

1. **IMF forecast-vs-actual labeling.** Requires an ETL change (thread Silver row
   metadata through `SilverSeries` → `silver_to_gold` → `_level_records` so
   `observation_type` reaches Gold). The dashboard deliberately does not read
   Silver; Phase 7.1 ships with an explicit in-UI disclaimer instead.
2. **Index-to-100 / normalized cross-unit comparison view**, and the normalized
   overlay on the correlation page. New (display-only) analytical transformations.
3. **Indicator detail view** (full metadata, segment ancestry, per-layer record
   counts, raw `record_metadata` keys) — partly served by the catalog page now.
4. **Search on domain pages** (catalog-page search ships now).
5. **Custom Jalali date-entry widget** (Jalali presets + Gregorian/Jalali echo ship
   now).
6. **A fully RTL dataframe/table component** (the grid is LTR-only).
7. **A vendored webfont / `@font-face` asset.** Phase 7.1 ships a font stack over
   OS fonts only, so nothing is vendored and nothing is fetched from a CDN.
8. **An English short-label map and a runtime locale switcher.** The catalog
   `name` stays the canonical English value (and is preserved in exports), and the
   keyed Persian catalog has no switcher; keys are stable so an `en` catalog can be
   added later without touching call sites.
9. **Persian names in the catalog** (`name_fa`/`description_fa` + `discover()` +
   Alembic migration) if translators need DB-driven labels.
10. **Derived series as catalog rows**, so they carry names/units natively without
    the parent-provenance join.
11. **Catalog-held domain taxonomy** (display order, grouping, labels) to replace
    the Python registry.
12. **Gold-level validation/outlier signals** (the data is in Silver, not Gold) and
    **typed, config-held staleness thresholds** (the cadence map is presentation
    metadata in this phase).
13. Carried forward unchanged: OPEC basket, CBI TSD, TSETMC trading value / market
    P/E / market cap, and a monetary-domain page.

## Quality-Gate Decision (Open Item 7)

The plan left the type-check scope ambiguous. The decision taken for this phase:

- **`poetry run mypy src dashboard` was run** and passes — `Success: no issues
  found in 63 source files`. Dashboard code is therefore type-checked in this
  phase.
- **`make typecheck` was NOT widened.** It still runs `mypy src/` only, and
  `--cov=src` is unchanged, so the project coverage gate does not measure
  `dashboard/`. Widening the Makefile target is a separate, explicit follow-up
  rather than an implicit change. See [VALIDATION.md](VALIDATION.md) for the
  command and result.
