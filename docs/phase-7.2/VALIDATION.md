# Phase 7.2 Validation Report

**Status:** Wave A complete (Tasks 1–24) — the visual review recorded here is
2026-09-21 against a populated local database.
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
