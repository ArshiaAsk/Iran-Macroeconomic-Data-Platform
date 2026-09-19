# Task: Phase 7.1 — Dashboard Refresh (Coverage, Catalog-Driven IA, Persian Localization)

**Status: revised after the scope & architecture review of 2026-09-16.** The
review outcome is recorded first so a reader can see exactly what changed from
the first draft and why.

## Review outcome

### Removed / deferred (see [Deferred Scope](#deferred-scope-phase-72-candidates))

| Item | Reason |
|---|---|
| IMF forecast-vs-actual distinction | `observation_type` exists only in **Silver** metadata (`src/etl/silver.py:235`); Gold's level `record_metadata` is built from chain-linking fields alone (`_level_records`, `src/etl/gold.py`). The "preferred" option needs `SilverSeries` to carry per-row metadata threaded through `load_silver_series` → `silver_to_gold` → `_level_records` — a real ETL change. The "alternative" (dashboard reads Silver) breaks the Gold-only rule this phase is built on. |
| Index-to-100 / normalized cross-unit view | A new (display-only) analytical transformation, explicitly outside the phase boundary. |
| Normalized overlay on the correlation page | Same class of change; depends on the item above. |
| "Duplicate timestamps collapsed by `pivot_table`" warning | Premise unverified: `build_correlation_chart` already passes `aggfunc="first"`, Silver has `uq_silver_indicator_timestamp`, and Gold is delete-and-reinsert per indicator. |
| Outlier/validation signals from Gold metadata | Not present in Gold: level rows carry only `linking_method`/`scale_factor`/`base_year_from`/`base_year_to`. |
| Indicator detail view | Valuable metadata browsing, but not required by the stated goal and largely covered by the catalog page plus `coverage_summary()`. |
| Search on every domain page | Catalog-page search satisfies "catalog metadata exploitation"; per-page search doubles the surface. |
| English "short label" map (50 indicators) | Duplicates the catalog `name`, which is already the canonical English value and is preserved in exports. |
| Runtime locale switcher / dual fa-en catalog | Contradicts "no English remains", adds a control to localize, doubles string maintenance. Keys stay stable so `en` can be added later. |
| `@font-face` / vendored webfont | Local-only, no-cloud constraint: a webfont means vendoring a binary or fetching from a CDN. A font stack is enough. |
| Custom Jalali date **input** widget | The plan's own highest UX-risk item. Jalali display + Jalali presets delivers "Jalali-aware filtering" without replacing a mature widget. |
| Labor-page analytics beyond the single published quarter | One observation cannot support a trend; rendering one honestly is the requirement. |

### Added (required for the stated goals, previously missing)

1. **Derived → parent provenance fill.** Gold has no `source_name`/`source_url`
   columns; with a LEFT JOIN, derived rows would ship `NULL` source in the
   observations table *and in exports*. Resolve from
   `record_metadata.derived_from` (`_growth_records`/`_daily_return_records`),
   which is exactly what makes parent-source inheritance possible with no
   catalog row and no ETL change.
2. **Domain → page ownership as data + test.** The router registry becomes a data
   structure consumed by both `st.navigation` and a coverage test, so the dead
   `economy` domain and the `welfare`/`labor` unemployment split can never recur
   silently.
3. **Jalali display timezone policy.** Period ends are stored at UTC midnight
   (`annual_period_end`, `month_period_end`), where Tehran is +3:30 and the
   Jalali day is stable. Daily snapshot sources (TGJU) store a scrape instant,
   where it is **not** stable. The policy must be explicit and round-trippable.
4. **`poetry lock` refresh** alongside the Streamlit floor bump: `pyproject.toml`
   declares `^1.29.0` while `poetry.lock` already resolves 1.61.1, so editing the
   constraint invalidates the lock `content-hash`.
5. **A Wave-0 spike** proving the `AppTest` + router test path before Task 2
   lands, because the whole smoke suite depends on it.
6. **The dead-code decision** (`build_coverage_chart`, `available_domains()`,
   `list_indicators(search=…)`): wire or delete explicitly.
7. **An automatable "no English literal remains" guard** (AST scan of dashboard
   render paths) instead of a manual claim.

### Corrected

- `expected_frequency_map()` does **not** belong in `repository.py`: the
  repository is SQL-only by this plan's own layering rule. Source labels and
  expected update cadence live in `dashboard/labels.py`; the trading-session
  constant lives with `PERIODS_PER_YEAR` in `dashboard/components/quality.py`.
- `series_kind` is determined from `record_metadata.derived_from` (ETL-written,
  authoritative), **not** from the id's last segment — last-segment parsing
  misfires on level ids such as `TGJU.USD.FREE` and would need a per-source
  pattern list to stay correct.
- Chart/table scaling is **additive** (keep per-indicator facets as the default;
  add an opt-in overlay mode and caps), not a replacement of the default that
  every page and chart test renders through.
- The HBSIR page owns the whole `welfare` domain; the old page shrinks to
  `trade` + `energy`. Excluding non-HBSIR ids would leave population and IMF
  `LUR` homeless and break the ownership test.
- "No user-visible English string remains" is scoped to UI chrome: the label map
  deliberately falls back to the catalog `name` for unmapped ids, and
  `source_name`/`frequency`/`domain` are data.

### Verified in the codebase (evidence for the above)

- `dashboard/repository.py`: `load_series` inner-joins `IndicatorCatalog`; `name`,
  `source_name`, `source_url` come from the catalog, `unit`/`frequency`/`domain`
  from Gold. No `source_*` column exists on Gold.
- `dashboard/page_view.py::_derived_ids`: validates three hardcoded WB/TGJU
  candidates against the catalog frame, so the toggle is inert in production.
- `src/etl/pipeline.py::upsert_indicator_catalog`: the catalog is seeded only
  from `discover()`, which never emits derived ids.
- `src/etl/gold.py`: derived rows carry `record_metadata.derived_from` + `method`;
  level rows carry linking metadata only.
- `dashboard/components/exports.py::render_chart_downloads` calls
  `serialize_figure_images` (Kaleido + Chromium) on every render.
- `dashboard/components/quality.py`: `PERIODS_PER_YEAR["daily"] = 365.25`.
- `dashboard/pages/5_FX_Gold.py` → `render_fx_gold_page` renders the title twice.
- `pyproject.toml`: `streamlit = "^1.29.0"`; `poetry.lock`: 1.61.1 (installed
  version confirmed 1.61.1). `make typecheck` runs `mypy src/`; `make lint` runs
  `ruff check .`; coverage is `--cov=src`.
- Installed Streamlit `AppTest` documents the router path: initialize with the
  entrypoint (the file you would pass to `streamlit run`) and use
  `switch_page("pages/x.py")` + `run()` — so the existing smoke harness migrates,
  it is not replaced.
- `src/utils/persian.py` already localizes Jalali→Gregorian through
  `zoneinfo.ZoneInfo("Asia/Tehran")` and exposes `PERSIAN_MONTHS` (name → number)
  and `iranian_year_end()` — the display layer mirrors that convention and needs
  no new dependency.

---

## Task Description

Refresh the Phase 7 Streamlit dashboard so it reflects the platform as it exists
after Phases 4–6, and add full Persian (Farsi) localization with RTL support.

Phase 7 was built when the only data in the platform was World Bank (12 annual
indicators) and TGJU (3 daily FX/gold indicators). Since then, IMF (6), EIA (2),
SCI (14 active), TSETMC (4 series) and HBSIR (12) have landed. The catalog is now
expected to hold **50 active indicators across 9 domains**, plus **4 inactive SCI
base-year segments** and **≈38 derived Gold series** (both counts are indicative:
Task 28 re-derives them from a real run).

The dashboard has not kept pace: `labor` and `market` have no page at all,
derived series are unreachable, the information architecture is hardcoded to a
Phase 3-era domain list, and every user-facing string, chart label, table header
and export column is English.

```text
As an Iranian economic analyst
I want to explore every validated Gold series in Persian, in an RTL interface
So that the platform reflects all completed sources and my research outputs are
publication-ready in my own language
```

**Why now, and why before Phase 8:** Phase 8 (production readiness: CI/CD,
backup automation, performance) will harden whatever exists. Localizing and
expanding the dashboard afterwards means re-validating, re-documenting, and
possibly re-testing the same surfaces twice. Phase 7.1 also removes two live
defects that make the app slow (Chromium rendering on every rerun) and misleading
(false "missing periods" for TSETMC).

**PRD mapping:** Phase 7.1 is a scope addition between PRD §11 Task 18 (Phase 7
dashboard) and PRD §11 Tasks 19–20 (Phase 8 production readiness). It does not add
data sources, connectors, or pipelines. (The `Task N` numbers elsewhere in this
document always refer to this plan's own tasks below, never to PRD tasks.)

**Hard boundary:** Phase 7.1 changes **no file under `src/`**. It touches
`dashboard/`, `tests/`, `docs/`, and two lines of `pyproject.toml`
(`streamlit` floor, Persian-literal ruff ignores) plus the refreshed
`poetry.lock`. This is the strongest available statement that connectors, ETL,
schema, chain-linking and Gold semantics are untouched — and it is checkable:

```bash
git diff --name-only origin/development...HEAD | grep -c '^src/'   # must be 0
```

## Scope

### In Scope

- [ ] **Catalog-driven navigation.** An `st.navigation` router whose page
      registry (labels, order, groups, and the domains each page owns) is a single
      declaration, instead of implicit `pages/` discovery plus English filenames.
- [ ] **Persian localization** of all UI chrome: navigation, titles, subheaders,
      metrics, filters, warnings, empty states, buttons, table headers, chart
      labels/legends/axes, and export headers/file names.
- [ ] **RTL support**: sidebar and form direction, right-aligned numerics,
      Persian-capable typography for HTML surfaces and Plotly figures, and a
      documented posture for the LTR-only dataframe grid.
- [ ] **Display-direction Persian utilities**: ASCII→Persian digits, Persian
      thousands/decimal separators, Gregorian→Jalali conversion under an explicit
      timezone policy, Jalali month/period/year labels, and a digit-mode switch.
- [ ] **Coverage of all completed sources**: new **Market** (TSETMC) and
      **Labor** (SCI unemployment) pages; a dedicated **HBSIR Welfare & Survey**
      page (owning domain `welfare`) split out of "Trade, Welfare & Energy"; a CPI
      **decile** view.
- [ ] **Derived-series visibility end-to-end**, so `WB.*.YOY`, `IMF.*.YOY`,
      `EIA.*.YOY`, `SCI.*.YOY`, `TGJU.*.RET1D/.MA30` and
      `TSETMC.*.RET1D/.MA30/.ME` are selectable, labelled, source-attributed, and
      exportable.
- [ ] **Catalog metadata exploitation**: catalog-page search across
      id/name/unit/source/domain, base-year/segment provenance, and per-source
      freshness/staleness on the Overview.
- [ ] **UX and quality maturation** (bounded): bounded chart scaling, lazy chart
      image rendering, cache TTL + manual refresh, correlation overlap guards,
      trading-calendar-aware expected-period counts.
- [ ] **Localized test coverage**: `AppTest` assertions on Persian labels,
      fixtures for derived/orphan rows and a future-dated (IMF) row, repository
      tests for the new join semantics, and an AST guard against untranslated
      literals.
- [ ] **Documentation**: `docs/phase-7.1/{README,IMPLEMENTATION,VALIDATION}.md`,
      plus corrections to the stale Phase 7 claims and the dashboard sections of
      `README.md` / `AGENTS.md`.

### Out of Scope

- [ ] Any new connector, source, pipeline, or Airflow DAG.
- [ ] **Any change under `src/`** — including propagating IMF `observation_type`
      into Gold (that is the deferred forecast-labeling item).
- [ ] New analytical transformations, including index-to-100 and normalized
      comparison modes.
- [ ] OPEC basket, CBI TSD, and the deferred TSETMC metrics (trading value,
      market P/E, market cap) — recorded deferrals, not missing functionality.
- [ ] A monetary-domain page (no monetary indicators exist).
- [ ] Forecasting models, ML training, or any inference feature.
- [ ] Authentication, multi-user authorization, cloud deployment, mobile design.
- [ ] Real-time/WebSocket updates; the UI still renders only what the last
      pipeline run wrote.
- [ ] Rewriting the repository, export, or quality layers (they are sound and
      reusable); replacing Streamlit or Plotly; building a custom JS frontend.
- [ ] Resampling, interpolation, or forward-filling of Gold data — unchanged.
- [ ] New database migrations, or new runtime dependencies (font stacks rely on
      the OS; `zoneinfo` and `jdatetime` are already available).

## Context

### Current state (observed)

Read from the code, not from the Phase 7 reports:

- **Structure:** `app.py` (shell + connection check) + implicit `pages/` nav
  (7 files, 5–10 lines each) + `page_view.py` (composition) + 4 components
  (filters, charts, exports, quality) + `queries.py` (`st.cache_data` wrappers) +
  `connection.py` (`st.cache_resource` pool) + `repository.py` (injected-session,
  read-only).
- **Data flow:** Gold **INNER JOIN** `IndicatorCatalog` for observations;
  `active_only=True` catalog queries; `DataCollectionLog` window function for
  per-source freshness. No interpolation or frequency conversion anywhere — the
  Phase 7 data contract holds and must stay.
- **Pages and the domains they hardcode:** Overview (all), Inflation
  (`inflation`), GDP & Economy (`gdp`, `economy`), Trade/Welfare/Energy
  (`trade`, `welfare`, `energy`), FX & Gold (`fx`, `gold`), Correlation (all),
  Data Catalog (all).
- **Catalog inventory:** 50 active indicators — World Bank 12, IMF 6, EIA 2,
  TGJU 3, SCI 14 (3 canonicals + 10 deciles + 1 quarterly unemployment), TSETMC 1,
  HBSIR 12 — over domains `gdp` (8), `inflation` (15), `trade` (4), `welfare`
  (15), `energy` (3), `fx` (1), `gold` (2), `labor` (1), `market` (1). Four SCI
  `B<year>` segments are seeded inactive. **No source emits `economy`**, so the
  GDP page claims a dead domain today.
- **Derived Gold series with no catalog row (≈38):** World Bank 12, IMF 2,
  EIA 2, TGJU 6, SCI 13, TSETMC 3. The catalog is seeded only from
  `connector.discover()`, which never emits derived ids; `load_series` inner-joins
  the catalog; `page_view._derived_ids` validates candidates against the catalog
  and hardcodes three WB/TGJU patterns. The "Include derived series" checkbox is
  therefore inert in production and untested. Derived rows **do** carry
  `record_metadata.derived_from`, so they are discoverable from Gold alone.
- **Live defects:** `render_chart_downloads` renders PNG+SVG with Kaleido/
  Chromium **on every page render** (latency, and a hard page failure where no
  Chromium exists); `quality.expected_observation_count` uses 365.25 days/year, so
  TSETMC's ~250 trading sessions per year always appear ~30 % incomplete; the FX
  & Gold page renders its title twice; `st.cache_data` has no TTL or refresh
  control, so a pipeline run is invisible until the app restarts.
- **Dead code signalling unfinished work:** `available_domains()` /
  `cached_available_domains()`, `list_indicators(search=...)`,
  `build_coverage_chart`, and `build_chain_linking_chart` (called only from a unit
  test) are never used by a page.
- **Localization surface (measured):** ≈50 user-visible English literals across
  `app.py`, `page_view.py`, `filters.py`, `charts.py`, `exports.py`, `quality.py`,
  seven nav labels from filenames, plus data-level English in catalog
  `name`/`description`, `unit`, `source_name`, `domain`/`frequency` slugs and
  `DataCollectionLog.status`. `src/utils/persian.py` is ingestion-direction only
  (Persian→ASCII digits, Jalali→Gregorian with `Asia/Tehran` localization); the
  display direction is absent.
- **Environment:** Streamlit **1.61.1** installed (so `st.Page`/`st.navigation`
  and `AppTest.switch_page` are available) while `pyproject.toml` declares
  `streamlit = "^1.29.0"` — the declared floor does not guarantee the router API,
  and `poetry.lock` already pins 1.61.1.
- **Tests:** `tests/unit/dashboard/` (13 files) uses a `FakeDashboardRepository`
  and `AppTest`; the page tests assert only `not app.exception`. No dashboard test
  mentions derived ids, Persian labels, orphan series, or forecast flags.
- **Gates:** `make check` = `format` + `lint` (`ruff check .`) + `typecheck`
  (`mypy src/` only) + `test` (`--cov=src --cov-fail-under=80`), so dashboard code
  is linted but neither type-checked nor coverage-measured today.

### Decisions taken by this plan

1. **Keep `st.navigation`, and declare the IA as data.** Verified rationale:
   (a) sidebar labels, icons, order and *grouping* are settable only per
   `st.Page` — `st.set_page_config(page_title=…)` affects the browser tab, not the
   sidebar label, and grouping has no alternative at all; (b) the smallest
   alternative (Persian filenames) trades an English-label problem for bidi/
   encoding and cross-platform git problems and still gives no grouping, while a
   manual sidebar-radio router loses URL routes, `st.page_link`, and per-page
   `AppTest`; (c) the testing path is officially supported in the installed
   version (`AppTest.from_file(entrypoint).switch_page("pages/x.py").run()`), so
   the existing suite migrates rather than being replaced. The page registry
   (path, i18n title key, icon, group, owned domains) is a module-level data
   structure so both `st.navigation` and the domain-coverage test consume the same
   declaration. Page files stay where they are, stay standalone-runnable, and keep
   the shared i18n key as both their nav label and their in-page title.
2. **Persian display names live in the presentation layer**
   (`dashboard/labels.py`), not in the catalog: no migration, no connector
   changes, reviewable as a diff, with an automatic fallback to the catalog `name`
   so an unmapped indicator never disappears. Moving the names into the catalog
   (`name_fa`/`description_fa` + `discover()` changes + Alembic) stays a deferred
   follow-up if translators need DB-driven labels.
3. **Derived-series visibility is solved dashboard-side, metadata-driven.** Derived
   rows are discovered from Gold via `record_metadata.derived_from` (never from a
   hardcoded id list, never from id parsing), labelled by a **suffix** map
   (`YOY`/`RET1D`/`MA30`/`ME`), and inherit `name`/`source_name`/`source_url` from
   their parent's catalog row. Gold stays the only analytical input; adding a new
   derivation strategy later needs no dashboard change.
4. **`load_series` becomes a LEFT JOIN** so derived (and orphan) Gold rows survive.
   Consequence, handled explicitly: `name`/`source_name`/`source_url` can be
   `NULL` for a genuinely orphan series, every consumer falls back to the label
   layer, and `_empty_series()` plus the integration fixtures change in the same
   commit.
5. **Jalali display mirrors the ingestion convention: `Asia/Tehran`.** A stored
   UTC instant is converted to Tehran wall-clock before its Jalali date is taken;
   a selected Jalali/Gregorian day in a filter means a **Tehran** day, whose
   inclusive UTC bounds are computed and shown back to the analyst. Period ends
   (UTC midnight) are unaffected; snapshot sources (TGJU) are protected from
   off-by-one-day labels. Storage and exports keep ISO-8601 Gregorian UTC values
   byte-for-byte; `zoneinfo` is stdlib, so no dependency is added.
6. **RTL posture for tables:** localized headers, Persian digits, Jalali dates and
   right-aligned numerics inside Streamlit's dataframe grid, whose column order
   stays LTR. A fully RTL HTML table is explicitly deferred (it would cost the
   built-in sort/search/CSV affordances).
7. **One locale.** Persian is the UI language; `i18n.py` is a single keyed catalog
   with no runtime switcher, because a second locale contradicts the "no English
   remains" goal and doubles maintenance. Keys are stable so an `en` catalog can be
   added later without touching call sites.
8. **No new runtime dependency and no vendored asset.** `jdatetime` (Jalali) and
   `zoneinfo` (timezone) are already available; typography is a font stack, not a
   webfont, so the app keeps working fully offline.

## Proposed Approach

Keep the Phase 7 layering (repository → components → composition → pages) and fix
the *presentation* layer, not the data layer:

1. **Spike first.** Prove the router/`AppTest` path and the lock step before
   anything depends on them.
2. **Router second.** One `st.navigation` call in `app.py`, driven by the page
   registry, becomes the single declaration of the information architecture and of
   domain ownership.
3. **Presentation modules third.** `i18n.py` (string catalog), `labels.py`
   (indicator/domain/source display names, derived suffix map, expected update
   cadence), `formatting.py` (Persian digits/separators, Jalali dates and periods
   under the Tehran policy). Nothing else may hold a user-visible literal or a
   name map.
4. **Repository hardening fourth.** Derived/orphan rows must survive the join and
   be identifiable and attributable; cache TTL and an explicit refresh must exist.
   This is what makes "Include derived series" actually work and stops stale
   frames.
5. **Page expansion fifth.** Market, Labor, HBSIR; decile view; additive scaling
   modes. Each new page is a composition of existing components plus the new
   presentation modules.
6. **Localization last within the refresh**, once every string has a single home:
   apply `t()` and the label/format layers across pages, charts, tables and
   exports, then a visual polish pass with real data.
7. **Validation throughout.** Extend the existing AppTest/repository test pattern,
   add the Jalali round-trip and domain-coverage tests, and add the AST guard that
   keeps untranslated literals out.

### Milestones

| Milestone | Tasks | Outcome | Effort |
|---|---|---|---|
| **0. Spike** | 1 | Router + `AppTest.switch_page` pattern and the lock step proven on a 2-page prototype | 0.5 d |
| **A. Foundations** | 2–9 | Catalog-driven router + registry, i18n/label/format layers, RTL + typography baseline, derived/orphan-aware repository with parent provenance, lazy chart rendering, calendar-aware quality | 5.5–6.5 d |
| **B. Coverage** | 10–16 | Market + Labor pages, HBSIR page (owns `welfare`), decile view, derived series exposed, additive chart/table scaling, refreshed Overview + domain ownership | 4.5–6 d |
| **C. Localization** | 17–22 | Persian UI, RTL, Jalali display + presets, localized charts/tables/exports, Polish pass | 4–5 d |
| **D. High-value UX** | 23–25 | Chain-linking transparency, correlation guardrails, catalog-page search | 1.5–2 d |
| **E. Docs & validation** | 26–28 | Phase 7.1 docs, corrected Phase 7 claims, localized/guard tests, analyst acceptance pass | 3–4 d |

**Total: ≈19–24 days** (was 24–35 before the review).

## Task Metadata

**Type:** Refresh / Localization (existing capability, expanded and localized)
**Complexity:** High
**Affected Areas:** `dashboard/` (router, pages, components, three presentation
modules, one new `direction` component), `tests/`, `docs/`,
`pyproject.toml` (Streamlit floor + Persian-literal ignores), `poetry.lock`
**Dependencies:** Phase 7 dashboard; Gold data from World Bank, TGJU, IMF, EIA,
SCI, TSETMC, HBSIR pipelines; `jdatetime` + `zoneinfo`; Streamlit ≥1.36
(`st.Page`/`st.navigation`/`AppTest.switch_page`); `kaleido` + Chromium
(optional, for PNG/SVG)

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `docs/plans/phase-7-dashboard.md` — the original dashboard plan, scope, and
  documented limitations this phase supersedes.
- `docs/phase-7/{README,IMPLEMENTATION,VALIDATION}.md` — runbook, built features,
  and validation record (contains statements this phase must correct).
- `dashboard/app.py`, `dashboard/page_view.py`, `dashboard/repository.py`,
  `dashboard/queries.py`, `dashboard/connection.py` — the surfaces being changed.
- `dashboard/components/{filters,charts,exports,quality}.py` — every hardcoded
  literal, the chart builders, the export serializers, and the buggy
  `PERIODS_PER_YEAR["daily"]`.
- `dashboard/pages/*.py` — the hardcoded domain tuples and default indicators.
- `tests/unit/dashboard/app_smoke.py` — the `FakeDashboardRepository` seam and
  `app_test()` helper that becomes `AppTest.from_file(app).switch_page(...)`.
- `tests/integration/test_dashboard_repository.py` — seeded catalog/Bronze/Silver/
  Gold rows in a rolled-back transaction; the pattern for the new join-semantics
  and provenance tests.
- `docs/phase-2/data_dictionary.md` — observed coverage, units, domains and known
  gaps per source; the authoritative inventory of what Gold contains.
- `src/database/schema.py` — `GoldAnalytical`, `IndicatorCatalog`,
  `DataCollectionLog`, and the `record_metadata`/`metadata` naming rule.
- `src/etl/gold.py` — derived-id construction (`_namespaced`,
  `derived_growth_indicator_id`, `RET1D`/`MA30`/`.ME` helpers), the
  `record_metadata.derived_from` contract, and Gold metadata composition.
- `src/utils/persian.py` — the digit tables, `PERSIAN_MONTHS` (name → number, in
  month order), `iranian_year_end()`, and the `Asia/Tehran` localization the
  display layer must mirror.
- `src/etl/pipeline.py` — `SourceSpec` and `upsert_indicator_catalog`/
  `update_catalog_availability`: why derived ids have no catalog rows today.
- `Makefile` — `check`/`typecheck`/`lint`/`test` targets (dashboard is linted but
  not type-checked or coverage-measured).
- `pyproject.toml`, `poetry.lock` — the Streamlit floor, the ruff per-file-ignores
  block, and the resolved 1.61.1 the lock already pins.
- `AGENTS.md` — naming, `record_metadata`, timezone, no-interpolation and
  blocked-source rules that this phase must continue to honour.

### Data / ML References

- Connector registries (the only source of indicator names, units and domains):
  `src/connectors/world_bank.py` (`INDICATOR_DOMAINS`),
  `src/connectors/imf.py` (`IMF_INDICATORS`),
  `src/connectors/eia.py` (`EIA_INDICATORS`),
  `src/connectors/tgju_scraper.py` (`INDICATOR_REGISTRY`),
  `src/connectors/sci_scraper.py` (`SCI_INDICATOR_REGISTRY`,
  `SCI_CANONICAL_INDICATORS`),
  `src/connectors/tsetmc.py` (`TSETMC_INDICATORS`),
  `src/connectors/hbsir.py` / `hbsir_parser.py` (`DEFAULT_INDICATORS`,
  `INDICATOR_UNITS`).
- `docs/phase-2/data_dictionary.md` §"SCI Indicators", §"TSETMC Indicators",
  §"HBSIR Indicators", §"Chain-linking and base years", §"Forecast convention" —
  live-observed coverage, real session counts to calibrate against, and the
  wording for caveats the UI must repeat.
- `src/etl/frequency.py` — month-end semantics behind `TSETMC.TEDPIX.ME`, which
  the Market page must present without implying a continuous monthly series.
- `src/etl/silver.py` — where `observation_type`/`allow_future` is recorded (Silver
  only; the reason forecast labeling is deferred).

### External Documentation

- Streamlit `st.Page` / `st.navigation`:
  https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation —
  page titles/labels/icons/sections are configurable per `st.Page`, the entrypoint
  becomes the router, and pages are executed with `pg.run()`.
- Streamlit automatic labels from filenames:
  https://docs.streamlit.io/develop/concepts/multipage-apps/overview — numeric
  prefixes are stripped and underscores become spaces, which is why today's nav
  labels are English and why they must move to `st.Page(title=…)`.
- Streamlit app testing:
  https://docs.streamlit.io/develop/api-reference/app-testing — `AppTest` renders
  one page at a time; for a `st.navigation` app you initialize with the entrypoint
  and call `switch_page()` then `run()`.
- Plotly static image export: https://plotly.com/python/static-image-export/ —
  PNG/SVG requires Kaleido plus a Chromium executable, motivating lazy rendering
  and the existing `DASHBOARD_CHROME_PATH` override.
- `jdatetime`: `jdatetime.date.fromgregorian(date=…)` for the display direction.
- Python `zoneinfo` (stdlib): the `Asia/Tehran` zone already used by
  `src/utils/persian.py`.

### Patterns to Follow

**Naming:** snake_case modules/functions, PascalCase classes, no user-visible
literal outside `dashboard/i18n.py`, no name map outside `dashboard/labels.py`, no
display formatting outside `dashboard/formatting.py`.

**Structure:** keep the Phase 7 layering — repository (SQL only), components
(pure), `page_view.py` (composition), `pages/*.py` (thin delegates). New pages add
a delegate plus a `page_view` function; they do not add SQL. No page module calls
`st.set_page_config` (the router owns it).

**Testing:** unit tests with injected sessions/DataFrames and `AppTest`; no
network, no live database, no Streamlit server; integration tests marked
`pytest.mark.integration` with rolled-back transactions.

**Data:** Gold is the only analytical input; timestamps stay timezone-aware UTC
and Gregorian in storage; `Asia/Tehran` + Jalali and Persian digits are a
**display** concern; nothing is interpolated, forward-filled, or resampled.

**Localization:** Persian is the default UI language; every translated literal is
keyed and testable; the English catalog metadata remains the canonical, auditable
value and is preserved in exports alongside the display form.

---

## IMPLEMENTATION PHASES

### Wave 0: Spike
Prove the router/`AppTest` path and the lock behaviour on a throwaway prototype
before any real task depends on them, with a documented fallback.

### Wave A: Foundations
Bump the Streamlit floor, add the router + page registry, and create the three
presentation modules plus the RTL baseline. Harden the repository for
derived/orphan visibility, parent provenance and cache freshness. Make chart image
rendering lazy. Fix the calendar-blind expected-period count.

### Wave B: Coverage
Add and reorganize pages (Market, Labor, HBSIR Welfare & Survey), add the decile
view, expose derived series with provenance, make scaling additive, and refresh
the Overview with domain ownership and staleness.

### Wave C: Localization
Apply the string catalog, label layer and formatters across navigation, filters,
charts, tables and exports; add Jalali-aware date presets; polish with real data.

### Wave D: High-value UX
Surface chain-linking transparency, add the correlation overlap guard and matched
observation counts, and wire catalog-page search.

### Wave E: Validation
Static checks, the AST literal guard, localized AppTest assertions, repository
integration tests, the full pipeline run, and the analyst browser acceptance pass
recorded in `docs/phase-7.1/VALIDATION.md`.

---

## STEP-BY-STEP TASKS

Execute in dependency order. Each task ends with a validation command. Wave
letters match the milestone table. Independent tasks are marked **[parallel]**.

### 1. (0) SPIKE the router/AppTest path and the dependency step

- **IMPLEMENT:** On a throwaway branch, create a two-page `st.navigation`
  prototype over two existing page files and verify: `AppTest.from_file(
  "dashboard/app.py").run()` renders the default page; `.switch_page(
  "pages/2_Inflation.py").run()` renders the second page and its assertions work;
  a monkeypatched `dashboard.queries.repository_session` still applies through the
  router. Then raise the `pyproject.toml` Streamlit constraint to `^1.36` in a
  scratch commit and record exactly what `poetry lock` / `poetry install` do
  (`poetry.lock` already resolves 1.61.1). Write the findings into the task log
  that will become `docs/phase-7.1/IMPLEMENTATION.md`.
- **PATTERN:** Streamlit `AppTest` documentation for multipage/`st.navigation` apps
  (entrypoint + `switch_page`).
- **DEPENDENCIES:** None. Blocks Task 2 and Task 27.
- **GOTCHA:** `AppTest` renders one page at a time and `switch_page` paths are
  relative to the *main script's* directory (`pages/…`, not `dashboard/pages/…`).
  If the spike cannot exercise a page through the router, the fallback is to keep
  `app_test()` targeting page files directly and test the router's registry with
  plain unit tests — record which path was chosen before Task 2 starts.
- **VALIDATE:** the prototype commands above, transcribed with real output into
  the implementation notes; `poetry check`.

### 2. (A) REPLACE implicit page navigation with an `st.navigation` router and a page registry

- **IMPLEMENT:** In `dashboard/app.py`: `st.set_page_config(...)` (shell chrome
  only), then a module-level `PAGES` registry — `(file path, i18n title key, icon,
  group, owned domains, default indicators)` per page — then
  `st.navigation({group: [st.Page(...), ...]}, position="sidebar")` and
  `pg.run()`. Owned domains: Overview/Correlation/Catalog own none (all-domain
  views); Inflation `("inflation",)`; GDP `("gdp",)` (**drop the dead `economy`**);
  Trade & Energy `("trade", "energy")`; FX & Gold `("fx", "gold")`; Market
  `("market",)`; Labor `("labor",)`; Welfare & Survey `("welfare",)`. Render the
  database-status check in the sidebar so it does not push page content down.
  Raise the declared floor in `pyproject.toml` to `streamlit = "^1.36"` and commit
  the refreshed `poetry.lock`.
- **PATTERN:** Streamlit `st.Page`/`st.navigation` docs (see External
  Documentation); existing `dashboard/connection.py::test_connection()`; the
  registry-dict style of the connector modules for `PAGES`.
- **DEPENDENCIES:** Task 1 (spike), Task 3 (label keys — an English placeholder key
  is acceptable for this task's own commit).
- **GOTCHA:** Page paths in `st.Page` are relative to the entrypoint
  (`dashboard/app.py`), not the repository root; keep `pages/` as content modules
  and do not move them. With the router active, `pages/` auto-discovery is
  disabled — the registry is now the only IA declaration, so a missing entry is a
  missing page. Executing a page inside the router means page modules must not call
  `st.set_page_config`. Keep each page's in-page title and its nav label on the
  *same* i18n key so they cannot drift, and keep page modules runnable standalone
  (they must render their own title) so the Wave-0 fallback test path stays alive.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard -q --no-cov` and
  `poetry run streamlit run dashboard/app.py --server.headless true`.

### 3. (A) [parallel] CREATE the UI string catalog (`dashboard/i18n.py`)

- **IMPLEMENT:** One module holding every user-visible string keyed by a stable
  identifier, Persian only, plus `t(key, **kwargs)`. Cover navigation labels, page
  titles, subheaders, metric labels, filter labels, warnings, empty states, button
  labels, table headers, chart labels, and file prefixes. Keep the key namespace
  aligned with the page registry (`nav.<page>`, `page.<page>`, `filter.*`,
  `chart.*`, `table.*`, `export.*`, `empty.*`, `warn.*`).
- **PATTERN:** `src/utils/config.py` / `src/utils/logging.py` (single home for a
  cross-cutting concern, typed, no I/O).
- **DEPENDENCIES:** None.
- **GOTCHA:** Persian string literals trip ruff `RUF001`/`RUF002`/`RUF003`. Add
  this module (and `dashboard/labels.py`) to `[tool.ruff.per-file-ignores]` in
  `pyproject.toml`; `src/utils/persian.py` and `src/connectors/sci_parser.py` are
  the existing precedent. `make lint` runs `ruff check .`, so any Persian literal
  added to a page or component file fails the build — call `t()` instead. Keep the
  catalog flat and keyed; do not build locale machinery (decision 7).
- **VALIDATE:** `poetry run ruff check dashboard pyproject.toml` and
  `poetry run pytest tests/unit/dashboard/test_i18n.py -q`.

### 4. (A) CREATE the presentation-name layer (`dashboard/labels.py`)

- **IMPLEMENT:** (a) every active `indicator_id` → Persian display name;
  (b) `domain` → Persian label + display order; (c) `source_name` → Persian label +
  **expected update cadence** (used for Overview staleness; presentation metadata,
  so it lives here, not in the repository or `src/`); (d) **derived-id suffix →
  label fragment** (`YOY` → رشد سالانه, `RET1D` → بازده روزانه, `MA30` → میانگین
  متحرک ۳۰ روزه, `ME` → ماهانه). Expose
  `indicator_label(indicator_id, catalog_name=None, derived_from=None)`,
  `domain_label()`, `source_label()`, `source_expected_cadence()`,
  `derived_label(suffix)`, and `is_derived(record_metadata)`. Every accessor falls
  back to the catalog value or the raw id so unmapped indicators are never hidden;
  derived labels compose as `indicator_label(parent) + " – " + derived_label(suffix)`.
- **PATTERN:** registry-dict style of the connector modules
  (`TSETMC_INDICATORS`, `SCI_CANONICAL_INDICATORS`) — a frozen mapping, not
  scattered conditionals.
- **DEPENDENCIES:** Task 3.
- **GOTCHA:** The deliverable is the map: coverage of all 50 active ids + every
  derived suffix. There is no second English name map (decision: the catalog
  `name` already is the English value). `is_derived` must read the Gold row's
  `record_metadata["derived_from"]` (the JSONB column, `metadata` in SQL) and
  never parse the id, so new derivation strategies need no dashboard change
  (`TGJU.USD.FREE` has no derived suffix yet is a level series). Never write translated
  text into Gold or any pipeline table — display names are read-only presentation.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_labels.py -q`,
  asserting 100 % coverage of the connector registries and every derived suffix
  plus the fallback path for an unknown id/domain/source.

### 5. (A) [parallel] CREATE display formatters (`dashboard/formatting.py`)

- **IMPLEMENT:** Pure functions for: ASCII→Persian digits (build the reverse of
  `PERSIAN_TO_ASCII`); Persian thousands/decimal separators (`٬`, `٫`);
  **`to_tehran(value)` → `gregorian_to_jalali(value)` → `jalali_date_label()`**
  under the Asia/Tehran policy (decision 5); Jalali month names derived from the
  ordered `PERSIAN_MONTHS` map rather than a duplicated literal list;
  `jalali_year_label()` (Jalali year containing the period end, with the Gregorian
  year available alongside); `tehran_day_bounds(day) -> (start_utc, end_utc)`
  inclusive bounds for filters; percentage and large-number formatting; period-end
  labelling for annual/monthly/quarterly series; and a digit-mode switch so Latin
  numerals remain available for exports and tests.
- **PATTERN:** `src/utils/persian.py` (pure, typed, docstring-with-examples) — and
  mirror its `Asia/Tehran` localization so ingestion and display agree.
- **DEPENDENCIES:** None.
- **GOTCHA:** Do not change `src/utils/persian.py` semantics — it is the ingestion
  contract used by the TGJU/SCI parsers; import from it. Display formatting must
  round-trip: the ISO Gregorian value stays the source of truth in every export,
  and `tehran_day_bounds` must round-trip (Jalali day in → UTC bounds → same Jalali
  day out) including a TGJU-style evening instant. Use `zoneinfo`, not a hardcoded
  +3:30 offset.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_formatting.py -q`
  with border cases: leap Esfand, HBSIR Esfand-year-end (via `iranian_year_end`),
  Dec-31 annual period ends, evening UTC instants, month-end periods, negatives,
  `None`.

### 6. (A) ADD the RTL and Persian typography foundation

- **IMPLEMENT:** Add `.streamlit/config.toml` (theme base, primary color, font
  baseline) and `dashboard/components/direction.py` that injects scoped CSS once
  per run: `direction: rtl` + text alignment for the sidebar, headings, markdown
  blocks, form labels and metric blocks; a Persian font stack (`Vazirmatn`,
  `IRANSans`, `Tahoma`, `sans-serif`). Set Plotly's default font family/color once
  via a `plotly_template()` helper so figures inherit Persian-capable typography.
- **PATTERN:** `dashboard/connection.py` (one module owning one cross-cutting
  concern behind a cached accessor that pages import).
- **DEPENDENCIES:** Task 2 (the router frame is the natural injection point).
- **GOTCHA:** No webfont, no CDN, no vendored font file — the app must work fully
  offline on an analyst laptop (decision 8); OS fallback covers missing fonts.
  Streamlit has no RTL mode, so this couples to DOM internals
  (`[data-testid="stSidebar"]`, `[data-testid="stMarkdownContainer"]`, …) that
  change between releases: name the selectors in one place, scope rules narrowly,
  and do not flip the whole flex tree (it breaks Plotly sizing).
- **VALIDATE:** manual visual check at `localhost:8501` plus an `AppTest` smoke
  test asserting the page renders and the injection helper is callable.

### 7. (A) [parallel] HARDEN the repository: derived/orphan visibility, parent provenance, cache freshness

- **IMPLEMENT:** In `dashboard/repository.py`:
  (a) change `load_series` to a **LEFT JOIN** on `IndicatorCatalog` and add
  `has_catalog_metadata` (orphan flag) and `series_kind` (`level`/`derived`) —
  `series_kind` from `record_metadata ->> 'derived_from'`, never from the id;
  (b) add a second aliased LEFT JOIN on the catalog keyed by
  `coalesce(record_metadata ->> 'derived_from', indicator_id)` and select
  `coalesce(catalog.name, parent.name)` etc., so **derived rows carry their
  parent's `name`, `source_name` and `source_url`** and only a genuinely orphan
  series is `NULL`; fall back to post-processing in pandas if the aliased join
  proves awkward, keeping the frame contract identical;
  (c) add `list_derived_ids(parent_ids)` that discovers derived Gold ids from
  `gold_analytical` (no catalog, no hardcoded id list) so the UI toggle resolves
  dynamically;
  (d) keep `list_indicators` as-is but rely on its existing `active_only=False` for
  the segment view. In `dashboard/queries.py` add `ttl=` to every `st.cache_data`
  wrapper plus `clear_dashboard_cache()`.
- **PATTERN:** existing repository query style (`select()`, `_frame()` shaping,
  `_empty_series()` column contract — extend it with the new columns); SQLAlchemy
  2.0 `aliased` + JSONB `->>` access.
- **DEPENDENCIES:** None. Nothing here is presentation, so it is fully parallel
  with Tasks 3–6.
- **GOTCHA:** The LEFT JOIN means a Gold row can now arrive with `name`/
  `source_name` = `NULL`; `_empty_series()` and the integration seed fixtures must
  change in the same commit or the export column contract breaks silently.
  `build_time_series_chart`'s `row.get("name", row["indicator_id"])` returns the
  string `"None"` for a present-but-null column — fix that to a `pd.isna` check.
  Do **not** put expected-frequency knowledge in SQL (decision/`expected_cadence`
  lives in Task 4).
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_repository.py
  tests/integration/test_dashboard_repository.py -q --cov-fail-under=0` plus new
  cases: derived row keeps parent provenance, orphan row is flagged and not
  dropped, `list_derived_ids` per source shape, `_empty_series()` contract.

### 8. (A) [parallel] MAKE chart image export lazy and failure-tolerant

- **IMPLEMENT:** Stop calling `serialize_figure_images` during page render. Render
  HTML downloads eagerly (cheap, no browser) and PNG/SVG behind an explicit control
  (expander/button) that renders on demand and caches per figure hash; when
  Chromium is unavailable, disable the buttons with the actionable
  `DASHBOARD_CHROME_PATH`/`plotly_get_chrome` message instead of raising. Convert
  `find_chromium_executable()`'s `RuntimeError` into a probed capability flag.
- **PATTERN:** the existing `exports.find_chromium_executable()` message text;
  `render_data_downloads` for the button layout.
- **DEPENDENCIES:** Task 7 for `clear_dashboard_cache()` (interface can be agreed
  first, so this stays parallel).
- **GOTCHA:** `tests/unit/dashboard/app_smoke.py` currently monkeypatches
  `render_chart_downloads` away entirely; keep a seam so page tests stay
  browser-free, and add the first test that exercises the disabled-without-Chromium
  path. Do not delete `serialize_figure_images` — it is the on-demand path.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard -q --no-cov` and a manual
  page-load timing check with and without `DASHBOARD_CHROME_PATH` set.

### 9. (A) [parallel] FIX expected-period counts to be calendar-aware

- **IMPLEMENT:** Make `expected_observation_count` calendar-aware: for `daily`
  market sources use a trading-session expectation (documented constant next to
  `PERIODS_PER_YEAR`, calibrated against TSETMC's observed ~250 sessions/year)
  instead of 365.25; keep month/quarter/year counts exact at period-end. Label the
  column as an estimate and only warn when the gap is material.
- **PATTERN:** the existing `PERIODS_PER_YEAR` mapping (extend it; do not bypass
  it); `docs/phase-2/data_dictionary.md` for the real session counts.
- **DEPENDENCIES:** None.
- **GOTCHA:** The current model produces a systematic false "missing periods"
  warning for every TSETMC daily series (~30 %); calibrate against observed counts
  (4,285 sessions since 2008-12-04) rather than an assumed constant, and keep
  monthly/quarterly/annual expectations unchanged. Do **not** add Gold-level
  outlier/validation surfacing — that data is not in Gold (deferred).
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_quality.py -q` with
  daily/annual/monthly/quarterly cases plus a TSETMC-like session-count case
  asserting no spurious warning.

### 10. (B) ADD the Market (TSETMC) page

- **IMPLEMENT:** `dashboard/pages/*_Market.py` + `render_market_page()` covering
  `TSETMC.TEDPIX` (daily level), `RET1D`, `MA30`, and `.ME` (month-end): level
  panel, return panel, moving-average overlay, month-end comparison, session-count
  and gap notes, and a warning that `RET1D`/`MA30`/`.ME` are platform-computed and
  not official TSETMC series (copy exists in the data dictionary).
- **PATTERN:** `page_view.render_domain_page` composition; the FX & Gold page's
  snapshot-warning pattern for source caveats.
- **DEPENDENCIES:** Tasks 2, 4, 7, 15.
- **GOTCHA:** Trading days are absent, not zero; do not plot `RET1D`/`MA30` on the
  same axis as the index level without the Task 15 overlay rules. `MA30` has no
  first 29 sessions — the UI must not imply a gap. `.ME` is a month-end
  downsample, not a continuous monthly series.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_market.py -q` and
  a manual check with the live-run counts (4,285 sessions / 4,284 / 4,256 / 214).

### 11. (B) ADD the Labor page

- **IMPLEMENT:** A page for `SCI.UNEMPLOYMENT.QUARTERLY` (quarterly, domain
  `labor`), showing the single-observation reality explicitly (only spring 1405 is
  published) as a table/marker. World Bank population context (`SP.POP.TOTL`,
  `SP.POP.GROW`) belongs to the Welfare page, where its `welfare` domain already
  puts it; IMF `LUR` likewise.
- **PATTERN:** domain page composition; `quality` sparse-history warning.
- **DEPENDENCIES:** Tasks 2, 4.
- **GOTCHA:** One published quarter must not render as an implied trend, and no
  analytics are built on it. Do not merge IMF `LUR` here — it is domain `welfare`,
  and the ownership test in Task 16 asserts that.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_labor.py -q`.

### 12. (B) SPLIT the HBSIR Welfare & Survey page out of "Trade, Welfare & Energy"

- **IMPLEMENT:** New page owning domain `welfare`: HBSIR `GINI`, `POVERTY.RATE` and
  `INCOME.DECILE.D1…D10` emphasis sections (Gini and poverty trend, decile-share
  chart, Jalali-year x-axis, survey-year metadata panel, and the explicit note that
  the poverty rate is **relative** — `k × weighted median`, recorded per
  observation) plus the generic domain composition for the remaining `welfare`
  members (population, IMF `LUR`). Reduce the old page to `trade` + `energy` and
  keep HBSIR caveats off it.
- **PATTERN:** `render_domain_page` for the generic members plus a dedicated
  composition function for the HBSIR sections; `iranian_year_end()` for the survey
  year convention.
- **DEPENDENCIES:** Tasks 2, 4, 5 (Jalali axis), 7.
- **GOTCHA:** HBSIR survey years are stored as Gregorian year-ends of the Jalali
  year with the Jalali year only in Silver metadata; label them by the Jalali year
  **containing the stored period end** (Task 5), which round-trips exactly for
  Esfand 29/30 and needs no Silver read. Excluding non-HBSIR ids would leave
  population/`LUR` unowned and break Task 16's coverage test — the page owns the
  whole domain and emphasises HBSIR by layout.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_welfare.py -q`.

### 13. (B) ADD the CPI decile analysis view

- **IMPLEMENT:** On the Inflation page, add a decile view: a decile selector
  (D1…D10 or "all") with a small-multiples or single-chart comparison (deciles
  share one unit, so a **plain overlay** is correct — no normalization), plus the
  canonical urban/national/rural chain-linked comparison. Do not force 10 facets
  into the generic multi-indicator chart.
- **PATTERN:** `build_time_series_chart` for the canonical comparison; the small
  multiples mode from Task 15 for the decile grid.
- **DEPENDENCIES:** Tasks 7, 15.
- **GOTCHA:** Decile ids are 10 separate catalog indicators with identical units
  and a shared base year — the view must make the relationship obvious rather than
  presenting 10 unrelated series. Phase 7 docs still call deciles "deferred"; this
  task and Task 26 correct that.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_economy.py -q`
  (extended) and a manual render with 10 deciles selected.

### 14. (B) EXPOSE derived series end-to-end

- **IMPLEMENT:** Replace `page_view._derived_ids` with a helper that (a) asks the
  repository (Task 7c) for the derived ids of the selected parents, (b) labels them
  via Task 4's suffix map, and (c) never appends an id that is already selected.
  The "Include derived series" toggle then resolves dynamically for all six
  prefixes, and derived rows flow through charts, the observations table and
  exports like any other series — with their parent's unit/domain/frequency and
  parent-inherited source provenance (Task 7b).
- **PATTERN:** `src/etl/gold.py::_namespaced` / `derived_growth_indicator_id` for
  the id shapes the discovery must recognise.
- **DEPENDENCIES:** Tasks 4, 7.
- **GOTCHA:** Keep the toggle off by default (mixed level+rate charts confuse) and
  make its effect visible in the legend. No id-pattern list may be introduced:
  derived-ness comes from `record_metadata.derived_from` and the suffix from the
  id's last segment *only for rows already known to be derived*.
- **VALIDATE:** new unit tests asserting that a parent with a derived Gold row
  yields the derived id for every source shape (WB/IMF/EIA/SCI/TGJU/TSETMC), that
  an unknown suffix is ignored, and that a repeated selection is not duplicated;
  plus the repository discovery test from Task 7.

### 15. (B) MAKE chart and table scaling bounded — additively

- **IMPLEMENT:** Keep per-indicator facets as the **default** mode (already
  unit-safe: one y-axis per panel) and add: (a) an opt-in single overlaid chart
  with unit-aware axis labelling for series sharing a unit; (b) an optional
  small-multiples mode capped at a documented series count; (c) a bounded height
  heuristic replacing `230 px × indicator count`; (d) a capped observations table
  with a documented row limit and a "narrow the date range" hint, keeping
  timezone-aware, Jalali-formatted timestamps. **No normalization or index-to-100
  mode** (deferred). Settle `build_coverage_chart` here: wire it (e.g. as the
  Overview's per-domain coverage chart) or delete it together with its unit test —
  leaving it unused with tests around it is not acceptable.
- **PATTERN:** `build_time_series_chart` (panel logic); `docs/phase-7/README.md`
  §"Filters And Exports" (the no-normalization rule, which this task preserves).
- **DEPENDENCIES:** Tasks 5, 7.
- **GOTCHA:** Every page renders through `build_time_series_chart`, so the default
  path and its tests must be untouched; the new modes are opt-in only. Mixed-unit
  selections must fall back to facets with a visible note rather than a shared
  axis.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_charts.py -q` plus a
  manual render with 15+ indicators selected.

### 16. (B) REFRESH the Overview and settle domain ownership

- **IMPLEMENT:** Rebuild Overview around: per-source freshness from
  `DataCollectionLog` **with staleness against the expected cadence** (Task 4's
  cadence map), per-domain indicator counts with `st.page_link` into the owning
  page, a collection-log table, and explicit counts of derived/orphan series that
  have no catalog row. Record the domain decisions: `economy` is dead and removed
  from the GDP page; IMF `LUR` (welfare) and SCI unemployment (labor) stay in their
  source-assigned domains with the page ownership declared in Task 2's registry.
  Settle the remaining dead code here: wire `available_domains()` /
  `cached_available_domains()` into the per-domain counts or delete both and their
  tests — the per-domain counts must come from one query either way.
- **PATTERN:** existing `source_freshness()` window query; `st.page_link` for
  navigation (works with the Task 2 router); the registry as the ownership source
  of truth.
- **DEPENDENCIES:** Tasks 2, 3, 4, 7.
- **GOTCHA:** Replace the "Key indicators" whole-catalog dump with counts plus
  links (it scales badly). AGENTS.md requires freshness to be tracked against
  expected frequency — this is the first place it becomes visible to an analyst;
  label it as a dashboard convention since the platform does not store it yet.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_overview.py -q`
  plus a seeded integration check of the staleness calculation, and the
  domain-ownership test (Task 27) asserting every active domain is claimed by
  exactly one page and that no page claims a domain with no active indicators.

### 17. (C) LOCALIZE navigation, page chrome, and states

- **IMPLEMENT:** Route every literal identified in the audit through `t()`:
  navigation labels and icons (Task 2), page titles and subheaders, metric labels,
  checkbox/expander labels, warnings, empty states, and the database-status banner.
  Remove the duplicate `st.title("FX & Gold")` on the FX & Gold path.
- **PATTERN:** `dashboard/i18n.py` (Task 3); no literal may survive outside it.
- **DEPENDENCIES:** Tasks 2, 3, 4.
- **GOTCHA:** Page titles are both the nav label and the in-page `st.title`; keep
  one i18n key per page so they cannot drift. Watch the ruff literal whitelist when
  editing component files — call `t()` rather than adding inline Persian to
  non-whitelisted modules.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard -q --no-cov` with new
  assertions on Persian titles (e.g. `app.title[0].value == t("page.inflation")`).

### 18. (C) LOCALIZE filters and add Jalali-aware date selection

- **IMPLEMENT:** Localize Domain/Frequency/Source/Indicators labels and their
  option values via the label layer — the *underlying* values stay raw slugs so the
  SQL is unchanged. Add Jalali convenience to the date range: Jalali year/month
  **preset** selectors (and a Jalali text preset for a specific day) that resolve
  to the same UTC Gregorian bounds the repository expects, plus a visible Jalali
  **echo** of the resolved range and of the Gregorian bounds actually applied.
  `FilterState` keeps its exact contract.
- **PATTERN:** `as_utc_datetime` for bound construction; `formatting.to_tehran` /
  `tehran_day_bounds` / `gregorian_to_jalali` for display and bounds.
- **DEPENDENCIES:** Tasks 4, 5.
- **GOTCHA:** A display label is not a filter value: mapping Persian labels back to
  slugs must be exact or filters silently return nothing. Keep `st.date_input`
  (Gregorian) — do **not** build a custom Jalali date-entry widget (deferred) —
  and interpret the selected day as a **Tehran** day per decision 5, so an evening
  TGJU observation lands on the day the analyst expects. Keep the existing
  start ≤ end validation.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_filters.py -q` with
  round-trip tests (Jalali preset → UTC bounds → Jalali echo returns the same day,
  including an evening-UTC case) and a test that Persian labels never leak into
  query values.

### 19. (C) LOCALIZE charts

- **IMPLEMENT:** Persian axis titles, legends, hover templates, colorbar titles and
  facet titles; indicator display names (or the catalog `name` when Latin is
  requested) in legends and panel titles; Jalali date axis labels with a Gregorian
  echo in the hover template; digit-grouping via `formatting`; explicit unit
  wording from the Gold row or the parent row; the Task 6 Persian-capable
  `plotly_template()` applied to every figure.
- **PATTERN:** `dashboard/components/charts.py` pure-builder contract — builders
  receive already-prepared labels, so localization belongs in the caller or in
  small helpers, not in new data logic.
- **DEPENDENCIES:** Tasks 4, 5, 6.
- **GOTCHA:** Plotly numeric-axis tick labels render client-side; Persian digits
  there need an explicit tick-text/tickformat strategy (or pre-formatted labels).
  Test with long Persian strings — facet titles and legends wrap badly at width.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_charts.py -q`
  (extended with Persian/label assertions) plus a manual RTL/legend check.

### 20. (C) LOCALIZE tables

- **IMPLEMENT:** Replace raw column names with Persian headers through
  `st.column_config` (or a renamed, ordered display frame) for the catalog,
  coverage, freshness, quality and observations tables; render Persian digits and
  Jalali dates in cells; right-align numerics; keep the underlying keys available
  in exports.
- **PATTERN:** `page_view.render_catalog_page` / `render_quality_summary` display
  frames; `exports.prepare_export_frame` for the export-side naming.
- **DEPENDENCIES:** Tasks 3, 5.
- **GOTCHA:** Streamlit's dataframe grid (glide-data-grid canvas) is **LTR-only**:
  it cannot be flipped, cannot right-align per-direction automatically, and its
  column order stays left-to-right. Adopt the documented posture (localized headers
  + right-aligned numerics) and note it in the Phase 7.1 runbook, or the acceptance
  review will report it as a bug.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard -q --no-cov` plus a manual
  check that long Persian headers do not truncate critical metadata columns.

### 21. (C) LOCALIZE exports

- **IMPLEMENT:** Persian column headers and indicator names in CSV and Excel; a
  Jalali display date column **alongside** the ISO-8601 Gregorian timestamp (never
  replacing it); UTF-8 **with BOM** for CSV so Excel decodes Persian correctly;
  Persian sheet name and `rightToLeft` sheet direction for Excel; ASCII-safe file
  names with a Persian display label; keep `record_metadata`, `original_value`,
  `is_chain_linked` and confidence columns, and keep source provenance non-empty
  for derived rows (Task 7b). Export numbers default to **Latin digits** with a
  toggle for Persian digits, so spreadsheets and downstream tooling keep working.
- **PATTERN:** `serialize_csv`, `serialize_excel`, `prepare_export_frame`;
  `sheet_name="Selected data"` is the exact slot to localize.
- **DEPENDENCIES:** Tasks 4, 5, 7.
- **GOTCHA:** Browser downloads with Persian file names can be mangled by the
  client; prefer ASCII file names plus a Persian label/sheet name. BOM and RTL
  sheet direction must be verified in a real spreadsheet application — unit tests
  only assert bytes. The existing `serialize_csv` byte test changes (BOM); that is
  expected and must be updated deliberately.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_exports.py -q` plus a
  manual open of both files in Excel/LibreOffice with Persian indicator names.

### 22. (C) POLISH Persian typography and digits with real data

- **IMPLEMENT:** A final pass with a populated database: digit consistency across
  charts/tables/exports, percent and large-number formatting (Rial/US$ amounts),
  Persian punctuation in warnings, overflow/ellipsis review, spacing in RTL
  layouts, chart legend legibility, and the digit-mode switch (Persian default in
  the UI, Latin default in exports). Record every accepted deviation.
- **PATTERN:** the Phase 7 §"Manual Validation Status" style of recording what was
  and was not verified interactively.
- **DEPENDENCIES:** Tasks 17–21.
- **GOTCHA:** Record deviations rather than fixing them silently — the data grid's
  LTR column order and any label truncation are expected findings of this phase.
- **VALIDATE:** manual browser checklist recorded in
  `docs/phase-7.1/VALIDATION.md` §"Manual validation".

### 23. (D) ADD chain-linking transparency

- **IMPLEMENT:** Surface the already-written but unused `build_chain_linking_chart`:
  an original-vs-linked panel with confidence, base-year badges
  (`has_base_year_changes`), and for SCI the segment ancestry
  (`SCI.CPI.URBAN.B2016` + `B2021`) with the overlap documented. Add an "include
  inactive base-year segments" toggle on the catalog page (existing
  `active_only=False`) so the four seeded inactive rows are inspectable.
- **PATTERN:** `build_chain_linking_chart` (existing), `SCI_CANONICAL_INDICATORS`
  for segment metadata, `docs/phase-2/data_dictionary.md` §"Chain-linking and base
  years" for the wording.
- **DEPENDENCIES:** Tasks 4, 7.
- **GOTCHA:** Chain-linking is a core project principle and its audit fields already
  exist in Gold; **recompute nothing in the UI** — display `original_value`,
  `is_chain_linked`, `chain_linking_confidence` and `record_metadata` as stored.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_charts.py
  tests/unit/dashboard/test_app_catalog.py -q` plus a manual check on
  `SCI.CPI.URBAN` (533 level rows, 521 YoY).

### 24. (D) HARDEN the correlation page

- **IMPLEMENT:** Add a minimum-overlap guard (warn and suppress cells below a
  documented pair count), Persian labels for the heatmap axes (display names
  instead of ids), and a "matched observations" summary beside the existing
  join-count matrix. Keep the exact-timestamp join and its limitation visible.
- **PATTERN:** `CorrelationBundle` (figure + correlation + join counts);
  `quality.summarize_quality` for the accompanying panel.
- **DEPENDENCIES:** Tasks 4, 15.
- **GOTCHA:** The no-imputation rule is the reason exact-timestamp joins exist —
  keep that behaviour and make the *limitation* obvious rather than "fixing" it by
  resampling. A heatmap cell with `NaN` must read as insufficient overlap, not
  zero. Do not add a duplicate-timestamp warning (the premise is unverified and
  `aggfunc="first"` is already explicit) — add an invariant assertion in the test
  suite instead if the guarantee is wanted.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_correlation.py -q`
  extended with a low-overlap case asserting the warning.

### 25. (D) WIRE catalog-page search

- **IMPLEMENT:** Search on the catalog page only: a search box matching indicator
  id, Persian display name, catalog (English) name, unit, source and domain, with
  the match count and a clear-filters affordance. Include derived suffix labels in
  the search terms.
- **PATTERN:** `repository.list_indicators` (already selects `description` and
  `ilike`s id/name/description); `queries.cached_list_indicators` already takes
  `search` in its cache key.
- **DEPENDENCIES:** Tasks 4, 18.
- **GOTCHA:** Search must run against catalog values **and** the label layer, so a
  Persian needle is matched against display names in the frame; apply
  `normalise_digits` and a small character-normalization helper (ی/ي, ک/ك) to the
  *needle* only, never to stored data. Do not add search boxes to the domain pages
  (deferred). If this wiring is not shipped, `list_indicators(search=…)`'s unused
  search path and its cache-key parameter must be deleted instead — the query may
  not be left unused.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard/test_app_catalog.py -q`
  extended with search cases (id, Persian name, unit, no-match).

### 26. (E) UPDATE documentation and correct stale Phase 7 claims

- **IMPLEMENT:** Add `docs/phase-7.1/{README,IMPLEMENTATION,VALIDATION}.md`
  (runbook with the Persian page guide, what was built, the validation record, the
  spike outcome, the Jalali timezone policy, and the accepted deviations). Correct
  in `docs/phase-7/*`: the "CPI decile analysis … not loaded yet" and
  "Monetary-domain page" deferral notes (decile data exists since Phase 5), the
  implication that the chain-linking chart and derived growth series are surfaced,
  the test/coverage counts, and the page list. Update `README.md` (dashboard
  section, roadmap: Phase 7.1 row, status line, test counts), `AGENTS.md` (dashboard
  structure: router + registry, i18n/labels/formatting modules, `Asia/Tehran`
  display convention, the `src/` boundary) and `docs/phase-2/data_dictionary.md`
  where it points at dashboard pages. Record the deferred list from this plan
  verbatim in `docs/phase-7.1/`. Also record the quality-gate decision there
  (Open item 7): that `mypy src dashboard` was run for this phase and whether
  `make typecheck` was widened — the document must not leave the gate ambiguous.
- **PATTERN:** `docs/phase-6/{README,IMPLEMENTATION,VALIDATION}.md` and the Phase 7
  documents being corrected.
- **DEPENDENCIES:** All implementation tasks.
- **GOTCHA:** Documentation drift is a finding of this audit — the fix must be
  factual: no claim of a feature that is not reachable, an explicit note that IMF
  forecasts are **indistinguishable** in the UI, and an explicit list of what
  remains deferred (see [Deferred Scope](#deferred-scope-phase-72-candidates)).
- **VALIDATE:** manual review against the implemented UI; `make check` clean.

### 27. (E) EXTEND the test suite: localization, derived/orphan, Jalali round-trip, domain coverage, literal guard

- **IMPLEMENT:** Migrate `tests/unit/dashboard/app_smoke.py::app_test()` to the
  router entrypoint (`AppTest.from_file(app).switch_page(f"pages/{name}").run()`),
  keeping the direct-file path as the Wave-0 fallback. Extend
  `FakeDashboardRepository` with derived rows (carrying `derived_from`), a
  Gold-only orphan series, and one future-dated (IMF) row used only to prove that
  such a row renders like any other and that the indistinguishability disclaimer
  is shown — forecast labeling itself is deferred, so no forecast-specific
  behaviour is asserted. Add `test_formatting.py`,
  `test_labels.py` (100 % registry coverage + fallback), and `test_i18n.py` (every
  key resolves, no empty values). Add:
  (a) **Jalali round-trip** tests (Task 5/18 semantics, including an evening-UTC
  instant); (b) **domain-ownership** tests asserting every domain present in the
  active catalog is claimed by exactly one page in `PAGES` and that no page claims
  a domain with no active indicators; (c) an **AST literal guard** walking
  `dashboard/**/*.py` for string constants passed to Streamlit display functions
  (`title`, `subheader`, `metric`, `button`, `checkbox`, `multiselect`,
  `date_input`, `warning`, `info`, `error`, `download_button`) and flagging
  anything that is not `t(...)`/a variable, with an explicit allowlist for the
  documented data-level English (catalog names, slugs). Extend
  `tests/integration/test_dashboard_repository.py` for the LEFT JOIN, parent
  provenance fill, derived discovery, orphan reporting and staleness.
- **PATTERN:** existing dashboard test layout and the integration seed/rollback
  pattern; keep unit tests free of database, browser and network; `inspect`/`ast`
  for the guard.
- **DEPENDENCIES:** Tasks 1–25.
- **GOTCHA:** Do not let Persian assertions depend on locale ordering or on
  Streamlit's internal label text beyond the keys in `i18n.py`; assert on `t()`
  output so translation edits do not break tests. Keep AppTest page runs
  browser-free (the Task 8 seam). The literal guard must not misfire on `i18n.py`/
  `labels.py` (the two whitelisted modules) or on docstrings.
- **VALIDATE:** `poetry run pytest tests/unit/dashboard -q` and
  `poetry run pytest tests/integration -m integration -q --cov-fail-under=0`.

### 28. (E) RUN the analyst acceptance pass and record the validation report

- **IMPLEMENT:** With a populated local database (all six pipelines run), walk
  every page in the browser: Persian navigation, RTL layout, Jalali presets and
  echo, derived toggle with parent provenance visible in the table/export,
  per-page defaults, catalog search, base-year/segment view, chain-linking panel,
  quality warnings, correlation guardrails, CSV/Excel opened in a real spreadsheet,
  HTML/PNG/SVG downloads, the no-Chromium degraded path, and cache
  TTL/refresh after a pipeline run. **Re-derive all counts** (active indicators,
  derived series, domains, per-source Silver/Gold/observation totals, TSETMC
  sessions) from this run rather than copying them from this plan. Record commands
  + real outputs per level in `docs/phase-7.1/VALIDATION.md`, including anything
  not automated.
- **PATTERN:** `docs/phase-7/VALIDATION.md` level-by-level structure (Level 1
  dependencies → Level 9 launch) and its explicit "not automated in this run"
  section.
- **DEPENDENCIES:** Tasks 1–27.
- **GOTCHA:** Record observed data reality (World Bank 758 Silver, SCI 2,649,
  TSETMC 4,285 sessions, HBSIR 384, IMF/EIA/TGJU) so a later reader can tell
  "sparse series" from "broken page", and record that forecasts are not
  distinguished in the UI.
- **VALIDATE:** the full Level 1–6 command set below.

---

## TESTING & VALIDATION

### Unit Tests

- `i18n.py`: every key resolves; no empty values; every `t("…")` call site in
  `dashboard/` has a matching key.
- `labels.py`: 100 % coverage of the connector registries (World Bank 12, IMF 6,
  EIA 2, TGJU 3, SCI 14 + 4 segments, TSETMC 1, HBSIR 12) and every derived suffix;
  fallback path for unknown ids/domains/sources; `is_derived` reads metadata, not
  id shape (both directions: a suffixed level id stays a level, a parent-derived id
  is derived).
- `formatting.py`: Persian/Latin digit round-trips, separators, Jalali conversion
  under `Asia/Tehran` (leap Esfand, HBSIR year-end, Dec-31 annual ends,
  evening-UTC instants, `None`), `tehran_day_bounds` round-trip, percent/
  large-number formatting.
- Repository: LEFT-JOIN shaping with `null` catalog fields, **parent provenance
  fill for derived rows**, orphan flagging, derived discovery per source shape,
  `_empty_series()` contract, date filtering, timezone preservation, staleness
  inputs.
- Charts: Persian/labeled variants of the time-series, chain-linking and
  correlation builders; small-multiples cap; the facet default unchanged; mixed-unit
  fallback note.
- Exports: CSV BOM + Persian headers + Latin digits, Excel RTL sheet + Persian sheet
  name + Jalali column, ISO Gregorian timestamps retained, non-empty source for
  derived rows, HTML/PNG/SVG on demand, and the disabled-without-Chromium path.
- Quality: trading-calendar expectations, no spurious warnings for daily market
  series, annual/monthly/quarterly regressions.
- Cache: every `cached_*` wrapper declares a TTL, and `clear_dashboard_cache()`
  clears all of them, so a pipeline run is visible without an app restart.
- AppTest: every page renders through the router with Persian nav/titles; filter
  labels Persian; derived toggle changes the rendered legend; empty and single-row
  states render their Persian copy; no page triggers a browser render.
- Guard: the AST literal scan finds no untranslated user-visible literal outside
  `i18n.py`/`labels.py`.
- Registry: domain ownership is exact (every active domain owned once; no page
  claims a domain with no active indicators).

### Integration Tests

- Seeded catalog/Bronze/Silver/Gold rows (rollback per test) for the new join:
  derived series without catalog rows are returned, labelled, and carry their
  parent's `name`/`source_name`/`source_url`.
- Orphan series (Gold exists, catalog missing) are reported, not dropped, and their
  source is `NULL` by design.
- Search across id/Persian name/unit; catalog `active_only=False` exposes the four
  inactive SCI segments.
- Coverage, freshness and staleness queries against real rows.
- Export row counts and column sets for the localized frame.
- Keep every test marked `pytest.mark.integration`.

### Data Validation

- The dashboard still reads observations only from `gold.gold_analytical`; no
  Silver or Bronze read is introduced (the forecast-labeling exception is deferred
  precisely to preserve this).
- No interpolation, forward-filling, resampling, or frequency conversion is added
  anywhere, including the new chart modes and the decile view.
- Exported ISO-8601 Gregorian timestamps remain the stored values; Jalali columns
  are additional, never replacements.
- Chain-linking fields (`original_value`, `is_chain_linked`,
  `chain_linking_confidence`) are displayed as stored.
- Catalog `NULL` availability and `NULL` unit are shown as unknown, not invented.
- Derived series are labelled as platform-computed, with units from the Gold row,
  source from the parent row, and no catalog requirement.
- IMF forecast rows are **explicitly declared indistinguishable in the UI**
  (deferred labeling), recorded in the runbook and validation report.
- `git diff --name-only` shows no file under `src/`.

### ML Validation

Not applicable. Phase 7.1 adds no model training, forecasting, inference or
evaluation, and (with forecast labeling deferred) touches no Silver/Gold
transformation. The no-leakage rule is preserved by not presenting forecast rows as
anything other than what they are: indistinguishable in this release and disclosed
as such.

### Localization & Accessibility Validation

- Every user-visible string resolves through `t()`; the AST guard and the
  key-coverage test enforce it.
- RTL layout checked in the sidebar, headings, metric blocks, form controls and
  navigation; charts keep correct numeric direction and readable legends.
- The dataframe grid's LTR-only limitation is documented and accepted.
- Exports opened in a real spreadsheet application preserve Persian text and
  numbers (BOM/RTL sheet verified).
- Contrast and focus order reviewed for the RTL layout; digit mode switch works
  without a reload.
- Fallback behaviour verified: an indicator with no Persian label still renders
  (catalog `name`), and each such case is listed in the validation report.

### Edge Cases

- Empty database, empty catalog, no active indicators.
- A domain with no indicators (post-split `trade`/`energy`), the dead `economy`
  domain no longer claimed by any page.
- Single-observation series (TGJU snapshot, SCI spring-1405 unemployment).
- Daily series with a trading calendar (TSETMC) vs calendar days.
- `MA30`'s missing first 29 sessions; a month with no session for `.ME`.
- Derived series whose parent is not selected; derived ids already selected; a
  derived row whose parent catalog row is missing.
- Gold rows with no catalog row; catalog rows with no Gold rows.
- Inactive base-year segments included via the toggle.
- Persian vs Latin digits, `None` units, very long Persian names in legends and
  table headers.
- Mixed-frequency and mixed-unit selections on the correlation page.
- Chromium unavailable (PNG/SVG degraded path) and Kaleido present but broken.
- Start date after end date; date range containing no observations.
- A Jalali day whose UTC bounds straddle an observation stored in the evening UTC;
  a leap Esfand boundary.
- Backends where the router is unavailable (Streamlit below the declared floor) —
  the declared `^1.36` floor plus the committed lock prevents this.

---

## VALIDATION COMMANDS

### Level 1: Static / Style

```bash
poetry run ruff check dashboard src tests
poetry run ruff format --check dashboard src tests
poetry run mypy src dashboard        # broader than `make typecheck`, which covers src/ only
```

### Level 2: Unit Tests

```bash
poetry run pytest tests/unit -q
poetry run pytest tests/unit/dashboard -q --no-cov
```

### Level 3: Integration / Pipeline Tests

```bash
make db-up
poetry run alembic upgrade head
poetry run alembic check
poetry run pytest tests/integration -m integration -q --cov-fail-under=0
```

### Level 4: Feature-Specific Validation

```bash
poetry run pytest tests/unit/dashboard -q --no-cov
poetry run pytest tests/integration/test_dashboard_repository.py -q --cov-fail-under=0
poetry run streamlit run dashboard/app.py --server.headless true
# boundary check: Phase 7.1 changes nothing under src/
git diff --name-only origin/development...HEAD | grep -c '^src/'   # expect 0
```

### Level 5: Data Refresh Before Manual Validation

```bash
poetry run python -m src.connectors.world_bank
poetry run python -m src.connectors.imf
poetry run python -m src.connectors.eia
poetry run python -m src.connectors.sci_scraper
poetry run python -m src.connectors.tsetmc
poetry run python -m src.connectors.hbsir
```

### Level 6: Manual Validation

```bash
make dashboard
```

Manually verify:

- Navigation and page titles are Persian; no untranslated chrome remains.
- Inflation page shows World Bank + IMF + SCI CPIs, with the decile view working.
- GDP & Economy page shows World Bank + IMF GDP series and derived YoY when the
  toggle is on; the page no longer claims a dead `economy` domain.
- Trade & Energy page no longer carries welfare; the Welfare & Survey page shows
  Gini, relative poverty and decile shares on a Jalali year axis, plus the
  remaining welfare members.
- Market page shows TEDPIX + `RET1D` + `MA30` + `.ME` with trading-day gaps
  visible and no false "missing periods" warning.
- Labor page shows the single quarterly unemployment observation honestly.
- FX & Gold page renders one title and its snapshot warning.
- Derived series appear when requested, with the parent's source in the table and
  in the export, and derive labels are readable.
- Catalog search, base-year/segment view and chain-linking panel work; the four
  inactive SCI segments are visible when requested.
- Correlation page warns on low overlap and shows matched-observation counts.
- CSV opens correctly in a spreadsheet with Persian headers, Latin digits and both
  date columns; Excel sheet is RTL; PNG/SVG download on demand and degrade cleanly
  without Chromium.
- Cache TTL/refresh picks up a pipeline run without restarting the app.
- `make check` passes with no reduction in coverage below the 80 % gate.

---

## ACCEPTANCE CRITERIA

* [ ] `make dashboard` launches a Persian, RTL dashboard through a single
      `st.navigation` router driven by a page registry; `pyproject.toml` declares
      Streamlit `^1.36`, `poetry.lock` is refreshed in the same change, and
      `poetry install` is clean.
* [ ] Every active catalog indicator is reachable from a page, **and a
      registry-driven test asserts that every active domain is owned by exactly one
      page and that no page claims a domain with no active indicators**. The two
      documented ownership facts (`welfare` covers population and IMF `LUR`;
      `labor` covers SCI unemployment) are asserted, not inferred, and `economy` is
      no longer claimed.
* [ ] The ≈38 derived Gold series are selectable, labelled by suffix, exportable,
      and **carry their parent's source provenance**; the "Include derived" control
      has an observable effect.
* [ ] Derived-series detection is metadata-driven (`record_metadata.derived_from`);
      adding a new derivation strategy in a later phase requires no dashboard
      change and no new id list.
* [ ] No untranslated user-visible English remains in navigation, page chrome,
      filters, charts, tables or exports — enforced by the AST guard, not by
      inspection. Indicator names absent from the label map fall back to the
      catalog `name` and are enumerated in `docs/phase-7.1/VALIDATION.md`.
* [ ] Persian display names exist for every active indicator, domain and source,
      with a fallback that cannot hide an unmapped indicator.
* [ ] RTL layout applies to navigation, text, forms and metrics; charts render
      Persian labels and a Jalali date axis; the dataframe grid's LTR limitation
      and the `data-testid` coupling are documented and accepted.
* [ ] Jalali date display and Jalali-aware date selection work under the documented
      `Asia/Tehran` policy, round-trip (Jalali day in → UTC bounds → same Jalali day
      out, including an evening-UTC observation) without changing stored Gregorian
      values or any query semantics, and the resolved Gregorian bounds are visible
      to the analyst.
* [ ] Exports keep ISO-8601 Gregorian timestamps, add a Jalali display column, use
      Persian headers with Latin digits, attribute derived rows to their parent
      source, and open correctly in a spreadsheet (CSV BOM, RTL Excel sheet).
* [ ] Chart image rendering is on demand; page loads do not start Chromium, and a
      missing Chromium disables the buttons instead of erroring.
* [ ] Trading-calendar-aware expected periods remove the false missing-period
      warning for TSETMC without changing annual/monthly/quarterly behavior.
* [ ] `st.cache_data` has a TTL and a refresh control, so a pipeline run is
      visible without restarting the app.
* [ ] No interpolation, resampling, or forward-filling is introduced; Gold remains
      the only analytical source; chain-linking fields are displayed as stored; no
      normalization/index mode exists.
* [ ] **No file under `src/` changes** (verified with `git diff --name-only`), no
      new Alembic migration or schema change is introduced (no new file under
      `alembic/versions/`), and no new runtime dependency or vendored asset is
      added — `streamlit`, `jdatetime` and `zoneinfo` cover the whole phase, and
      the app works offline.
* [ ] `make check`, the integration suite, and `alembic check` pass; new unit and
      integration tests cover localization, derived/orphan series and parent
      provenance, the Jalali round-trip, domain ownership and the new quality
      semantics.
* [ ] `docs/phase-7.1/` exists; the stale Phase 7 / README / AGENTS claims are
      corrected (decile deferral, chain-linking and derived-series surfacing, page
      list, test counts); the deferred list below is recorded there, including the
      explicit statement that IMF forecasts are indistinguishable in this release.
* [ ] No regression in existing connector, ETL, database, or dashboard behavior,
      and no change to the local, foreground, single-user deployment model.

---

## RISKS & TRADE-OFFS

- **RTL depends on Streamlit internals (High).** There is no supported RTL mode,
  so CSS targets `data-testid` selectors that change across releases. Mitigation:
  one module, narrowly scoped rules, a visual check recorded after any Streamlit
  upgrade, and no reliance on CSS for functionality.
- **Persian indicator-name coverage is translation work, not code (Medium–High).**
  50 indicators plus domain/source labels and every UI key. Mitigation: make
  coverage a test (registry-driven assertion), land the map with the fallback first
  so the app is never blocked, and treat wording as reviewable content.
- **Derived-series visibility changes the meaning of the join (Medium).** Moving
  `load_series` to a LEFT JOIN means `name`/`source_name` can be `NULL`, which every
  consumer, export and test must handle, and the parent-provenance join adds a
  JSONB expression to the query. Mitigation: extend `_empty_series()`, update
  integration fixtures in the same change, add derived/orphan/provenance tests
  before touching pages, and keep the pandas fallback if the aliased join is
  awkward.
- **Router migration touches every page and every page test (Medium).** `AppTest`
  currently targets page files directly. Mitigation: the Wave-0 spike proves the
  `switch_page` path first; page files stay standalone-runnable as the fallback;
  the registry keeps IA declarative with no logic in `app.py`.
- **Localization can silently break filters (Medium).** Displaying Persian labels
  risks mapping them back to the wrong slug. Mitigation: labels are display-only,
  values stay slugs, and a round-trip test asserts the query values are unchanged.
- **Jalali/TIMEZONE semantics are easy to get subtly wrong (Medium).** Period ends
  are safe (UTC midnight), snapshot sources are not, and filter bounds are
  inclusive. Mitigation: one documented policy mirroring `src/utils/persian.py`,
  `tehran_day_bounds` as the only bounds constructor, round-trip tests including an
  evening-UTC instant, and the Gregorian bounds echoed in the UI.
- **Chart scaling is the broadest UI change (Medium).** Every page renders through
  `build_time_series_chart`. Mitigation: keep the facet default and its tests
  untouched; add modes behind explicit options; regression-test builders before
  wiring pages.
- **Excel/BOM/RTL export behavior cannot be unit-tested fully (Medium).**
  Mitigation: assert bytes in tests and require one real spreadsheet open in the
  manual validation report; the existing CSV byte test changes deliberately.
- **Translation content can lag implementation (Medium).** The AST guard fails
  until every literal is keyed, which is the point — but it makes
  Task 17 the gating step for a green build. Mitigation: land `i18n.py` early
  (Task 3) and key page-by-page rather than in one sweep.
- **Snapshot/sparse sources can look broken in a Persian UI (Low–Medium).** TGJU
  (one observation per run) and SCI unemployment (one quarter) will still look
  thin. Mitigation: keep and localize the explicit warnings, and show per-series
  observation counts.
- **Streamlit floor bump could affect other tooling (Low).** `^1.36` is above the
  declared `^1.29`; the validated environment already runs 1.61.1 and the lock
  already pins it. Mitigation: refresh the lock, reinstall, and re-run `make check`
  and the AppTest suite in the same commit (Task 1 establishes the exact commands).
- **Dashboard is not type-checked or coverage-measured today (Low).** Mitigation:
  run `mypy src dashboard` explicitly in Level 1; decide separately whether
  `make typecheck` should include `dashboard/` (see open items) — do not silently
  widen the coverage gate.

---

## Deferred Scope (Phase 7.2 candidates)

Record these in `docs/phase-7.1/` so a reader cannot mistake a deferral for a
missing feature:

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

## NOTES

- **Do not rewrite.** The repository, export, quality and caching layers are sound;
  this phase changes the presentation layer, adds two pages, splits one, hardens
  three behaviors, and adds a router. Prefer the smallest change that makes the
  platform's own metadata drive the UI.
- **Absolute boundary:** nothing under `src/` changes. If a task seems to need it,
  the task belongs in Phase 7.2 — that is exactly how the forecast-labeling item
  was deferred.
- **Metadata over lists:** derived-ness, domains, sources and cadence all come from
  data or from one keyed map. No new hardcoded indicator list may be introduced,
  and `page_view._derived_ids`' hardcoded WB/TGJU patterns are removed, not
  extended.
- **Never bypass the data contract:** Gold in, no imputation, timezone-aware UTC,
  Gregorian storage, `Asia/Tehran` only for display, `record_metadata` (not
  `metadata`) as the Python attribute name, no secrets or microdata in the UI.
- **Ruff literals:** only `dashboard/i18n.py` and `dashboard/labels.py` may hold
  Persian literals and must be whitelisted for `RUF001`/`RUF002`/`RUF003` in
  `pyproject.toml` (plus any test file that must contain Persian fixtures), because
  `make lint` runs `ruff check .`.
- **Type checking:** `make typecheck` covers `src/` only — use
  `poetry run mypy src dashboard` for this phase, and treat widening the Makefile
  target as an open item rather than an assumed change.
- **Keep `make dashboard` working** and keep the app local, foreground and
  single-user; nothing in Phase 7.1 changes the deployment model that Phase 8 will
  harden.
- **Reuse what exists:** `build_chain_linking_chart`, `list_indicators(search=…)`,
  `expected_observation_count`, `find_chromium_executable`, `PERSIAN_MONTHS`,
  `iranian_year_end` and the digit tables are already written and tested — wiring
  them up is cheaper than adding equivalents. `build_coverage_chart` and
  `available_domains()` must be **wired or deleted** in this phase; leaving them
  unused with new tests around them is not acceptable.
- **Record reality, not intent:** every Phase 7.1 document should distinguish
  "implemented and verified" from "implemented but not interactively verified", as
  `docs/phase-7/VALIDATION.md` already does; counts quoted in this plan are
  indicative until Task 28 re-derives them from a real run.

## Open items for human approval before implementation

1. **Router and registry** (decision 1): approve the `st.navigation` migration with
   the page registry as data, plus the `streamlit ^1.36` floor and `poetry.lock`
   refresh (the lock already pins 1.61.1, so this is a refresh, not an upgrade).
2. **Derived provenance** (decision 3 + Task 7b): approve the LEFT JOIN with a
   parent catalog join via `record_metadata ->> 'derived_from'`, so derived rows
   inherit `name`/`source_name`/`source_url` and only genuine orphans are `NULL`.
3. **Jalali timezone policy** (decision 5): approve `Asia/Tehran` for display and
   for interpreting a selected day, with UTC storage unchanged. This is a visible
   behaviour change for snapshot sources and cannot be inferred from the code.
4. **Forecast labeling**: approve the deferral with an in-UI disclaimer, rather than
   the ETL change it would require.
5. **Locale model** (decision 7): approve fa-only with stable keys and no runtime
   switcher.
6. **Domain ownership** (Task 2/16): approve the registry as the single source of
   ownership — `economy` dropped from the GDP page, `welfare` covering population
   and IMF `LUR`, `labor` covering SCI unemployment — with `domain` values in the
   catalog left untouched.
7. **Quality-gate scope**: approve running `mypy src dashboard` in this phase and
   leaving `make typecheck`/`--cov=src` unchanged (or explicitly approve widening
   them).
8. **Dead code**: approve wiring `build_chain_linking_chart` and catalog search, and
   deleting `build_coverage_chart` and `available_domains()`/
   `cached_available_domains()` if they earn no place.
