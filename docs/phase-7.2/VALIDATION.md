# Phase 7.2 Validation Report

**Status:** Wave B complete (shell — Tasks 25–28 + Step 0 close-out); **Wave C
part 1 complete** (Step 0f + Tasks 29–31, Overview page). The visual review
recorded here is 2026-09-21 against a populated local database.
**Plan:** [phase-7.2-dashboard-redesign.md](../plans/phase-7.2-dashboard-redesign.md)
**Design system:** [design-system.md](design-system.md) ·
**Wave 0 evidence:** [wave-0-spike.md](wave-0-spike.md) ·
**Per-task record:** [execution-log.md](execution-log.md)

This report separates **verified in this run** from **not automated in this run**.
Wave A is the token/typography/CSS foundation plus the shared components; the
per-archetype owner reviews are a later wave and are **not** covered here.

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
