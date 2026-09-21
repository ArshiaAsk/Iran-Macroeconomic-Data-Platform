# Task: Phase 7.2 — Dashboard Redesign (Design System, Shell, All Pages)

## Review outcome

This plan was amended after a structural review (AM-1 … AM-16) and a final
amendment round (AM-21 … AM-27). The task numbering below is final; NOTES carries
the old→new mapping. Every fact marked **verified now** was re-checked against the
installed package or the working tree and cites its evidence. **AM-15:** the
narrative sections (Review outcome, the D-decisions, Proposed Approach,
Milestones, wave descriptions, Testing & Validation, Deferred Scope, NOTES,
Risks, Open items) were updated to match the final numbering and the ratified
decisions; every `[ASSUMED]` this review resolved was removed, and each remaining
open item has an owner and a Wave 0 task that closes it. **AM-21 … AM-27:** a
pre-change baseline is captured in Task 1; the missing page-header component is
added (Task 18); an owner review gate closes the shell + Overview before Waves
D–H (Task 34); Wave A's "pages unchanged" claim is corrected and its visual
evidence scheduled (Task 10 moves the screenshot script, Task 24 records the
after-screenshots); the export smoke moves into the Plotly-template task
(Task 14); the HTML table gains a responsive wrapper (Task 15); and the remaining
contract clean-ups (AM-27) are applied.

### Removed / deferred (see [Deferred Scope](#deferred-scope-phase-73-candidates))

| Item | Reason |
|---|---|
| IMF forecast-vs-actual labeling | Carried from 7.1: `observation_type` reaches Silver only; Gold level `record_metadata` is built from chain-linking fields alone. An ETL change, therefore out of the presentation-only boundary. |
| Indicator detail view | Not required by the stated goal; largely covered by the catalog page plus `coverage_summary()`. |
| Search on domain pages | The catalog page search ships; per-page search doubles the surface. |
| Explicit refresh control | 7.1 deferral; a config-held TTL on the freshness query replaces it (D7). |
| Custom Jalali date-entry widget | 7.1 deferral; Jalali presets + Gregorian/Jalali echo stay. |
| Normalized / index-to-100 cross-unit comparison | New analytical transformation, outside the phase boundary. |
| New pages | Explicitly out of scope. |
| English catalog / runtime locale switcher | Keys stay stable so `en` can be added later; one locale ships. |
| Dark-mode support | **D14 ratifies light-only.** `base="light"` is locked; dark mode is deferred (see D14 and Deferred Scope). |
| Per-page module split of `page_view.py` | Not a 7.2 task; the guard is made function-scoped instead (AM-14). Deferred to 7.3. |

### Added (required for the stated goals, previously missing)

1. **A design-token layer.** There is no single source for the palette, radius, spacing or monospace family today; every colour is a literal in `.streamlit/config.toml` or absent. Tokens become one module plus one theme table.
2. **A shared component set.** The Overview hand-rolls metrics, a `st.page_link` list and raw `st.dataframe`s; no page shares a callout, page header, KPI band, chip, bar list, section header, filter bar or state component.
3. **A page-layout contract + consistency guard.** Nothing today prevents a page from calling raw `st.title`/`st.metric`/`st.warning` or `unsafe_allow_html`; `test_literal_guard.py` is the precedent for enforcing it.
4. **Calendar-aware date display.** `tables.py:103-111` converts every date column to Jalali, which is why World Bank ranges render as Jalali. A config-held source→calendar map makes Gregorian display opt-in.
5. **Relative-time and freshness-aggregate helpers.** Both are absent; the mockup requires them.
6. **A shell.** Sidebar brand, nav icons, active-item styling, pinned DB status and a top bar/breadcrumb do not exist.
7. **A vendored font task (blocker).** The mockup's typography needs Vazirmatn; the font files exist in the tree but are not in the location static serving requires (AM-1, AM-20).
8. **A typed HTML-table cell model (blocker).** `ltr_columns`/`title_columns` cannot express the mockup's dot, chip, two-line and unit cells (AM-2).
9. **A test-migration strategy and helper.** AppTest cannot see `st.html` as text; the old "existing suites pass unchanged" claim was unsupported (AM-4).
10. **Three traceability tables.** Mockup→task, page→archetype→task, table/chart→component→task (AM-11).
11. **A design-system document** (`docs/phase-7.2/design-system.md`) as the reference for later phases.
12. **A baseline and visual-evidence gate (AM-21, AM-23, AM-24).** Nothing captures the pre-change `make check`/`mypy`/test baseline or the "before" screenshots, and no owner review gate closes the shell + Overview before the archetype waves; Tasks 1, 24 and 34 add them.

### Corrected (discovery leads that did not survive verification)

1. **`st.dataframe` *does* have a density control.** `st.dataframe(row_height=...)` exists in the installed 1.61.1 (introduced **1.43.0**). The discovery claim that density needs a custom component is wrong; density is native for both table classes.
2. **AGENTS.md contains no offline/font/CDN rule.** The only relevant sentence is "**Local-only deployment:** No cloud infrastructure; all services run via Docker Compose" (`AGENTS.md:620`). The "no CDN, no webfont, no vendored font file" rule lives in `.streamlit/config.toml:4-6` and `dashboard/components/direction.py:14-16` — a 7.1 *decision*, not a repo hard rule.
3. **Vendoring a font is natively supported and local.** `[[theme.fontFaces]]` + `server.enableStaticServing=true` serves `static/<file>` at `app/static/<file>` with no CDN (advanced theming and `fontFaces`, **1.44.0**). Base64 is unnecessary.
4. **`st.badge` exists (1.44.0)** with colours and an icon, so status chips and the "نیازمند بررسی" tag are native, not HTML. **Verified now:** `st.badge` renders as a Markdown directive, so `st.badge("tag", color="orange")` appears to AppTest as `app.markdown == [":orange-badge[tag]"]` (evidence: `AppTest.from_string` probe, 2026-09-20).
5. **Material icons are supported and validated.** `ALL_MATERIAL_ICONS` lives in `streamlit/material_icon_names.py` (4 267 names) and `validate_material_icon` in `streamlit/string_util.py`; **verified now (Wave 0, 2026-09-20)** that `overview`, `compare_arrows`, `menu_book`, `show_chart`, `analytics`, `currency_exchange`, `swap_horiz`, `bolt`, `home`, `paid`, `trending_up`, `work` are all members of `ALL_MATERIAL_ICONS`. **Correction:** `validate_material_icon` expects a full shortcode — a bare name (`"overview"`) **raises** `StreamlitAPIException`; `validate_material_icon(":material/overview:")` returns `":material/overview:"`. The valid `st.Page` form is `icon=":material/overview:"`.
6. **The declared Streamlit floor is too low for the intended APIs.** `pyproject.toml` declares `^1.36`; `row_height` needs 1.43 and `fontFaces`/`badge`/advanced-theming colours need 1.44 (installed 1.61.1). The floor must be raised (D9).
7. **There are ten pages, not eleven.** `navigation.py:52-121` registers exactly ten `PageSpec` rows; `page_for_domain("economy")` is deliberately `None`.
8. **The font files are already under `dashboard/static/` (AM-20, re-verified Wave 0).** **Verified now (Wave 0, 2026-09-20):** `ls dashboard/static/` → `Vazirmatn.ttf` (241 328 B) and `OFL.txt` (4 391 B); both **untracked** (`git status --short` → `?? dashboard/static/`); `git ls-files` returns nothing; `.gitignore` has no `*.ttf`/`static/` rule. `dashboard/Vazirmatn.ttf` / `dashboard/OFL.txt` **do not exist** (the earlier "still at `dashboard/`" claim was stale). Task 7 therefore only needs to **commit** the existing `dashboard/static/` files and wire static serving — no relocation step. Static serving resolves a `static/` directory beside the entrypoint (Task 2 confirmed `app/static/…` serves the file).
9. **`st.html` is sanitized by DOMPurify with `USE_PROFILES:{html:true}`.** **Verified now** from `streamlit/static/static/js/Html.Be1G6END.js`: default path `sanitize(body, {USE_PROFILES:{html:true}, FORCE_BODY:true})`; the `unsafe_allow_javascript=True` path adds `ADD_TAGS:["script","style"]` and `ADD_ATTR:["src","type","async","defer","nonce","crossorigin","referrerpolicy","integrity"]`. The HTML profile allows `<bdi>`, `<style>` and the `class`/`dir`/`title`/inline-`style` attributes; SVG is a separate profile that is **not** enabled, so `<svg>` is expected to be stripped (Wave 0 browser task 4 confirms rendering). `st.html` is not iframed and ignores JavaScript by default.
10. **`direction.py` injects CSS through `st.markdown(..., unsafe_allow_html=True)`, not `st.html`.** Evidence: `dashboard/components/direction.py:104`. Task 9 keeps that API, so `test_direction.py`'s `app.markdown` assertions stay valid.
11. **AppTest exposes no `html` or `badge` accessor.** **Verified now:** `hasattr(at, "html") == False`, `hasattr(at, "badge") == False`; `at.get("html")` returns an `UnknownElement` whose markup is reachable only as `el.proto.body` (`.value` raises `AttributeError`); `at.get("badge") == []` because badges surface as Markdown (see corrected #4). This drives the test-migration strategy (AM-4) and the test-helper task (Task 16).
12. **`st.logo` is an image API, not a text-brand API.** **Verified now** signature: `st.logo(image, *, size="small"|"medium"|"large"="medium", link=None, icon_image=None)`; `image` is "anything supported by `st.image` (except list) or str", where a `str` is an emoji, a `:material/…:` shortcode, a path or a URL. There is no text-brand parameter, so D5's fallback (1) needs a logo *image asset*; a text brand uses the CSS/text fallback (Task 27).
13. **`client.toolbarMode` values are `auto` / `developer` / `viewer` / `minimal`.** **Verified now** from `streamlit/config.py:608-627`; `minimal` hides the menu when no options remain and `viewer` hides developer options. The `viewer` behaviour was fixed in **1.54.0** (Streamlit 2026 release notes). This is the lever for hiding the native Deploy button/kebab (AM-7) and the settings-menu theme toggle (D14).

### Verified in the codebase (evidence for the above)

- Installed Streamlit **1.61.1**; package root `/home/arshiaask/.cache/pypoetry/virtualenvs/iran-macro-platform-M9QKMlbU-py3.12/.../streamlit`; constraint `^1.36` in `pyproject.toml`.
- Theme options present in 1.61.1 (`poetry run python -c "import streamlit.config as c; c.get_config_options()"`): font family/face options `theme.font`, `theme.fontFaces`, `theme.headingFont`, `theme.codeFont`, `theme.headingFontSizes`, `theme.headingFontWeights`, `theme.codeFontSize`, `theme.codeFontWeight`, `theme.baseFontWeight`, `theme.metricValueFontSize`, `theme.metricValueFontWeight`; alert colour options `theme.{red,orange,yellow,blue,green,violet,gray}{Color,BackgroundColor,TextColor}` (plus `theme.sidebar.*` / `theme.dark.*` / `theme.light.*` variants); plus `theme.baseRadius`, `theme.borderColor`, `theme.dataframeHeaderBackgroundColor`, `theme.showWidgetBorder`, `theme.showSidebarBorder`, `theme.chartCategoricalColors`.
- `st.html(body, *, width="stretch", unsafe_allow_javascript=False)` (1.33), `st.navigation`/`st.Page` (1.36), `st.metric(help=…)`, `st.page_link`, `st.badge(label, *, icon, color, width, help)`, `st.segmented_control(...)`, `st.container(*, border=None, …)`, `st.dataframe(row_height=…)` all present in 1.61.1.
- Ten page delegates under `dashboard/pages/`, each a thin call into `dashboard/page_view.py`.
- `dashboard/components/direction.py:48-83` is the single DOM-touch owner (`CSS_SELECTORS`, `_RULES`); CSS is injected at `direction.py:104` via `st.markdown(..., unsafe_allow_html=True)`.
- `dashboard/components/tables.py:43` caps grid rows at `OBSERVATIONS_ROW_LIMIT = 500`; `tables.py:103-111` is the Jalali-all-dates rule; `MISSING_VALUE` is re-exported there.
- `test_literal_guard.py` already walks `dashboard/**/*.py` with an AST and a `WHITELISTED_MODULES` allowlist — the precedent for D11.
- Real DB (read-only, 2026-09-20): active catalog 50, domains 9, sources 7, derived 32, orphan 32, catalog-linked Gold rows 8 195, total Gold rows 20 074.
- Font assets (AM-20, re-verified Wave 0 2026-09-20): `dashboard/static/Vazirmatn.ttf` and `dashboard/static/OFL.txt` — **already under `dashboard/static/`, untracked** (`ls`, `git status --short` → `?? dashboard/static/`). `dashboard/Vazirmatn.ttf` / `dashboard/OFL.txt` do not exist. `git ls-files` returns nothing for `vazir`/`ofl`/`static`; `.gitignore` has no `*.ttf`/`static/` rule. Task 7 commits the existing files and wires static serving.

---

## Task Description

Phase 7.2 turns ten independently-built Streamlit pages into one product. It adds a
shared design system (tokens, theme, shell CSS, components), a consistent shell
(sidebar, brand, icons, DB status, top bar), and redesigns **every** registered
page to compose those components under one layout contract. The Overview page is
the reference implementation and must match
`docs/design/phase-7.2/overview-redesign-mockup.html`.

This is a **presentation-only** phase. It changes look, layout and consistency. It
does not change data semantics, does not touch `src/`, `alembic/` or `airflow/`,
and does not add features.

The phase is structured so that every wave ends in a state where all ten pages
render and `make check` passes. No page may be left half-migrated.

---

## Scope

### In Scope

- [ ] A shared design system: theme config, design tokens, shell CSS, shared components.
- [ ] The shell: sidebar, brand header, Material nav icons, active-nav style, pinned DB status, top bar/breadcrumb.
- [ ] Redesign of **all ten** pages in `navigation.py` onto the shared components and layout contract.
- [ ] Consistent chart styling: one Plotly template built from the tokens, used by every chart builder, and verified through the image-export path.
- [ ] Consistent empty, loading and error states.
- [ ] Overview implemented to match the mockup.
- [ ] A vendored, statically-served Vazirmatn font (D4, ratified).
- [ ] A design-system reference document and a Phase 7.2 validation record.

### Out of Scope

- [ ] IMF forecast labeling, indicator detail view, per-domain search, explicit refresh control, any new data feature (→ Deferred Scope).
- [ ] New pages, new domains, new indicators.
- [ ] Any change under `src/`, `alembic/`, `airflow/`.
- [ ] Any change to Gold data semantics, SQL, caching keys or exports' *content* (export styling may change, values may not).
- [ ] Dark-mode support (D14: light only).

---

## Context

### Current state (observed)

The dashboard is a `st.navigation` router (`dashboard/app.py:56`) over a plain-data
registry (`dashboard/navigation.py:52-121`). Ten page modules under
`dashboard/pages/` are one-line delegates into `dashboard/page_view.py`. Three
presentation modules own the display layer: `i18n.py` (UI chrome), `labels.py`
(names/cadence), `formatting.py` (digits/Jalali/Tehran). `direction.py` is the
single DOM-touch owner. `repository.py` is the only Gold reader.

The Overview renders a title, a `st.warning` methodology note, a 4-column metric
row, a 2-column derived/orphan metric row, a `st.page_link` domain list and two
`st.dataframe`s (`page_view.py:742-793`). There is no shell chrome, no shared
component, no calendar policy and no consistency guard.

### Verified capability notes (evidence in "Verified in the codebase")

- **`st.html` sanitization.** DOMPurify with `USE_PROFILES:{html:true}, FORCE_BODY:true`; HTML profile allows `<bdi>`, `<style>` and `class`/`dir`/`title`/inline-`style`; SVG is not in the enabled profile. Not iframed; JS ignored unless `unsafe_allow_javascript=True`. A style-only payload is routed to the event container so it takes no layout space. Where an attribute does not survive, fall back to a `data-` attribute plus CSS `::after` tooltip, or `st.markdown(..., unsafe_allow_html=True)`.
- **AppTest visibility.** Native elements (`st.title`, `st.warning`, `st.info`, `st.metric`, `st.dataframe`, `st.subheader`, `st.caption`, `st.badge`→markdown) are visible; `st.html` is an `UnknownElement` reachable only through `proto.body`. This is why D13 prefers native elements and why the test-helper task exists.
- **Internal links (AM-17, verified now).** `st.page_link` is the supported internal-navigation primitive: its docstring states that clicking a page link "stops the current page execution and runs the specified page as if the user clicked it in the sidebar navigation" (external URLs open a new tab and do not rerun). A plain `<a href>` to an internal page URL is **not** that primitive — it is an ordinary browser navigation that reruns the script without the in-app switch. So any component that must link to an owner page uses native `st.page_link`; `st.html` fragments carry no navigation.
- **`st.logo` is image-only** (no text brand) — D5 addendum.
- **`client.toolbarMode` ∈ {auto, developer, viewer, minimal}** — the native Deploy button/kebab and the settings-menu theme toggle are the levers for AM-7/D14.
- **Alert colour theme options exist** (`theme.{red,orange,blue,green,yellow}{Color,BackgroundColor,TextColor}`), so `st.warning`/`st.info`/`st.error` can be tinted to the amber/blue/red tokens.

### PAGE INVENTORY

Row counts are from the real DB (2026-09-20) or the code's own cap.

| page | registry key / group | file::function | widgets | charts (lib) | tables (kind, rows) | filters / controls | i18n keys / owner | tests | mockup? |
|---|---|---|---|---|---|---|---|---|---|
| Overview | `overview` / overview_analysis (default) | `pages/1_Overview.py` → `page_view.render_overview_page:742` | `st.title`, `st.warning`, `st.metric`×6, `st.page_link`, `st.dataframe`×2 | none | freshness (df, 7); coverage (df, 50) | none | `page/nav/section/metric/table/value/warn.*` in `i18n.py` | `test_app_overview.py` | **yes** |
| Compare & Correlation | `correlation` / overview_analysis | `pages/6_Correlation.py` → `render_correlation_page:1002` | `st.title`, `st.warning`×2, `st.caption`, `st.plotly_chart`, `st.dataframe`×2, `st.subheader`, `st.columns` | heatmap (Plotly) `build_correlation_chart` | join_counts (df, N×N); overlap_summary (df, N) | `render_filters` (domain/freq/source/indicator/dates) | `page.correlation`, `warn.correlation_*`, `section.exact_join_counts` | `test_app_correlation.py` | no |
| Data Catalog | `catalog` / overview_analysis | `pages/7_Data_Catalog.py` → `render_catalog_page:588` | `st.title`, `st.checkbox`, `st.button`, `st.text_input`, `st.metric`, `st.info`, `st.dataframe` | none | catalog (df, 50–54, sortable) | `render_filters` + search + clear + inactive toggle | `page.catalog`, `filter.*`, `table.*` | `test_app_catalog.py` | no |
| Inflation | `inflation` / domains | `pages/2_Inflation.py` → `render_inflation_page:196` | `st.title`, `st.subheader`×4, `st.multiselect`, `st.caption`, `st.info`, `st.plotly_chart`×3+, `st.dataframe`, `st.expander` | line/small-multiples/chain-link (Plotly) | provenance (df, ~3); observations (df, capped 500) | `render_filters` + decile multiselect + chart-mode selectbox | `page.inflation`, `section.cpi_*`, `warn.chain_linking_*` | `test_app_economy.py` (gdp), inflation via smoke | no |
| GDP & Economy | `gdp` / domains | `pages/3_GDP_Economy.py` → `render_domain_page`→`render_domain_body:155` | `st.title`, filters, `st.checkbox`, `st.info`, `st.plotly_chart`, `st.expander`, `st.dataframe` | line (Plotly) | quality (df, N); observations (df, capped 500) | `render_filters` + include-derived + chart-mode | `page.gdp`, `section.observations`, `table.*` | `test_app_economy.py` | no |
| Trade & Energy | `trade_energy` / domains | `pages/4_Trade_Welfare_Energy.py` → `render_domain_page` | same as GDP | line (Plotly) | same as GDP | same as GDP | `page.trade_energy` | `test_app_trade_welfare.py` | no |
| FX & Gold | `fx_gold` / domains | `pages/5_FX_Gold.py` → `render_fx_gold_page:913` | `st.title`, `st.warning`, then domain body | line (Plotly) | same as GDP | same as GDP | `page.fx_gold`, `warn.tgju_snapshot` | `test_app_fx_gold.py` | no |
| Welfare & Survey | `welfare` / domains | `pages/8_Welfare_Survey.py` → `render_welfare_page:929` | `st.title`, `st.warning`, `st.info`, `st.subheader`×4, `st.plotly_chart`×2, `st.dataframe`, then domain body | survey-year line (Plotly) `build_survey_year_chart` | survey-year panel (df, 2); quality; observations (capped 500) | `render_filters` | `page.welfare`, `section.hbsir_*`, `warn.hbsir_*` | `test_app_welfare.py` | no |
| Market | `market` / domains | `pages/9_Market.py` → `render_market_page:413` | `st.title`, `st.warning`+`st.info`×4, `st.subheader`×N, `st.metric`, `st.plotly_chart`×N, `st.expander`, `st.dataframe` | line per series (Plotly) | quality; observations (capped 500) | `render_filters` | `page.market`, `section.market_level`, `warn.tsetmc_*` | `test_app_market.py` | no |
| Labor | `labor` / domains | `pages/10_Labor.py` → `render_labor_page:970` | `st.title`, `st.info`, then domain body | line (Plotly) | quality; observations (capped 500) | `render_filters` | `page.labor`, `warn.labor_publication` | `test_app_labor.py` | no |

### Archetypes

Grouping was verified against `page_view.py`, not assumed: the seven domain pages
do **not** share one template.

| # | Archetype | Pages | Shared shape | Existing code reused |
|---|---|---|---|---|
| A1 | **Overview** (all-domain dashboard) | overview | title → callout → KPI band → two-column (freshness + bars) → coverage table | `render_overview_page`, `freshness_display`, `_render_series_inventory`, `_render_domain_counts` |
| A2 | **Generic domain explorer** | gdp, trade_energy, fx_gold, labor | page header (+ optional callout) → filter bar → chart → quality → observations expander → downloads | `render_domain_page`/`render_domain_body`, `render_filters`, `_render_series_section`, `_render_scaled_chart`, `_render_capped_rows`, `render_quality_summary`, `render_data_downloads`, `render_chart_downloads` |
| A3 | **Emphasis-domain page** | inflation, welfare, market | page header + callouts → filters → **emphasis sections** → generic domain body | A2's composition plus `_render_cpi_decile_section`, `_render_cpi_canonical_section`, `_render_chain_linking_section`, `_render_hbsir_sections`, `survey_year_panel`, `_render_market_level`, `_render_market_derived_panels` |
| A4 | **Comparison / correlation** | correlation | header + callout → filter bar → heatmap → two summary tables → quality → downloads | `render_correlation_page`, `build_correlation_chart`, `render_filters`, `render_quality_summary`, `render_data_downloads` |
| A5 | **Catalog** | catalog | header → search + filter bar + clear → count → table | `render_catalog_page`, `search_catalog`, `_apply_catalog_filters`, `localize_table_frame` |

### Traceability — mockup element → task (AM-11)

Nothing in `docs/design/phase-7.2/overview-redesign-mockup.html` is silently
dropped. Every element maps to a final task number or an accepted deviation.

| Mockup element | Task (final numbering) |
|---|---|
| Sidebar width 256 px | Task 9 (chrome CSS) |
| Sidebar brand (icon + "سامانهٔ داده‌ها") | Task 27 (brand), Task 9 (position) |
| Nav groups ("مرور و تحلیل", "حوزه‌ها") | Task 27 (registry `GROUPS` already exists) |
| Material nav icons | Task 25 |
| Active-item accent bar | Task 9 (chrome CSS) |
| Pinned DB status dot | Task 20 (dot), Task 27 (pin) |
| Top-bar breadcrumb | Task 28 |
| Last-collection stamp (date · time · Tehran) | Task 28 |
| Page header (title) | Task 18 (component), Task 33 (Overview) |
| Methodology callout (bold label + icon) | Task 17 (component), Task 18 (header), Task 33 (Overview) |
| KPI band (6 cells, secondary group) | Task 19 (component), Task 29 (Overview) |
| KPI tooltips (3 annotated cells) | Task 19, Task 29 |
| "نیازمند بررسی" review tag | Task 19 (`st.badge`), Task 29 |
| Freshness dot | Task 20, Task 30 |
| Freshness two-line date (date + time · relative age) | Task 15 (`TwoLine`), Task 30 |
| Freshness records + run chip | Task 15 (`StatusChip`), Task 20, Task 30 |
| Freshness stale-first order | Task 12, Task 30 |
| Freshness header summary ("۵ به‌روز · ۲ کهنه") | Task 12, Task 30 |
| Domain bars with total ("جمع ۵۰ شاخص") | Task 20 (bar list: native `st.page_link` + `st.html` bar per row), Task 31 |
| Filter bar (3 selects) | Task 21 (filter bar), Task 32 (Overview) |
| Density toggle (راحت/فشرده) | Task 15 (CSS class), Task 21 (`st.segmented_control`) |
| "نمایش N ردیف" | Task 21 (`filter.showing_rows`), Task 32 |
| Coverage table columns | Task 15, Task 32 |
| Coverage LTR ids (`<bdi class="ltr">`) | Task 15 (`Ltr` cell), Task 32 |
| Coverage unit chips | Task 15 (`UnitChip`), Task 32 |
| Coverage em-dash for nulls | Task 15 (`MISSING_VALUE`), Task 32 |
| Gregorian-year rule + tooltip | Task 13 (calendar map), Task 32 |
| Coverage footnote | Task 13 (`table.coverage_footnote`), Task 32 |
| Vazirmatn font | Task 7 |
| Design tokens (`:root`) | Task 5 |
| Max content width 1360 px | Task 9 (CSS), Task 28 (top-bar layout) |
| Top bar height 48 px | Task 28 |
| Brand SVG glyph | **Accepted deviation** — `st.Page` cannot take inline SVG text and `st.logo` is image-only; the text brand is a CSS-pinned sidebar block (fallback 2) or top-bar brand (fallback 3), with `st.logo` used only for an optional collapsed-sidebar icon (Task 27, D5 addendum, AM-19) |
| Nav SVG glyphs | **Accepted deviation** — nav uses Material shortcodes only (Task 25, D5) |

### Traceability — page → archetype → wave → task → guard (AM-11)

| Page | Archetype | Wave | Migration task(s) | Guard-enabled task |
|---|---|---|---|---|
| overview | A1 | C | 29, 30, 31, 32 | 33 |
| gdp, trade_energy, fx_gold, labor | A2 | D | 35 (composition), 36 (headers) | 36 |
| inflation | A3 | E | 38 | 38 |
| welfare | A3 | E | 39 | 39 |
| market | A3 | E | 40 | 40 |
| correlation | A4 | F | 42 | 42 |
| catalog | A5 | G | 44 | 44 |
| all | — | H | — | 46 |

**Owner review gate (AM-23):** Task 34 (OWNER VISUAL REVIEW — shell + Overview
vs mockup) closes Wave C; every task in Waves D–H depends on it.

### Traceability — table/chart → component → migration task (AM-11)

| Table / chart (page) | Component (D1/D12) | Migration task |
|---|---|---|
| Freshness (overview) | HTML table (typed cells) | 30 |
| Coverage (overview) | HTML table | 32 |
| Domain bars (overview) | bar-list component | 31 |
| Survey-year panel (welfare) | HTML table | 39 |
| Chain-linking provenance (inflation) | HTML table | 38 |
| Quality summary (all domain/emphasis pages) | HTML table | 35, 38, 39, 40, 42 |
| Catalog (catalog) | `st.dataframe` | 44 |
| Observations (all domain/emphasis pages) | `st.dataframe(row_height=…)` | 35, 38, 39, 40, 44 |
| Join counts (correlation) | `st.dataframe` | 42 |
| Overlap summary (correlation) | `st.dataframe` | 42 |
| Correlation heatmap | Plotly shared template | 14 (template), 42 |
| Domain line charts | Plotly shared template | 14 |
| Survey-year chart (welfare) | Plotly shared template | 14, 39 |
| Market per-series panels | Plotly shared template | 14, 40 |

### Decisions taken (D1–D14)

**D1 — Tables (decision matrix).** Verified in 1.61.1: `st.html` is available and
sanitizes HTML with DOMPurify `USE_PROFILES:{html:true}`; `st.dataframe` supports
`row_height` (**1.43.0**) and `column_config`; `st.badge` (**1.44.0**) renders
coloured chips. Therefore:
small, static, presentation tables → a shared **RTL HTML table component** (typed
escaped cells, scoped CSS, LTR `<bdi>` spans for ids/units, em-dash for nulls, density
toggle via a CSS class); large/sortable/scrollable tables → **`st.dataframe`**
styled by theme + `column_config`, with `row_height` as the density control and
the documented LTR-grid limitation retained.

| Table (page) | Rows (observed) | Class | Component |
|---|---|---|---|
| Freshness (overview) | 7 | small/static | HTML table |
| Coverage (overview) | 50 | small/static | HTML table |
| Survey-year panel (welfare) | 2 | small/static | HTML table |
| Chain-linking provenance (inflation) | ~3 | small/static | HTML table |
| Quality summary (all domain pages) | = indicator count | small/static | HTML table |
| Catalog (catalog) | 50–54 | sortable | `st.dataframe` |
| Observations (all domain/emphasis pages) | capped 500 (underlying up to ~20 074) | large/scrollable | `st.dataframe` |
| Join counts (correlation) | N×N | matrix | `st.dataframe` |
| Overlap summary (correlation) | N | small/sortable | `st.dataframe` |

**D2 — KPI band.** Overview keeps all six mockup cells. "Derived series" and
"Series without catalog row" are currently the **same set** (32 = 32; verified in
the DB as `derived_and_orphan = 32`), computed by separate expressions in
`_render_series_inventory:796-804`. They are **not** deduped; both get `help=`
tooltips explaining the nesting. "Gold-layer observations" counts catalog-linked
rows only (8 195 of 20 074); the label is kept and the tooltip states the scope.
The band is a reusable component. Tooltip copy is **data-agnostic** (AM-9): it
describes the sets, never a current count or a claim about today's data.

**D3 — Calendar display.** Add `SOURCE_CALENDAR` (source→`"gregorian"`/`"jalali"`)
to `labels.py`, analogous to `SOURCE_EXPECTED_CADENCE:94-104`. Gregorian slugs
(confirmed in `SOURCE_LABELS:80-90`): `world_bank`, `imf`, `eia`. Iranian slugs:
`tgju`, `sci`, `tsetmc`, `hbsir`. The calendar-aware range formatter is **opt-in**
so un-migrated pages are byte-identical. A test pins the opt-in behaviour.

**D4 — Font (ratified).** Vendoring is permitted and now ratified: `AGENTS.md:620`
forbids only cloud infrastructure; `theme.fontFaces` + `server.enableStaticServing=true`
serves a local `static/Vazirmatn.ttf` at `app/static/` with no CDN (1.44.0). The
font and licence are already in the tree at `dashboard/static/Vazirmatn.ttf` and
`dashboard/static/OFL.txt` (variable font, wght 100–900, from the official
`vazirmatn` npm package 33.0.3), but **untracked** (re-verified Wave 0
2026-09-20; `dashboard/Vazirmatn.ttf` / `dashboard/OFL.txt` do not exist). Task 7
**commits** the existing `dashboard/static/` files and wires static serving — no
relocation is required. Do **not** download or replace them. The OS-font fallback
(`FONT_STACK:39`) stays as a safety net only. Browser verification (Task 2
confirmed): `http://localhost:8501/app/static/Vazirmatn.ttf` serves the file
(HTTP 200, `font/ttf`, 241 328 B) and `document.fonts` reports `Vazirmatn`
loaded.

**D5 — Icons and brand.** Use `st.Page(icon=":material/…:")` for every registered
page; `validate_material_icon` was verified and all ten chosen names validate.
Provide a mapping for all ten pages, semantically distinct (see Task 25). Inline
SVG in nav is not supported by `st.Page`.
**D5 addendum — sidebar brand, ordered fallbacks (ratified, AM-19; Wave 0 outcome):** the text brand uses **(2) a comment-marked CSS rule in the chrome block that pins the brand above the navigation**, else **(3) the brand moves into the top bar** and the sidebar shows navigation only. `st.logo` is **not** used for the text brand (image-only API) — it may *optionally* supply only the collapsed-sidebar icon (`icon_image`), never the brand text. **Wave 0 (Task 2) confirmed fallback (2) is stable, but with a corrected recipe:** the brand does **not** come from `st.sidebar` content (that renders in `stSidebarUserContent`, *below* the nav, and reordering it above the nav also drags the DB status up). Instead the brand is emitted via a CSS rule on `[data-testid="stSidebarHeader"]` (which already sits **above** `stSidebarNav`), with the text supplied from `i18n.py` through `t()`; the DB status is pinned at the bottom by `[data-testid="stSidebarContent"]{display:flex;flex-direction:column}` + `[data-testid="stSidebarUserContent"]{order:2;margin-top:auto}`. All hooks are stable `data-testid`s. Task 27 records which one shipped and how the task changed (see Task 27).

**D6 — Theme layering.** Prefer native, then CSS, then HTML:
1. `.streamlit/config.toml` theme options — verified available: `base`,
   `primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`,
   `borderColor`, `baseRadius`, `buttonRadius`, `font`, `headingFont`,
   `codeFont`, `fontFaces`, `headingFontSizes`, `headingFontWeights`,
   `baseFontWeight`, `baseFontSize`, `metricValueFontSize`,
   `dataframeHeaderBackgroundColor`, `showWidgetBorder`, `showSidebarBorder`,
   `chartCategoricalColors`, and the alert colours
   `theme.{red,orange,yellow,blue,green,violet,gray}{Color,BackgroundColor,TextColor}`.
2. Design tokens + scoped CSS in the `direction.py` ownership area.
3. `st.html` components (only where no native element exists).
Streamlit-chrome selectors (sidebar width, active-nav bar, pinned DB status, top
bar) are version-fragile: isolate them in one comment-marked block naming the
tested version (1.61.1) with a manual checklist, because AppTest cannot see chrome.

**D7 — Cache.** Add a minimal config-held TTL to `cached_source_freshness` only
(`queries.py:60`). The explicit refresh control stays deferred.

**D8 — Verification.** No new CI gate for visuals. Wave 0 adds a manual browser
checklist covering all ten pages. An optional dev-only Playwright screenshot
script (Playwright is already a dependency) is added but kept out of `make check`.
`docs/phase-7.2/VALIDATION.md` separates "verified in this run" from "not automated".

**D9 — Streamlit constraint (AM-13).** APIs used and their introducing versions:

| API / config | Introduced | In declared `^1.36`? |
|---|---|---|
| `st.navigation`, `st.Page`, `st.page_link` | 1.36.0 | yes |
| `st.html` | 1.33.0 | yes |
| `st.metric(help=…)` | 1.36.0 | yes |
| `st.logo` | 1.35.0 | no |
| `st.container(border=True)` | 1.29.0 | yes |
| `st.segmented_control` (density toggle) | 1.40.0 | no |
| `st.dataframe(row_height=…)` | **1.43.0** | **no** |
| `st.badge` | **1.44.0** | **no** |
| Advanced theming: `theme.fontFaces`, `theme.font`/`headingFont`/`codeFont`, heading size/weight arrays, alert colour options | **1.44.0** | **no** |
| `client.toolbarMode` | present in 1.61.1; `viewer` fixed in 1.54.0; exact introducing version confirmed in Task 1 | n/a |

The highest requirement is **1.44.0**, so the proposed floor `>=1.44,<2` is
**still sufficient**. Task 6 raises the floor to `>=1.44,<2` and refreshes the lock
(lock already resolves 1.61.1, so no package version changes — the 7.1 precedent,
`docs/phase-7.1/VALIDATION.md`).

**D10 — Pure helpers.** `relative_time_label(now, then)` goes in `formatting.py`
(injectable `now`, Persian strings via `i18n`); `freshness_summary(frame, now)` and
the stale-first ordering go in `page_view.py` next to `freshness_display`. Both get
unit tests.

**D11 — Consistency guard.** Define the layout contract (one page-header pattern
via `render_page_header`, one KPI-band pattern, one section-header pattern, one
filter-bar pattern, shared empty/error/loading states) and enforce it with an AST
guard modelled on `test_literal_guard.py`. The guard fails when a **migrated**
page calls raw `st.title`, `st.metric`, `st.warning`/`st.info`/`st.error`, or
`unsafe_allow_html` where a shared component exists. Because every page
composition lives in one large module (`page_view.py`), the guard must be
**function-scoped**: `MIGRATED_PAGES` is a mapping of module → migrated function
names, not a set of files (AM-14). A `MIGRATED_PAGES` entry lets it be enabled per
function as each wave lands. False-positive risk: the shared components
themselves call those APIs, so they are whitelisted exactly as `i18n.py`/`labels.py`
are — the whitelist is the shared-component modules (`components/layout.py` incl.
`render_page_header`/`render_callout`/`render_kpi_band`/`render_section_header`/
`render_filter_bar`, `components/states.py`, `components/html_table.py`,
`components/direction.py`), not the page modules.

**D12 — Charts.** One Plotly template built from the tokens
(`direction.plotly_template:107`) with the Persian font, token palette, token grid
and RTL-friendly legend/axis placement. Every builder already funnels through
`apply_plotly_typography` (`charts.py:341,377,445,626`), so the template is the
single lever. The image export path (`exports.serialize_figure_images:139`) renders
via Kaleido/Chromium and must be smoke-tested with the new template.

**D13 — Callouts, page header, KPI cells and states are native-first (ratified).**
Shared callout, page header, KPI cells and states are built on native elements
(`st.warning`/`st.info`/`st.error`, `st.title`, `st.metric`,
`st.container(border=True)`, `st.columns`, `st.badge` where a standalone chip is
needed) styled by theme options and scoped CSS. `st.html` is used only where no
native element exists (the RTL HTML table cells, the bar itself inside a bar-list
row, the brand block). Where a native element must coexist with an HTML fragment,
the row is composed with native `st.columns` — e.g. the domain bar-list row is a
native `st.page_link` (owner link) beside a small escaped `st.html` bar (AM-17) —
because `st.page_link` cannot live inside `st.html`. This
keeps AppTest visibility and reduces the escaping surface. The D11 guard bans raw
calls in page modules while the shared component modules are whitelisted.

**D14 — Theme lock, light only (ratified).** `base="light"` is locked; dark mode
is not supported in 7.2 and is deferred. **D14 addendum (ratified, AM-19; Wave 0
outcome):** a custom `[theme]` in `.streamlit/config.toml` **already removes the
settings-menu theme toggle** in 1.61.1 — Task 2/4 compared a custom-theme app (no
`stMainMenuItem-theme-*` in the DOM) against a no-theme control
(`stMainMenuItem-theme-System/Light/Dark` present and visible). **No
`toolbarMode` change is needed to hide the toggle**; the locked theme meets the
requirement. Recommended `client.toolbarMode = "viewer"` (Task 2) to also hide
the native Deploy button and developer options while keeping the kebab and the
viewer options (Print, Record screen); `minimal` is not recommended (it removes
Print/Record screen). **No CSS hacks on the native settings menu.** The developer
override `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` (env var) is documented in the
README so local development keeps the toolbar. Dark mode is listed in Deferred
Scope.

---

## Proposed Approach

Build the design system first, then the shell, then migrate pages one archetype per
wave. Each wave is independently shippable: the shared components are additive and
the layout contract is opt-in until a page adopts it, so the dashboard renders at
every commit. The Overview is the reference implementation; the other archetypes
compose the same components in the same visual language, with an owner visual
review per archetype because only the Overview has a mockup.

The migration order is by shared surface, not by page number: the escaping helper
and the HTML table land **first** (Task 15) so every dependent table task can rely
on them; the generic domain explorer (four pages, one code path) precedes the
emphasis pages, which reuse its composition; correlation and catalog are
single-page archetypes.

A dedicated test-migration task (Task 16) lands with the table component, because
AppTest cannot read `st.html` text and the affected suites must move to the new
assertion strategy before later waves rely on them.

Because the Wave A global look (Tasks 7–9) changes the font, base size, colours,
alert tint and radius for all ten pages, the pages are **not** visually unchanged
after Wave A: Task 10 (the dev-only screenshot script) and Task 24 (the Wave A
after-screenshot regression review) make that change explicit and reviewed.

---

### Milestones

| Milestone | Waves | Exit criterion |
|---|---|---|
| Capabilities confirmed | 0 | Spike recorded; inventory verified; floor decision made; **baseline captured (Task 1: `make check`, `mypy src dashboard` error count, `pytest tests/unit/dashboard -q` counts, "before" screenshots)**; `st.html`/brand/toolbar/theme behaviours confirmed in a browser |
| Design system available | A | Tokens, theme, font, formatters and components exist and are tested; the global look changes for all ten pages (font, 14 px base, colours, alert tint, radius) and the after-screenshot regression review (Task 24) is recorded |
| Shell shipped | B | Sidebar/brand/icons/status/top bar render; all pages still pass smoke |
| Reference page shipped | C | Overview matches the mockup; **owner review gate passed (Task 34)**; guard on for Overview |
| Archetypes migrated | D–G | Every page composes the shared components; guard on for each; **every D–H task depends on the Task 34 gate** |
| Consistent product | H | Guard on for all pages; validation + design-system docs written |

---

## Task Metadata

**Type:** Refactor (presentation layer) + Enhancement (shared design system)
**Complexity:** High
**Affected Areas:** `dashboard/**` (presentation only), `.streamlit/config.toml`, `pyproject.toml`, `tests/unit/dashboard/**`, `docs/phase-7.2/**`, `docs/design/phase-7.2/**`, `dashboard/static/**`
**Dependencies:** Streamlit ≥1.44 (floor raise), Plotly 6.x, existing `jdatetime`; no new runtime dependency

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `AGENTS.md` — hard boundaries: dashboard must not touch `src/`/`alembic/`/`airflow/`; Gold-only reads; data contracts.
- `docs/plans/phase-7.1-dashboard-refresh.md` — structural template; "Deferred Scope (Phase 7.2 candidates)" at line 1432.
- `docs/phase-7.1/VALIDATION.md`, `docs/phase-7.1/README.md`, `docs/phase-7.1/wave-0-spike.md` — AppTest/router limitations and the accepted deviations.
- `docs/design/phase-7.2/overview-redesign-mockup.html` — the Overview design spec.
- `dashboard/app.py` — the shell and router entrypoint.
- `dashboard/navigation.py` — the page registry and domain ownership.
- `dashboard/page_view.py` — every page composition (`render_*` at 138, 155, 196, 413, 588, 742, 913, 929, 970, 1002).
- `dashboard/components/direction.py` — the single DOM/CSS owner and the Plotly template.
- `dashboard/components/tables.py` — `localize_table_frame`, `cap_table_rows`, the Jalali-column rule, `MISSING_VALUE`.
- `dashboard/components/charts.py` — chart builders and `apply_plotly_typography` usage.
- `dashboard/components/exports.py` — CSV/Excel/HTML/PNG/SVG export path.
- `dashboard/components/filters.py` — `render_filters` and Jalali presets.
- `dashboard/components/quality.py` — `render_quality_summary`.
- `dashboard/i18n.py`, `dashboard/labels.py`, `dashboard/formatting.py` — the three presentation owners.
- `.streamlit/config.toml` — theme baseline.
- `dashboard/Vazirmatn.ttf`, `dashboard/OFL.txt` — the vendored font and licence to relocate (D4).
- `tests/unit/dashboard/test_literal_guard.py`, `app_smoke.py`, `test_direction.py`, `test_tables.py`, `test_navigation.py` — the patterns the new tests must follow.

### Data / ML References

- `dashboard/repository.py` — the six read-only queries; `source_freshness:296`, `coverage_summary:206`, `series_inventory:262`, `available_domains:325`.
- `dashboard/queries.py` — cached wrappers; TTL change lands at `cached_source_freshness:60`.
- `src/database/schema.py` — `DataCollectionLog` (status, records_collected, collection_timestamp) and `IndicatorCatalog` (unit, frequency, availability_start/end).

### External Documentation

- Streamlit release notes 2024/2025 (1.35.0 `st.logo`; 1.40.0 `st.segmented_control`; 1.43.0 `row_height`; 1.44.0 advanced theming, `fontFaces`, `st.badge`; 1.54.0 `toolbarMode="viewer"` fix) — https://docs.streamlit.io/develop/quick-reference/release-notes
- Streamlit variable-fonts tutorial (`server.enableStaticServing`, `app/static/…`) — https://docs.streamlit.io/develop/tutorials/configuration-and-theming/variable-fonts
- Streamlit theming options — https://docs.streamlit.io/develop/api-reference/configuration/config.toml

### Patterns to Follow

**Naming:** snake_case modules/functions, PascalCase classes, UPPER constants; JSONB attribute is `record_metadata`.
**Structure:** one concern per module; page modules stay thin delegates; components under `dashboard/components/`.
**Testing:** pure helpers unit-tested with injectable `now`; `AppTest` through the router harness (`app_smoke.app_test`); HTML components tested through their pure render functions and, where needed, `app.get("html")[i].proto.body`; AST guard in the `test_literal_guard.py` style.
**Data/ML:** Gold-only reads; no interpolation/forward-fill/normalization; timezone-aware UTC storage; `Asia/Tehran` display only.

---

## IMPLEMENTATION PHASES

### Wave 0: Verification spike + inventory
Confirm every version-specific capability and the AGENTS wording before writing
code. No production file changes except the recorded spike note. Ends with a
browser pass for the behaviours a source read cannot prove (AM-5, AM-6, AM-7, D14).

### Wave A: Foundation
Theme, font, tokens, formatters, calendar mapping, Plotly template and the base
shared components (escaping + HTML table first). Tasks 7–9 change the **global
look for all ten pages** (font, 14 px base, colours, alert tint, radius), so the
pages are **not** visually unchanged after Wave A; the moved dev-only screenshot
script (Task 10) and the after-screenshot regression review (Task 24) capture and
review that change against the Task 1 baseline.

### Wave B: Shell
Sidebar, brand, Material nav icons, active-item style, DB status, top bar/breadcrumb.

### Wave C: Overview (reference implementation)
Match the mockup using the Wave A components, then close the wave with the owner
visual review gate (Task 34, shell + Overview vs mockup) that Waves D–H depend on.

### Wave D: Generic domain explorer (A2)
GDP, Trade & Energy, FX & Gold, Labor.

### Wave E: Emphasis-domain pages (A3)
Inflation, Welfare, Market.

### Wave F: Comparison / correlation (A4)

### Wave G: Catalog (A5)

### Wave H: Cross-page consistency audit
Enable the guard for all pages, run the full regression, write
`docs/phase-7.2/README.md` and `docs/phase-7.2/VALIDATION.md`.

---

## STEP-BY-STEP TASKS

Every task lists **Files**, **Build**, **i18n keys**, **Depends**, a checkbox
**Acceptance** list and a **Verify** command or manual step. Execute in order.

---

### 1. (0) VERIFY Streamlit capabilities, APIs, sanitization and AGENTS wording; RECORD the pre-change baseline

- **Files:** `docs/phase-7.2/wave-0-spike.md` (new), `docs/phase-7.2/README.md` (new, stub), `docs/phase-7.2/wave-0-assets/before/` (new directory, ten PNGs).
- **Build (AM-21):** Record, with the exact command output, (a) installed Streamlit version; (b) the exact font theme option names (`theme.font`, `theme.fontFaces`, `theme.headingFont`, `theme.codeFont`, `theme.headingFontSizes`, `theme.headingFontWeights`) and the alert colour options (`theme.{red,orange,blue,green,yellow}.{Color,BackgroundColor,TextColor}`); (c) that `st.html`, `st.badge`, `st.segmented_control`, `st.container(border=True)`, `st.dataframe(row_height=…)`, `st.metric(help=…)` exist; (d) the Material icon set size and that the final ten names validate; (e) the `st.logo` signature and that it is image-only; (f) the `client.toolbarMode` allowed values and the introducing version; (g) the exact AGENTS.md sentence about offline/cloud (line 620) and the `direction.py:14-16` / `.streamlit/config.toml:5-6` offline convention; (h) the **separator** check: render `format_number(8195)` in a browser and record whether the glyph is U+066C or U+060C; (i) the **pre-change baseline**: the `make check` result, the `poetry run mypy src dashboard` result **as an error count**, the `pytest tests/unit/dashboard -q` pass counts, and "before" screenshots of all ten pages at 1440×900 taken with a throwaway Playwright snippet and stored in `docs/phase-7.2/wave-0-assets/before/`. If `mypy dashboard` already reports errors, record that count as the baseline and define the per-wave gate as **"no new errors"** rather than "zero"; otherwise the gate stays "zero".
- **i18n keys:** none.
- **Depends:** —
- **Acceptance:**
  - [x] Spike note records each item with its raw evidence.
  - [x] Separator result recorded as confirmed or refuted (do not treat as a delta unless confirmed).
  - [x] AGENTS.md is quoted verbatim where the discovery claimed a font/CDN rule.
  - [x] `st.logo` and `client.toolbarMode` findings recorded.
  - [x] Baseline recorded: `make check`, `mypy src dashboard` error count, `pytest tests/unit/dashboard -q` counts, and ten "before" screenshots under `docs/phase-7.2/wave-0-assets/before/`.
  - [x] If `mypy dashboard` has pre-existing errors, the per-wave gate is recorded as "no new errors"; otherwise as "zero". **→ zero errors → gate is "zero".**
- **Verify:** `poetry run python -c "import streamlit; print(streamlit.__version__)"`, `make check`, `poetry run mypy src dashboard`, `poetry run pytest tests/unit/dashboard -q`, plus a manual browser screenshot of the Overview KPI band.

### 2. (0) VERIFY shell DOM selectors, static serving, toolbar mode and brand fallbacks

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append).
- **Build:** In a running app, confirm (a) the sidebar/active-nav/top-bar DOM can be targeted by the existing `CSS_SELECTORS` pattern; (b) `server.enableStaticServing=true` serves a file at `app/static/<name>` when `static/` sits beside `dashboard/app.py`; (c) `[[theme.fontFaces]]` loads the served font; (d) the `client.toolbarMode` value that hides the native Deploy button/kebab (and, per D14 addendum, the settings-menu theme toggle) without removing anything the analyst needs; (e) which sidebar-brand fallback (D5 addendum, AM-19) is stable — the **CSS-pinned brand block above the nav (2)** first, else **brand-in-top-bar (3)**; `st.logo` is not used for the text brand (it may only supply the collapsed-sidebar `icon_image`). Record which selectors are stable vs fragile at 1.61.1.
- **Wave 0 outcome (2026-09-20, recorded in `docs/phase-7.2/wave-0-spike.md` §4):** (b) `/app/static/Vazirmatn.ttf` → 200 `font/ttf` 241 328 B; the wrong `app/dashboard/static/…` path returns the SPA shell with HTTP 200 (fails silently). (c) `document.fonts` reports `Vazirmatn` `loaded` (weight `100 900`). (d) the custom `[theme]` **already hides the theme toggle** (no `stMainMenuItem-theme-*`); recommended `toolbarMode="viewer"` to hide Deploy + developer options while keeping Print/Record screen. (e) **fallback (2) is stable with a corrected recipe** — brand via `[data-testid="stSidebarHeader"]` CSS (above nav) + DB status pinned via `stSidebarContent` flex + `stSidebarUserContent{margin-top:auto}` (see D5 addendum and Task 27). Stable hooks are all `data-testid`s + `[aria-current="page"]`; the active-link `st-emotion-cache-*` class is FRAGILE.
- **i18n keys:** none.
- **Depends:** Task 1.
- **Acceptance:**
  - [x] Font served locally and rendered from `dashboard/static/`, or the failure recorded with its cause and the corrected path.
  - [x] The chosen sidebar-brand fallback recorded (CSS-pinned block preferred, else top bar), with how Task 27 changes.
  - [x] The chosen `toolbarMode` value recorded, including whether it hides the theme toggle without removing needed controls (D14 addendum).
  - [x] Fragile selectors listed explicitly for D6's isolated block.
- **Verify:** Manual browser check on `make dashboard`.

### 3. (0) RECORD the verified page inventory and archetypes

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append).
- **Build:** Re-verify the PAGE INVENTORY table above against the code (ten pages, their `render_*` symbols and line numbers) and the archetype grouping. Correct any drift in this plan's Context.
- **Wave 0 outcome (2026-09-20):** ten page modules under `dashboard/pages/`, ten `PageSpec` rows; every `render_*` symbol and line number in the PAGE INVENTORY matches the current `page_view.py` (`render_overview_page:742`, `render_correlation_page:1002`, `render_catalog_page:588`, `render_inflation_page:196`, `render_domain_page:138`/`render_domain_body:155`, `render_fx_gold_page:913`, `render_welfare_page:929`, `render_market_page:413`, `render_labor_page:970`); archetypes A1–A5 verified against the code. **No drift — no plan correction needed.**
- **i18n keys:** none.
- **Depends:** Task 1.
- **Acceptance:**
  - [x] Ten pages accounted for; each mapped to one archetype.
  - [x] Any line-number drift corrected in the plan (none found).
- **Verify:** `poetry run python -m pytest tests/unit/dashboard/test_navigation.py -q` and a manual read of `navigation.py:52-121`.

### 4. (0) VERIFY st.html browser rendering and theme-switcher behaviour

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append).
- **Build (AM-19):** In a running app, render an `st.html` probe containing a `<style>` block, a `class`, an inline `style`, a `title`, a `dir="rtl"`, a `<bdi>` and an `<svg>`, and record which survive to the DOM (the source read shows DOMPurify `USE_PROFILES:{html:true}`; rendering cannot be proven from source). Separately, confirm in the settings menu whether the theme toggle is still offered when a custom `[theme]` is defined, and decide per the D14 addendum: use `client.toolbarMode="viewer"`/`"minimal"` to hide it **only if** that hides the toggle without removing anything the analyst needs; otherwise accept and document the limitation. **No CSS hacks on the native settings menu.**
- **Wave 0 outcome (2026-09-20, recorded in `docs/phase-7.2/wave-0-spike.md` §6):** `st.html` **keeps** `<style>` (rule applies), `class`, inline `style`, `title`, `dir="rtl"`, `<bdi>`, `data-*` and `<a href>`; `<svg>` is **stripped** (use an icon font / Material glyph or a CSS-drawn shape instead). `st.markdown(unsafe_allow_html=True)` CSS applies (confirmed, as `direction.py:104` relies on). A `<td title>` survives; the native hover tooltip could not be captured in headless Chromium (UNVERIFIED — see the spike note's owner checklist). Theme toggle: **already hidden by the custom `[theme]`** (no-theme control exposes System/Light/Dark); no toolbarMode change needed.
- **i18n keys:** none.
- **Depends:** Tasks 1, 2.
- **Acceptance:**
  - [x] Survival of each probe element/attribute recorded; any non-surviving attribute has a named alternative (`data-` + CSS `::after`, or `st.markdown(unsafe_allow_html=True)`).
  - [x] Theme-toggle behaviour recorded; the mitigation (toolbarMode) or the accepted limitation written into the design-system doc and NOTES.
  - [x] The developer override `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` is noted for the README (Task 47).
- **Verify:** Manual browser check on `make dashboard`.

---

### 5. (A) ADD the design-token module

- **Files:** `dashboard/components/tokens.py` (new), `tests/unit/dashboard/test_tokens.py` (new).
- **Build:** A frozen `Mapping` of the mockup tokens (bg, surface, border, border-strong, text-1/2/3, accent, accent-soft, ok/warn/err + their soft backgrounds, neutral-bg, radius 6/8, mono family, and the Vazirmatn UI family) plus helpers to emit them as CSS custom properties. This is the single source the theme table, the CSS and the Plotly template read.
- **i18n keys:** none.
- **Depends:** —
- **Acceptance:**
  - [x] Tokens are immutable and typed; no literal colour remains outside this module and `.streamlit/config.toml`.
  - [x] A test asserts the token set matches the mockup's `:root` block.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_tokens.py -q`.

### 6. (A) RAISE the Streamlit floor and refresh the lock

- **Files:** `pyproject.toml`, `poetry.lock`.
- **Build:** Change the Streamlit constraint from `^1.36` to `>=1.44,<2` (D9, AM-13). The highest API requirement is 1.44.0 (`fontFaces`/`badge`/advanced theming), so `>=1.44` remains sufficient; do not raise it further unless Task 1 shows a higher requirement. Refresh the lock only; no package version should change (installed is already 1.61.1). Note the lock-file implication in the plan's NOTES.
- **i18n keys:** none.
- **Depends:** Task 1.
- **Acceptance:**
  - [x] Constraint updated; `poetry lock` shows no version deltas.
  - [x] `make check` still passes.
- **Verify:** `poetry check && poetry run pytest tests/unit/dashboard -q`.

### 7. (A) VENDOR the Vazirmatn font and wire theme + static serving

- **Files:** `dashboard/static/Vazirmatn.ttf`, `dashboard/static/OFL.txt` (both already present, untracked), `.streamlit/config.toml`, `dashboard/components/tokens.py` (font token), `.gitignore`, packaging/Docker copy-paths, `docs/phase-7.2/design-system.md`.
- **Build (AM-20; Wave 0 re-verified):** **Commit** the existing font and licence under `dashboard/static/` — **verified now (Wave 0, 2026-09-20)** they are already at `dashboard/static/Vazirmatn.ttf` (241 328 B) and `dashboard/static/OFL.txt` (4 391 B), untracked, and `dashboard/Vazirmatn.ttf` / `dashboard/OFL.txt` do not exist. No relocation step is required (the earlier "still at `dashboard/`" claim was stale). Do **not** download or replace them. Set `[server] enableStaticServing = true`; add `[[theme.fontFaces]]` with `family="Vazirmatn"`, `url="app/static/Vazirmatn.ttf"` and `weight="100 900"`; set `theme.font`, `theme.headingFont`, `theme.codeFont` to full fallback stacks (`Vazirmatn, IRANSans, Tahoma, Segoe UI, sans-serif` for UI; the mono stack for code). Keep the licence file beside the font. Check `.gitignore`, packaging and Docker/Compose copy-paths so `dashboard/static/` ships with the dashboard. Describe the graceful fallback to the OS stack. The `app/static/…` URL is **confirmed** to resolve (Task 2: HTTP 200, `font/ttf`, 241 328 B; `document.fonts` reports `Vazirmatn` loaded). Update the existing 7.1 comments in `.streamlit/config.toml:4-6` and `direction.py:14-16` so they no longer contradict the code. **AM-24:** this is the first of the three global-look tasks (7, 8, 9); once it lands the font changes on all ten pages, so the pages are **not** visually unchanged — Task 10's screenshot script and Task 24's after-screenshot review cover it.
- **i18n keys:** none.
- **Depends:** Tasks 2, 5.
- **Acceptance:**
  - [x] Font and licence under `dashboard/static/`, tracked in git; `dashboard/static/` ships with the dashboard.
  - [x] Theme font options resolve to the vendored family; OS fallback documented.
  - [x] `http://localhost:8501/app/static/Vazirmatn.ttf` serves the file and the rendered UI uses Vazirmatn.
  - [x] The two stale 7.1 comments corrected.
- **Verify:** Browser check of `http://localhost:8501/app/static/Vazirmatn.ttf` and that Persian text renders in Vazirmatn + `poetry run python -c "import streamlit.config as c; print([k for k in c.get_config_options() if 'font' in k])"`.

### 8. (A) UPDATE the Streamlit theme to the design tokens

- **Files:** `.streamlit/config.toml`.
- **Build:** Set `base="light"`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `borderColor`, `baseRadius`, `buttonRadius`, `primaryColor` (accent), `baseFontSize=14`, `dataframeHeaderBackgroundColor`, `showWidgetBorder`, `showSidebarBorder`, `chartCategoricalColors`, and the alert colours (`theme.red/orange/blue/green/yellow{Color,BackgroundColor,TextColor}`) from the tokens so `st.warning`/`st.info`/`st.error` match the amber/blue/red tokens. `font`, `headingFont`, `codeFont` and `fontFaces` are **owned by Task 7** and only referenced here (no duplicates). Keep the existing header comment and extend it with the token module reference. **AM-24:** this is the second of the three global-look tasks (7, 8, 9); after it the colours, 14 px base size, alert tint and radius change on all ten pages, so the pages are **not** visually unchanged — Task 10's screenshot script and Task 24's after-screenshot review cover it.
- **i18n keys:** none.
- **Depends:** Tasks 5, 7.
- **Acceptance:**
  - [x] Every colour/radius in the theme matches `tokens.py`.
  - [x] `font`/`fontFaces` are not duplicated (Task 7 owns them).
  - [x] App starts with the new theme and no config error.
- **Verify:** `make dashboard` (manual) + `poetry run python -c "import streamlit.config as c; c.get_config_options()"`.

### 9. (A) EXTEND the shell CSS owner with tokens and the chrome block

- **Files:** `dashboard/components/direction.py`, `tests/unit/dashboard/test_direction.py`.
- **Build:** Emit the token custom properties into `direction_css()` and add a comment-marked, version-named block for Streamlit-chrome selectors (sidebar width 256 px, active-nav accent bar, pinned DB status, top bar, main-container top padding, max content width 1360 px). Keep `CSS_SELECTORS` as the one selector registry; add any new selector there. Keep CSS injection on `st.markdown(..., unsafe_allow_html=True)` (`direction.py:104`) so `test_direction.py`'s `app.markdown` assertions stay valid. **AM-24:** this is the third of the three global-look tasks (7, 8, 9); the chrome/layout changes affect all ten pages, so the pages are **not** visually unchanged — Task 10's screenshot script and Task 24's after-screenshot review cover it.
- **i18n keys:** none.
- **Depends:** Tasks 2, 5.
- **Acceptance:**
  - [x] The chrome block is the only place with version-fragile selectors and names the tested version (1.61.1).
  - [x] The selector set is consistent with the Wave 0 selector findings (Task 2).
  - [x] `test_direction.py` still passes and gains a test that the chrome block is comment-tagged.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_direction.py -q`.

### 10. (A) ADD the dev-only screenshot script (moved from Wave H; AM-24)

- **Files:** `scripts/dashboard_screenshots.py` (new), `Makefile` (new non-default target).
- **Build (AM-24):** A Playwright script that visits all ten pages at 1440×900 and writes PNGs to a gitignored directory. It is the reusable capture tool behind the Task 24 after-screenshots and is reused by the later audit tasks (Tasks 47, 48). **Not** part of `make check` (D8). It lands here, immediately after the global-look tasks (7–9), so it exists when the Wave A global change is reviewed.
- **i18n keys:** none.
- **Depends:** Task 9.
- **Acceptance:**
  - [x] Script runs locally and produces ten images, or records why Chromium is unavailable.
  - [x] `make check` does not invoke it.
  - [x] Captures at 1440×900 so its output is comparable with the Task 1 baseline.
- **Verify:** `poetry run python scripts/dashboard_screenshots.py` (manual, optional).

### 11. (A) ADD the relative-time formatter

- **Files:** `dashboard/formatting.py`, `dashboard/i18n.py`, `tests/unit/dashboard/test_formatting.py`.
- **Build:** `relative_time_label(value, *, now, digit_mode="fa") -> str` returning "امروز", "{n} ساعت پیش", "{n} روز پیش" (and a week/month granularity). `now` is required and injectable; a future instant clamps to "امروز".
- **i18n keys:** `value.relative_today`="امروز", `value.relative_hours_ago`="{count} ساعت پیش", `value.relative_days_ago`="{count} روز پیش", `value.relative_months_ago`="{count} ماه پیش".
- **Depends:** —
- **Acceptance:**
  - [x] Pure function; no wall-clock call inside.
  - [x] Tests pin today/hours/days/months and the future-clamp.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_formatting.py -q`.

### 12. (A) ADD the freshness aggregate and stale-first ordering

- **Files:** `dashboard/page_view.py`, `dashboard/i18n.py`, `tests/unit/dashboard/test_app_overview.py`.
- **Build:** `freshness_summary(frame, *, now) -> tuple[int, int]` (fresh, stale) reusing `_staleness_label`, and make `freshness_display` order stale rows first while keeping a stable secondary order. `freshness_display` already accepts `now:829`.
- **i18n keys:** `section.freshness_summary`="{fresh} به‌روز · {stale} کهنه".
- **Depends:** Task 11.
- **Acceptance:**
  - [x] Aggregate and ordering are pure and `now`-injectable.
  - [x] Existing `test_freshness_display_*` tests still pass; new tests pin the order and counts.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_overview.py -q`.

### 13. (A) ADD the source calendar map and calendar-aware range formatter

- **Files:** `dashboard/labels.py`, `dashboard/formatting.py`, `tests/unit/dashboard/test_labels.py`, `tests/unit/dashboard/test_formatting.py`.
- **Build:** `SOURCE_CALENDAR` in `labels.py` (`world_bank`/`imf`/`eia` → `"gregorian"`; `tgju`/`sci`/`tsetmc`/`hbsir` → `"jalali"`) plus `source_calendar(source_name) -> str | None`. In `formatting.py`, `range_label(start, end, *, frequency, calendar, digit_mode)` renders Gregorian periods for `"gregorian"` and Jalali periods otherwise. **AM-27(e):** for a Gregorian source, `range_label` renders an **annual** series as the year only (`2023`) and a **monthly or daily** series as year-month (`2023-05`), never a Jalali period and never a bare year for a sub-annual series; this is pinned by a test. Default `calendar="jalali"` so un-migrated callers are unchanged.
- **i18n keys:** `table.coverage_footnote`="تاریخ مشاهدهٔ منابع میلادی (مانند بانک جهانی) به‌صورت سال میلادی نمایش داده می‌شود؛ تاریخ دقیق در راهنمای هر خانه است."
- **Depends:** Task 5.
- **Acceptance:**
  - [x] Opt-in proven by a test that the default output equals today's Jalali output byte-for-byte.
  - [x] Gregorian mapping covers exactly the three non-Iranian slugs.
  - [x] A test pins annual Gregorian → year only and monthly/daily Gregorian → year-month (`2023` vs `2023-05`).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_formatting.py tests/unit/dashboard/test_labels.py -q`.

### 14. (A) REBUILD the Plotly template from the tokens

- **Files:** `dashboard/components/direction.py`, `tests/unit/dashboard/test_direction.py`, `tests/unit/dashboard/test_charts.py`, `tests/unit/dashboard/test_exports.py`.
- **Build:** Extend `plotly_template:107` with the token palette (`chartCategoricalColors`), token grid/border colours, and RTL-friendly legend/axis placement. **AM-27(a):** because the template now covers palette, grid and legend/axis placement as well as typography, the contract test `test_plotly_template_is_typography_only` must be explicitly revised — **renamed or split** (e.g. `test_plotly_template_is_typography_palette_and_layout_only` plus a focused typography test) — so its name and assertions match the new scope. What stays **forbidden** in the template is figure **sizing** (width/height/autosize) and **margins** (they stay the builders' own); the test must assert those are absent from the template. All builders already call `apply_plotly_typography`.
- **i18n keys:** none.
- **Depends:** Tasks 5, 9.
- **Acceptance:**
  - [x] The template contract test is renamed/split and passes; it asserts the template covers typography **plus** palette/grid/legend-axis placement and still forbids sizing and margins (extended, not weakened).
  - [x] `test_charts.py` passes; a new assertion checks the token palette is applied.
  - [x] **AM-25:** `tests/unit/dashboard/test_exports.py` includes a Kaleido PNG **and** SVG render smoke of at least one figure built with the new template (the export path is exercised here, not only in the final audit).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_charts.py tests/unit/dashboard/test_direction.py tests/unit/dashboard/test_exports.py -q`.

### 15. (A) ADD the escaping helper and the RTL HTML table with the typed cell model

- **Files:** `dashboard/components/html_table.py` (new), `dashboard/components/escaping.py` (new), `tests/unit/dashboard/test_html_table.py` (new), `tests/unit/dashboard/test_escaping.py` (new).
- **Build:** `render_html_table(columns, rows, *, density="comfortable", null_placeholder=MISSING_VALUE)`. Replace `ltr_columns`/`title_columns` with a **typed cell model**, a `Cell` union:
  - `Text(value, *, title=None)` — plain text, escaped;
  - `Ltr(value, *, title=None)` — mono, wrapped in `<bdi class="ltr">`;
  - `UnitChip(value, *, title=None)` — LTR mono chip;
  - `StatusChip(label, tone, *, title=None)` — HTML/CSS chip with a token tone;
  - `Dot(label, tone, *, title=None)` — HTML/CSS status dot;
  - `TwoLine(primary, secondary_parts, *, title=None)` — name + LTR id beneath, or date + time · relative age.
  Every variant carries an optional `title` tooltip and handles null (`None` → `MISSING_VALUE` em-dash, except chips/dots). **Every data-derived value is escaped** (`html.escape`) before interpolation. Chips and dots here are pure HTML/CSS and are **not** `st.badge` (which cannot live inside `st.html`); they read tone tokens from `tokens.py`. `st.badge`-based chips are for standalone use outside tables (Task 20). Density toggles a CSS class. Scoped CSS lives in the `direction.py` ownership area. **AM-26:** the whole table is emitted inside a wrapper element with `overflow-x: auto` so a wide table scrolls **within its own box** and the page never scrolls sideways; long ids/units (the `Ltr`/`UnitChip` cells) use `max-width` + ellipsis/wrap inside the wrapper so they cannot break the page layout.
- **i18n keys:** none (headers come from `t()` keys supplied by callers).
- **Depends:** Tasks 5, 9.
- **Acceptance:**
  - [x] An explicit test feeds `<script>`, `&`, `"` and Persian text through **every cell variant** and asserts the output is escaped.
  - [x] LTR spans isolate ids/units without flipping the table.
  - [x] Density class toggles between comfortable and compact.
  - [x] Null handling is tested per variant.
  - [x] **AM-26:** the wrapper carries `overflow-x: auto`; a test asserts the wrapper attribute/style is present, and long ids/units do not break the layout.
  - [x] **AM-26:** the Overview coverage table is manually checked at **1280 px and 1024 px** viewport widths — the table scrolls inside its wrapper and the page does not scroll sideways. **(verified on the Task 15 probe app, 2026-09-21 — the real Overview table does not exist until Task 32; re-check added to Task 32.)**
- **Verify:** `poetry run pytest tests/unit/dashboard/test_html_table.py tests/unit/dashboard/test_escaping.py -q` + the 1280 px / 1024 px manual check of the Overview coverage table (Task 32 renders it).

### 16. (A) ADD the AppTest HTML-text helper and record the test-migration map

- **Files:** `tests/unit/dashboard/app_smoke.py` (helper), `tests/unit/dashboard/test_html_text_helper.py` (new, unit test for the helper).
- **Build (AM-18):** Add a small helper (e.g. `html_texts(app) -> list[str]` reading `app.get("html")[i].proto.body`) so an AppTest can assert on the markup produced by `render_html_table`. **This task only adds the helper and records the map**; each affected suite is rewritten by the task that causes the change (Tasks 30, 32, 35, 39), not here. The table below is the migration map; every "must pass unchanged" claim in this plan is bounded by it.

  | Existing test | Assertion type | Affected by which task | Required change |
  |---|---|---|---|
  | `test_app_overview.py` | `app.title` | 33 (header native) | none |
  | `test_app_overview.py` | `app.warning` | 33 (callout native) | none |
  | `test_app_overview.py` | `app.metric` | 29 (KPI band native) | none |
  | `test_app_overview.py` | `app.subheader` | 33 (section header native) | none |
  | `test_app_overview.py` | `app.dataframe` (freshness, coverage) | 30, 32 (→ `st.html`) | rewrite: assert markup via `html_texts` / component render test |
  | `test_app_correlation.py` | `app.warning`, `app.caption` | 42 | none |
  | `test_app_correlation.py` | `app.dataframe` (join/overlap) | 42 (stay `st.dataframe`) | none |
  | `test_app_catalog.py` | `app.dataframe`, `app.info` | 44 (grid stays; callout native) | none |
  | `test_app_economy.py` | `app.title`, `app.subheader`, `app.caption` | 36 | none |
  | `test_app_economy.py` | `app.dataframe` (observations) | 35 (stays `st.dataframe`) | none |
  | `test_app_trade_welfare.py` | *(no `app.dataframe` assertion)* | 35 | none — **corrected 2026-09-21**: the file only smoke-asserts `not app.exception`; there is no quality-table dataframe assertion to migrate |
  | `test_app_fx_gold.py` | *(no `app.dataframe` assertion)* | 35 | none — **corrected 2026-09-21**: same as `test_app_trade_welfare.py`, smoke-only |
  | `test_app_labor.py` | `app.title`, `app.info` | 36 | none |
  | `test_app_labor.py` | `app.dataframe` (quality, `table.rows_returned`) | 35 | rewrite: markup assertion |
  | `test_app_welfare.py` | `app.title`, `app.subheader`, `app.info`, `app.warning` | 39 | none |
  | `test_app_welfare.py` | `app.dataframe` (survey-year panel) | 39 (→ `st.html`) | rewrite: markup assertion |
  | `test_app_economy.py` (Inflation) | `app.subheader`, `app.caption` (chain-linking) | 38 | none — **verified now**: no `app.dataframe` assertion covers the Inflation provenance table (`test_app_economy.py:253-255` asserts `app.subheader`/`app.caption`) |
  | `test_app_market.py` | `app.title`, `app.subheader`, `app.metric`, `app.info`, `app.warning` | 40 | none |
  | `test_derived_series.py` | `app.dataframe` (observations) | 35 (stays `st.dataframe`) | none |
  | `test_derived_series.py` | `app.dataframe` (quality, `_quality_frame`, lines 230/243) | 35 (→ `st.html`) | rewrite: markup assertion — **added 2026-09-21**: the file asserts the quality table too, not only observations |
  | `test_scaling.py` | `app.dataframe`, `app.info` | 35 | none |
  | `test_filters.py` | `app.caption` | 21/32 | none |
  | `test_i18n.py`, `test_app_router.py` | `app.title` | — | none |
  | `test_direction.py` | `app.markdown` (CSS) | 9 (keeps `st.markdown`) | none |
  | `test_quality.py` | pure helpers (no AppTest) | 35 (render path only) | none, unless a pure helper changes |
- **i18n keys:** none.
- **Depends:** Task 15.
- **Acceptance:**
  - [x] The helper exists and has a unit test against a minimal `st.html` probe.
  - [x] The migration map above is recorded (not the rewrites; those live in Tasks 30, 32, 35, 39).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_html_text_helper.py -q`.

### 17. (A) ADD the callout component (native, D13)

- **Files:** `dashboard/components/layout.py` (new), `tests/unit/dashboard/test_layout.py` (new).
- **Build (AM-8):** `render_callout(key, *, tone="warn"|"info"|"error", label_key=None)` wrapping `st.warning`/`st.info`/`st.error` (D13), rendering the mockup's amber/info/error callout with a bold label and an info icon. Text resolves through `t()`; the amber/blue/red tint comes from the Task 8 alert theme options, with scoped CSS only for the left accent bar and icon. Native rendering means no escaping is needed.
- **i18n keys:** `note.methodology_label`="یادداشت روش‌شناسی".
- **Depends:** Task 5.
- **Acceptance:**
  - [x] Tone maps to the theme alert colours; label is optional.
  - [x] No literal Persian string outside `i18n.py`.
  - [x] The callout is visible to AppTest as `app.warning`/`app.info`/`app.error`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout.py -q`.

### 18. (A) ADD the page-header component (native, D13, AM-22)

- **Files:** `dashboard/components/layout.py`, `tests/unit/dashboard/test_layout.py`.
- **Build (AM-22):** `render_page_header(title_key, *, callout_key=None, tone="warn")` wrapping native `st.title` (so AppTest still sees `app.title`) and, when `callout_key` is given, an optional `render_callout(...)` (Task 17). This is the single page-header pattern the D11 contract and the layout guard expect every migrated page to use. Text resolves through `t()`; no literal Persian string.
- **i18n keys:** none new (the callout's `note.methodology_label` comes from Task 17).
- **Depends:** Task 17.
- **Acceptance:**
  - [x] `render_page_header` renders the title natively and, with `callout_key`, the callout beneath it.
  - [x] AppTest still sees `app.title` (the header is native, not `st.html`).
  - [x] The callout remains visible as `app.warning`/`app.info`/`app.error`.
  - [x] No literal Persian string outside `i18n.py`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout.py -q`.

### 19. (A) ADD the KPI band component

- **Files:** `dashboard/components/layout.py`, `tests/unit/dashboard/test_layout.py`.
- **Build:** `render_kpi_band(cells)` where each cell is `(label_key, value, help_key|None, tone)`; one bordered band (`st.container(border=True)` + `st.columns`), optional secondary group, optional `st.badge` tag. Reusable by any page (D2).
- **i18n keys:** `metric.derived_series_help`="سری‌هایی که این سامانه از سری والد محاسبه کرده و ردیف فهرست مستقل ندارند.", `metric.orphan_series_help`="سری‌های لایهٔ طلایی که ردیف فهرست ندارند. سری‌های مشتق‌شده معمولاً در این مجموعه قرار می‌گیرند؛ بنابراین این دو شمارنده می‌توانند هم‌پوشانی داشته باشند.", `metric.gold_observations_help`="تنها مشاهدات متصل به یک ردیف فهرست را می‌شمارد؛ سری‌های مشتق‌شده و بدون فهرست در این عدد نیستند.", `metric.orphan_series_tag`="نیازمند بررسی".
- **Depends:** Task 17.
- **Acceptance:**
  - [x] Six-cell band renders; tooltips via `st.metric(help=…)`.
  - [x] Secondary group is visually separated.
  - [x] No UI string states a specific count or a claim about current data (AM-9).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout.py -q`.

### 20. (A) ADD the chip, status-dot and bar-list components

- **Files:** `dashboard/components/layout.py`, `dashboard/i18n.py`, `tests/unit/dashboard/test_layout.py`.
- **Build:** `render_status_chip(status)` mapping `success`/`failed`/`partial` to token tones via `st.badge` (standalone use **outside** tables; the in-table chip/dot variants are the Task 15 HTML cells); `render_status_dot(label, tone)`; `render_bar_list(rows, total_label)` for the indicators-by-domain bars (AM-17: each row is composed with native `st.columns` — the label is a native `st.page_link` for an owned domain or plain text for an unowned one, and the bar itself is a small escaped `st.html` fragment; the total footer is unchanged).
- **i18n keys:** `value.status_success`="موفق", `value.status_failed`="ناموفق", `value.status_partial`="ناقص", `value.status_unknown`="نامشخص", `section.indicators_by_domain_total`="جمع".
- **Depends:** Task 19.
- **Acceptance:**
  - [x] Status slug → tone mapping is total (unknown slug renders the unknown chip).
  - [x] Bar list is unit-safe (counts only).
  - [x] The chip component states that in-table chips use the Task 15 HTML variants, not `st.badge`.
  - [x] Each bar row exposes a native `st.page_link` for an owned domain (or plain text for an unowned one); only the bar is an `st.html` fragment.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout.py -q`.

### 21. (A) ADD the section header and filter bar components

- **Files:** `dashboard/components/layout.py`, `dashboard/i18n.py`, `tests/unit/dashboard/test_layout.py`.
- **Build:** `render_section_header(title_key, *, subtitle=None, trailing=None)` (native `st.subheader` so AppTest keeps seeing it) and `render_filter_bar(controls)` giving one filter-bar layout. The Overview's three selects, the density toggle (`st.segmented_control`), the "نمایش N ردیف" label and the existing `render_filters` compose inside it.
- **i18n keys:** `filter.all`="همه", `filter.showing_rows`="نمایش {count} ردیف", `filter.density`="چگالی", `filter.density_comfortable`="راحت", `filter.density_compact`="فشرده".
- **Depends:** Task 19.
- **Acceptance:**
  - [x] Section headers use the token type scale and remain visible as `app.subheader`.
  - [x] Filter bar renders an arbitrary number of controls without layout break.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout.py -q`.

### 22. (A) ADD shared empty / error / loading states (native, D13)

- **Files:** `dashboard/components/states.py` (new), `dashboard/i18n.py`, `tests/unit/dashboard/test_states.py` (new).
- **Build:** `render_empty(key)`, `render_error(key, *, detail=None)`, `render_loading()`; consistent tone and spacing, routed through the native callout component.
- **i18n keys:** `state.loading`="در حال بارگذاری…", `state.error`="خطا در بارگذاری داده.", `state.retry_hint`="برای تلاش دوباره صفحه را بازخوانی کنید.".
- **Depends:** Task 17.
- **Acceptance:**
  - [x] Existing `empty.*` keys keep working; states are composable.
  - [x] States remain visible to AppTest as `app.info`/`app.error`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_states.py -q`.

### 23. (A) WRITE the design-system document (first draft)

- **Files:** `docs/phase-7.2/design-system.md` (new).
- **Build:** Tokens table, component catalogue (signature, purpose, example), the page-layout contract, the D1 table-classification rule, the typed-cell model, the calendar rule, the light-only theme lock (D14), and a do/don't list. The component catalogue must include the **page-header component** (`render_page_header`, Task 18) alongside the callout, KPI band, chip/dot/bar-list, section header, filter bar and states. This is the reference for later phases; it is a **first draft** — Task 47 extends it with the components that land after this point (top bar, sidebar shell, screenshot script).
- **i18n keys:** none.
- **Depends:** Tasks 5–22.
- **Acceptance:**
  - [x] Every component in `dashboard/components/` (including `render_page_header`) is documented.
  - [x] The layout contract matches the D11 guard.
- **Verify:** Manual review; links resolve.

### 24. (A) RECORD the Wave A after-screenshots and review them against the baseline (AM-24)

- **Files:** `docs/phase-7.2/wave-0-assets/after/` (new directory, ten PNGs), `docs/phase-7.2/wave-0-spike.md` (append) or `docs/phase-7.2/VALIDATION.md` (new stub).
- **Build (AM-24):** Run the Task 10 screenshot script to capture all ten pages at 1440×900 after the global-look tasks (7–9), store them under `docs/phase-7.2/wave-0-assets/after/`, and compare each against the Task 1 "before" baseline. Review explicitly for regressions: **clipped tables** (the AM-26 wrapper), **chart typography** (font fallback on axes/legend), **font fallback** (Vazirmatn actually rendering, not the OS stack), and **sidebar overlap**. Record the outcome (pass, or defect + task) in the spike/validation notes. This is the visual evidence that Wave A changes all ten pages; it does **not** replace the per-archetype owner reviews.
- **i18n keys:** none.
- **Depends:** Tasks 1, 7, 8, 9, 10.
- **Acceptance:**
  - [x] Ten after-screenshots captured at 1440×900 and compared with the Task 1 baseline.
  - [x] Each of the four regression categories (clipped tables, chart typography, font fallback, sidebar overlap) is recorded as pass or filed as a defect.
  - [x] The result is recorded in the spike/validation notes.
- **Verify:** Manual comparison of `wave-0-assets/before/` vs `wave-0-assets/after/` (Task 10 script).

---

### 25. (B) SWITCH nav icons to Material icons for all ten pages

- **Files:** `dashboard/navigation.py`, `tests/unit/dashboard/test_navigation.py`.
- **Build (AM-12):** Replace each emoji `PageSpec.icon:52-121` with a validated `:material/…:` shortcode, semantically distinct: overview→`overview`, correlation→`compare_arrows`, catalog→`menu_book`, inflation→`show_chart`, gdp→`analytics`, trade_energy→`swap_horiz` (or `bolt`), welfare→`home`, fx_gold→`currency_exchange`, market→`trending_up`, labor→`work`. Ensure uniqueness. All ten names were verified against `ALL_MATERIAL_ICONS` (Task 1).
- **i18n keys:** none.
- **Depends:** Task 1.
- **Acceptance:**
  - [x] All ten icons validate against `ALL_MATERIAL_ICONS`.
  - [x] Icons are semantically distinct (`fx_gold` and `trade_energy` do not share a glyph).
  - [x] `test_navigation.py` passes; a new test asserts every icon is a Material shortcode.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_navigation.py -q`.

### 26. (B) ADD the freshness-query TTL (D7)

- **Files:** `dashboard/queries.py`, `tests/unit/dashboard/test_queries_ttl.py` (new).
- **Build:** Add a config-held TTL (e.g. `FRESHNESS_CACHE_TTL_SECONDS`) to `@st.cache_data` on `cached_source_freshness:60` only. Document that the explicit refresh control stays deferred.
- **i18n keys:** none.
- **Depends:** —
- **Acceptance:**
  - [x] Only the freshness wrapper changes; other wrappers keep their current TTL behaviour.
  - [x] A test asserts the TTL is passed.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_queries_ttl.py -q`.

### 27. (B) BUILD the sidebar shell (brand, DB status, active item)

- **Files:** `dashboard/app.py`, `dashboard/components/direction.py`, `dashboard/i18n.py`, `tests/unit/dashboard/test_app_router.py`.
- **Build (AM-19; Wave 0 corrected recipe):** In `main():48-62`, render the brand header ("سامانهٔ داده‌ها") using **fallback (2)** — confirmed stable in Task 2. **Correction from Wave 0:** the brand is **not** added via `st.sidebar` content (that renders in `stSidebarUserContent`, *below* the nav; reordering it above the nav also drags the DB status up). Instead emit a comment-marked chrome CSS rule on `[data-testid="stSidebarHeader"]` (which already sits above `stSidebarNav`) whose `::after` `content` comes from `t("app.brand")`, and pin the DB status with `[data-testid="stSidebarContent"]{display:flex;flex-direction:column}` + `[data-testid="stSidebarUserContent"]{order:2;margin-top:auto}`. `st.logo` is **not** used for the text brand; it may optionally supply only the collapsed-sidebar `icon_image` in `stSidebarHeader`. Keep `st.navigation(position="sidebar")`, and replace the `st.success`/`st.error` banner (`render_database_status:39-45`) with the pinned status-dot component at the bottom. Active-item styling comes from the chrome CSS block (Task 9). Record which fallback shipped in the design-system doc.
- **i18n keys:** `app.brand`="سامانهٔ داده‌ها", `app.db_status_label`="پایگاه داده متصل", `app.db_status_offline`="پایگاه داده متصل نیست".
- **Depends:** Tasks 9, 20.
- **Acceptance:**
  - [ ] DB status is pinned at the sidebar bottom and no longer an alert box.
  - [ ] The chosen brand fallback is recorded in the design-system doc, with the mockup deviation if fallback (2)/(3) is used.
  - [ ] Router test still renders the default page.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_router.py -q` + manual browser check.

### 28. (B) BUILD the top bar / breadcrumb with the last-collection stamp

- **Files:** `dashboard/app.py`, `dashboard/components/layout.py`, `dashboard/queries.py`, `dashboard/i18n.py`, `tests/unit/dashboard/test_layout.py`.
- **Build (AM-19; Wave 0 outcomes):** A 48 px top bar rendered once in the shell, built with native `st.columns` inside `st.container` plus scoped CSS (D13/AM-7): breadcrumb from the registry group + page label on one side; "آخرین گردآوری: <Jalali date> · <time> · منطقهٔ زمانی تهران" on the other, sourced from `cached_source_freshness()` (max `collection_timestamp`, TTL from Task 26). Apply `layout="wide"` plus a max content width of 1360 px and account for the fixed native header (main-container top padding). **Wave 0 note:** the native `[data-testid="stHeader"]` is **60 px** tall and `position:absolute` at `z-index:999990`, not 48 px — the 48 px mockup bar is a *new* element (or a CSS override of the native header), and the main-container top padding is already 96 px; Task 2 confirmed `[data-testid="stMainBlockContainer"]{max-width:1360px}` applies. Full-bleed styling is optional; if a non-bleed fallback is used it is recorded as an accepted mockup deviation. Apply the `client.toolbarMode` value chosen in Task 2 (`"viewer"` recommended) to hide the native Deploy button/kebab; **the settings-menu theme toggle is already hidden by the custom `[theme]`** (Task 2/4), so no toolbarMode change is needed for D14. Document the `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` env override for local development.
- **i18n keys:** `shell.last_collection`="آخرین گردآوری: {date}", `shell.timezone`="منطقهٔ زمانی تهران", `shell.breadcrumb_root`="سامانه".
- **Depends:** Tasks 11, 26, 27.
- **Acceptance:**
  - [ ] Breadcrumb derives from `PAGES`/`GROUPS`, not a literal.
  - [ ] Missing collection log renders the unknown placeholder, not a crash.
  - [ ] The toolbar mode is set (per the D14 addendum) and the non-bleed deviation (if used) is recorded.
  - [ ] The `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` override is documented.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_router.py -q` + manual browser check.

---

### 29. (C) REDESIGN the Overview KPI band (6 cells)

- **Files:** `dashboard/page_view.py` (`render_overview_page:742-777`, `_render_series_inventory:796-804`), `tests/unit/dashboard/test_app_overview.py`.
- **Build:** Replace the 4-column row and the 2-column inventory row with one `render_kpi_band` of six cells in mockup order: sources, domains, active indicators, Gold observations (with scope tooltip), derived series (tooltip), orphan series (tooltip + "نیازمند بررسی" badge). Do **not** dedupe derived/orphan (D2). The band is independent of the top bar.
- **i18n keys:** reuse `metric.sources/domains/active_indicators/gold_observations/derived_series/orphan_series`; new keys from Task 19.
- **Depends:** Task 19.
- **Acceptance:**
  - [ ] Six cells, correct order, tooltips on the three annotated cells.
  - [ ] Derived and orphan values remain separate metrics.
  - [ ] No UI string states a specific count or a claim about current data.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_overview.py -q`.

### 30. (C) REDESIGN the Overview freshness table

- **Files:** `dashboard/page_view.py` (`freshness_display:829`, `render_overview_page:782-790`), `dashboard/components/html_table.py`, `tests/unit/dashboard/test_app_overview.py`.
- **Build:** Render the freshness table through `render_html_table` with the typed cells: source (`Text`), freshness dot (`Dot`), last collection (`TwoLine`: Jalali date + time · relative age), collected records, run-status chip (`StatusChip`). Stale rows first. Section header carries the "۵ به‌روز · ۲ کهنه" summary. Migrate the `app.dataframe` assertions per the Task 16 map.
- **i18n keys:** `table.freshness_dot`="وضعیت تازگی", `table.relative_age`="عمر نسبی", `table.run_status`="وضعیت اجرا"; reuse `table.source_name`, `table.collection_timestamp`, `table.records_collected`, `section.freshness_summary`.
- **Depends:** Tasks 12, 15, 20, 21, 29.
- **Acceptance:**
  - [ ] Relative age and run-status chip render; stale rows sort first.
  - [ ] Empty log renders the shared empty state.
  - [ ] The freshness assertions use the markup strategy, not `app.dataframe`.
  - [ ] The `section.freshness_summary` string (Task 12) is rendered as the
    `trailing` text of the freshness section header via `render_section_header`
    (Task 21).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_overview.py -q`.

### 31. (C) REDESIGN the Overview domain bars

- **Files:** `dashboard/page_view.py` (`_render_domain_counts:807-826`, `render_overview_page:779-780`), `tests/unit/dashboard/test_app_overview.py`.
- **Build (AM-17):** Replace the `st.page_link` list with `render_bar_list`, keeping each domain's link to its owner via `page_for_domain` as a **native `st.page_link`** per row (the bar is an `st.html` fragment; `st.page_link` cannot live inside `st.html`). Footer reads "۵۰ شاخص".
- **i18n keys:** `section.indicators_by_domain_total` (Task 20).
- **Depends:** Tasks 20, 29.
- **Acceptance:**
  - [ ] Bars are proportional to counts; unowned domains stay visible as plain text.
  - [ ] Each owned domain's owner link is preserved as a native `st.page_link` and is still visible to AppTest via `app.page_link`.
  - [ ] No raw `<a href>` to an internal page URL is used (a plain anchor would be a full browser navigation, not the supported in-app switch).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_overview.py -q`.

### 32. (C) REDESIGN the Overview coverage table with filters and calendar opt-in

- **Files:** `dashboard/page_view.py` (`render_overview_page:792-793`), `dashboard/components/html_table.py`, `tests/unit/dashboard/test_app_overview.py`.
- **Build:** Render the coverage table via `render_html_table` with typed cells: indicator (`TwoLine`: name + LTR mono id beneath), domain (`Text`), source (`Text`), frequency (`Text`), unit (`UnitChip`), coverage range, observed range, observation count, chained rows, average confidence; em-dash for nulls; density toggle; "نمایش N ردیف". Add three filter-bar selects (domain/source/frequency) with an "همه" option that filter the **coverage frame in memory** (the frame is already loaded and ~50 rows — no extra query), and a footnote explaining Gregorian-calendar sources with the exact date in a `title` tooltip (D3 opt-in).
- **i18n keys:** `table.coverage_range`="بازهٔ پوشش", `table.observed_range`="بازهٔ مشاهده‌شده", `table.chained_rows`="ردیف‌های زنجیره‌شده", `table.average_confidence`="میانگین اطمینان", `filter.all`, `filter.showing_rows`, `filter.density*`, `table.coverage_footnote`.
- **Depends:** Tasks 13, 15, 21, 30.
- **Acceptance:**
  - [ ] World Bank rows show Gregorian years; Iranian rows stay Jalali; tooltip carries the exact date.
  - [ ] Filters reduce the row count and the label updates.
  - [ ] Nulls render the em-dash.
  - [ ] The coverage assertions use the markup strategy, not `app.dataframe`.
  - [ ] **AM-26:** at 1280 px and 1024 px the coverage table scrolls inside its `overflow-x: auto` wrapper and the page does not scroll sideways (manual check, shared with Task 15).
  - [ ] **AM-26 (deferred from Task 15):** re-run the 1280/1024 px check on the **real Overview coverage table** (Task 15 could only verify this on its probe app).
  - [ ] **Compact daily range (opt-in):** `range_label` gains an opt-in `compact`
    argument (default unchanged, so the golden Jalali tests keep passing) that
    collapses a same-month/same-year daily range to the mockup's form
    (`۱۸ – ۲۰ شهریور ۱۴۰۵`), with tests.
  - [ ] **Two-line headers (opt-in):** `render_html_table` gains an opt-in
    `wrap_headers` option matching the mockup's two-line coverage headers
    (`تعداد<br>مشاهدات`), with a test.
  - [ ] **Bidi placement:** Gregorian ranges render in an `Ltr` cell and Jalali
    ranges in a `Text` cell, per the Task 13 bidi decision.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_overview.py -q` + manual browser check against the mockup.

### 33. (C) APPLY the page header + methodology callout and enable the guard for Overview

- **Files:** `dashboard/page_view.py:755-756`, `tests/unit/dashboard/test_layout_guard.py` (new).
- **Build:** Replace `st.title`+`st.warning` with `render_page_header(title_key, callout_key=…)` (Task 18), which wraps `st.title` plus `render_callout` (methodology label, Task 17). Add the D11 AST guard with a **function-scoped** `MIGRATED_PAGES = {"dashboard/page_view.py": {"render_overview_page", ...}}` — scoped so only the Overview's migrated functions are checked, using a mapping that grows per wave.
- **i18n keys:** `note.methodology_label` (Task 17).
- **Depends:** Tasks 18, 32.
- **Acceptance:**
  - [ ] Overview renders the amber methodology callout with the bold label.
  - [ ] The guard fails on a deliberate raw `st.metric` in a migrated function and passes on the current tree.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout_guard.py tests/unit/dashboard/test_app_overview.py -q`.

### 34. (C) OWNER VISUAL REVIEW — shell + Overview vs mockup (AM-23)

- **Files:** `docs/phase-7.2/validation/reference-overview.md` (new).
- **Build (AM-23):** With the shell (Wave B) and the Overview (Wave C) complete, take screenshots at **1440 px** and compare them against `docs/design/phase-7.2/overview-redesign-mockup.png` (the mockup; `overview-redesign-mockup.html` is the source) **element by element using the mockup traceability table**. Each deviation is either **approved** (recorded as an accepted deviation in this file and, where relevant, in the design-system doc) or **fixed** (a defect task is filed). This gate closes Wave C; every task in Waves D–H depends on it.
- **i18n keys:** none.
- **Depends:** Tasks 28, 33.
- **Acceptance:**
  - [ ] Element-by-element comparison against the mockup recorded, using the mockup traceability table.
  - [ ] Every deviation is marked approved (accepted deviation recorded) or fixed (defect filed).
  - [ ] Owner sign-off recorded.
- **Verify:** Manual browser comparison at 1440 px + review of `docs/phase-7.2/validation/reference-overview.md`.

---

### 35. (D) MIGRATE the generic domain composition to the layout contract

- **Files:** `dashboard/page_view.py` (`render_domain_page:138`, `render_domain_body:155`, `_render_series_section:1060`, `_render_scaled_chart:1075`, `_render_capped_rows:1102`), `dashboard/components/quality.py`, `tests/unit/dashboard/test_app_economy.py`, `tests/unit/dashboard/test_app_trade_welfare.py`, `tests/unit/dashboard/test_app_fx_gold.py`, `tests/unit/dashboard/test_app_labor.py`, `tests/unit/dashboard/test_quality.py`.
- **Build (AM-10):** One `render_page_header` (Task 18) with one callout slot, one filter bar, one section header, shared empty states, and the quality table via `render_html_table` (typed cells) and the observations grid via `st.dataframe(row_height=…)`. `render_quality_summary` (`quality.py:423`) is the renderer that changes to the HTML table; its pure helpers are untouched, which is why `test_quality.py` (pure-helper assertions only) stays green while the four AppTest quality-table assertions move to the markup strategy. No semantic change: same filters, same chart mode, same downloads, same caps.
- **i18n keys:** reuse; `section.observations` already exists.
- **Depends:** Tasks 15–22, 33, 34.
- **Acceptance:**
  - [ ] Four pages render through the same composition; no feature or value changed.
  - [ ] Quality-table assertions use the markup strategy; other four-page suites pass.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_economy.py tests/unit/dashboard/test_app_trade_welfare.py tests/unit/dashboard/test_app_fx_gold.py tests/unit/dashboard/test_app_labor.py tests/unit/dashboard/test_quality.py -q`.

### 36. (D) MIGRATE the domain-page headers and enable the guard

- **Files:** `dashboard/pages/3_GDP_Economy.py`, `dashboard/pages/4_Trade_Welfare_Energy.py`, `dashboard/page_view.py` (`render_fx_gold_page:913`, `render_labor_page:970`), `tests/unit/dashboard/test_layout_guard.py`.
- **Build:** Route each page's title and its TGJU/Labor caveats through `render_page_header` + `render_callout` (Tasks 18/17). Add the four page modules and their `page_view` entry points to the function-scoped `MIGRATED_PAGES` mapping.
- **i18n keys:** reuse `warn.tgju_snapshot`, `warn.labor_publication`.
- **Depends:** Tasks 34, 35.
- **Acceptance:**
  - [ ] No raw `st.title`/`st.warning`/`st.info` in the four migrated paths.
  - [ ] Guard passes; all four smoke tests pass.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout_guard.py tests/unit/dashboard/test_app_economy.py tests/unit/dashboard/test_app_trade_welfare.py tests/unit/dashboard/test_app_fx_gold.py tests/unit/dashboard/test_app_labor.py -q`.

### 37. (D) OWNER VISUAL REVIEW — generic domain explorer

- **Files:** `docs/phase-7.2/validation/archetype-domain.md` (new).
- **Build:** Walk the four pages in a browser against the design-system doc and record pass/fail per layout-contract item.
- **i18n keys:** none.
- **Depends:** Tasks 34, 36.
- **Acceptance:**
  - [ ] Owner sign-off recorded, or defects filed as tasks.
- **Verify:** Manual browser checklist.

---

### 38. (E) MIGRATE the Inflation page emphasis sections

- **Files:** `dashboard/page_view.py` (`render_inflation_page:196`, `_render_cpi_decile_section:252`, `_render_cpi_canonical_section:291`, `_render_chain_linking_section:377`), `tests/unit/dashboard/test_layout_guard.py`.
- **Build (AM-18):** `render_page_header` (Task 18), section headers, callouts (chain-linking stored/overlap), the provenance table via `render_html_table`, and the observations grid via `st.dataframe(row_height=…)`. Charts pick up the Task 14 template automatically. **Verified now:** no existing `app.dataframe` assertion covers the Inflation provenance table (`test_app_economy.py:253-255` asserts `app.subheader`/`app.caption`), so this task adds a markup assertion for the migrated table rather than rewriting one.
- **i18n keys:** reuse `section.cpi_*`, `section.chain_linking`, `warn.chain_linking_*`.
- **Depends:** Tasks 15–22, 34, 36.
- **Acceptance:**
  - [ ] Inflation renders through the shared components; no chart/value change.
  - [ ] Guard enabled for the Inflation functions.
  - [ ] The migrated provenance table's assertions use the markup strategy, not `app.dataframe`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout_guard.py -q` + the inflation smoke path.

### 39. (E) MIGRATE the Welfare page emphasis sections

- **Files:** `dashboard/page_view.py` (`render_welfare_page:929`, `_render_hbsir_sections:1199`, `survey_year_panel:1147`), `tests/unit/dashboard/test_app_welfare.py`.
- **Build (AM-18):** `render_page_header` (Task 18), shared headers/callouts; survey-year panel via `render_html_table` (typed cells); the HBSIR caveats through `render_callout`. Rewrite the `app.dataframe` survey-year assertion in this task (per the Task 16 map).
- **i18n keys:** reuse `section.hbsir_*`, `warn.hbsir_*`.
- **Depends:** Tasks 15–22, 34, 36.
- **Acceptance:**
  - [ ] Welfare renders through the shared components; survey-year panel unchanged in content.
  - [ ] Guard enabled for the Welfare functions.
  - [ ] The survey-year assertions use the markup strategy, not `app.dataframe`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_welfare.py tests/unit/dashboard/test_layout_guard.py -q`.

### 40. (E) MIGRATE the Market page emphasis sections

- **Files:** `dashboard/page_view.py` (`render_market_page:413`, `_render_market_notes:484`, `_render_market_level:505`, `_render_market_derived_panels:527`), `tests/unit/dashboard/test_app_market.py`.
- **Build:** The five TSETMC caveats become one callout stack under a `render_page_header` (Task 18); the sessions metric joins a small KPI band; panels use shared section headers; the quality table uses `render_html_table`. No derived-panel or quality-value change.
- **i18n keys:** reuse `warn.tsetmc_*`, `metric.market_sessions`, `section.market_level`.
- **Depends:** Tasks 19–22, 34, 36.
- **Acceptance:**
  - [ ] Market renders through the shared components; panel count and labels unchanged.
  - [ ] Guard enabled for the Market functions.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_market.py tests/unit/dashboard/test_layout_guard.py -q`.

### 41. (E) OWNER VISUAL REVIEW — emphasis-domain pages

- **Files:** `docs/phase-7.2/validation/archetype-emphasis.md` (new).
- **Build:** Browser walk of Inflation, Welfare, Market against the design-system doc.
- **i18n keys:** none.
- **Depends:** Tasks 34, 38–40.
- **Acceptance:**
  - [ ] Owner sign-off recorded, or defects filed.
- **Verify:** Manual browser checklist.

---

### 42. (F) MIGRATE the correlation page

- **Files:** `dashboard/page_view.py` (`render_correlation_page:1002`), `tests/unit/dashboard/test_app_correlation.py`, `tests/unit/dashboard/test_layout_guard.py`.
- **Build:** `render_page_header` + callouts (mixed frequencies, low overlap, exact join); join-counts and overlap-summary tables classified per D1 (join counts → `st.dataframe`; overlap summary → `st.dataframe(row_height=…)`); the quality table via `render_html_table`; heatmap picks up the new template.
- **i18n keys:** reuse `warn.correlation_*`, `section.exact_join_counts`.
- **Depends:** Tasks 15–22, 34.
- **Acceptance:**
  - [ ] Correlation renders through the shared components; suppression and overlap logic unchanged.
  - [ ] Guard enabled for the correlation functions.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_correlation.py tests/unit/dashboard/test_layout_guard.py -q`.

### 43. (F) OWNER VISUAL REVIEW — comparison / correlation

- **Files:** `docs/phase-7.2/validation/archetype-correlation.md` (new).
- **Build:** Browser walk of the correlation page.
- **i18n keys:** none.
- **Depends:** Tasks 34, 42.
- **Acceptance:**
  - [ ] Owner sign-off recorded, or defects filed.
- **Verify:** Manual browser checklist.

---

### 44. (G) MIGRATE the catalog page

- **Files:** `dashboard/page_view.py` (`render_catalog_page:588`), `tests/unit/dashboard/test_app_catalog.py`, `tests/unit/dashboard/test_layout_guard.py`.
- **Build:** `render_page_header`, a filter bar hosting search + filters + clear, a KPI cell for the matching count, and the catalog grid via `st.dataframe` with theme + `column_config` (kept sortable, LTR-grid limitation documented). Search and inactive-segment behaviour unchanged.
- **i18n keys:** reuse `filter.search`, `filter.clear`, `filter.include_inactive_segments`, `metric.matching_indicators`.
- **Depends:** Tasks 19–22, 34.
- **Acceptance:**
  - [ ] Search/filter/clear behaviour and results unchanged.
  - [ ] Guard enabled for the catalog functions.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_catalog.py tests/unit/dashboard/test_layout_guard.py -q`.

### 45. (G) OWNER VISUAL REVIEW — catalog

- **Files:** `docs/phase-7.2/validation/archetype-catalog.md` (new).
- **Build:** Browser walk of the catalog page.
- **i18n keys:** none.
- **Depends:** Tasks 34, 44.
- **Acceptance:**
  - [ ] Owner sign-off recorded, or defects filed.
- **Verify:** Manual browser checklist.

---

### 46. (H) ENABLE the consistency guard for all pages

- **Files:** `tests/unit/dashboard/test_layout_guard.py`.
- **Build:** Complete the function-scoped `MIGRATED_PAGES` mapping so every migrated page function is enforced. Verify no false positives on the shared components (whitelisted, including `render_page_header`) or on data-level English values.
- **i18n keys:** none.
- **Depends:** Tasks 33, 34, 36, 38–40, 42, 44.
- **Acceptance:**
  - [ ] Guard enforces all ten pages; a deliberate raw `st.title` anywhere fails the test.
  - [ ] No mapping entries remain except the migrated functions.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_layout_guard.py -q`.

### 47. (H) WRITE the validation record and refresh the README

- **Files:** `docs/phase-7.2/README.md`, `docs/phase-7.2/VALIDATION.md`, `docs/phase-7.2/design-system.md`.
- **Build (AM-19, AM-27(c)):** Runbook (pages, tokens, components, how to verify) plus a validation report separating "verified in this run" from "not automated", in the `docs/phase-7.1/VALIDATION.md` style. Include the ten-page browser checklist result, the archetype review outcomes, the Task 4 st.html/theme-switcher findings and the chosen brand/toolbar fallbacks. Document the developer override `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` (env var) for local development when the shipped `client.toolbarMode` is `viewer`/`minimal`. **AM-27(c):** extend `docs/phase-7.2/design-system.md` (first drafted in Task 23) to cover the components added after that draft — the **top bar** (Task 28), the **sidebar shell** (Task 27), the **page header** (Task 18) and the **screenshot script** (Task 10).
- **i18n keys:** none.
- **Depends:** Tasks 10, 34, 46.
- **Acceptance:**
  - [ ] Every page's migration is recorded with its evidence.
  - [ ] Open items are listed as open, not implied done.
- **Verify:** Manual review; `make check` passes.

### 48. (H) RUN the cross-page consistency audit

- **Files:** `docs/phase-7.2/VALIDATION.md` (append).
- **Build:** Confirm one header pattern (via `render_page_header`), one KPI pattern, one section-header pattern, one filter-bar pattern and shared states across all ten pages; confirm every chart uses the shared template; **re-confirm** the export image path still renders (PNG/SVG) with the new template — the export smoke itself lives in Task 14 (AM-25), this task only re-confirms it. Reuse the Task 10 screenshot script for the cross-page capture.
- **i18n keys:** none.
- **Depends:** Tasks 34, 47.
- **Acceptance:**
  - [ ] A consistency table (page × contract item) is complete.
  - [ ] Export smoke test result recorded (re-confirming the Task 14 `test_exports.py` PNG + SVG smoke).
- **Verify:** `make check` + `poetry run pytest tests/unit/dashboard/test_exports.py -q`.

---

## TESTING & VALIDATION

### Unit

- New formatter tests: relative time (Task 11), freshness aggregate + ordering (Task 12), calendar-aware ranges with the opt-in guarantee, including the Gregorian year-only vs year-month rule (Task 13).
- HTML escaping test across **every typed cell variant**, including `<script>`, `&`, quotes and Persian text (Task 15).
- AppTest HTML-text helper test (Task 16).
- Layout-guard AST test, function-scoped per page and finally global (Tasks 33, 46).
- Token/theme consistency test (Tasks 5, 8).
- Plotly-template contract test (renamed/split) plus the export PNG/SVG render smoke of a figure built with the new template (Task 14).
- `test_literal_guard.py` must keep passing: all new UI text lives in `i18n.py`/`labels.py`.
- **Existing assertions keep passing (files may be extended)** (native elements, per the Task 16 map): `test_direction.py`, `test_navigation.py`, `test_charts.py`, `test_exports.py`, `test_scaling.py`, `test_filters.py`, `test_labels.py`, `test_i18n.py`, `test_derived_series.py`, `test_app_catalog.py`, `test_app_correlation.py`, `test_app_market.py`, `test_app_router.py`, `test_quality.py`.
- **Suites that need rewriting** (dataframe → `st.html`), **rewritten by the migrating task** (AM-18): Overview freshness + coverage in Tasks 30/32 (`test_app_overview.py`); the four domain quality tables in Task 35 (`test_app_economy.py`, `test_app_trade_welfare.py`, `test_app_fx_gold.py`, `test_app_labor.py`); the Welfare survey-year panel in Task 39 (`test_app_welfare.py`). The Inflation provenance table had no `app.dataframe` assertion (verified now: `test_app_economy.py:253-255` uses `app.subheader`/`app.caption`); Task 38 adds a markup assertion. See the Task 16 migration map.

### Integration

- `tests/integration/test_dashboard_repository.py` must pass unchanged (no repository/SQL change).
- Per-page `AppTest` smoke through the router harness (`app_smoke.app_test`) for all ten pages, plus `test_app_router.py` for the default page.
- Chart/export smoke: `serialize_figure_images` renders PNG and SVG with the new template (Task 14; re-confirmed in Task 48).

### Manual / visual

- Wave 0 browser checklist (separator, font, selectors, `st.html` survival, theme switcher, toolbar mode, brand fallback) (Tasks 1–4), plus the Task 1 "before" baseline screenshots.
- Wave A after-screenshot regression review against the baseline (Task 24).
- One owner visual review per archetype (Tasks 37, 41, 43, 45), preceded by the shell + Overview gate (Task 34).
- Final ten-page browser walk recorded in `docs/phase-7.2/VALIDATION.md`.
- Dev-only screenshot script (Task 10, moved into Wave A); not a CI gate (D8).

### Gate (every wave)

`make check` (format + lint + typecheck + test) and the router smoke of all ten pages. Because `make typecheck` covers `src/` only, waves must also run `poetry run mypy src dashboard`. The ten-page router smoke is `tests/unit/dashboard/test_all_pages_smoke.py` (parametrized over the registry, Step 0) and must pass every wave. **AM-21:** the per-wave `mypy` gate is **"zero errors"** if the Task 1 baseline had none, otherwise **"no new errors"** against the recorded baseline error count; the baseline `make check`/`pytest` results are the reference for "no regressions". **Wave 0 baseline (2026-09-20):** `mypy src dashboard` → **0 errors**, so the gate is **"zero errors"**; `make check` PASS (1 158 passed, 3 skipped), dashboard subset 341 passed — "no regressions" against those.

---

## Deferred Scope (Phase 7.3+ candidates)

1. **IMF forecast-vs-actual labeling.** Requires an ETL change (thread Silver row metadata through `SilverSeries` → `silver_to_gold` → `_level_records`). Carried unchanged from 7.1.
2. **Indicator detail view** (full metadata, segment ancestry, per-layer counts, raw `record_metadata`).
3. **Search on domain pages.**
4. **Explicit refresh control.**
5. **Custom Jalali date-entry widget.**
6. **Normalized / index-to-100 cross-unit comparison**, and its correlation overlay.
7. **Persian names in the catalog** (`name_fa`/`description_fa` + `discover()` + migration).
8. **Derived series as catalog rows**, so they carry names/units without the parent-provenance join.
9. **Catalog-held domain taxonomy** (display order, grouping, labels) replacing the Python registry.
10. **Gold-level validation/outlier signals** and fully DB-held staleness thresholds.
11. **English catalog / runtime locale switcher.**
12. **Dark-mode support** (D14 ships light-only; `theme.dark.*` options exist but are out of scope).
13. **Per-page module split of `page_view.py`** — the D11 guard is function-scoped in 7.2 (AM-14); splitting into per-page modules is a 7.3 candidate.
14. Carried forward: OPEC basket, CBI TSD, TSETMC trading value / P/E / market cap, monetary-domain page.

---

## NOTES

- **AGENTS.md boundary is absolute.** Nothing under `src/`, `alembic/` or `airflow/` changes. If a task seems to need it, it belongs in Deferred Scope. This is how the IMF forecast item was deferred in 7.1.
- **AGENTS.md contains no offline/font/CDN rule (AM-20).** The only relevant line is `AGENTS.md:620` ("Local-only deployment: No cloud infrastructure"). The stricter "no CDN, no webfont, no vendored font file" wording is a **7.1 decision** documented at `.streamlit/config.toml:5-6` and `dashboard/components/direction.py:14-16`. **D4 is ratified:** the owner reverses that 7.1 decision and vendors Vazirmatn locally. **Verified now (Wave 0):** the font and licence are already at `dashboard/static/Vazirmatn.ttf` / `dashboard/static/OFL.txt` (untracked); Task 7 commits them and wires static serving (no relocation). The OS fallback remains a safety net only.
- **D9 lock-file implication.** Raising the constraint to `>=1.44,<2` should not change any resolved version (1.61.1 is already installed). If `poetry lock` proposes changes, stop and report rather than accepting upgrades silently. **Wave A result (Task 6, 2026-09-21):** `poetry lock` rewrote the lock's content hash but **no package version changed** (219 packages, byte-identical version list before/after; `streamlit` still 1.61.1). `poetry.lock` is **git-ignored** in this repo (`.gitignore:37`), so the refreshed lock is not committed; only `pyproject.toml` is. The lock file remains locally valid for local runs.
- **Theme lock (D14 addendum, AM-19).** `base="light"` is locked; dark mode is unsupported and deferred. The settings-menu theme toggle is hidden with `client.toolbarMode="viewer"`/`"minimal"` **only if** Task 4 shows that hides the toggle without removing anything the analyst needs; otherwise it is accepted and documented as a limitation. No CSS hacks on the native settings menu. Local development keeps the toolbar via `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` (documented in the README).
- **Plan-template conflict.** `.agents/commands/plan-feature.md:171-357` prescribes a different skeleton (Phases 1–4, `VALIDATION COMMANDS`, `ACCEPTANCE CRITERIA`) than the 7.1 plan. Per the task instruction, the 7.1 skeleton wins; the extra sections (`VALIDATION COMMANDS`, `ACCEPTANCE CRITERIA`) are folded into `## TESTING & VALIDATION` and the per-task acceptance lists.
- **`make typecheck` does not cover `dashboard/`.** Run `poetry run mypy src dashboard` in every wave; widening the Makefile target is an open item, not an assumed change.
- **Ruff literals.** Only `dashboard/i18n.py` and `dashboard/labels.py` may hold Persian literals and must be whitelisted for `RUF001/002/003`; any new test with Persian fixtures must be whitelisted too.
- **Chrome selectors are version-fragile.** Keep them in one comment-marked block naming Streamlit 1.61.1; AppTest cannot see nav chrome, so these need the manual checklist.
- **AppTest cannot read `st.html` as text.** `app.get("html")[i]` is an `UnknownElement`; the markup is only at `.proto.body`. Use the Task 16 helper. `st.badge` surfaces as Markdown, so `app.markdown` can assert it.
- **Line numbers in this plan are snapshots (AM-27(f)).** Every `file.py:NNN` reference (e.g. `page_view.py:742`, `direction.py:104`, `tables.py:103-111`) records where a symbol sat when this plan was written. Executors must **locate code by symbol name** (function/class/constant) and **re-verify every "verified now" fact** against the current tree before relying on it; treat any line-number mismatch as expected drift, not a contradiction.
- **`page_view.py` is one large module (AM-14).** All page compositions live there, so the D11 guard is function-scoped (`MIGRATED_PAGES: module → function names`) rather than file-scoped. A per-page module split is a 7.3 candidate; the trade-off is accepted for 7.2.

### Old → new task numbering (AM-3 stage, then AM-21 … AM-27 final)

The **Old** column is the original pre-amendment numbering; **AM-3** is the
numbering after the structural review (still cited by some narrative above);
**New** is the final numbering used throughout this plan after AM-21 … AM-27.

| Old | AM-3 | New | | Old | AM-3 | New | | Old | AM-3 | New |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | | 15 | 19 | 21 | | 29 | 32 | 36 |
| 2 | 2 | 2 | | 16 | 14 | 15 | | 30 | 33 | 37 |
| 3 | 3 | 3 | | 17 | 20 | 22 | | 31 | 34 | 38 |
| 4 | 5 | 5 | | 18 | 21 | 23 | | 32 | 35 | 39 |
| 5 | 6 | 6 | | 19 | 22 | 25 | | 33 | 36 | 40 |
| 6 | 8 | 8 | | 20 | 24 | 27 | | 34 | 37 | 41 |
| 7 | 9 | 9 | | 21 | 25 | 28 | | 35 | 38 | 42 |
| 8 | 10 | 11 | | 22 | 23 | 26 | | 36 | 39 | 43 |
| 9 | 11 | 12 | | 23 | 26 | 29 | | 37 | 40 | 44 |
| 10 | 12 | 13 | | 24 | 27 | 30 | | 38 | 41 | 45 |
| 11 | 13 | 14 | | 25 | 28 | 31 | | 39 | 42 | 46 |
| 12 | 16 | 17 | | 26 | 29 | 32 | | 40 | 43 | 10 (moved) |
| 13 | 17 | 19 | | 27 | 30 | 33 | | 41 | 44 | 47 |
| 14 | 18 | 20 | | 28 | 31 | 35 | | 42 | 45 | 48 |
| — | 4 | 4 (new, AM-3) | | — | 7 | 7 (new, AM-3) | | — | 15 | 16 (new, AM-3) |
| — | — | 18 (new, AM-22) | | — | — | 24 (new, AM-24) | | — | — | 34 (new, AM-23) |

Notable moves/inserts: old 40 (screenshot script) → **10** (moved into Wave A by
AM-24); **18** page header (AM-22); **24** Wave A after-screenshot review
(AM-24); **34** owner review gate for shell + Overview (AM-23). Total tasks: 48.

### Risks

1. **Streamlit-version-fragile CSS.** Sidebar width, active-nav bar, pinned status and top bar rely on internal DOM. Mitigation: one isolated, version-named block + manual checklist; prefer theme options wherever possible.
2. **HTML table vs native dataframe.** The HTML component is escaped and RTL-correct but loses sorting/virtualization; the native grid is sortable but LTR and cannot style chips. Mitigation: the D1 classification is explicit per table; in-table chips use the HTML variants, `st.badge` is standalone-only.
3. **Font vendoring (AM-20).** Ratified; **verified now (Wave 0)** the files are already at `dashboard/static/Vazirmatn.ttf` / `dashboard/static/OFL.txt` (untracked), so Task 7 only commits them. Mitigation: Task 2 confirmed the `app/static/…` serving path and that `document.fonts` loads the family; Task 7 commits the files and wires static serving; OS fallback retained.
4. **Calendar mapping is a heuristic.** `SOURCE_CALENDAR` is a slug-keyed map, in tension with 7.1's "metadata over lists" principle. Mitigation: it is presentation-only, opt-in, and pinned by a test; a DB-held calendar would be a future phase.
5. **"Gold observations" label semantics.** The KPI counts catalog-linked rows (8 195), not total Gold (20 074). Mitigation: keep the label, state the scope in the tooltip (D2); tooltip copy is data-agnostic (AM-9).
6. **No visual-regression tooling.** Mitigation: Wave 0 browser checklist, per-archetype owner review, optional screenshot script; validation doc separates verified from unverified.
7. **Scope size.** Ten pages plus a design system is large. Mitigation: wave gating (each wave ships independently), the guard enabled per function, and `make check` + ten-page smoke at every wave boundary.
8. **`page_view.py` is one large module (AM-14).** A file-scoped guard would be unusable; the guard is function-scoped and a per-page split is deferred. Trade-off: finer guard bookkeeping now vs. a refactor later.
9. **`st.html` sanitization surface.** DOMPurify strips unknown attributes/tags (SVG expected stripped); in-table tooltips may need `data-` + CSS `::after`. Mitigation: Task 4 browser-verifies the survival list; the escaping helper is mandatory.
10. **Theme toggle under a locked theme (D14 addendum).** The settings menu may still offer a theme switch. Mitigation: hide it with `client.toolbarMode` only if that removes nothing needed; otherwise accept and document the limitation. No CSS hacks on the native settings menu; local dev uses `STREAMLIT_CLIENT_TOOLBAR_MODE=developer`.

### Open items

- `[ASSUMED]` The D11 guard can be scoped per **function** without false positives; validate in Task 33 before relying on it in later waves. **(Still open — not testable in Wave 0.)**
- **Resolved (Wave 0, Task 2/4):** `client.toolbarMode` behaviour is verified — `viewer` hides the native Deploy button and developer options while keeping the kebab and viewer options (Print, Record screen); `minimal` hides the whole menu; and the settings-menu **theme toggle is already hidden by the custom `[theme]`**, so no toolbarMode change is needed for D14. Recommended value: `"viewer"`.
- **Resolved (Wave 0, Task 2):** `http://localhost:8501/app/static/Vazirmatn.ttf` resolves (HTTP 200, `font/ttf`, 241 328 B) when the font sits in `dashboard/static/` beside `dashboard/app.py`; the wrong `app/dashboard/static/…` path returns the SPA shell with HTTP 200 (fails silently).

Resolved since the review (no longer open): the font-vendoring ratification (D4); the Material-icon set (D5); the **sidebar-brand fallback order** (D5 addendum, AM-19 — CSS-pinned sidebar block, else top bar; `st.logo` icon-only); the **settings-menu theme-toggle handling** (D14 addendum, AM-19 — hide via `toolbarMode` only if nothing needed is removed, else document the limitation, no CSS hacks); `theme.fontFaces` accepting the `app/static/…` path (source-confirmed, browser-confirmed in Task 2); the separator observation (Task 1 records confirmed/refuted).
