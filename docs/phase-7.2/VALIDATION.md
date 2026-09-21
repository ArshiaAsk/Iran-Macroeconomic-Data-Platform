# Phase 7.2 Validation Report

**Status:** Phase 7.2 **complete through Wave H**, pending owner acceptance. All
five archetype reviews are **signed off APPROVED** (Overview, the four generic
domain pages, the three emphasis pages, the correlation page, and the catalog page
conditional on Wave H P1 — verified). Wave H added the four polish items P1–P4, the
completed consistency guard (Task 46), this record (Task 47) and the cross-page
audit (Task 48).
The visual review recorded here is 2026-09-21/22 against a populated local database.
**Plan:** [phase-7.2-dashboard-redesign.md](../plans/phase-7.2-dashboard-redesign.md)
**Design system:** [design-system.md](design-system.md) ·
**Wave 0 evidence:** [wave-0-spike.md](wave-0-spike.md) ·
**Per-task record:** [execution-log.md](execution-log.md)

This report separates **verified in this run** from **not automated in this run**.
The per-wave sections below are the "verified" record; the explicit
"not automated" list is at the end of the report (§ *Not automated in this run*).

**Scope note (important).** The shared components added by Tasks 17–22
(`render_callout`, `render_page_header`, `render_kpi_band`, `render_status_chip`,
`render_status_dot`, `render_bar_list`, `render_section_header`,
`render_filter_bar`, the `states` module and the typed-cell HTML table) are **not
adopted by any page yet** — page composition changes are Waves C–G, and `page_view.py`
was deliberately untouched in Wave A. They are therefore **invisible in these
screenshots**; they are verified by their unit tests and by the live-DOM probes
recorded per task in the execution log. The visible Wave A delta is the global
look (Tasks 7–9) plus the chart template (Task 14).

## Validated environment

| Component | Version |
|-----------|---------|
| Poetry | 2.4.1 |
| Python | 3.12.3 |
| Streamlit | 1.61.1 |
| Plotly | 6.9.0 |
| Kaleido | 1.4.0 |
| pandas | 2.3.3 |
| PostgreSQL + TimescaleDB | `timescale/timescaledb:latest-pg15` (healthy) |
| pytest | 7.4.4 |
| Chromium | Playwright-bundled (`~/.cache/ms-playwright/chromium-*`) |

---

## Task 24 — Wave A after-screenshots and regression review

### Method

```bash
poetry run streamlit run dashboard/app.py --server.port 8501 --server.headless true
poetry run python scripts/dashboard_screenshots.py --out-dir docs/phase-7.2/wave-0-assets/after
```

Ten PNGs, 1440×900, viewport-only, one per registered page, captured through the
sidebar in registry order (the Task 10 script, hardened in Step 0b). Baseline:
`docs/phase-7.2/wave-0-assets/before/` (Task 1, pre-Wave-A). Captures are
compared by pixel diff, by the category probes below, and by eye.

### Per-page comparison

| Page | Global look | Delta vs. `before` | Status |
|---|---|---|---|
| `overview` | Vazirmatn 14 px, `#F6F7F9`, sidebar 256 px + accent active item, freshness table visible at the fold | font, colours, sidebar, 2 px of antialiasing | PASS |
| `correlation` | same | same; the info box is `accent-soft` | PASS |
| `catalog` | same | same; the search field is now visible at the fold | PASS |
| `inflation` | same | same; the section heading renders in Vazirmatn bold | PASS |
| `gdp` | same | same; the chart legend row is now visible at the fold | PASS |
| `trade_energy` | same | same; info box `accent-soft` | PASS |
| `welfare` | same | same; the "روند جینی و فقر نسبی" section reaches the fold | PASS |
| `fx_gold` | same | same; the warning banner is `warn-bg` | PASS |
| `market` | same | same; one warn + four info banners in token tints | PASS |
| `labor` | same | same | PASS |

### The four regression categories

| Category | Result | Evidence |
|---|---|---|
| **Clipped tables (AM-26 wrapper)** | **PASS** | No page scrolls sideways: `documentElement.scrollWidth == clientWidth == 1440` on all seven probed pages (overview, catalog, correlation, market, inflation, welfare, labor), and `body` likewise. Wide tables scroll **inside their own box** — the grid scroller carries `overflow-x: auto` and overflows by 513 px (overview), 1058 px (catalog), 132 px (labor), 27 px (inflation). The Task 15 `render_html_table` wrapper (`overflow-x: auto`) is not yet adopted, so the category is "no regression introduced", not "wrapper verified in a page". |
| **Chart typography** | **PASS** | DOM probe on the market chart: tick, legend and axis-title text compute to `Vazirmatn, IRANSans, Tahoma, "Segoe UI", sans-serif` at 10.5 px (ticks/legend) and 12.25 px (axis title). Jalali tick labels render (`۱۴ آذر ۱۳۸۷`). The time axis flows LTR (oldest left) as documented; grid lines are `--border`, the trace is `--accent`. |
| **Font fallback** | **PASS** | Computed family on `body`, `stMarkdownContainer`, `stMetricValue` and `stSidebarNavLink` is the Vazirmatn stack (Streamlit appends its own `"Source Sans", sans-serif` tail to `body`/nav, which is harmless). `document.fonts` reports `Vazirmatn` **loaded**; no page falls back to Tahoma/Segoe UI. |
| **Sidebar overlap** | **PASS** | Sidebar occupies 0–256 px and `stMainBlockContainer` starts at 256 px (width 1184 px) — no overlap. Visually, the DB-status card sits at the sidebar bottom without covering a nav item, and no page element crosses the boundary. |

### Delta against the Tasks 7–10 checkpoint

The Tasks 7–10 global-look captures
(`docs/phase-7.2/wave-a-assets/after-global-look/`, 01:29) predate Tasks 12–14.
Comparing them with this set:

- **5 of 10 captures are byte-identical** (correlation, inflation, trade_energy,
  welfare, market).
- The other 5 differ by **≤ 0.23 % of pixels**. Four of those are sub-pixel
  antialiasing at container edges; the one substantive delta is `gdp`, where the
  chart's legend row sits **~48 px higher** because **Task 14** moved the legend
  into the template (horizontal, top-anchored, right-aligned). The filter
  controls are at identical coordinates in both sets, so the page does not shift.
- Tasks 15–22 add components and helpers that pages do not adopt, so they produce
  no page-visible change.

This is the intended Wave A outcome: one global look plus one chart template, with
the shared components staged for the waves that adopt them.

### Defects filed

1. **Chart legend title reads `label`** — every chart renders a redundant English
   legend title because the builders pass `color="label"`
   (`dashboard/components/charts.py:163,190,235,326,564`), so Plotly titles the
   legend after the column. **Pre-existing** (last changed 2026-09-19, Phase 7.1),
   **not a Wave A regression**, and not visible in the `before` baseline only
   because the charts sat below the fold there. Fixing it is a chart-builder
   change and needs its own task; filed as an open item.
2. **10 px container overflow around `st.dataframe`** — the dataframe's outer
   `stVerticalBlock` chain reports `scrollWidth` 9–10 px above `clientWidth` with
   `overflow-x: visible`. It is Streamlit's own padding, it does **not** reach the
   document (no sideways scroll), and nothing is visually cut. Recorded as an
   observation, not a defect; it becomes moot when the domain pages adopt
   `render_html_table`.

### Not automated in this run

- **Per-archetype owner reviews** (later wave) — this is the Wave A visual
  evidence, not a replacement for them.
- **Pixel-diff regression gate** — the comparison above was run ad hoc with PIL;
  no committed image-diff test exists and none is planned for 7.2.
- **Dark mode** — deferred (D14); `base="light"` is locked.
- **Native alert icon** — the native `stAlertContainer` ships no icon element, so
  the Wave A callout draws its glyph in CSS; the banners in these captures have no
  icon by design (see `design-system.md` §6).

---

## Wave A gate

Run after Task 24, against the Wave 0 pre-change baseline recorded in
`wave-0-spike.md`. The per-wave rule is **no new errors and no regressions**, not
an absolute count.

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1307 passed, 3 skipped, 136 deselected** in 141.5 s; ruff format/lint and mypy clean; coverage **89.22 %** (≥ 80 %) |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **491 passed** |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed** (PNG + SVG render through Kaleido 1.4.0) |
| Ten-page AppTest smoke | Throwaway pytest file (not committed) parametrized over every `PageSpec`, rendered through the router with the repository's fake repository | **11 passed** (10 pages + the registry count), no page raises |
| Working tree | `git status --short` | clean |

**Against the baseline.** The recorded Wave 0 pre-change counts
(`wave-0-spike.md` §3) are **1158 passed / 3 skipped / 135 deselected** for the
full suite and **341 passed** for the dashboard subset. Nothing regressed, and the
increase is the Wave A test suites:

| | Wave 0 | Start of A-3 (after Task 16) | After Wave A | Wave 0 → now |
|---|---|---|---|---|
| Full suite (`make check`) | 1158 passed, 3 skipped, 135 deselected | — | **1307 passed, 3 skipped, 136 deselected** | **+149 passed, +1 deselected** |
| Dashboard subset | 341 passed | **426 passed** | **491 passed** | **+150** |

The full-suite delta (+149) and the subset delta (+150) differ by exactly the one
new integration test — the export PNG/SVG smoke in `test_exports.py`, which
`make check` deselects (hence the deselected count 135 → 136) but a plain subset
run collects. The dashboard subset grew **+65** across this stretch (Tasks 17–24:
426 → 491).

**Not covered by the gate.** The dashboard subset runs with `--no-cov` by design
(coverage is measured on `src`, so a dashboard-only run would fail the gate for
the wrong reason); the export smoke is deselected by `make check` because it needs
a Chromium binary, which is why it is run explicitly above.

---

## Wave B — shell (Tasks 25–28 + Step 0 close-out)

Wave B adds the sidebar shell (brand, DB status, active item), the nav icon map,
the freshness TTL fix and the top bar/breadcrumb with the last-collection stamp.
Step 0 then closed four shell defects found in review: the brand wrapped to two
lines (0a), the top bar sat 67.5 px below the native header (0b), the page-spec
lookup depended on display text (0c), and the heading/metric type scale was
Streamlit's default rather than the mockup's (0e).

### Method

```bash
poetry run streamlit run dashboard/app.py --server.port 8501 --server.headless true
poetry run python scripts/dashboard_screenshots.py \
    --out-dir docs/phase-7.2/wave-b-assets/all-pages
```

Ten PNGs, 1440×900, viewport-only, one per registered page, captured through the
sidebar in registry order. Baseline: the Wave A set in
`docs/phase-7.2/wave-a-assets/after-global-look/`. This is the Wave B gate
screenshot set; the element-by-element mockup comparison is Task 34 (Wave C).

### Per-page shell check

Every page renders the full shell: the single-line brand block
(`سامانهٔ دادهها` + accent mark) in `stSidebarHeader`, the native Material nav
icons, the active item highlighted, the pinned DB-status dot at the sidebar
bottom, and the top bar (breadcrumb from the registry group + page label on one
side, `آخرین گردآوری: … · … · منطقهٔ زمانی تهران` on the other) seated directly
under the native header.

| Page | Breadcrumb (group → page) | Status |
|---|---|---|
| `overview` | `سامانه ، مرور و تحلیل ، مرور کلی` | PASS |
| `correlation` | `سامانه ، مرور و تحلیل ، مقایسه و همبستگی` | PASS |
| `catalog` | `سامانه ، مرور و تحلیل ، فهرست دادهها` | PASS |
| `inflation` | `سامانه ، حوزهها ، تورم` | PASS |
| `gdp` | `سامانه ، حوزهها ، تولید ناخالص داخلی و اقتصاد` | PASS |
| `trade_energy` | `سامانه ، حوزهها ، تجارت و انرژی` | PASS |
| `welfare` | `سامانه ، حوزهها ، رفاه و آمارگیری خانوار` | PASS |
| `fx_gold` | `سامانه ، حوزهها ، ارز و طلا` | PASS |
| `market` | `سامانه ، حوزهها ، بازار سرمایه` | PASS |
| `labor` | `سامانه ، حوزهها ، بازار کار` | PASS |

**Shell pass on all ten pages.** The Wave B delta is the shell only; the page
bodies are unchanged from Wave A and are redesigned in Waves C–G.

### Observations (not Wave B defects)

- **`Choose options` placeholder** — the filter `st.multiselect` controls on the
  data pages show Streamlit's untranslated default placeholder. It is a
  page-composition concern (Wave C–G adopt `render_filter_bar`), not shell; filed
  as an open item for the page waves.
- **`label` chart-legend title** — the GDP chart legend title reads `label`
  (already filed under Wave A defects 1; the builders pass `color="label"`). A
  chart-builder change for its own task, unchanged here.
- **`welfare.png` captured mid-run** — the capture shows the transient `Stop`
  status widget while a chart finished rendering. A capture-timing artifact, not a
  page defect.

### Wave B gate

Run after Step 0e, against the Wave 0 baseline and the Wave A gate above. The
per-wave rule is **no new errors and no regressions**.

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1351 passed, 3 skipped, 136 deselected** in 152.8 s; ruff format/lint and mypy clean; coverage **89.22 %** (≥ 80 %) |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **535 passed** |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed** (PNG + SVG render through Kaleido 1.4.0) |
| Ten-page AppTest smoke | `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov` | **10 passed**, no page raises |
| Working tree | `git status --short` | clean |

**Against the baseline.** The Wave B start-of-wave baseline was **1341 passed /
3 skipped** (full) and **525 passed** (dashboard subset); after Step 0 the counts
are **1351 / 3 skipped** and **535**. The +10 is the Step 0 tests (0a: brand
single-line + no-wrap; 0b: top-bar row `min-height`; 0c: four page-spec-lookup
tests; 0e: four type-scale tests), so **nothing regressed**.

### Accepted deviations carried in Wave B

- **Top bar is 48 px, inside the 1360 px content column (non-bleed)** — the
  mockup draws a full-bleed white strip with a `border-bottom`. The shipped bar is
  the main container's first child (inside the column) and has no surface
  background or border; this is not visible at 1440 px (main area 1184 px < 1360 px
  cap). Recorded in `design-system.md` §9/§14 (see also Step 0b).
- **Brand is a CSS-pinned sidebar block (fallback 2)** — `st.logo` is image-only,
  so the text brand is emitted from `t("app.brand")` via a
  `[data-testid="stSidebarHeader"]` `::after` rule; the mark is a CSS `::before`.
  Recorded in `design-system.md` and Task 27.

---

## Wave C part 1 — Overview page (Step 0f + Tasks 29–31)

**Scope.** Wave C part 1 is the Overview page only. It is the first wave that
*adopts* the Wave A shared components, so this is the first section of this
report where they are visible in a screenshot. Three page-composition tasks plus
one capture-tooling step:

| Step / task | Commit | Delta |
|---|---|---|
| Step 0f | `e6d701f` | Harden `scripts/dashboard_screenshots.py`; re-capture `wave-b-assets/all-pages/welfare.png` |
| Task 29 | `db49a81` | Overview KPI band (6 cells) + scoped KPI/heading typography |
| Task 30 | `288ea81` | Overview freshness table (typed cells, pure builder) |
| Task 31 | `bba20ae` | Overview domain bars + the `[7, 5]` two-column row |

### Step 0f — capture tooling

The Wave B `welfare.png` was captured while a chart was still settling, so it
carried Streamlit's transient `Stop` status widget. The script now asserts the
running indicator and every spinner/skeleton are absent before each shot:

- `_TRANSIENT_SELECTORS` (`stStatusWidget`, `stSpinner`, `stSkeleton`),
  `_SETTLE_RETRIES = 20`, `_SETTLE_POLL_MS = 250`, `_SETTLE_QUIET_MS = 500`.
- `wait_until_settled(page, page_key)` requires a *quiet* window (no transient
  selector present for `_SETTLE_QUIET_MS`) and is called both from `wait_ready`
  and again immediately before each `capture`.
- `ScreenshotNotReadyError` makes a page that never settles fail loudly instead
  of writing a bad image.

`welfare.png` was re-captured with the hardened script; the `Stop` widget is
gone (verified in the re-capture below).

### Task 29 — KPI band

The 4-column metric row **and** the separate series-inventory row are replaced by
one `render_kpi_band` of six cells in mockup order: `منابع`, `حوزهها`,
`شاخصهای فعال`, `مشاهدات لایه طلایی`, `سریهای مشتقشده`, `سریهای بدون ردیف
فهرست`. Derived + orphan form a visually separated secondary group (a leading
divider via the `:has()` boundary rule) and the orphan cell carries the
`نیازمند بررسی` badge; the three annotated cells carry `help=` tooltips.
`_render_series_inventory` is removed. Derived and orphan counts are **not**
deduped (D2) — they are two overlapping views of the same series, exactly as the
mockup draws them.

**Computed typography vs mockup.** The mockup's type is partly inexpressible in
the Streamlit theme (the theme has no per-element label weight or heading
line-height knob), so it is applied as scoped CSS in `direction.py` and verified
by computed style, not by eyeballing:

| Element | Mockup | Computed (live DOM) | Match |
|---|---|---|---|
| `h1` (page title) | 39.2 px / lh 1.4 | 39.2 px / **1.4** | yes |
| `h3` (section header) | 27 px / lh 1.5 | 27 px / **1.5** | yes |
| KPI label | 13 px / 500 | **13 px / 500** | yes |
| KPI primary value | 28 px / 600 | 28 px / 600 | yes |
| KPI secondary value | 20 px | **20 px** | yes |
| Body markdown | lh 1.85 | 25.9 px / **1.85** | yes |
| Band direction | `rtl` | `rtl`, 6 cells | yes |
| Row column ratio | 7 : 5 | measured **1.406** | yes |

Two of these needed main-block scoping: Streamlit's own `h1`/`h3` rule (lh 1.2)
outranks a bare element selector, so the heading rules are written against
`[data-testid="stMainBlockContainer"] h1/h3`. The body line-height was measured
at **1.9** before this task and is now 1.85.

### Task 30 — freshness table

`build_freshness_rows(frame, *, now) -> FreshnessTable` is a **pure function** —
no Streamlit, no clock — producing typed cells: source `Text`, freshness `Dot`,
last collection `TwoLine` (clock line + relative-time line), records `number`,
and run status `StatusChip` reusing the existing chip mapping via the new
`status_chip_cell` in `layout.py`. Stale rows sort first. The section header's
trailing slot carries `t("section.freshness_summary")` (`۴ بهروز · ۳ کهنه`), and
an empty collection log renders `render_empty` rather than an empty table. Tests
use the **markup strategy** (`html_texts`) because the table is `st.html`.
`TwoLine` gained an optional trailing `primary_tone` so the freshness verdict can
colour its primary line.

### Task 31 — domain bars + two-column row

The `st.page_link` inventory list is replaced by `render_bar_list`, and the page
composes `st.columns([7, 5])` inside a keyed `overview-row` container: freshness
in the first column (which is the **right-hand** column under RTL) and the domain
bars in the second. `overview_row` gets an explicit `direction: rtl` rule so the
column order is stable. The AppTest assertion is `len(app.get("page_link"))`
rather than `app.page_link` (AppTest exposes no such attribute).

### Per-page pass / defect (ten pages, hardened script)

Captured to `docs/phase-7.2/wave-c-assets/part1-all-pages/`.

| Page | Result |
|---|---|
| `overview` | **PASS** — shell; six-cell KPI band in mockup order with the separated secondary group and the `نیازمند بررسی` tag; two-column row (freshness right/wider, bars left); stale-first ordering; both section headers carry trailing summaries; coverage table below |
| `correlation` | **PASS** — shell + callout; empty-state hint; no defect |
| `catalog` | **PASS** — shell + `پاک کردن پالایهها` + catalog search + regions table below the fold |
| `inflation` | **PASS** — shell + callout; multi-select chips; decile section header below |
| `gdp` | **PASS** — shell; *defect*: chart legend title reads `label` (carry item, see below) |
| `trade_energy` | **PASS** — shell + callout; empty-state hint |
| `welfare` | **PASS** — shell + two callouts; **no `Stop` widget** (Step 0f re-capture confirmed) |
| `fx_gold` | **PASS** — shell + callout; empty-state hint |
| `market` | **PASS** — shell + five callouts (one warn, four info) |
| `labor` | **PASS** — shell + callout |

No page regressed relative to the Wave B gate. The only per-page defect is the
pre-existing `label` legend title on `gdp`.

### Wave C part 1 gate

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1375 passed, 3 skipped, 136 deselected** in 170.5 s; ruff format/lint and mypy clean; coverage **89.22 %** (≥ 80 %) |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **559 passed** |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed** |
| Ten-page AppTest smoke | `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov` | **10 passed**, no page raises |
| Working tree | `git status --short` | clean (assets committed) |

**Against the Wave B gate.** Wave B ended at **1351 passed / 3 skipped** (full)
and **535 passed** (dashboard subset); part 1 ends at **1375 / 3** and **559**.
The **+24** is the Step 0f–31 tests (29: band cells + KPI typography; 30:
freshness builder + `TwoLine` tone + `tehran_clock_label`; 31: bar list + row
composition) — **nothing regressed**.

### Accepted deviations and carry items

- **Top bar has no surface or border** — the mockup draws a full-bleed white
  strip with a `border-bottom`. Unchanged from Wave B (accepted deviation); a
  shell concern, not a Wave C page concern.
- **English `Choose options` placeholder** — every filter `st.multiselect` shows
  Streamlit's untranslated default. It is a `render_filter_bar` concern; carried
  to the page waves (Tasks 32–34 adopt the filter bar).
- **`label` chart-legend title** — the GDP chart legend title reads `label`
  (builders pass `color="label"`). A chart-builder fix, carried to its own task.
- **Derived/orphan counts intentionally overlap (D2)** — no dedupe by design.

### Carry list for Tasks 32–34

1. Top bar: give the strip its surface + `border-bottom` (shell).
2. Filter controls: adopt `render_filter_bar` so the placeholder is Persian.
3. Chart builders: drop the `color="label"` legend title.

---

## Wave C part 2a — Overview polish (P1–P5) and the coverage table (Task 32)

**Scope.** Part 2a finishes the Overview reference page: five owner-flagged polish
items (P1–P5, deferred from the part 1 gate) and Task 32, which replaces the last
`st.dataframe` on the page with the typed HTML table. Nothing outside the
presentation layer changed.

| Item | Commit | Delta |
|---|---|---|
| P1 | `16aefda` | Domain bars sort count-descending, ties by Persian domain name ascending |
| P2 | `3dd58c0` | Secondary KPI cells take the mockup's `flex: 1.35` |
| P3 | `4528e56` | Overview freshness header uses `آخرین گردآوری` |
| P5 | `4a5995f` | Top bar surface + bottom border + full-bleed via one `--main-pad-x` |
| P4 | `c8fcb6f` | Amber stale count in the freshness summary |
| Task 32 | `3191e2f` | Coverage table (typed cells, filters, density, calendar opt-in) |

### P1 — bar order

`ordered_domain_rows(domain_counts) -> list[BarRow]` is a **pure** helper: count
descending, ties by the domain's Persian display name ascending (`domain_label`),
which reproduces the mockup's own tie order (`تورم` before `رفاه` at 15; `ارز`
before `بازار …` at 1). A missing or non-numeric count is treated as zero and
never dropped; the sort is stable. The rendered order in the capture below is
**15, 15, 8, 4, 3, 2, 1, 1, 1**.

### P2 — secondary KPI width

`kpi_column_weights(cells)` returns `1.35` for a cell flagged `secondary` and
`1.0` otherwise, and `render_kpi_band` passes those weights to `st.columns`. The
ratio lives in the component rather than CSS because `st.columns` owns the
geometry. Measured at 1440 px: the four primary cells render **143.85 px** and the
two secondary cells **198.30 px** — a rendered ratio of **1.378**. Streamlit's
`flex-basis` percentages are exactly **14.9254 %** / **20.1493 %** (i.e. `1.35×`);
the rendered widths diverge only because the basis is `calc(<pct>% - 14px)`, so a
fixed 14 px gap is subtracted from every cell.

### P3 — last-collection header

The Overview freshness table's third header is the mockup's `آخرین گردآوری`
(new key `table.last_collection`). The generic `table.collection_timestamp`
(`زمان گردآوری`) is deliberately **not** changed, because `freshness_display` and
the exports still use it.

### P4 — amber stale count

`section.freshness_summary` is now `{fresh} بهروز · :orange[{stale}] کهنه`. Only
the stale count is wrapped in the markdown orange directive — the section
header's trailing slot is a markdown string, so the directive is the native route
to the mockup's amber number. The theme maps `orange` to the warn palette
(`orangeColor = #9A5B00`). Measured live: the stale count's span computes
`color: rgb(154, 91, 0)`; the fresh count stays muted. The tuple return and the
empty-log behaviour are untouched.

### P5 — top bar surface, border and full-bleed

The bar gains `background: var(--surface)` and `border-bottom: 1px solid
var(--border)`. For the full-bleed variant the main container declares
`--main-pad-x: 70px` and reads it for its own horizontal padding; the bar reads
the same property for `width`, `max-width`, `margin-inline` and `padding-inline`,
so the four values cannot drift. The `width`/`max-width` pair is required because
the bar's containing block is Streamlit's inner `stLayoutWrapper` (already inside
the main padding) and Streamlit sets `max-width: 100%`, so a negative margin
alone shifts the bar left without widening it.

Measured live: 1440 px → bar `x=256, width=1184` (right edge 1440),
`background: rgb(255,255,255)`, `border-bottom: 1px solid rgb(225,229,235)`,
`scrollWidth == clientWidth == 1440`; bar content aligned to the page column
(`breadcrumb right = 1370 = h1 right`). 1280 px → bar `x=256, width=1024`,
`scrollWidth == clientWidth == 1280`. No horizontal page scroll at either width.

### Task 32 — the coverage table

The coverage grid is now the typed HTML table (`dt cov`) instead of
`st.dataframe`: ten columns in the mockup's order, the three right-hand headers
two-line (`wrap_headers`), the indicator name above its raw id in a block-level
LTR mono line, `UnitChip` units, and the em-dash for every null.

- **Calendar (D3).** `build_coverage_rows(frame, *, calendar_map=SOURCE_CALENDAR)`
  takes the calendar map as a parameter: a Gregorian source's range is an `Ltr`
  cell carrying the exact stored bounds in its `title`, a Jalali source's is a
  `Text` cell. `range_label(..., compact=True)` — opt-in, default unchanged —
  collapses a same-month/same-year daily Jalali range to `۱۸ – ۲۰ شهریور ۱۴۰۵`.
- **Filter bar (Task 21's first consumer).** Three `st.selectbox` controls with an
  "همه" option filter the already-loaded frame **in memory** (no extra query),
  plus the `نمایش ۵۴ ردیف` echo and an `st.segmented_control` density toggle. The
  selections are read from `st.session_state` before the bar renders, so the frame
  the table renders is the one the controls describe in the same run.
- **Footnote.** `st.caption(t("table.coverage_footnote"))`, with the whole section
  wrapped in `st.container(key="overview-coverage-section")` so it has one
  addressable boundary (Task 34's per-region crops need it).

Measured live (AM-26, including the Task 15 deferral): page-level
`scrollWidth == clientWidth` at **1440, 1280 and 1024 px** (1440/1440, 1280/1280,
1024/1024), so the page never scrolls sideways; the coverage wrapper's
`scrollWidth` stays 1169 against client widths 1042 / 882 / 626, so the table
scrolls **inside its own box**. The rendered table is `dt cov comfortable`,
1169×3450 px, **54 rows**. Header cells: 12 px, `white-space: normal`,
`vertical-align: bottom`; first cell `min-width: 230px`; body cells 13.5 px.
The density toggle changes the same table's row height **64 px → 60 px**.

### Per-page pass / defect (ten pages, hardened script)

Captured to `docs/phase-7.2/wave-c-assets/part2a-all-pages/` at 1440×900 with the
Step 0f hardened script (every page asserts the `Stop` widget, spinner and
skeleton are absent before the capture). `overview-coverage.png` is an extra
scrolled capture that shows the coverage section in the committed tree.

| Page | Result |
|---|---|
| `overview` | **PASS** — top bar now has its surface + border (P5); KPI band with the wider secondary group (P2); freshness header `آخرین گردآوری` (P3) and the amber stale count (P4); bars count-descending (P1); coverage table with the filter bar, two-line headers and the em-dash below the fold |
| `correlation` | **PASS** — shell + callout + empty-state hint; top bar chrome present |
| `catalog` | **PASS** — shell + catalog search; top bar chrome present |
| `inflation` | **PASS** — shell + callout; top bar chrome present |
| `gdp` | **PASS** — *pre-existing defect*: chart legend title reads `label` (unchanged carry item) |
| `trade_energy` | **PASS** — shell + callout + empty-state hint |
| `welfare` | **PASS** — shell + two callouts; **no `Stop` widget** |
| `fx_gold` | **PASS** — shell + callout + empty-state hint |
| `market` | **PASS** — shell + five callouts; top bar chrome present |
| `labor` | **PASS** — shell + callout |

No page regressed relative to the part 1 gate. The only per-page defect remains
the pre-existing `label` legend title on `gdp`.

### Wave C part 2a gate

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1426 passed, 3 skipped, 136 deselected** in 177.2 s; ruff format/lint and mypy clean; coverage **89.22 %** (≥ 80 %) |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **610 passed** |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed** |
| Ten-page AppTest smoke | `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov` | **10 passed**, no page raises |
| Working tree | `git status --short` | clean (assets committed) |

**Against the part 1 gate.** Part 1 ended at **1375 passed / 3 skipped** (full) and
**559 passed** (dashboard subset); part 2a ends at **1426 / 3** and **610**. The
**+51** is the P1–P5 and Task 32 tests (P1: ordering; P2: weights; P3: header key;
P4: amber directive; P5: `--main-pad-x`; Task 32: 42 across `test_html_table.py`,
`test_formatting.py` and `test_app_overview.py`) — **nothing regressed**.

### Accepted deviations and carry items

- **Native filter selects (Task 32).** The three coverage filter controls are
  native `st.selectbox` widgets, not the mockup's 32 px inline-label chips (D13);
  the bar measures 73 px against the mockup's 55 px.
- **Coverage table width (Task 32).** The real table needs 1169 px in a 1042 px
  wrapper, so the leftmost column is partly scrolled out where the mockup's
  shorter sample fits. AM-26 accepts the in-box scroll.
- **Footnote wording (Task 32).** The footnote reads `راهنمای هر خانه` where the
  mockup says `tooltip` — the Task 13 key's Persian wording.
- **Caption direction (Task 32).** A native `st.caption` inherits the LTR main
  block, so the Persian footnote hugged the left edge; fixed **scoped** via the
  `coverage_footnote` hook, with the shell-wide caption gap carried to Task 34 (a
  global rule would move every un-migrated page).
- **Top-bar breadcrumb details (P5).** The separator is `›` live vs `/` in the
  mockup, the current-page crumb is not bold, and the live bar is 49 px (48 px row
  + 1 px border) vs the mockup's 48 px box. Carried to the Task 34 review.
- **English `Choose options` placeholder.** Still present on every un-migrated
  page (`gdp`, `welfare`, `correlation`, …) because those pages have not adopted
  `render_filter_bar` yet. Waves D–G.
- **`label` chart-legend title.** Unchanged; a chart-builder fix carried to its
  own task.

### Carry list for Tasks 33–34

1. Page header + methodology callout: adopt `render_page_header` on Overview
   (Task 33) and turn on the D11 layout guard.
2. Shell-wide `st.caption` direction rule (Task 34 review item).
3. Top-bar breadcrumb separator/bold/height (Task 34 review item).
4. AM-23 owner visual review — **prepared, not signed off** (Task 34).

---

## Wave C part 2b — page header + D11 guard (Task 33) and the AM-23 review (Task 34)

**Scope.** Part 2b closes Wave C: Task 33 adopts the page-header pattern on the
Overview and turns on the D11 layout guard, and Task 34 prepares the AM-23 owner
visual review. **Task 34 changes no code** — it is evidence and a decision
document.

| Item | Commit | Delta |
|---|---|---|
| Task 33 | `e5fdef3` | `render_page_header` + the bold methodology callout on the Overview; the function-scoped D11 AST guard |
| Task 34 | this commit | The 1440×2200 capture, the per-region crops and `validation/reference-overview.md` (prepared; sign-off pending) |

### Task 33 — page header, methodology callout and the D11 guard

`render_overview_page` opens with `render_page_header("page.overview",
callout_key="warn.forecasts_indistinguishable",
label_key="note.methodology_label")` instead of a raw `st.title` + `st.warning`,
and the empty-catalog `st.warning` became `render_callout("warn.catalog_empty")`
— same tone, same text, same early return, but no longer a raw call. The
Overview's callout now carries the mockup's bold `یادداشت روش‌شناسی` prefix.

**The one plan deviation.** `render_page_header`'s Task 18 signature had no way
to pass a label, so it gained an optional `label_key` forwarded to
`render_callout`. The parameter is additive and defaults to `None`, so the
ratified Task 18 shape is unchanged for every other caller. The plan's Task 33
file list named only `page_view.py` and the new guard; the `layout.py` addition is
recorded in design-system §14 rather than slipped in silently.

**The guard.** `tests/unit/dashboard/test_layout_guard.py` is the static half of
the D11 contract, modelled on `test_literal_guard.py`. It is **function-scoped**
(`MIGRATED_PAGES` maps module → migrated function names, because every page
composition lives in one module, AM-14) and starts with the Overview's whole
composition: `render_overview_page`, `_render_domain_counts`,
`_render_coverage_section`. `BANNED_FUNCTIONS` is exactly the §12 list plus the
`unsafe_allow_html` keyword, and `LAYOUT_WHITELIST` is the four shared-component
modules — pinned to the document by
`test_the_whitelist_matches_the_design_system_contract`, which derives the §12
list from `design-system.md` and asserts set equality, so the guard and the
contract cannot drift.

Measured live (1440 px): the callout container is
`st-key-callout-warn-forecasts_indistinguishable`, the bold run computes
`font-weight: 600` / `color: rgb(154, 91, 0)`, and the alert computes
`background: rgb(251, 241, 220)` (= `--warn-bg`) with
`border-inline-start: 3px solid currentColor`. `scrollWidth == clientWidth`.

### Task 34 — the AM-23 owner visual review (prepared, then signed off)

`docs/phase-7.2/validation/reference-overview.md` compares the shipped shell and
Overview against the mockup **element by element over the plan's mockup
traceability table** — all 34 rows, each with live evidence and a verdict.
**Verdict tally: 30 PASS, 4 PASS-with-approved-deviation, 1 FIX recommended.**
The owner signed it off on 2026-09-21; see "Wave C part 2c" below for the
decisions.

Six findings needed the owner's decision, and each was presented with a
recommendation rather than applied, because Task 34 changes no code:

| # | Finding | Recommendation | Owner decision |
|---|---|---|---|
| F1 | The main content padding is 70 px where the mockup's `.wrap` uses 40 px, so the content column is 60 px narrower at every width (1044 vs 1104 at 1440 px) | **FIX** as its own shell task — the 70 px restates Streamlit's own default (P5 needed to name it so the top bar's negative margin could not drift), and a one-line change moves every page at once | **Not requested now** (optional Wave H) |
| F2 | The breadcrumb separator is `،` where the mockup writes `/`, and the current crumb is not bold | **FIX** in the same shell task | **Not requested now** (optional Wave H) |
| F3 | The `gdp` chart legend title reads `label` (pre-existing, carried from the part 1 gate) | **FIX** against the chart builders | **Scheduled** in Waves D–G, from Task 35 |
| F4 | English `Choose options` placeholder on every un-migrated page | **FIX in Waves D–G**, already proven by Task 32 | **Scheduled** in Waves D–G, from Task 35 |
| F5 | A native `st.caption` inherits LTR, so Persian captions hug the left edge (fixed scoped for the coverage footnote only) | **FIX** in the shell task, once the pages have migrated | **Not requested now** (optional Wave H) |
| F7 | The short categorical coverage columns (حوزه/منبع/تواتر) wrap onto a second line at 1440 px; the mockup keeps them on one line | **FIX** the wrap rule for those three columns | **Not requested now** (optional Wave H) |

The Gregorian-vs-Jalali range-cell **direction** difference is recorded the same
way (**not requested now**); its **font-size** half was a defect and is **fixed**
(Step 0a). The owner's numbering skips **F6** — no F6 finding was raised.

Nine deviations are recommended for approval (A1–A9): the callout's native-alert
styling, the KPI tooltip marker, the native filter selects, the coverage table's
in-box scroll, the footnote wording, the 49 px bar, the freshness counts and the
54-row table (both data, not design), and Task 33's `label_key` addition.

**Evidence.** `wave-c-assets/task34/`: `overview-1440x2200.png` (the requested
capture), `overview-1440x4900.png` (the whole page, which is 4637 px tall),
`region-{topbar,header,callout,kpi-band,overview-row,coverage-section}.png` and
the like-for-like `region-*-mockup.png` crops, plus
`region-coverage-section-full.png` (1044×3613).

### Wave C part 2b gate

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1438 passed, 3 skipped, 136 deselected** in 173.5 s; ruff format/lint and mypy clean; coverage **89.22 %** (≥ 80 %) |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Task 33 verify | `poetry run pytest tests/unit/dashboard/test_layout_guard.py tests/unit/dashboard/test_app_overview.py tests/unit/dashboard/test_layout.py -q --no-cov` | **117 passed** |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **622 passed** (was 610; +12 = 10 guard + 2 header-label) |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed** |
| Ten-page AppTest smoke | `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov` | **10 passed**, no page raises |
| Lint/format | `poetry run ruff check` / `ruff format` | clean |

**Against the part 2a gate.** Part 2a ended at **1426 passed / 3 skipped** (full)
and **610** (dashboard subset); part 2b ends at **1438 / 3** and **622**. The
**+12** is the D11 guard and the two header-label tests — **nothing regressed**.

### Accepted deviations and carry items

Task 33's `label_key` addition is the only new plan deviation (design-system §14).
The F1–F5 findings are carried into `validation/reference-overview.md` for the
owner's decision; **none of them is applied in Wave C.**

### Carry list for Wave D

1. ~~**AM-23 owner sign-off** on `validation/reference-overview.md`~~ — **signed
   off 2026-09-21** (see "Wave C part 2c" below); the gate is open.
2. The F1–F5 fixes, if the owner files them (F1/F2/F5 are one shell task; F3 is the
   chart builders; F4 lands per page in Waves D–G).
3. `MIGRATED_PAGES` grows by one entry per wave (Task 36 for the four A2 pages,
   then 38–44).

## Wave C part 2c — AM-23 owner sign-off (docs only)

The owner reviewed `validation/reference-overview.md` and the 1440 px captures and
recorded the decisions below. **No code changed in this close-out**; the one code
change it authorises is **Step 0a**, which landed separately (`a239d2f`).

| Decision | Items | Detail |
|---|---|---|
| **Owner sign-off: APPROVED** | A1–A9 | Approved as recommended |
| **Fixed** | Gregorian range font size | Step 0a (`a239d2f`): the Gregorian range cells in the Overview coverage table rendered in the id's mono 11.5 px; measured live, they now compute to Vazirmatn 13.5 px, matching the Jalali range and the count cells |
| **Scheduled** | F3, F4 | Chart legend title `label` and the English `Choose options` placeholder, in Waves D–G starting with Task 35 |
| **Not requested now** (optional Wave H polish candidates, not scheduled) | F1, F2, F5, F7, the Gregorian-vs-Jalali range-cell direction | Content padding 70 px vs 40 px; breadcrumb separator and bold current crumb; shell-wide `st.caption` direction; no-wrap in the short categorical coverage columns; the range-cell direction difference (the font-size half is fixed) |

**Data-quality findings handed to the ETL/catalog side** (the presentation is
correct in both cases; recorded in the plan's Deferred Scope as items 15 and 16):

- **D1** — the TGJU snapshot rows declare a coverage window of `۲۰ – ۲۰ شهریور
  ۱۴۰۵` while the observed range is `۱۸ – ۲۰ شهریور ۱۴۰۵`, so the declared range
  is narrower than what was observed.
- **D2** — several Statistical Centre of Iran monthly catalog rows declare
  coverage but have no Gold observations, so their observed-range, count,
  chained-rows and confidence cells render the em-dash.

**Owner checklist outcome.** Every box in `reference-overview.md` §6 is ticked,
and the sign-off line now reads **APPROVED (2026-09-21)**.

### Wave C part 2c gate

| Gate | Command | Result |
|---|---|---|
| Step 0a verify | `poetry run pytest tests/unit/dashboard/test_direction.py -q --no-cov` | **30 passed** |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **623 passed** (was 622; +1 = the Step 0a CSS/class pin) |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Lint/format | `poetry run ruff check` / `ruff format --check` | clean |

Wave C is **closed**; Wave D starts from this record.

## Wave D part A — Step 0 (F3/F4 fixes) and Task 35 (generic domain composition)

Step 0a (Gregorian range font size) and Step 0b (the AM-23 sign-off record) are
documented in "Wave C part 2c" above and in the execution log. This section
records **Task 35**, the A2 archetype's migration to the layout contract.

### Task 35 — the generic domain composition

The four A2 pages (GDP & Economy, Trade & Energy, FX & Gold, Labor) now render
through the shared components: the filter set, a chart section header, the chart
and its mode control, a quality section header, the quality summary as the shared
RTL HTML table, the observations grid in its expander, and the downloads.

| Change | Detail |
|---|---|
| Quality summary → HTML table (D1) | `build_quality_rows` builds typed cells from `localize_table_frame`'s output, so columns, values, Persian digits, Jalali dates and em-dashes are identical to the old grid. `coverage` variant: measured **1040 px** at the page's 1042 px column (fits) vs `default` **1324 px** and `default`+`compact` **1242 px** (both scroll sideways) |
| Section headers | `render_section_header("section.chart")` and `render_section_header("section.quality")` (new keys); observations keep their expander |
| Shared empty states | Every composition `st.info` → `render_empty`; the chart-mode and row-cap notices → `render_callout(…, body=…)` with a per-caller container key |
| Observations density (D1) | `st.dataframe(row_height=OBSERVATIONS_ROW_HEIGHT)` = 40 px (the `.dt.compact` row height) |
| **F3** legend title | `apply_plotly_typography` blanks `legend_title_text`; `color="label"` no longer renders an English `label` heading. Affects every time-series chart: the four A2 pages + Inflation, Welfare, Market, Correlation |
| **F4** placeholder | `render_filters` passes `placeholder=t("filter.placeholder")` ("انتخاب کنید") to its four multiselects and two Jalali selectboxes. Affects every page that renders it: gdp, trade_energy, fx_gold, labor, inflation, welfare, market, correlation, catalog (Overview unaffected) |

### Visual evidence (ten pages + four detail sets)

`docs/phase-7.2/wave-d-assets/`: `partA-all-pages-before/` and
`partA-all-pages/` (ten pages each, 1440×900), plus
`task-35/before-scroll/` and `task-35/after-scroll/` (the four A2 pages at four
scroll offsets each). Pixel diff of the ten before/after pairs:

| Page | Changed pixels | What changed |
|---|---|---|
| overview | **0** | nothing — the Overview is untouched |
| correlation, catalog, inflation, welfare, market | 1977–2636, all inside one 87 px strip at x≈335–422 | the filter widgets' placeholder text (F4) only |
| gdp, trade_energy, fx_gold, labor | 5766–77611 | F4 placeholders + the new section headers + the HTML quality table + (trade_energy, fx_gold) the shared empty-state callout |

Read from the crops: the GDP quality table shows all eleven columns with Persian
digits (`۶۶`, `۰`, `خیر`, `سالانه`) and no sideways scroll; the Labor single-quarter
row reads `۱ / ۱ / خیر / ۰` with Jalali dates; no chart legend carries a `label`
heading any more.

### Accepted deviations and carry items

1. **"One filter bar" is the shared `render_filters`.** The domain filter set
   renders its own stacked native widgets; Task 35 does not restructure it onto
   `render_filter_bar`. The plan's file list has no filter-bar refactor, no mockup
   prescribes a domain-page bar, and widgets, labels, keys and the returned
   `FilterState` are unchanged. **For the owner's Task 37 review.**
2. **`_render_capped_rows` gained a required `key_prefix`** (the callout
   container key), because the Market page renders several grids in one run. One
   call site in `test_scaling.py` was updated; no behaviour change.
3. **`RecordingStreamlit` (test_quality.py) gained an `html` recorder.** The plan
   described that file as pure-helper only; it also drives the render path, so the
   stub was extended and three tests added for the new builder and its markup.
4. **The quality table's id cell is capped at 24ch** by the shared `.dt .ltr`
   rule (`SCI.UNEMPLOYMENT.QUARTERLY` → `SCI.UNEMPLOYMENT.QUAR...`). The cell
   carries the full id as its `title`, so the token is recoverable on hover — the
   same cap and tooltip practice the coverage table already uses. **For the
   owner's review** rather than widening a global rule.
5. **Titles and caveats are still raw** on the four pages
   (`render_domain_page`'s `st.title`, `render_fx_gold_page`, `render_labor_page`).
   Task 36 routes them through `render_page_header`/`render_callout` and enables
   the D11 guard; Task 35 deliberately stops at the composition.
6. **Observation for the screenshot script's owner (Task 47):**
   `neutralise()` scrolls `stMainBlockContainer`, which is not the scroll
   container (`stMain` is), so its scroll-to-top is a no-op. Captures are
   unaffected because each page navigation starts at the top.

### Wave D part A gate

| Gate | Command | Result |
|---|---|---|
| Task 35 verify | `poetry run pytest tests/unit/dashboard/test_app_economy.py tests/unit/dashboard/test_app_trade_welfare.py tests/unit/dashboard/test_app_fx_gold.py tests/unit/dashboard/test_app_labor.py tests/unit/dashboard/test_quality.py -q --no-cov` | **66 passed** |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **628 passed** (was 623; +5 new tests) |
| Full gate | `make check` | **1444 passed, 3 skipped**; coverage **89.22 %** |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Lint/format | `poetry run ruff check` / `ruff format --check` | clean |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed** |

### Wave D part B — Task 36, the review and the Scope B gate

**Task 36 — domain-page headers.** `render_domain_page` opens with
`render_page_header`; `render_fx_gold_page` and `render_labor_page` route their
TGJU / Labor caveats through `render_page_header(..., callout_key=…)` with the
matching tone, and the Labor page's own catalog-empty alert became
`render_empty`. The D11 guard's `MIGRATED_PAGES` grew by the A2 archetype's whole
composition; two tests pin the four page modules to the thin-delegate shape.

| Gate | Command | Result |
|---|---|---|
| Task 36 verify | `poetry run pytest tests/unit/dashboard/test_layout_guard.py tests/unit/dashboard/test_app_economy.py tests/unit/dashboard/test_app_trade_welfare.py tests/unit/dashboard/test_app_fx_gold.py tests/unit/dashboard/test_app_labor.py -q --no-cov` | **41 passed** |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **630 passed** |
| Full gate | `make check` | **1446 passed, 3 skipped**; coverage **89.22 %** |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Lint/format | `poetry run ruff check` / `ruff format --check` | clean |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed** |

**Task 37 — owner visual review.** The review is
[`validation/archetype-domain.md`](validation/archetype-domain.md). It walks the
four A2 pages against the layout contract (§11–§12) and the Overview:

- **14 MATCH** — page header, section headers, shared empty states, no raw
  alerts, no `unsafe_allow_html`, one callout slot, the F4 placeholder, the F3
  legend title, the HTML quality table (`coverage` variant), the native
  observations grid (`row_height` 40 px), table semantics, escaping, `t()`
  coverage and CSS scoping.
- **1 DEVIATION (carried)** — the shared filter set is `render_filters`, not the
  Overview's `render_filter_bar`; recorded in the Wave D part A carry items and
  carried to the owner.
- **1 N/A** — no KPI band on a domain page (no aggregate metric to band).
- **0 layout defects.** One **content** defect is filed: `warn.single_observation`
  names TGJU but fires on the Labor page (SCI's lone quarterly observation).
  **Fixed now** in Wave E Step 0b as a source-neutral string.
- **Owner sign-off: APPROVED** (2026-09-21). The owner keeps the shared
  `render_filters` filter set (aligning it with `render_filter_bar` is an optional
  Wave H polish candidate, not scheduled), approves the 24-character quality-table
  id cap (full id in the `title`) and approves the absence of a KPI band on domain
  pages (N/A). The plan's Task 37 acceptance box is ticked. The decision is
  recorded in [`validation/archetype-domain.md`](validation/archetype-domain.md).
- **Carry-forward list for Wave H:** the filter-bar shape; optional polish **F1**
  (content padding 70 vs 40 px), **F2** (breadcrumb separator and bold current
  crumb), **F5** (shell-wide caption direction), **F7** (no-wrap short coverage
  columns); the Gregorian(LTR)/Jalali(RTL) range direction; and
  `scripts/dashboard_screenshots.py` `neutralise()` scrolls `stMainBlockContainer`
  (not the real scroll container `stMain`), so its scroll-to-top is a no-op
  (**Task 47**).

The ten-page 1440×900 captures after Task 36 are in
`docs/phase-7.2/wave-d-assets/partB-all-pages/`, with the four-page scroll crops
in `task-36/after-scroll/`. The Task 35 before/after diff shows `gdp` and
`trade_energy` byte-identical (0 px) and `fx_gold`/`labor` differing only in the
caveat callout strip, so `render_page_header` reproduces `st.title` exactly.

## Wave E part A — Step 0 + Tasks 38–39 (Inflation and Welfare emphasis sections)

**Scope.** Wave E part A is the first two of the three emphasis-domain pages
(A3 archetype): Step 0a records the Wave D owner sign-off, Step 0b fixes the
`warn.single_observation` string to be source-neutral, Task 38 migrates the
Inflation page, and Task 39 migrates the Welfare page. The Market page (Task 40)
and the owner review (Task 41) are part B.

| Item | Commit | Delta |
|---|---|---|
| Step 0a | `6da57d4` | Wave D owner sign-off APPROVED recorded in `validation/archetype-domain.md` and `VALIDATION.md` |
| Step 0b | `fb2c0b3` | `warn.single_observation` rewritten source-neutral; new source-neutrality test |
| Task 38 | `8512a44` | Inflation page: `render_page_header`/`render_callout`/`render_section_header`; provenance table via `render_html_table` (`coverage` variant) |
| Task 39 | `013d1fb` | Welfare page: `render_page_header`/`render_callout`/`render_section_header`; survey-year panel via `render_html_table` (`default` variant) |

### Per-page pixel diff (wave-e part A vs wave-d part B)

Ten PNGs, 1440×900, viewport-only, captured to
`docs/phase-7.2/wave-e-assets/partA-all-pages/`. Baseline:
`docs/phase-7.2/wave-d-assets/partB-all-pages/`.

| Page | Changed pixels | What changed |
|---|---|---|
| `overview` | 0.0 % (51×12 px at x≈1000) | timing artifact (not a regression) |
| `correlation` | 0 | nothing |
| `catalog` | 0 | nothing |
| `inflation` | 0 | the Inflation emphasis sections are below the fold; the top viewport is the title + filters, which `render_page_header` reproduces exactly |
| `gdp` | 0 | nothing (GDP is an A2 page, not migrated in Wave E) |
| `trade_energy` | 0 | nothing |
| `welfare` | 30.2 % | the two HBSIR callouts at the top now carry the scoped accent bars and info glyph (`render_callout` vs raw `st.warning`/`st.info`); the survey-year panel below the fold is the shared HTML table |
| `fx_gold` | 0 | nothing |
| `market` | 0 | nothing (Market is Task 40, part B) |
| `labor` | 0 | nothing |

**No regressions.** The 8 un-migrated pages are byte-identical (the overview's
0.0 % is a 51×12 px tooltip artifact, not a layout change). The Welfare page's
30.2 % is the expected callout-styling delta, confirmed in the Task 39
`after-top/welfare.png` and `after-scroll/survey-year-panel.png` crops.

### Wave E part A gate

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1453 passed, 3 skipped, 136 deselected** in 182.3 s; ruff format/lint and mypy clean; coverage **89.22 %** (≥ 80 %) |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **637 passed** (was 634; +3 new Welfare tests) |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -q --no-cov` | **16 passed** |
| Ten-page AppTest smoke | `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov` | **10 passed**, no page raises |
| Lint/format | `poetry run ruff check` / `ruff format --check` | clean |
| Working tree | `git status --short` | clean (assets committed) |

**Against the Wave D part B gate.** Wave D part B ended at **630 passed**
(dashboard subset); part A ends at **637**. The **+7** is the Step 0b
source-neutrality test (+1), the three Inflation tests (+3) and the three Welfare
tests (+3). **Nothing regressed.**

### Carry-forward items for Wave E part B

- The Market page (Task 40) is not yet migrated; its five TSETMC caveats and
  sessions metric are still raw `st.warning`/`st.info`/`st.metric`.
- The emphasis owner review (Task 41) is not yet prepared.
- The Wave H carry list from Wave D (F1, F2, F5, F7, filter-bar shape,
  Gregorian/Jalali range direction, `neutralise()` scroll no-op Task 47) is
  unchanged.

## Wave E part B — Task 40 (Market) + Task 41 (emphasis review prepared)

**Scope.** Wave E part B is the third emphasis-domain page and the archetype
review: Task 40 migrates the Market page (new `render_callout_stack` component),
and Task 41 prepares the emphasis owner review doc (not signed off).

| Item | Commit | Delta |
|---|---|---|
| Task 40 | `fb58ae8` | Market page: `render_page_header` + new `render_callout_stack` (five TSETMC caveats), one-cell `render_kpi_band` (sessions), `render_section_header` (level), shared empty states; design-system §4.1/§11/§12 updated |
| Task 41 | `6981991` | `validation/archetype-emphasis.md` prepared (owner sign-off **PENDING**); README status → "Wave E awaiting owner review" |

### Per-page pixel diff (wave-e part B vs wave-e part A and vs wave-d part B)

Ten PNGs, 1440×900, viewport-only, captured to
`docs/phase-7.2/wave-e-assets/partB-all-pages/`.

| Page | vs wave-d baseline | vs wave-e part A | What changed |
|---|---|---|---|
| `overview` | 0.0 % (51×12 px) | IDENTICAL | timing artifact |
| `correlation` | 0 | IDENTICAL | nothing |
| `catalog` | 0 | IDENTICAL | nothing |
| `inflation` | 0 | IDENTICAL | nothing in part B |
| `gdp` | 0 | IDENTICAL | nothing |
| `trade_energy` | 0 | IDENTICAL | nothing |
| `welfare` | 30.2 % | IDENTICAL | (part A's Task 39 change; nothing in part B) |
| `fx_gold` | 0 | IDENTICAL | nothing |
| `market` | 3.0 % (y 198–549) | 3.0 % | the five TSETMC caveats gain the scoped accent bars/glyphs (Task 40) |
| `labor` | 0.0 % (3×68 px at x≈326) | 0.0 % | timing artifact (a filter-area caret), not a layout change |

**No regressions.** Part B differs from part A on **only** `market` (the Task 40
change); every other page is byte-identical between the two captures. Against the
Wave D baseline, the only real changes are `welfare` (part A) and `market`
(part B); the `labor`/`overview` 0.0 % strips are sub-0.1 % timing artifacts.

### Wave E part B gate

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1455 passed, 3 skipped, 136 deselected** in 188.7 s; ruff format/lint and mypy clean; coverage **89.22 %** |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **637 passed** |
| Export + all-pages smoke | `poetry run pytest test_all_pages_smoke.py test_exports.py -q --no-cov` | **26 passed** (10 pages + 16 exports) |
| Lint/format | `poetry run ruff check` / `ruff format --check` | clean |
| Working tree | `git status --short` | clean (assets committed) |

**Against the Scope A gate.** Part A ended at **1453 passed** (full suite); part B
ends at **1455**. The **+2** is the two `render_callout_stack` component tests in
`test_layout.py`. The dashboard subset is unchanged at **637** — Task 40 changed
no page test (every Market assertion passes unchanged), so the component tests
are the only new tests. **Nothing regressed.**

### Carry-forward items for Wave F

- The emphasis owner review (Task 41) is **prepared, awaiting sign-off**
  (`validation/archetype-emphasis.md`). The three carried decisions (row 4 filter
  set, row 3 Market panel titles, §4 Welfare callout-stack observation) are
  recorded there.
- The Wave H carry list from Wave D (F1, F2, F5, F7, filter-bar shape,
  Gregorian/Jalali range direction, `neutralise()` scroll no-op Task 47) is
  unchanged.

## Wave E part C — owner sign-off (docs only)

**Scope.** Wave E close-out: record the owner's decision on the emphasis-domain
review (`validation/archetype-emphasis.md`, Task 41) and tick its plan box. No
code change; the Wave F Step 0a commit carries this record.

| Item | Commit | Delta |
|---|---|---|
| Task 41 sign-off | *(this commit)* | `validation/archetype-emphasis.md` §10 added (status → **SIGNED OFF — APPROVED**); README status → "Wave E complete; Wave F/G in progress"; plan Task 41 box ticked |

Recorded verbatim on 2026-09-22:

- Owner sign-off: **APPROVED**; the 15 MATCH rows accepted.
- Approved deviations:
  - the shared `render_filters` set on Inflation/Welfare/Market — aligning it
    with `render_filter_bar` remains an optional Wave H polish candidate;
  - Market's derived-panel titles stay a raw `st.subheader` (resolved display
    strings, visually identical to `render_section_header`);
  - Inflation's three explanatory captions rendered as info callouts (contract:
    notices are callouts).
- Not needed: routing Welfare's two top-level caveats through
  `render_callout_stack` (no rendered difference).

**Gate.** Documentation-only change: no test run is required (the Wave F gate
re-runs the full suite). The tree contains only `docs/` edits.

## Wave F — Step 0 (Wave E sign-off + single-cell KPI band) and Tasks 42–43 (correlation)

**Scope.** Wave F closes Wave E (owner sign-off recorded, docs only), fixes the
one-cell KPI band width (Step 0b), migrates the A4 comparison / correlation page
to the layout contract (Task 42), and prepares its owner review (Task 43, not
signed off).

| Item | Commit | Delta |
|---|---|---|
| Step 0a | `2c16584` | Wave E owner sign-off recorded (APPROVED, 15 MATCH rows, three deviations); README → "Wave E complete; Wave F/G in progress"; plan Task 41 box ticked |
| Step 0b | `8a791ad` | `kpi_band_column_weights` pads a <3-cell band to the four-cell reference width; `render_kpi_band` renders the padding column empty; design-system §4.1; +4 tests |
| Task 42 | `f557a45` | `render_correlation_page` on the layout contract (page header, three callout caveats, `render_empty`, `render_section_header`, `row_height` on the overlap summary); guard covers A4; one assertion changed (caption → info) |
| Task 43 | `51dd15e` | `validation/archetype-correlation.md` prepared (owner sign-off **PENDING**); README → "Wave F awaiting owner review" |

### Step 0b — the single-cell KPI band measurement

| Band | Before | After |
|---|---|---|
| Market one-cell (`kpi-band-market-level`) | cell **1042.0 px / band 1044.0 px = 99.8 %** | cell **253.5 px = 24.3 %** (one quarter) |
| Overview six-cell (reference) | primary cell 143.8 px = 13.8 % | unchanged |

The lone cell stretched across the whole content column; it now keeps the
four-cell reference width and stays at the RTL start (the appended spacer takes
the far end). Evidence: `wave-f-assets/step-0b/` (before/after crops).

### Per-page pixel diff (wave-f part A vs wave-e part B)

Ten PNGs, 1440×900, viewport-only, captured to
`docs/phase-7.2/wave-f-assets/partA-all-pages/`.

| Page | Changed | What changed |
|---|---|---|
| `correlation` | 0.17 % (x 1061–1369, y 728–780) | the default no-selection empty state is now the shared callout, so it gains the accent bar and the info glyph |
| `overview` | 0.00 % | nothing |
| `catalog` | 0.00 % | nothing (Wave G not started) |
| `inflation` | 0.00 % | nothing |
| `gdp` | 0.00 % | nothing |
| `trade_energy` | 0.00 % | nothing |
| `welfare` | 0.00 % | nothing |
| `fx_gold` | 0.00 % | nothing |
| `market` | 0.00 % | nothing at the top viewport — the Step 0b KPI change is **below the fold** (documented in `wave-f-assets/step-0b/`) |
| `labor` | 0.00 % | nothing |

**No regressions.** The only viewport change is the correlation empty-state
callout; every other page is byte-identical. The Step 0b change is below the fold
and is evidenced separately.

### Wave F gate

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1459 passed, 3 skipped, 136 deselected** in 177.38 s; ruff format/lint and mypy clean; coverage **89.22 %** |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **643 passed** |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed**, 15 deselected |
| All-pages smoke | `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov` | **10 passed** |
| Lint/format | `poetry run ruff check` / `ruff format --check` | clean |
| Working tree | `git status --short` | clean (assets committed) |

**Against the Scope A baseline.** The full suite ends at **1459**, exactly
**+4** over the Wave E **1455** — the four Step 0b KPI tests; nothing else
changed a test count. The dashboard subset ends at **643**. The Wave E part B
record recorded **637**, but a **re-measurement at `0ef17fb` in a clean worktree
returns 639**; the recorded figure was stale by 2. Against the re-measured
baseline the subset is **+4** (Step 0b only). **Nothing regressed.**

### Carry-forward items for Wave G

- The correlation owner review (Task 43) is **prepared, awaiting sign-off**
  (`validation/archetype-correlation.md`). The one carried decision (row 4, the
  shared `render_filters` set) is recorded there; it does not block Wave G.
- The Wave D carry list (F1, F2, F5, F7, filter-bar shape, Gregorian/Jalali range
  direction, `neutralise()` scroll no-op Task 47) is unchanged.

## Wave G — Step 0c and Tasks 44–45 (catalog)

**Scope.** Wave G proceeds while the Wave F review is pending (Step 0c), migrates
the A5 data catalog page to the layout contract (Task 44), and prepares its owner
review (Task 45, not signed off).

| Item | Commit | Delta |
|---|---|---|
| Step 0c | `127ce90` | Wave G proceeds while Wave F's review is pending; Task 43 left unticked |
| Task 44 | `ed2b4a4` | `render_catalog_page` on the layout contract: `render_page_header`, a `render_filter_bar` hosting search + the shared filter set + the inactive toggle + clear, a one-cell `render_kpi_band` count, `render_empty`, the grid with `row_height`; guard covers A5; +2 tests |
| Task 45 | `0e45d08` | `validation/archetype-catalog.md` prepared (owner sign-off **PENDING**); README → "Waves F and G awaiting owner review" |
| Evidence fix | `78e4c8d` | the Tasks 42–43 full-page captures replaced with true full-height captures (Streamlit scrolls an inner container, so `full_page=True` returned the 900 px viewport) |

### Per-page pixel diff (wave-g part B vs wave-f part A)

Ten PNGs, 1440×900, viewport-only, captured to
`docs/phase-7.2/wave-g-assets/partB-all-pages/`.

| Page | Changed | What changed |
|---|---|---|
| `catalog` | 25.03 % (x 326–1370, y 200–899) | Task 44: the vertical filter stack became a four-column `render_filter_bar`; the matching count is now a one-cell KPI band; the grid takes the shared `row_height` |
| the other nine pages | 0.00 % | byte-identical |

**No regressions.** The only viewport change is the catalog page (Task 44); every
other page is byte-identical to the Wave F part A set.

### Wave G gate

| Gate | Command | Result |
|---|---|---|
| Full quality gate | `make check` | **1461 passed, 3 skipped, 136 deselected** in 175.69 s; ruff format/lint and mypy clean; coverage **89.22 %** |
| Types | `poetry run mypy src dashboard` | **0 errors**, 68 source files |
| Dashboard subset | `poetry run pytest tests/unit/dashboard -q --no-cov` | **645 passed** |
| Export smoke | `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov` | **1 passed**, 15 deselected |
| All-pages smoke | `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov` | **10 passed** |
| Lint/format | `poetry run ruff check` / `ruff format --check` | clean |
| Working tree | `git status --short` | clean (assets committed) |

**Against the Scope B baseline.** The full suite ends at **1461**, **+2** over the
Wave F **1459** — the two new catalog tests (`test_catalog_matching_count_is_a_kpi_band_cell`,
`test_catalog_hosts_every_control_in_the_filter_bar`). The dashboard subset ends at
**645**, **+2** over the Wave F **643**. No existing assertion changed. **Nothing
regressed.**

### Carry-forward items for Wave H

- The correlation (Task 43) and catalog (Task 45) owner reviews are **prepared,
  awaiting sign-off** (`validation/archetype-correlation.md`,
  `validation/archetype-catalog.md`). Task 43's plan box and Task 45's plan box
  stay open.
- Two recorded layout deviations: the shared filter set is the bar on the catalog
  page (Task 45 row 22 — a tall narrow column) and is *not* the bar on the
  domain/emphasis/correlation pages (the Wave D/E/F carry item). A single bar
  shape is the Wave H candidate.
- The Wave D carry list (F1, F2, F5, F7, filter-bar shape, Gregorian/Jalali range
  direction, `neutralise()` scroll no-op Task 47) is unchanged.

## Wave H — Step 0 (Wave F and G owner decisions, docs only)

**Scope.** Wave H opens by recording the owner's decisions on the two pending
archetype reviews (Wave F correlation, Task 43; Wave G catalog, Task 45). No code
change; this is a docs-only step.

| Item | Commit | Delta |
|---|---|---|
| Step 0 | *(this commit)* | Wave F sign-off APPROVED recorded (`validation/archetype-correlation.md` §10); Wave G sign-off APPROVED **conditional on P1** recorded (`validation/archetype-catalog.md` §10, row 22 → DEFECT); README status → "Waves F and G approved; Wave H in progress"; plan Task 43 box ticked, Task 45 box left open until P1 |

The owner's decisions, recorded verbatim on 2026-09-22:

- **Wave F: owner sign-off APPROVED.** The **14 MATCH** rows are accepted; the one
  carried decision (row 4, the shared `render_filters` filter set instead of the
  Overview's `render_filter_bar`) is an **accepted deviation**.
- **Wave G: owner sign-off APPROVED, conditional on P1.** The 15 MATCH and 8 N/A
  rows are accepted. The one deviation (row 22, the shared filter set hosted as a
  tall narrow bar column) is a **DEFECT, not an accepted deviation**; **P1** fixes
  it and the Task 45 plan box is ticked only after P1 is verified.
- **Filter-set shapes are not unified** — recorded as an **accepted deviation**:
  the Overview uses `render_filter_bar` of selects; the domain/emphasis/correlation
  pages use `render_filters`; the catalog uses a bar of simple controls plus a
  full-width `render_filters`.
- **Not done, accepted deviations (with reasons):**
  - **F1** content padding 70 px vs the mockup's 40 px — owner did not request it;
    it is a global change.
  - **F7** no-wrap of the short categorical coverage columns — owner did not
    request it.
  - the Gregorian ranges read LTR while the Jalali ranges read RTL — the **D3**
    bidi decision.
  - the `<td title>` hover tooltip is **unverified in a real browser** — an owner
    checklist item.
  - the ETL/catalog findings **D1** and **D2** — handed to the ETL/catalog side
    (the plan's Deferred Scope).
- **README status:** "Waves F and G approved; Wave H in progress".

**Gate.** Documentation-only change: no test run is required (the P1 and gate
steps re-run the suite). The tree contains only `docs/` edits.

## Wave H — part A (P1–P4, the quality gate and the all-pages capture)

**Scope.** Scope A (the four polish items P1–P4) and the Scope B part-A gate: the
full quality gate, the ten-page capture, and this record. Presentation-layer only.

### P1–P4

| Item | Commit | Delta |
|---|---|---|
| P1 | `996bd0a` | Catalog filter bar hosts only the three simple controls (`weights=[3.0, 2.0, 1.0]`, bar 555 → 61 px); `render_filters` renders full width below it (251 px column → 1044 px). Fixes the Wave G sign-off defect (row 22). |
| P2 | `d3ee015` | Shell-level `stMainBlockContainer stCaptionContainer { direction: rtl; text-align: start }` makes every main-block caption read RTL; replaces the scoped `coverage_footnote` hook (verified byte-identical on the Overview). |
| P3 | `31b88b6` | Breadcrumb separator `›` (U+203A) → `/` with `<span class="crumb-sep">`; current crumb bolded (`<b class="crumb-current">`, weight 600). Matches the mockup (`overview-redesign-mockup.html:141`). |
| P4 | `2c0977c` | `scripts/dashboard_screenshots.py`: `neutralise()` scrolls `stMain` (the real scroll container; the block container it targeted was not scrollable); new optional `--full-height` flag. |

### Quality gate (Wave H part A)

- **`poetry run mypy src dashboard`** → **Success: no issues found in 68 source
  files** (the gate is "zero errors"; the Task 1 baseline had none).
- **`make check`** (format + lint + typecheck + full test) → **PASS**, `1468
  passed, 3 skipped`; coverage **89.22%**. The Wave 0 baseline was 1 158 passed /
  3 skipped; the count has grown with the waves, no regressions.
- **Dashboard subset** (`pytest tests/unit/dashboard -q --no-cov`) → **652
  passed**.
- **Export smoke** (`pytest tests/unit/dashboard/test_exports.py -m integration
  -q --no-cov`) → **1 passed** (the Task 14 PNG + SVG render with the new
  template; re-confirmed in Task 48).
- **All-pages smoke** — `tests/unit/dashboard/test_all_pages_smoke.py` is inside
  the 652 above; all ten pages render through the router harness.

### All-pages capture

Ten PNGs, all **1440 x 900**, captured at commit **`2c0977c`** into
`wave-h-assets/partA-all-pages/` (fresh server, 2026-09-22 02:41:58). The
per-page pass/defect result and the pixel diff against the Wave G reference
(`wave-g-assets/partB-all-pages/`) are in
`wave-h-assets/partA-all-pages/DIFF.md`. **No defects:** the diffs are exactly the
intended P1 (catalog, 20.4%), P2 (caption strip, ~0.5% on nine pages) and P3
(breadcrumb, top bar on all ten) changes.

**Boundary.** No file under `src/`, `alembic/` or `airflow/` changed.

## Wave H — part B (Task 46 guard, Task 47 documentation)

**Scope.** Close the consistency guard (Task 46) and write the phase record and
runbook (Task 47). Docs and tests only; no presentation change.

### Task 46 — the consistency guard, verified

- **Decision:** the guard stays **function-scoped** (`MIGRATED_PAGES` maps module →
  migrated function names). Widening to file scope would report the shared
  components' own implementation (`render_callout` *is* a `st.warning`). The
  coverage gap the function scope leaves open is closed by two completeness tests
  instead:
  - `test_every_registered_page_delegates_to_a_migrated_function` — each of the
    ten `PAGES` rows delegates to exactly one listed composition.
  - `test_the_mapping_covers_every_render_function` — `MIGRATED_PAGES` **equals**
    `page_view.py`'s render functions (23 = 23; verified no gap, no stale entry).
- A deliberate raw `st.title` now fails whether it lands in a listed function, in
  a new render function, or in a page module.
- **Verified:** `pytest tests/unit/dashboard/test_layout_guard.py` → 17 passed;
  dashboard subset → 657 passed.

### Task 47 — runbook and this record

- `README.md` now carries the **runbook** (pages table, layering, how to verify)
  and the **"How to add or change a page"** checklist.
- `design-system.md` §16 documents the dev-only screenshot script; §4.1 the top
  bar and page header; §6 the sidebar shell. §15's Task-47 open item is closed.
- `AGENTS.md` gained a **Dashboard UI conventions (Phase 7.2)** section.
- `PR-DESCRIPTION.md` is the pull-request summary.

### Ten-page browser checklist (Wave H part A capture)

Ten PNGs at 1440x900, commit **`2c0977c`**, in
`wave-h-assets/partA-all-pages/`; per-page result and pixel diff in
`wave-h-assets/partA-all-pages/DIFF.md`.

| Page | Renders | Header / KPI / sections | Notes |
|---|---|---|---|
| overview | yes | yes | reference page |
| correlation | yes | yes | empty-state (no pair selected) |
| catalog | yes | yes | P1 filter bar (3 controls + full-width filter set) |
| inflation | yes | yes | emphasis (CPI decile + canonical + chain-linking) |
| gdp | yes | yes | generic domain (empty state in the capture) |
| trade_energy | yes | yes | generic domain |
| welfare | yes | yes | emphasis (HBSIR survey panel) |
| fx_gold | yes | yes | generic domain, own header |
| market | yes | yes | emphasis (TSETMC notes) |
| labor | yes | yes | generic domain, own header |

**No defects.** Every pixel diff is an intended Wave H change (P1 catalog, P2
caption RTL on nine pages, P3 breadcrumb on all ten).

### Archetype review outcomes

All five reviews are **signed off APPROVED** (2026-09-21/22):

| Review | File | Result |
|---|---|---|
| Shell + Overview (AM-23) | `validation/reference-overview.md` | APPROVED (deviations A1–A9 accepted) |
| Generic domain pages (A2) | `validation/archetype-domain.md` | APPROVED |
| Emphasis pages (A3) | `validation/archetype-emphasis.md` | APPROVED (15 MATCH; 3 deviations) |
| Correlation (A4) | `validation/archetype-correlation.md` | APPROVED (14 MATCH; shared `render_filters` deviation accepted) |
| Catalog (A5) | `validation/archetype-catalog.md` | APPROVED **conditional on P1**; P1 verified |

### Wave 0 findings carried into this record (Task 4)

- **`st.html` survival:** `<style>`, `class`, inline `style`, `title`,
  `dir="rtl"`, `<bdi>`, `data-*` and `<a href>` survive; **`<svg>` is stripped**.
  The callout glyph is a CSS shape; the sidebar brand mark is a CSS square.
- **Theme switcher:** the custom `[theme]` already hides the settings-menu theme
  toggle; no toolbar-mode change was needed to hide it.
- **Brand fallback:** CSS-pinned brand block above the nav (fallback **2**), via
  `[data-testid="stSidebarHeader"]` pseudo-elements + the `stSidebarUserContent`
  flex pin for the DB status.
- **Toolbar fallback:** shipped `client.toolbarMode="viewer"` (hides Deploy and
  the developer options, keeps Print/Record); `STREAMLIT_CLIENT_TOOLBAR_MODE=developer`
  restores the developer toolbar locally.

### Not automated in this run

These are **not** covered by the automated suite and rely on the owner checklist /
manual review; they are recorded as open, not as verified:

- **Native hover tooltip on a `<td title>`** — not rendered by headless Chromium;
  unverified in a real browser (an owner checklist item).
- **Streamlit-chrome selectors** (`direction.py` §6) — `AppTest` cannot see chrome;
  only the manual browser walk (and the screenshot set) catches a break. The block
  is version-named (1.61.1) and must be re-probed before extending.
- **Font rendering** (Vazirmatn) and **OS-stack fallback** — visual only.
- **The two recorded accepted deviations** that the owner chose not to fix: **F1**
  content padding 70 px vs the mockup's 40 px; **F7** no-wrap of the short
  categorical coverage columns. Plus the D3 bidi direction for Gregorian vs Jalali
  ranges.
- **ETL/catalog findings D1 and D2** — handed to the ETL/catalog side; out of the
  dashboard's boundary.
- **Cache-TTL item** and Phase 7.1 Tasks 27–28 (extended suite + analyst
  acceptance) — deferred (plan Deferred Scope).

## Wave H — part C (Task 48 cross-page consistency audit)

**Scope.** Confirm one header / KPI / section-header / filter-bar pattern and the
shared states across all ten pages, confirm every chart uses the shared template,
and re-confirm the export image path. No code change.

**Evidence:** `wave-h-assets/audit/contract-audit.md` — a page × contract-item
matrix from two checks (a static call graph of each page's composition, plus a live
Playwright DOM probe at 1440x900). Live app at HEAD **`4e7c3a8`** (dashboard code
unchanged since `2c0977c`).

| Contract item | Result |
|---|---|
| One header pattern (`render_page_header`) | CONFIRMED — all ten; live `h1 == t("page.<key>")` on every page |
| One KPI pattern (`render_kpi_band`) | CONFIRMED — Overview, Catalog, Market (the pages with KPI cells); N/A elsewhere |
| One section-header pattern (`render_section_header`) | CONFIRMED — nine pages; Catalog N/A (single grid) |
| One filter-bar pattern (`render_filter_bar` / `render_filters`) | CONFIRMED — all ten |
| Shared states (`render_empty`) | CONFIRMED — all ten empty cases |
| Shared error/loading states | N/A — `render_error`/`render_loading` are defined but no page renders an error/loading path |
| Typed table (`render_html_table`) | CONFIRMED — eight pages; Catalog uses the native `st.dataframe` (D1 grid), N/A |
| Every chart uses the shared template | CONFIRMED — the eight chart pages reach a `charts.build_*` builder; none builds Plotly directly |
| Exports (`render_data_downloads` / `render_chart_downloads`) | CONFIRMED — eight pages |
| Layout guard (no raw `st.title`/`st.metric`/… in a migrated function) | PASS — `test_layout_guard.py` |

**Export smoke re-confirmed:** `pytest tests/unit/dashboard/test_exports.py -m
integration -q --no-cov` → **1 passed** (PNG + SVG render with the shared
template). No defect found in the audit.
