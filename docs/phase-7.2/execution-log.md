# Phase 7.2 — Execution log

Per-task log. One entry per task with **files**, **Verify result**,
**deviations**, and **commit hash**.

Decisions for Wave A/B live in
[`wave-0-spike.md` §7](wave-0-spike.md#7-decisions-for-waves-ab).

---

## Task 1 — (0) VERIFY Streamlit capabilities/APIs/sanitization/AGENTS; RECORD baseline

- **Files:** `docs/phase-7.2/wave-0-spike.md` (new), `docs/phase-7.2/README.md`
  (new stub), `docs/phase-7.2/execution-log.md` (new),
  `docs/phase-7.2/wave-0-assets/before/*.png` (10 new).
- **Verify:**
  - `streamlit.__version__` → 1.61.1.
  - `make check` → **PASS** (EXIT=0; 1 158 passed, 3 skipped, 135 deselected; cov 89.22 %).
  - `poetry run mypy src dashboard` → **0 errors**.
  - `poetry run pytest tests/unit/dashboard -q` → **341 passed, 0 failed**
    (EXIT=1 from the subset coverage gate only).
  - Separator → U+066C (VERIFIED). Ten before screenshots captured.
  - `git status --short` unchanged by `make check` (format-clean).
- **Deviations:** none to production. Drift recorded in the plan's Material-icon
  claim (bare names do **not** validate; the shortcode does) and corrected in
  Task 3's commit.
- **Commit hash:** `35ce5f6`

## Task 2 — (0) VERIFY shell DOM, static serving, toolbar mode, brand fallbacks

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append),
  `docs/phase-7.2/execution-log.md`,
  `docs/phase-7.2/wave-0-assets/{shell-injection,shell-variant-b,header-auto,header-viewer,header-minimal}.png`.
- **Verify:** `/app/static/Vazirmatn.ttf` → 200 `font/ttf` 241 328 B; font
  `document.fonts` "Vazirmatn" loaded; toolbar matrix (auto/viewer/minimal);
  sidebar selectors via `[data-testid]`/`[aria-current="page"]`; brand fallback
  injection. All manual browser checks passed.
- **Deviations:** none to production.
- **Commit hash:** `834fe38`

## Task 3 — (0) RECORD verified page inventory and archetypes

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append), plan corrections.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_navigation.py -q` →
  10 passed; ten page modules; render symbols/line numbers match the plan.
- **Deviations:** none to production.
- **Commit hash:** `8a0e245`

## Task 4 — (0) VERIFY st.html rendering and theme-switcher behaviour

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append + decisions + owner
  checklist), `docs/phase-7.2/wave-0-assets/badge-segmented.png`.
- **Verify:** `st.html` survival matrix (style/class/inline-style/title/dir/bdi/
  data-/a survive; svg stripped); `st.markdown(unsafe_allow_html=True)` CSS
  applies; custom `[theme]` already hides the theme toggle.
- **Deviations:** none to production.
- **Commit hash:** `f8bbfcd`

---

## Wave 0 commit summary

| Task | Commit |
|---|---|
| 1 — capabilities + baseline | `35ce5f6` |
| 2 — shell/static/toolbar/brand | `834fe38` |
| 3 — page inventory | `8a0e245` |
| 4 — `st.html` + theme switcher + plan corrections | `f8bbfcd` |

All commits are docs-only. The untracked font files under `dashboard/static/`
were never staged or committed (Task 7 owns them).

---

## Task 5 — (A) ADD the design-token module

- **Files:** `dashboard/components/tokens.py` (new),
  `tests/unit/dashboard/test_tokens.py` (new), plan checkboxes.
- **Build:** frozen `MappingProxyType` of the mockup's entire `:root` block
  (22 tokens: palette, soft backgrounds, `surface-2`, `hover`, radii, `font-ui`,
  `font-mono`), with `token()` / `custom_properties()` /
  `css_custom_properties()` helpers. The test parses
  `docs/design/phase-7.2/overview-redesign-mockup.html` and asserts set equality.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_tokens.py -q --no-cov`
  → **6 passed**. `ruff format`/`ruff check` clean. `poetry run mypy src dashboard`
  → **0 errors** (64 source files).
- **Deviations:** the token↔`[theme]` consistency assertion is deferred to
  Task 8: its premise (the Task 8 theme values) does not exist yet, and a
  failing test must not be committed. Task 8 appends it to `test_tokens.py`.
- **Commit hash:** `27df2ec`

## Task 6 — (A) RAISE the Streamlit floor and refresh the lock

- **Files:** `pyproject.toml`, `poetry.lock` (git-ignored, not committed).
- **Build:** `streamlit = "^1.36"` → `">=1.44,<2"`.
- **Verify:** `poetry check` → exit 0 (pre-existing deprecation warnings only).
  `poetry lock` → lock content hash rewritten, **no package version deltas**
  (219 packages before/after; `streamlit` still 1.61.1). `poetry run pytest
  tests/unit/dashboard -q --no-cov` → **347 passed** (341 baseline + 6 token
  tests).
- **Deviations:** `poetry.lock` is git-ignored (`.gitignore:37`) and is not
  tracked, so the refreshed lock is not committed; only `pyproject.toml` lands.
  The D9 implication note in the plan records this.
- **Commit hash:** `7569676`

## Task 7 — (A) VENDOR the Vazirmatn font and wire theme + static serving

- **Files:** `dashboard/static/Vazirmatn.ttf`, `dashboard/static/OFL.txt`
  (committed by path, unchanged), `.streamlit/config.toml`,
  `dashboard/components/direction.py`, plan checkboxes.
- **Build:** `[server] enableStaticServing = true`; `[[theme.fontFaces]]`
  `family="Vazirmatn"`, `url="app/static/Vazirmatn.ttf"`, `weight="100 900"`;
  `theme.font`/`headingFont`/`codeFont` set to full fallback stacks. The two
  stale 7.1 comments in `.streamlit/config.toml` and `direction.py` corrected.
  `.gitignore` has no `static/`/`*.ttf` rule; there is no Dockerfile and
  `docker-compose.yml` mounts only the Postgres data volume + `init-db.sql`,
  so `dashboard/static/` ships in-repo and is served by Streamlit static serving
  (everything in `dashboard/static/` is publicly served — only the font and
  licence live there).
- **Verify:** `curl /app/static/Vazirmatn.ttf` → **200 `font/ttf` 241 328 B**
  (byte-identical; wrong `app/dashboard/static/...` → SPA shell 200 `text/html`
  10 951 B, fails silently). Playwright: `document.fonts.check('16px Vazirmatn')`
  → **true**, Vazirmatn entry **loaded**, computed body family starts with
  `Vazirmatn`. No config error in the streamlit log. `ruff`/`mypy` clean;
  `test_direction.py` + `test_tokens.py` → 15 passed.
- **Deviations:** none.
- **Commit hash:** `7606c01`

## Task 8 — (A) UPDATE the Streamlit theme to the design tokens

- **Files:** `.streamlit/config.toml`, `tests/unit/dashboard/test_tokens.py`,
  plan checkboxes.
- **Build:** set `base="light"`, `primaryColor`, `backgroundColor`,
  `secondaryBackgroundColor`, `textColor`, `borderColor`, `baseRadius=6px`,
  `buttonRadius=6px`, `baseFontSize=14`, `dataframeHeaderBackgroundColor`,
  `showWidgetBorder`, `showSidebarBorder`, `chartCategoricalColors` and the
  red/orange/yellow/blue/green `{Color,BackgroundColor,TextColor}` keys from
  the tokens. Semantic mapping: orange=warn, blue=accent/info, red=err,
  green=ok; **yellow has no mockup token and is folded into the warn palette**
  (recorded). `font`/`fontFaces` kept from Task 7 (not duplicated). Every
  listed option name was confirmed to exist via
  `c.get_config_options()` first.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_tokens.py -q --no-cov`
  → **10 passed** (token equality + `[theme]`↔token consistency + base size +
  chart colours + font-owner checks). App started with the new theme, **no
  config error** in the streamlit log (`curl /` → 200).
- **Deviations:** none.
- **Commit hash:** `2bca541`

## Task 9 — (A) EXTEND the shell CSS owner with tokens and the chrome block

- **Files:** `dashboard/components/direction.py`,
  `tests/unit/dashboard/test_direction.py`, plan checkboxes.
- **Build:** added `css_custom_properties()` to `direction_css()` so the token
  `:root` block is emitted; registered stable chrome selectors in
  `CSS_SELECTORS`; added a comment-marked, version-named `/* Streamlit-chrome
  selectors — verified on Streamlit 1.61.1 ... */` block implementing sidebar
  width 256 px, flex column pinning `stSidebarUserContent` to the bottom via
  `order:2;margin-top:auto`, active-nav accent via `[aria-current="page"]`
  (`border-inline-start:3px solid var(--accent)`), and main-container max-width
  1360 px. No brand or top-bar rules; main top padding untouched. CSS still
  injected via `st.markdown(..., unsafe_allow_html=True)`.
- **Verify:** `poetry run pytest tests/unit/dashboard -q --no-cov` → **356
  passed** (341 baseline + 15 new). `poetry run mypy src dashboard` → **0
  errors**. Visual Playwright check: sidebar computed width **256 px**, main
  container `max-width:1360px`, `--accent` token on `:root` equals
  `#1D4E89`, active nav item has the accent bar, DB status pinned at the
  bottom. Native header computed height **52.5 px** at the 14 px base set in Task 8.
  The header height is **3.75 rem** (60 px at a 16 px base, 52.5 px at the 14 px
  base), so Task 28 must use rem units, not fixed px.
- **Deviations:** none.
- **Commit hash:** `163cb3b`

## Task 10 — (A) ADD the dev-only screenshot script (moved from Wave H; AM-24)

- **Files:** `scripts/dashboard_screenshots.py` (new), `Makefile` (new
  `dashboard-screenshots` target), `.gitignore` (new entry for the default
  output directory), plan checkboxes.
- **Build:** a Playwright script (`capture(base_url, out_dir)`) that launches
  Chromium at 1440×900, navigates to the app, and clicks through all ten pages
  in registry order using the sidebar nav links (labels resolved via
  `t(f"nav.{spec.key}")`, no URL guessing). `wait_ready()` waits for
  `stApp` + `stMainBlockContainer` and suppresses transient spinner/skeleton
  detach timeouts. Each page is screenshotted to `{out_dir}/{key}.png`. Default
  output: `docs/phase-7.2/wave-a-assets/after-global-look/` (gitignored). The
  Makefile target `dashboard-screenshots` is non-default and **not** part of
  `make check`. Fixed Playwright `TimeoutError` handling: the script imports
  `TimeoutError as PlaywrightTimeoutError` from `playwright.sync_api` and uses
  `contextlib.suppress(PlaywrightTimeoutError)` (Playwright's `TimeoutError`
  does not inherit Python's builtin `TimeoutError`).
- **Verify:** `poetry run ruff format`/`ruff check` on the script → **clean**.
  `poetry run mypy scripts/dashboard_screenshots.py` → **0 errors**. Script run
  against the live app → **10 PNGs written** (63–91 KB each, 1440×900).
  `make check` does not invoke it (non-default target). `.gitignore` confirmed
  working (`git status` shows no untracked files under `after-global-look/`).
- **Deviations:** none.
- **Commit hash:** `396706e`

---

## Global-look checkpoint — Wave A after Tasks 7–10

- **Before baseline:** `docs/phase-7.2/wave-0-assets/before/*.png` (10 images, tracked).
- **After captures:** `docs/phase-7.2/wave-a-assets/after-global-look/*.png` (10
  images, gitignored; captured at 1440×900 by `scripts/dashboard_screenshots.py`).
- **Method:** visual side-by-side comparison of the same viewport.

### Per-page findings

| Page | Finding | Status |
|---|---|---|
| `overview` | Global look applied: Vazirmatn 14 px, token backgrounds, sidebar 256 px + accent active bar, main max-width 1360 px, DB-status card pinned at bottom. | PASS |
| `correlation` | Same global look changes. Info box renders in `accent-soft` background. | PASS |
| `catalog` | Same global look changes. Search/filter fields now visible below date range because max-width constraints changed vertical flow. | PASS |
| `inflation` | Same global look changes. The "شاخص‌ها" multiselect renders **expanded** in the capture (many selected chips visible). This is a capture artifact from navigation, not a design change; it is a known screenshot timing issue. | PASS with note |
| `gdp` | Same global look changes. "حالت نمودار" (chart state) dropdown visible below the date range. | PASS with note |
| `trade_energy` | Same global look changes. Info box uses `accent-soft` background. | PASS |
| `welfare` | Same global look changes. The new max-width/layout reveals the "روند جینی و فقر نسبی" section lower on the page. | PASS with note |
| `fx_gold` | Same global look changes. Warning banner uses `warn-bg` background. | PASS |
| `market` | Same global look changes. Warning + info banners use token tints. | PASS |
| `labor` | Same global look changes. "حالت نمودار" dropdown now visible below the date range. | PASS with note |

### Summary of changes

- **Font:** Vazirmatn now loads and is used for Persian text on all pages.
- **Typography:** Base font size reduced to 14 px; headings and body text are visibly smaller.
- **Color:** Page backgrounds switched to `#F6F7F9`; warning/info/info banners picked up token tints (`warn-bg`, `accent-soft`, etc.).
- **Chrome:** Sidebar is 256 px wide with an accent left border on the active item; main block has `max-width:1360px`; DB-status card is pinned at the bottom of the sidebar.
- **Icons/emoji:** Unchanged (still the original emoji icons); Material-icon swap is Wave B.
- **No layout breakage:** No clipped tables, no sidebar overlap, no obvious font fallback to Tahoma (Vazirmatn is present).

### Defects filed for later tasks

1. **Screenshot capture timing — open multiselect (inflation):** The script does
   not collapse open dropdowns before capturing. Filed for a future Task 10
   refinement or for Task 24 retake if needed. Non-blocking. — **RESOLVED in
   Step 0b** (see below): the re-run shows the previously expanded
   "شاخص‌ها" multiselect collapsed to a single chip and no open popover.
2. **Extra controls visible below the fold (gdp/labor):** The chart-state
   selector is present in the DOM but becomes visible because the main content
   max-width changed the layout. Not a Wave A defect; confirm it still renders
   correctly after Wave C overview refactor.
3. **Toolbar state in captures:** The after images show "Stop" + "Deploy" (dev
   toolbar) while the baseline shows only "Deploy". This is runtime environment
   noise, not a product regression. No action needed unless automated pixel
   comparison is introduced later. — **RESOLVED in Step 0b** (see below): the
   re-run captures show only "Deploy".

### Gate result

- **Visual regression:** no blocking defects for Wave A.
- **Next work:** Wave A continues with Task 11 (relative-time formatter).
  Wave B (shell: brand, Material icons, active-item style, DB status, top
  bar/breadcrumb) begins at Task 25, **not** Task 11 as previously recorded
  here.

---

## Step 0b — (0) Harden the screenshot script and re-verify captures

- **Files:** `scripts/dashboard_screenshots.py` (committed in `6c1296c`), this
  log entry.
- **Build (committed `6c1296c`):** `wait_ready()` now also waits for
  `[data-testid="stStatusWidget"]` to detach (the "Stop"/running indicator)
  plus a 500 ms settle; `neutralise(page)` presses Escape, moves the mouse to
  the sidebar top and scrolls the main container to the top before every
  capture. File names and the default output directory are unchanged.
- **Verify (this session):** app launched with
  `poetry run streamlit run dashboard/app.py --server.port 8501`; script re-run
  → **10 PNGs** written to
  `docs/phase-7.2/wave-a-assets/after-global-look/` (gitignored).
  - **"Stop" button: GONE.** The re-run captures show only "Deploy" + the kebab
    menu in the toolbar.
  - **Inflation multiselect: GONE (no open dropdown).** A live DOM probe
    (`/tmp/probe_inflation.py`, throwaway) reported
    `visible popovers=0 visible listboxes=0 statusWidget=0` on the inflation
    page. The "شاخص‌ها" multiselect now shows a single collapsed chip; the
    decile multiselect's ten chips are its normal *collapsed* inline wrap, not
    an open menu.
  - `poetry run ruff format --check` / `ruff check` / `mypy` on the script →
    clean (0 errors).
- **Deviations:** none. Defects #1 and #3 of the global-look checkpoint are now
  resolved (annotated above).
- **Commit hash:** `6c1296c` (script); this entry is docs-only.

## Task 11 — (A) ADD the relative-time formatter

- **Files:** `dashboard/formatting.py`, `dashboard/i18n.py`,
  `tests/unit/dashboard/test_formatting.py`.
- **Build:** `relative_time_label(value, *, now, digit_mode="fa")` with explicit
  floor-division boundaries — `< 1 h` → "امروز"; `< 24 h` → `{n} ساعت پیش`;
  `< 30 d` → `{n} روز پیش`; otherwise `{n} ماه پیش` (`days // 30`). A future
  instant clamps to "امروز". `now` is required and no wall-clock call appears
  inside. Naive datetimes are normalised to UTC (the neighbouring helpers'
  convention). Persian digits via `to_persian_digits` honouring `digit_mode`.
  Four i18n keys added: `value.relative_today` / `_hours_ago` / `_days_ago` /
  `_months_ago`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_formatting.py
  tests/unit/dashboard/test_app_overview.py -q --no-cov` → **54 passed**. The
  parametrized boundary test pins 12 cases (0 m, 30 m, 3599 s, 1 h, 5 h, 23 h,
  24 h, 5 d, 29 d, 30 d, 60 d, 365 d) plus a future-clamp and a `latin` digit
  case.
- **Deviations:** the plan mentioned "a week/month granularity"; only the four
  keys listed in the plan were added (no week granularity) — the plan's own key
  list does not include a week key, and the prompt allowed skipping it if
  logged. Months use floor division on `days // 30`.
- **Commit hash:** `dc5f05e`

## Task 12 — (A) ADD the freshness aggregate and stale-first ordering

- **Files:** `dashboard/page_view.py`, `dashboard/i18n.py`,
  `tests/unit/dashboard/test_app_overview.py`, plan checkboxes.
- **Build:** `freshness_summary(frame, *, now) -> tuple[int, int]` counts fresh
  and stale sources by reusing `_staleness_label`, so its verdict matches
  `freshness_display` exactly; a source with no known cadence (`"unknown"`) is
  counted as neither. `freshness_display` now sorts stale rows first with a
  **stable** secondary order (Python's stable sort keeps the original
  `source_freshness()` order within each verdict group). i18n key
  `section.freshness_summary` added. Both functions are pure and `now` is
  required/injectable; no wall-clock call inside.
- **Verify:** `poetry run pytest tests/unit/dashboard -q --no-cov` → **373
  passed** (356 baseline + 14 from Task 11 + 3 new here).
  `poetry run mypy src dashboard` → **0 errors**. The existing
  `test_freshness_display_*` tests were left untouched and still pass. New
  tests: stale-first order with a fresh source first in input order, stable
  secondary order across two stale rows, summary counts (fresh/stale/unknown),
  `now`-sensitivity, and the empty-frame `(0, 0)`.
- **Deviations:** none. The `section.freshness_summary` string is added but not
  yet rendered — its consumer is the Overview refresh (Tasks 30/32), per the
  plan.
- **Commit hash:** `e3f47cf`

## Task 13 — (A) ADD the source calendar map and calendar-aware range formatter

- **Files:** `dashboard/labels.py`, `dashboard/formatting.py`, `dashboard/i18n.py`,
  `tests/unit/dashboard/test_labels.py`, `tests/unit/dashboard/test_formatting.py`,
  plan checkboxes.
- **Source slugs (verified in `labels.py`, not assumed):** `SOURCE_LABELS` holds
  exactly `world_bank`, `imf`, `eia`, `tgju`, `sci`, `tsetmc`, `hbsir` — the
  plan's mapping is correct as written.
- **Build:** `SOURCE_CALENDAR` (`world_bank`/`imf`/`eia` → `"gregorian"`;
  `tgju`/`sci`/`tsetmc`/`hbsir` → `"jalali"`) plus
  `source_calendar(source_name) -> str | None` (``None`` when unmapped, so the
  caller keeps the default). In `formatting.py`, `range_label(start, end, *,
  frequency, calendar="jalali", digit_mode="fa")` joins two period labels with
  :data:`RANGE_SEPARATOR` (`" – "`, en dash, matching the mockup):
  `jalali_period_label` for the Jalali path, `_gregorian_period_label` for the
  Gregorian path. AM-27(e): Gregorian annual → year only (`2023`), every
  sub-annual frequency → year-month (`2023-05`); quarterly is treated as
  sub-annual. i18n key `table.coverage_footnote` added.
- **Golden values (captured before implementing):** `jalali_period_label` on
  annual 1960-12-31/2025-12-31 → `۱۳۳۹`/`۱۴۰۴`; monthly 1982-03-31/2023-01-31 →
  `فروردین ۱۳۶۱`/`بهمن ۱۴۰۱`; daily 2026-09-09/2026-09-11 →
  `۱۸ شهریور ۱۴۰۵`/`۲۰ شهریور ۱۴۰۵`. `range_label(..., calendar="jalali")` (the
  default) is asserted to reproduce `۱۳۳۹ – ۱۴۰۴`, `فروردین ۱۳۶۱ – بهمن ۱۴۰۱`,
  `۱۸ شهریور ۱۴۰۵ – ۲۰ شهریور ۱۴۰۵` byte-for-byte, and separately to equal the
  `jalali_period_label` composition. The monthly golden value matches the
  mockup's SCI coverage row exactly.
- **Bidi decision:** the Gregorian year-month form is LTR-ordered data embedded
  in RTL text; two tokens separated by a neutral en dash can visually swap
  start/end under the RTL paragraph direction. Decision: the caller must isolate
  the range in an LTR span (`dir="ltr"` / `<bdi>`) — recorded in the
  `range_label` docstring and to be applied at the Task 32 call site.
- **Verify:** `poetry run pytest tests/unit/dashboard -q --no-cov` → **385
  passed** (373 + 12 new). `poetry run mypy src dashboard` → **0 errors**.
  `ruff format` / `ruff check` on the touched files → clean.
- **Deviations:** (1) the mockup *compacts* a daily range that shares a month
  (`۱۸ – ۲۰ شهریور ۱۴۰۵`); `range_label` does not — it emits the two full period
  labels (`۱۸ شهریور ۱۴۰۵ – ۲۰ شهریور ۱۴۰۵`). The plan's acceptance only requires
  byte-for-byte reproduction of the existing Jalali output, so compaction is left
  out of scope. (2) quarterly Gregorian → year-month is a decision, not a plan
  requirement (the plan names only annual/monthly/daily).
- **Commit hash:** `9b5e7ad`

## Task 14 — (A) REBUILD the Plotly template from the tokens

- **Files:** `dashboard/components/tokens.py`, `dashboard/components/direction.py`,
  `tests/unit/dashboard/test_tokens.py`, `tests/unit/dashboard/test_direction.py`,
  `tests/unit/dashboard/test_charts.py`, `tests/unit/dashboard/test_exports.py`,
  plan checkboxes.
- **Export engine (verified, plan wording correct):** the export path is
  **Kaleido v1**, not Playwright. `dashboard/components/exports.py` imports
  `from kaleido import Kaleido` and calls `Kaleido(path=find_chromium_executable())`
  → `await renderer.open()` → `renderer.calc_fig(...)`. Playwright is only the
  *source of the Chromium binary* (`find_chromium_executable()` scans
  `~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome`, then system Chrome).
  On this machine it resolves to `/usr/bin/google-chrome` and a real PNG+SVG
  render succeeds.
- **Build:** `tokens.py` gains `CHART_CATEGORICAL_COLOR_TOKENS` (the token names,
  in order) and `CHART_CATEGORICAL_COLORS` (derived from `TOKENS`, so no literal
  colour is introduced). The palette's single source is the token map;
  `.streamlit/config.toml`'s `chartCategoricalColors` is now asserted equal to it,
  order included. `plotly_template()` gains `layout.colorway` (the token
  palette), token grid/border colours (`gridcolor`=`border`,
  `linecolor`/`zerolinecolor`=`border-strong`) and RTL-friendly legend/title
  placement (legend horizontal at the top, right-aligned; title right-aligned).
  Sizing and margins stay with the builders.
- **RTL decision:** legend and title are aligned for RTL reading, but the **time
  axis is not reversed** — time flows left to right on the LTR plot canvas (the
  grid stays LTR, per AGENTS.md). Recorded in the `plotly_template` docstring and
  asserted in the contract test (`xaxis.autorange is None`).
- **Test revision:** `test_plotly_template_is_typography_only` was **split** into
  `test_plotly_template_typography` (focused typography) and
  `test_plotly_template_is_typography_palette_and_layout_only` (palette + grid +
  legend/title placement present; sizing and all four margins still absent).
  `test_charts.py` gained a per-builder token-palette assertion.
- **AM-25 smoke and how it is run:** `test_kaleido_renders_png_and_svg_with_the_new_template`
  renders a real PNG+SVG of a figure built with the new template. It needs a
  Chromium executable, so it is marked `@pytest.mark.integration` and is
  **deselected by `make check`** (`pytest -m "not integration"`). Run it
  explicitly: `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov`
  → **1 passed** (PNG starts with the PNG magic bytes, SVG with `<svg`).
- **Visual check (before/after, real charts):** captured the first Plotly chart
  on `inflation` (small multiples, 10 series) and `gdp` (single series) with the
  **old** template (reverted `direction.py` to `HEAD`, then restored) and the new
  one. Findings:
  - **Legend placement changed as intended:** inflation's legend moved from a
    vertical stack down the right edge (old) to a horizontal right-aligned band
    above the plot (new); gdp's single-entry legend stays top-right. No legend
    overlap with the plot area or panel titles.
  - **Panel/title alignment:** the small-multiples panel titles are now
    right-aligned (RTL) instead of left-aligned.
  - **Palette:** the trace colours are **identical before and after** in the
    browser. Reason: Streamlit injects the theme's `chartCategoricalColors`
    (set in Task 8) into every Plotly chart client-side, so the browser already
    used the token palette. The template `colorway` therefore matters for the
    **server-side/export** path (Kaleido renders with the figure's own template);
    it is asserted in tests and exercised by the AM-25 smoke.
  - **No defects found:** Persian glyphs render in Vazirmatn, axis titles/ticks
    are readable, grid lines are the token border colour. The rotated bottom
    Jalali tick labels are dense on the 10-series inflation chart — a
    pre-existing density artifact, identical before and after, not introduced
    here.
- **Verify:** `poetry run pytest tests/unit/dashboard -q --no-cov` → **389 passed**
  (385 + 4 new). `poetry run mypy src dashboard` → **0 errors**. `ruff format` /
  `ruff check` on the touched files → clean.
- **Deviations:** none material. The `chartCategoricalColors` palette lives in
  `.streamlit/config.toml` (Task 8), not in `tokens.py` as the prompt assumed;
  `tokens.py` now derives the same palette from token names and a test pins the
  two equal, so there is still exactly one colour source.
- **Commit hash:** `8b2e6ee`

## Task 15 — (A) ADD the escaping helper and the RTL HTML table with the typed cell model

- **Files:** `dashboard/components/escaping.py` (new),
  `dashboard/components/html_table.py` (new), `dashboard/components/direction.py`
  (table CSS owner), `tests/unit/dashboard/test_escaping.py` (new),
  `tests/unit/dashboard/test_html_table.py` (new), plan checkboxes + a Task 32
  acceptance line.
- **Build:** `escape_html(value)` escapes `&`, `<`, `>`, `"` and `'` in one pass
  and coerces with `str`, so it is safe in **both** text and quoted-attribute
  contexts (escaping quotes in text is redundant but harmless). The typed cell
  model is `Text`, `Ltr`, `UnitChip`, `StatusChip`, `Dot`, `TwoLine` (the union
  is `Cell`); `TwoLine.secondary_parts` is a tuple of the text-like variants, so
  a name can carry a mono `Ltr` id beneath it. `build_html_table` is the pure
  builder; `render_html_table` wraps it in `st.html`. Markup is semantic
  (`<table>`, `<th scope="col">`) inside `<div class="dt-wrap" dir="rtl">`.
  `tone` is validated against the closed set `{ok, warn, err, accent, neutral}`
  and `density` against `{comfortable, compact}`; an unknown value **raises**, so
  neither can be interpolated into a class name. `title` tooltips are escaped.
  No `<svg>`.
- **CSS ownership:** the table/chip/dot/two-line CSS is emitted **once** by
  `direction_css()` (`_TABLE_RULES`, after the chrome block) — not a `<style>` per
  table. Values mirror the mockup's `.dt`/`.chip`/`.dot`/`.unit`/`.ltr`/`.tm`
  rules and read the design tokens; the wrapper carries `overflow-x: auto` and the
  `.dt .ltr`/`.unit` cells carry `max-width` + ellipsis. Tone classes are
  `tone-*` (prefixed to avoid colliding with the mockup's generic `.ok`/`.warn`).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_html_table.py
  tests/unit/dashboard/test_escaping.py -q --no-cov` → **35 passed**.
  `poetry run pytest tests/unit/dashboard -q --no-cov` → **424 passed**
  (389 + 35). `poetry run mypy src dashboard` → **0 errors**. `ruff format` /
  `ruff check` on the touched files → clean.
- **Visual check (throwaway probe, `/tmp/phase72-probe-table/`, not added to the
  repo):** a probe app imports the real component + `inject_direction_css()` and
  renders a freshness-like table (dots, status chips, two-line date + time · age)
  and a coverage-like table (LTR ids, unit chips, em-dashes) in both densities.
  Screenshotted at **1440 / 1280 / 1024 px** and compared with
  `docs/design/phase-7.2/overview-redesign-mockup.png`: header background, row
  borders, hover, tone dots/chips, unit chips, the two-line name + mono id and the
  em-dash all match. **AM-26 measured in the DOM:** at 1440/1280 px no wrapper
  scrolls and `document.scrollWidth == clientWidth`; at **1024 px** the two
  coverage tables scroll **inside** their wrapper (`scrollWidth 981 > clientWidth
  882`) while `document.scrollWidth == clientWidth == 1024` — the table scrolls in
  its own box and the page never scrolls sideways.
- **Deviations:** (1) the plan's last acceptance item (manual check on the real
  Overview coverage table) cannot be satisfied until Task 32 renders it; it is
  ticked **"verified on probe"** and a matching acceptance line was added to Task
  32. (2) The mockup's `.dt.cov` header-wrapping variant is not implemented — the
  plan specifies only the comfortable/compact density class; Task 32 can add a
  wrapping variant if the real coverage headers need it. (3) `TwoLine`'s
  `secondary_parts` is typed as a tuple of text-like **cells** (not raw strings),
  which is what lets the coverage id render as an isolated mono `Ltr`; the plan
  left the element type open.
- **Commit hash:** `f501078`

## Task 16 — (A) ADD the AppTest HTML-text helper and record the test-migration map

- **Files:** `tests/unit/dashboard/app_smoke.py` (helper),
  `tests/unit/dashboard/test_html_text_helper.py` (new), plan migration map
  (corrected), plan checkboxes.
- **Build:** `html_texts(app) -> list[str]` reads
  `app.get("html")[i].proto.body` for every ``st.html`` element in render order.
  `AppTest` has no typed accessor for ``st.html``, so this is the only way to
  assert on the markup a migrated table renders. No suite was rewritten here (per
  the plan, the rewrites live in Tasks 30, 32, 35, 39).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_html_text_helper.py -q
  --no-cov` → **2 passed** (a minimal `st.html` probe app returns both bodies in
  order; a page with no `st.html` returns `[]`).
- **Migration map verified by grep and corrected (3 rows drifted):**
  - `test_app_economy.py` — the map claimed an `app.dataframe` **quality**
    assertion; the file has only the **observations** grid
    (`table.timestamp`, line 90). Row removed; the observations row already
    covers it. The Inflation chain-linking claim is accurate
    (`test_app_economy.py:253-255` asserts `app.subheader`/`app.caption`).
  - `test_app_trade_welfare.py` and `test_app_fx_gold.py` — the map claimed
    `app.dataframe` **quality** assertions; both files contain a single smoke test
    asserting `not app.exception` and **no** `app.dataframe`. Rows corrected to
    "none".
  - `test_derived_series.py` — the map listed only the **observations** grid; the
    file also asserts the **quality** table via `_quality_frame` (lines 230/243),
    which will migrate to `st.html` in Task 35. A rewrite row was added.
  - All other rows were confirmed accurate (the authoritative quality-table
    marker is the `table.rows_returned` column; only `test_app_labor.py` and
    `test_derived_series.py` assert it).
- **Deviations:** none beyond the map corrections above (the plan explicitly asks
  for drift to be fixed here).
- **Commit hash:** `37e26f4`

## Step 0 (A-3) — EXTEND the Task 30/32 acceptance lines before starting Tasks 17–24

- **Files:** `docs/plans/phase-7.2-dashboard-redesign.md` (Task 30 + Task 32
  acceptance only), `docs/phase-7.2/execution-log.md`.
- **Build:** Docs-only, no code. Two acceptance additions so later Wave-C work is
  pinned to decisions already taken in Wave A:
  - **Task 30** — the `section.freshness_summary` string (Task 12) is rendered as
    the `trailing` text of the freshness section header via `render_section_header`
    (Task 21).
  - **Task 32** — (a) an opt-in `compact` argument to `range_label` (default
    unchanged so the golden Jalali tests keep passing) collapsing a
    same-month/same-year daily range to the mockup's `۱۸ – ۲۰ شهریور ۱۴۰۵`, with
    tests; (b) an opt-in `wrap_headers` option for `render_html_table` matching the
    mockup's two-line coverage headers, with a test; (c) Gregorian ranges render in
    an `Ltr` cell and Jalali ranges in a `Text` cell (the Task 13 bidi decision).
- **Verify:** `git diff --stat` shows only the two docs; no checkbox in Tasks
  1–16 changed. No test run needed (no code touched).
- **Deviations:** none.
- **Commit hash:** `d06f4cd`

## Task 17 — (A) ADD the callout component (native, D13)

- **Files:** `dashboard/components/layout.py` (new),
  `dashboard/components/direction.py` (component-hook CSS block + `CSS_SELECTORS`
  entry), `dashboard/i18n.py` (`note.*` + `state.*` namespace prefixes,
  `note.methodology_label`), `tests/unit/dashboard/test_layout.py` (new),
  plan checkboxes.
- **Build:** `render_callout(key, *, tone="warn", label_key=None,
  container_key=None)` maps the tone to a native `st.warning`/`st.info`/
  `st.error` through a closed `CALLOUT_TONES` set (an unknown tone raises, so a
  tone can never reach a class attribute). The optional label is rendered as a
  markdown-bold prefix inside the body (`**label** body`), which needs no HTML and
  no escaping. `container_key` is a **documented addition to the plan signature**:
  the keyed container is the CSS hook and Streamlit raises on a repeated container
  key, so a callout whose body key legitimately renders twice in one run (two
  Overview-style sections both showing `empty.no_observations`) needs a
  disambiguator.
- **Hook pattern verified in the live DOM (Streamlit 1.61.1).** A throwaway probe
  (`/tmp/phase72-probe-layout/`, not added to the repo) rendered the real component
  with the real `inject_direction_css()` and read the DOM back with Playwright:
  - `st.container(key="callout-warn.forecasts_indistinguishable")` →
    `class="stVerticalBlock st-key-callout-warn-forecasts_indistinguishable …"`.
    **Streamlit sanitizes the key into a CSS identifier** (`.` → `-`, `_` kept), so
    the attribute-substring selector `[class*="st-key-callout-"]` is valid and the
    hook is stable. Recorded in `design-system.md`.
  - Stable native alert hooks: `[data-testid="stAlert"]`,
    `[data-testid="stAlertContainer"]` (carries `role="alert"` and the tint),
    `[data-testid="stAlertContentWarning"|"stAlertContentInfo"|"stAlertContentError"]`.
  - **The native alert ships no icon element** (no `<svg>`, no icon testid), so the
    mockup's inline SVG is drawn in CSS as a ring with the "i" dot and stem
    (background layers on `::before`). Verified computed: bar `3px solid` in the
    tone colour (`#9A5B00`/`#1D4E89`/`#B42318`), radius `6px`, glyph `15×15`,
    bold label `font-weight: 600`, no page exception.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_layout.py -q --no-cov` →
    **8 passed**.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **434 passed**
    (426 + 8).
  - `poetry run mypy src dashboard` → **0 errors** (67 source files).
  - `ruff format` / `ruff check` on the touched files → clean (en dashes replaced
    with hyphens in the new comments/strings; RUF001/2/3).
- **Deviations:** (1) `container_key` added to the plan signature (reason above).
  (2) The callout CSS is scoped to the keyed container rather than applied to
  `[data-testid="stAlertContainer"]` globally, so the sidebar DB-status
  `st.success`/`st.error` banner keeps its native look until Wave B rebuilds the
  sidebar (Task 27). (3) The icon is a CSS-drawn glyph, not the mockup's SVG
  (SVG is stripped by `st.html`, wave-0-spike §6).
- **Finding for Task 33:** `tests/unit/dashboard/test_app_overview.py:79` asserts
  `t("warn.forecasts_indistinguishable") in [warning.value for warning in app.warning]`
  — an **exact** match. Once Task 33 routes the Overview's first warning through
  `render_callout(..., label_key="note.methodology_label")` the value becomes
  `"**یادداشت روش‌شناسی** <body>"`, so that assertion must switch to a
  `t("note.methodology_label") in value` / substring check. Recorded here, not
  changed in this wave.
- **Commit hash:** `924bfa3`

## Task 18 — (A) ADD the page-header component (native, D13, AM-22)

- **Files:** `dashboard/components/layout.py`, `tests/unit/dashboard/test_layout.py`,
  plan checkboxes.
- **Build:** `render_page_header(title_key, *, callout_key=None, tone="warn")` calls
  native `st.title(t(title_key))` and, when `callout_key` is given, delegates to
  `render_callout(callout_key, tone=tone)` (Task 17). The tone is validated lazily
  — only when a callout is actually rendered — so a page without a callout is not
  coupled to the callout tone set. This is the single header shape the D11 contract
  and the Task 33 guard expect every migrated page to use.
- **Hook pattern:** **no keyed container and no new CSS.** `st.title` already takes
  the theme's heading font/size and the callout brings its own hook, so the header
  has nothing to scope; adding a `st-key-page-header-*` class with no rule would
  only satisfy the letter of the pattern while `test_every_declared_selector_is_styled`
  forced a meaningless declaration. Recorded in `design-system.md` as the rule:
  *a component gets a keyed container only when it has scoped CSS to hang off it.*
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_layout.py -q --no-cov` →
    **12 passed** (8 + 4).
  - `poetry run mypy src dashboard` → **0 errors**.
  - `ruff format` / `ruff check` on the touched files → clean.
- **Deviations:** none to production. The "every component has a keyed container"
  pattern is applied where scoped CSS exists (the callout), not mechanically.
- **Commit hash:** `22739b9`

## Task 19 — (A) ADD the KPI band component

- **Files:** `dashboard/components/layout.py`, `dashboard/components/direction.py`
  (KPI hook selectors + rules), `dashboard/i18n.py` (four `metric.*` keys),
  `tests/unit/dashboard/test_layout.py`, `pyproject.toml` (one
  `per-file-ignores` line for Persian digits in the new test file, matching the
  existing dashboard test-file convention), plan checkboxes.
- **Build:** `render_kpi_band(cells, *, key="default")` renders one
  `st.container(border=True)` holding **one** `st.columns(len(cells))` row (so the
  cells line up as a single strip, as in the mockup), one `st.metric` per column
  with `help=` from `help_key`, and an optional `st.badge` tag. Cells are
  `KpiCell(label_key, value, help_key=None, tone="default", secondary=False,
  tag_key=None)` — a `NamedTuple` rather than the plan's bare 4-tuple, because the
  user's brief adds the `secondary` flag and the `st.badge` tag to the same cell
  spec; named fields keep the call sites readable. Value formatting stays with the
  caller.
  - **Secondary group separation** is a `:has()` rule on the band's columns:
    `[class*="st-key-kpi-band-"] [data-testid="stColumn"] + [data-testid="stColumn"]`
    draws the normal separator and
    `… [data-testid="stColumn"]:has([class*="st-key-kpi-"][class*="-secondary-0-tone-"])`
    upgrades it to `--border-strong` at the group boundary. The two rules have equal
    specificity, so the `:has()` rule is emitted **after** the `+` rule. `:has()` is
    a CSS feature, not a Streamlit API, so the 1.44 floor (D9/AM-13) is unchanged;
    `CSS.supports('selector(:has(*))')` is **true** in the app's Chromium.
  - The cell key is `kpi-<band key>-<group>-<index>-tone-<tone>`, so the tone is
    addressable (`[class*="-tone-warn"] [data-testid="stMetricValue"]`) and two
    bands can coexist on one page without a duplicate key. The CSS anchors on the
    fixed suffix, so the band key in the middle does not affect it.
- **Tone sizing / theme:** the band sets **no font-size literal**. The metric value
  size comes from the theme as it stands; per the plan's `Files:` field neither
  Task 19 nor 21 may edit `.streamlit/config.toml`, so `metricValueFontSize` /
  `headingFontSizes` remain the theme's own defaults (31.5 px value / 24.5 px
  subheader) rather than the mockup's 28 px / 18 px. Flagged for Task 29/34: if the
  owner wants the mockup's exact scale it is a **theme-layer** change, not a
  component change. Recorded in `design-system.md`.
- **Hook pattern verified in the live DOM (Streamlit 1.61.1).** Throwaway probe,
  real component + real `inject_direction_css()`:
  - **one** `stHorizontalBlock` inside the band → a single row (6 columns);
  - band computed `border-radius: 8px` (`--radius-lg`), `padding: 0`, theme border;
  - columns 2–6 `border-inline-start: 1px solid rgb(225,229,235)` (`--border`) and
    column 5 (the first secondary cell) `1px solid rgb(201,208,218)`
    (`--border-strong`) — the `:has()` boundary applies exactly once;
  - primary metric values `rgb(27,36,48)` (`--text-1`), secondary `rgb(74,85,102)`
    (`--text-2`, the `muted` tone);
  - cell classes: `st-key-kpi-overview-primary-0-tone-default` … and
    `st-key-kpi-overview-secondary-0-tone-muted`;
  - the `st.badge` renders as `.stMarkdownBadge` with the warn background beneath
    the metric; no page exception.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_layout.py -q --no-cov` →
    **21 passed** (12 + 9).
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **447 passed**.
  - `poetry run mypy src dashboard` → **0 errors**; `ruff check` clean.
- **Deviations:** (1) the cell spec is a 6-field `NamedTuple`, not the plan's
  4-tuple (reason above). (2) The tag is a real `st.badge` **beneath** the metric,
  per the brief, rather than the mockup's inline tag beside the label; the
  `:orange-badge[…]` markdown shorthand would leak its own syntax into the metric
  label and the tooltip's accessible name. Task 29/34 may revisit the placement.
  (3) The band's own `key` argument and the `:has()`-based boundary are additions
  the plan did not specify (the plan's signature is `render_kpi_band(cells)`).
  (4) The mockup's exact metric/subheader type scale is **not** applied (theme-layer
  change, out of this task's file scope).
- **Commit hash:** `PENDING`
