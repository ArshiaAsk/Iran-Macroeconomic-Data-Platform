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
- **Commit hash:** `56a2564`

## Task 20 — (A) ADD the chip, status-dot and bar-list components

- **Files:** `dashboard/components/layout.py`, `dashboard/components/direction.py`
  (component-hook CSS block + `CSS_SELECTORS`), `dashboard/i18n.py`
  (`value.status_*`, `section.indicators_by_domain_total`),
  `tests/unit/dashboard/test_layout.py`, `tests/unit/dashboard/test_connection.py`
  (test-isolation fix, see deviations), plan checkboxes.
- **Build:** `render_status_chip(status)` maps the `src.etl.bronze` `STATUS_*` slugs
  to token tones through the **total** `STATUS_CHIPS` map plus a
  `STATUS_CHIP_FALLBACK` (`value.status_unknown`, gray) — a new source status must
  not blank a page, so an unrecognised slug renders the unknown chip instead of
  raising. `render_status_dot(label, tone)` is one escaped `st.html` fragment that
  reuses the Task 15 `.dot`/`.tone-*` rules (global class selectors, so no second
  copy of the CSS). `render_bar_list(rows, total_label, *, key="default")` renders a
  keyed bordered panel: each row is a native `st.columns([5, 12, 1])` trio whose
  label is a native `st.page_link` for an owned domain (`page_for_domain`) or plain
  text for an unowned one, whose middle column is the escaped bar fragment, and
  whose value column is the formatted count; the footer is one escaped
  `st.html` line. Only the bar and the footer are HTML — `st.page_link` cannot live
  inside `st.html`. Counts only, so no unit is ever mixed on one scale.
- **Live-DOM verification (Streamlit 1.61.1).** A throwaway Playwright probe
  (`/tmp/phase72-probe-layout/`, not added to the repo) rendered the real components
  with the real `inject_direction_css()` and read the geometry back. It surfaced a
  **defect that affected Tasks 17, 19 and 20 alike**:
  - **Before the fix, every shared-component container was `dir: ltr`** (Streamlit's
    main block is LTR). Measured: the callout's `border-inline-start` resolved to a
    3 px **left** border with the `::before` glyph at the left; the KPI band's first
    cell (`منابع`) rendered **leftmost** at x = 327 and its last cell at x = 1369, so
    the six cells were mirrored against the mockup's right-to-left order; the bar
    list's label column sat at x = 340 (left) with the count at x = 1309 (right), the
    footer put `جمع` at the left and the total at the right, and the bar fill was
    anchored to the **left** (`fill.left == rail.left`, `anchoredRight: false`),
    growing left-to-right.
  - **Fix:** each component container now declares `direction: rtl` — the callout on
    `[data-testid="stAlertContainer"]`, the KPI band and the bar list on their keyed
    containers, and the `.bar-rail` as well so the fragment is self-anchoring. This
    is the same self-contained-RTL-context rule the Task 15 table already follows
    with `dir="rtl"` on its wrapper, and it mirrors the mockup's
    `body{direction:rtl}`. A **global** main-block flip was deliberately **not** used:
    it is not scheduled in this plan and would reorder every un-migrated page's
    columns.
  - **After:** callout `borderRight: 3px rgb(154,91,0)`, `borderLeft: 0px`; KPI band
    `dir rtl` with the first cell at x = 1207–1369 (rightmost) and the last at
    x = 327–489 (leftmost), separators on `borderRight`, and the secondary-group
    boundary still applied exactly once at `1px rgb(201,208,218)` (`--border-strong`);
    bar list `dir rtl` with the label column at 1083–1356 (right), the rail at
    401–1069 (middle) and the count at 340–387 (left), footer `جمع` at 1331–1356
    (right) and the total at 340–356 (left); **every fill right-anchored**
    (`fill.right == rail.right`, `anchoredRight: true`) for the 100 % / 53.3 % /
    26.7 % / 0 % rows; no page exception. The keyed-container hook is re-confirmed
    (`st-key-bar-list-overview` on the panel's `stVerticalBlock`).
  - `render_status_dot` now emits a `dir="rtl"` block wrapper, so the inline-level
    `.dot` anchors to the right edge (measured 1328–1370, the page's right edge)
    instead of drifting to the host block's LTR start.
  - **Recorded limitation (carried to Task 23):** `render_status_chip` uses native
    `st.badge`, which Streamlit renders inside a shrink-to-fit element at the host
    block's inline start; at the main-block top level that is the **left** (measured
    `موفق` at x = 327). Its planned home is an RTL context — the Task 27 sidebar
    already declares `direction: rtl` — and Task 30 uses the Task 15 in-table
    `StatusChip` cell, so no planned usage is affected. If a page ever needs a
    top-level standalone chip, the remedy is the documented hook pattern: wrap it in
    a keyed container whose rule declares `direction: rtl`.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_layout.py -q --no-cov` →
    **32 passed** (21 + 11).
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **458 passed** (447 + 11),
    no regressions against Task 19.
  - `poetry run mypy src dashboard` → **0 errors**; `ruff check` / `ruff format`
    clean.
- **Deviations:** (1) the `direction: rtl` declarations were applied to the **Task 17
  callout and Task 19 KPI-band CSS as well**, not only to Task 20's own rules: the
  probe showed all three components were mirrored to the left of the mockup, so the
  correction is one declaration per component rather than a Task 20-only patch.
  (2) `render_status_dot`'s fragment gained a `dir="rtl"` wrapper (the plan's
  signature is unchanged). (3) `tests/unit/dashboard/test_connection.py` gained a
  module-scoped autouse fixture that clears the `st.cache_resource` `get_connection`
  cache before and after each test — **not** in the plan's Task 20 file list. That
  module populates the process-wide cache with a `FakeDatabaseConnection`, and
  `monkeypatch` undoes the attribute patches but **not** the cache entry, so any later
  test that runs the real `dashboard/app.py` failed with
  `'FakeDatabaseConnection' object has no attribute 'test_connection'`. The Task 20
  owner-link test is the first test in the suite to run the real entrypoint, which is
  why a pre-existing isolation bug surfaced now (reproduced with
  `pytest tests/unit/dashboard/test_connection.py tests/unit/dashboard/test_layout.py::test_bar_list_keeps_the_owner_link_a_native_page_link`).
  It is fixed at the source rather than worked around in the new test.
  (4) `BarRow`'s second field is `indicator_count`, not the plan's `count`: `count`
  shadows `tuple.count` under mypy strict.
- **Finding for Tasks 21/22/23:** Tasks 21 (section header, filter bar) and 22
  (states) must declare `direction: rtl` on their own containers or they will mirror
  the same way; Task 23's component catalogue should state the rule once.
- **Commit hash:** `496b4ce`

## Task 21 — (A) ADD the section header and filter bar components

- **Files:** `dashboard/components/layout.py`, `dashboard/components/direction.py`
  (component-hook CSS block + `CSS_SELECTORS`), `dashboard/i18n.py`
  (`filter.all`, `filter.showing_rows`, `filter.density`, `filter.density_comfortable`,
  `filter.density_compact`), `tests/unit/dashboard/test_layout.py`, plan checkboxes.
- **Build:** `render_section_header(title_key, *, subtitle=None, trailing=None, key=None)`
  renders a native `st.subheader` plus optional already-resolved secondary text.
  `render_filter_bar(controls, *, trailing=(), key="default")` lays out one row of
  zero-argument control callables (the leading group, then the mockup's `.grow`
  spacer, then `trailing`) with `st.columns(..., vertical_alignment="center")`; it
  raises on an empty bar.
- **Design notes.**
  - **The title is grouped.** The row override makes the header container a
    `space-between` row, so the title and its subtitle share a
    `section-title-<suffix>` container and the trailing text is the row's other
    child; otherwise the subtitle would be spread into the middle of the row. That
    grouping container has no CSS of its own and therefore no `CSS_SELECTORS` entry
    (`test_direction.py::test_every_declared_selector_is_styled` enforces that every
    registry entry is styled).
  - **`key` defaults to `title_key`**, not to `"default"`: a page legitimately
    renders several section headers, so a fixed default key would raise on the
    second one. This is a documented addition to the plan's signature (the plan
    lists `subtitle`/`trailing` only); the plan's call form is unaffected.
- **Live-DOM verification (Streamlit 1.61.1).** A throwaway Playwright probe
  (`/tmp/phase72-probe-layout/probe_task21.py`, not added to the repo) rendered the
  real components with the real `inject_direction_css()`:
  - Section header container computed `direction: rtl; display: flex;
    flex-direction: row; justify-content: space-between; align-items: baseline`; the
    title child sits at x = 855–1370 (RTL start) and the trailing child at
    x = 326–841 (far end) — the mockup's `.sec-h`. A header with no secondary text
    spans the full 326–1370.
  - Secondary text computed `font-size: 12.5px`, `color: rgb(102,115,133)`
    (`--text-3`) — the mockup's `.sec-h .sub`.
  - **Finding (fixed in this task):** the first cut scoped that rule to the *title*
    container, which also matched the subheader's own markdown container and
    recoloured the heading. `st.subheader` renders `stHeading` **and** a
    `stMarkdownContainer`, so the secondary type needs its own container
    (`section-subtitle-<suffix>`). Re-measured: the heading is `H3` at `24.5px` in
    `rgb(27,36,48)` (`--text-1`), unchanged by the component CSS; the page `H1` is
    `38.5px`.
  - Filter bar: container `direction: rtl`; with three selects plus the trailing
    group the six columns sit at x = 1233–1370 (`حوزه`, rightmost), 1081–1219,
    930–1067, 629–916 (the spacer, 287 px), 477–615 (`نمایش ۸ ردیف`) and 326–463
    (`چگالی`, leftmost) — the mockup's `.tb` with its `.grow`. A bar with one control
    and no trailing group spans the full width and gets no spacer.
  - **`vertical_alignment="center"` verified to work** (it does **not** set
    `align-items` on the row; Streamlit makes the short column fit-content and
    centres it): in the bar the 62 px row holds the 27 px row-count column at
    y = 379 and the 55 px density column at y = 365, both centred; an isolated probe
    confirmed the same behaviour for a plain `st.columns(2, vertical_alignment="center")`
    against an unaligned control row.
  - **Selector inventory addition:** `st.segmented_control` renders as
    `[data-testid="stButtonGroup"]` (there is no `stSegmentedControl` testid). The
    filter bar does not need it — the density toggle is a control callable, not
    styled chrome — but the hook is recorded for the Task 23 design-system doc.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_layout.py -q --no-cov` →
    **46 passed** (32 + 14).
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **472 passed** (458 + 14),
    no regressions against Task 20.
  - `poetry run mypy src dashboard` → **0 errors**; `ruff check` / `ruff format`
    clean.
- **Deviations:** (1) `render_section_header` gains an optional `key` (reason above);
  the plan's signature has none. (2) The plan's acceptance says the section header
  uses "the token type scale" — read as: the heading keeps the theme's scale (no
  competing scale is introduced) and only the *secondary* text gets a component
  value (`12.5px`/`--text-3`, the mockup's `.sub`). `tokens.py` holds no type-scale
  tokens, so no token could be referenced; this matches the Task 19 deviation about
  the theme-owned type scale. (3) `render_filter_bar`'s spacer weight is a module
  constant (`2.0`) rather than a mockup value: the mockup's `.grow` is `flex: 1`
  over fixed-width controls, which `st.columns` proportions cannot express exactly.
- **Commit hash:** `f55efaf`

## Task 22 — (A) ADD shared empty / error / loading states

- **Files:** `dashboard/components/states.py` (new),
  `dashboard/components/layout.py` (`render_callout` gains `detail`),
  `dashboard/i18n.py` (`state.loading`, `state.error`, `state.retry_hint`),
  `tests/unit/dashboard/test_states.py` (new), plan checkboxes.
- **Build:** `render_empty(key)` renders the shared empty state for any existing
  `empty.*` key; `render_error(key, *, detail=None)` renders the error message, the
  retry hint and an optional extra paragraph; `render_loading()` renders the
  loading placeholder. All three route through
  `render_callout` (Task 17), so they inherit the native alert element, the
  keyed-container CSS hook and its tone tint, and no state owns any CSS. The tone
  is fixed **by the state** — empty/loading are informational, error is an error —
  so no caller can render a failed load in the informational tone.
- **`render_callout` gained one optional parameter**, `detail`: an
  **already-resolved** paragraph appended to the body after a blank line. The
  callout body is markdown (which is how Task 17's bold `label_key` prefix works),
  so a second paragraph is the natural way to carry the retry hint and a technical
  detail without a second alert or a second copy of the component. It is not an
  escaping surface: `st.error`/`st.info`/`st.warning` render markdown with
  `unsafe_allow_html` off, so HTML in `detail` is never interpreted; the docstring
  asks callers to keep it to plain text.
- **Live-DOM verification (Streamlit 1.61.1).** A throwaway Playwright probe
  (`/tmp/phase72-probe-layout/probe_task22.py`, not added to the repo) rendered all
  three states with the real `inject_direction_css()`:
  - empty → `st-key-callout-empty-no_observations`, `stAlertContentInfo`,
    `direction: rtl`, `border-inline-start` resolved to a 3 px **right** border in
    `rgb(29,78,137)` (`--accent`), background `rgb(232,239,248)` (`--accent-soft`),
    glyph 15×15, full width 326–1370;
  - loading → `st-key-callout-state-loading`, `stAlertContentInfo`, same styling;
  - error → `st-key-callout-state-error`, `stAlertContentError`, 3 px right border
    in `rgb(180,35,24)` (`--err`), background `rgb(253,236,234)` (`--err-bg`), body
    `خطا در بارگذاری داده.` / `برای تلاش دوباره صفحه را بازخوانی کنید.` /
    `relation gold_analytical does not exist` on three lines;
  - no page exception.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_states.py -q --no-cov` →
    **9 passed**.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **481 passed** (472 + 9),
    no regressions against Task 21.
  - `poetry run mypy src dashboard` → **0 errors** (68 source files);
    `ruff check` / `ruff format` clean.
- **Deviations:** (1) `render_callout` gains `detail` (reason above); the plan's
  Task 17 signature had none. (2) The states take no `container_key`: the plan's
  signatures are `render_empty(key)`/`render_error(key, *, detail=None)`/
  `render_loading()`, and the callout's key already derives from the body key. The
  consequence — one state key must not render twice in a single run — is documented
  in the module docstring and pinned by a test; the escape hatch is
  `render_callout(..., container_key=…)`. (3) `render_loading()` renders a native
  `st.info`, not `st.spinner`: the plan routes states through the callout and the
  acceptance requires `app.info`, and a spinner is invisible to `AppTest`.
- **Commit hash:** `a38ce18`

## Task 23 — (A) WRITE the design-system document (first draft)

- **Files:** `docs/phase-7.2/design-system.md` (new),
  `tests/unit/dashboard/test_design_system_doc.py` (new), plan checkboxes.
- **Build:** Fifteen sections: the native→CSS→`st.html` layering (D6/D13); the
  token table plus the three consumers (theme / `:root` / Plotly template); the
  theme mapping; the component catalogue (every `render_*`/`build_*` with signature
  and purpose, a worked example, and the contract details that are easy to get
  wrong — closed tone sets, catalog-key vs already-resolved arguments, container-key
  collisions); CSS ownership and the keyed-container hook including the
  **`direction: rtl`-per-container rule** with its measured consequences; the
  Streamlit-chrome selectors split into STABLE and FRAGILE with the version named;
  the `st.html` survival table with an alternative per stripped feature; the D1
  table classification and the six typed cells; the D3 calendar rule and the D14
  theme lock; charts and the Kaleido-v1 export engine; the testing rules; the D11
  layout contract; do/don't; accepted deviations; open items.
- **The document is guarded, not just written.** `test_design_system_doc.py` scans
  `dashboard/components/*.py` with an AST and fails when a public `render_*` or
  `build_*` is absent from the document, asserts the page-header component is named,
  asserts all six typed cells are listed, pins the seven required section headings,
  re-states the D11 whitelist (the four shared-component modules and the five
  shared layout components) against the decision text, and resolves every relative
  markdown link. The guard is itself tested: an empty document and a document with
  one name renamed both fail, and the link helper is asserted to ignore `http`,
  `mailto:` and `#` targets.
- **Two factual errors were found by the manual review and fixed before commit.**
  (1) The first draft claimed `client.toolbarMode = "viewer"` was set in
  `.streamlit/config.toml`; it is **not** — no `[client]` section exists, and the
  plan lands that value with the top bar (Task 28). Sections 3 and 9 now say the
  lock is enforced today by the custom `[theme]` alone (the toggle is already
  hidden) and name Task 28 for `toolbarMode` plus the
  `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` override. (2) The first draft equated
  `theme.font`/`codeFont` with the `font-ui`/`font-mono` tokens; the config actually
  carries richer family lists (`IRANSans`/`Menlo`), so the row now states that only
  the palette, the radii and the base size are token-equal.
- **A dangling link was removed rather than left for Task 24.**
  `docs/phase-7.2/VALIDATION.md` does not exist yet (Task 24 creates it), so the
  "Wave A review" reference is plain text until then; every remaining link resolves,
  and the link test will hold Task 47 to that when it extends the document.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_design_system_doc.py -q --no-cov` →
    **10 passed**.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **491 passed** (481 + 10),
    no regressions against Task 22.
  - `poetry run mypy src dashboard` → **0 errors** (68 source files);
    `ruff check` / `ruff format` clean.
- **Deviations:** (1) The guard's scope is the component surface (`render_*` +
  `build_*`), not every public function in the package: `serialize_*`,
  `find_chromium_executable`, `unique_values` and the other helpers are engine
  internals, and documenting them would turn the reference into an API dump. The
  scope is stated in the test docstring. (2) The document is longer than the plan's
  Build list strictly requires (it also covers the export engine, the chrome
  selector split and the testing rules) because those are the facts later waves
  would otherwise re-derive; the plan calls this a first draft for Task 47 to
  extend.
- **Commit hash:** `e007d5e`

---

## Task 24 — (A) RECORD the Wave A after-screenshots and review them against the baseline (AM-24)

- **Files:** `docs/phase-7.2/wave-0-assets/after/` (new, ten PNGs),
  `docs/phase-7.2/VALIDATION.md` (new), `docs/phase-7.2/design-system.md`
  (the validation link is live again), plan checkboxes.
- **Build:** Launched the app
  (`poetry run streamlit run dashboard/app.py --server.port 8501 --server.headless true`;
  the TimescaleDB container was already up and healthy) and ran the Task 10 script
  against the Task 24 destination:
  `poetry run python scripts/dashboard_screenshots.py --out-dir docs/phase-7.2/wave-0-assets/after`
  → **10 PNGs at 1440×900**, one per registered page, captured through the sidebar
  in registry order. Created `docs/phase-7.2/VALIDATION.md` as the Wave A
  validation report: environment table, method, per-page comparison, the four
  regression categories with evidence, the delta against the Tasks 7–10
  checkpoint, filed defects, and an explicit "not automated in this run" list.
- **The four regression categories — all PASS, each with evidence rather than an
  eyeball:**
  - **Clipped tables (AM-26):** a live DOM probe over seven pages
    (`/tmp/phase72-probe-charts/probe_tables.py`, throwaway) reports
    `documentElement.scrollWidth == clientWidth == 1440` and
    `body` likewise on every page — **no page scrolls sideways**. Wide tables
    scroll inside their own box: the grid scroller carries `overflow-x: auto` and
    overflows by 513 px (overview), 1058 px (catalog), 132 px (labor), 27 px
    (inflation). The Task 15 wrapper is not adopted by pages yet, so the finding is
    "no regression introduced", recorded as such.
  - **Chart typography:** a DOM probe on the market chart
    (`/tmp/phase72-probe-charts/probe_charts.py`) reports tick/legend text at
    10.5 px and the axis title at 12.25 px, all in
    `Vazirmatn, IRANSans, Tahoma, "Segoe UI", sans-serif`; Jalali ticks render
    (`۱۴ آذر ۱۳۸۷`); the time axis flows LTR; grid `--border`, trace `--accent`.
  - **Font fallback:** `body`, `stMarkdownContainer`, `stMetricValue` and
    `stSidebarNavLink` all compute to the Vazirmatn stack, and `document.fonts`
    reports `Vazirmatn` **loaded** — no fallback to Tahoma/Segoe UI.
  - **Sidebar overlap:** sidebar 0–256 px, `stMainBlockContainer` 256–1440 px
    (width 1184 px); the DB-status card sits at the sidebar bottom without
    covering a nav item; nothing crosses the boundary.
- **Delta against the Tasks 7–10 global-look set (01:29, before Tasks 12–14):**
  **5 of 10 captures byte-identical**; the other 5 differ by **≤ 0.23 % of pixels**
  (four are sub-pixel antialiasing; `gdp` is the substantive one). Measured with
  PIL: `gdp` differs by 2941 px in a single band because **Task 14** moved the
  chart legend into the template, raising the legend row ~48 px; the filter
  controls are at identical coordinates in both sets, so the page itself does not
  shift. Tasks 15–22 add components pages do not adopt, so they are invisible —
  the intended Wave A outcome.
- **Defects filed:**
  1. **Chart legend title reads `label`** on every chart, because the builders
     pass `color="label"` (`charts.py:163,190,235,326,564`). **Pre-existing**
     (last changed 2026-09-19, Phase 7.1) and **not a Wave A regression** — it is
     invisible in the `before` baseline only because the charts sat below the fold
     there. Needs a chart-builder task; recorded as an open item in
     `VALIDATION.md`.
  2. **10 px container overflow around `st.dataframe`** — the outer
     `stVerticalBlock` chain reports `scrollWidth` 9–10 px above `clientWidth`
     with `overflow-x: visible`. Streamlit's own padding; it does not reach the
     document and nothing is cut. Recorded as an observation, not a defect.
- **Verify:** Manual comparison of `wave-0-assets/before/` vs
  `wave-0-assets/after/` — per-page table in `VALIDATION.md`, plus the PIL pixel
  diff and the two DOM probes above. `poetry run pytest tests/unit/dashboard -q
  --no-cov` → **491 passed** (the new link in `design-system.md` keeps
  `test_every_relative_link_resolves` green); `poetry run mypy src dashboard` →
  **0 errors** (68 source files); `ruff check` / `ruff format` clean.
- **Deviations:** (1) The after-screenshots are committed under
  `wave-0-assets/after/` as the plan's Files line requires, even though the Task 10
  script's default output directory is the gitignored
  `wave-a-assets/after-global-look/`; the script takes `--out-dir`, so no script
  change was needed. (2) `VALIDATION.md` is created here as a Wave A report rather
  than a bare stub, because the plan's acceptance requires the four categories to
  be recorded in it; later tasks append to the same file.
- **Commit hash:** `081e227`

---

## Wave A gate — after Tasks 1–24

- **Files:** `docs/phase-7.2/VALIDATION.md` (gate section),
  `docs/phase-7.2/README.md` (status), this entry.
- **Build:** Ran the per-wave gate recorded in `wave-0-spike.md` §3 and recorded
  it in `VALIDATION.md`, against the Wave 0 pre-change baseline.
- **Results:**
  - `make check` → **PASS**. `ruff format` + `ruff check` clean; `mypy src/`
    clean; `pytest -m "not integration"` → **1307 passed, 3 skipped, 136
    deselected** in 141.53 s; coverage **89.22 %** (≥ 80 % gate).
  - `poetry run mypy src dashboard` → **0 errors** (68 source files).
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **491 passed**.
  - Export smoke (deselected by `make check`):
    `poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q
    --no-cov` → **1 passed** (PNG + SVG through Kaleido 1.4.0).
  - Ten-page AppTest smoke: a throwaway pytest file (not committed, in `/tmp`)
    parametrized over every `PageSpec` and rendered through the router with the
    repository's fake repository → **11 passed** (10 pages + the registry count),
    no page raises.
  - `git status --short` → clean after the Task 24 commits.
- **Baseline comparison.** Wave 0 recorded **1158 passed / 3 skipped / 135
  deselected** (full suite) and **341 passed** (dashboard subset). The dashboard
  subset was **426 passed** after Task 16, i.e. immediately before this stretch.
  So the stretch (Tasks 17–24) added **+65** dashboard tests (426 → 491) and the
  full suite moved **+149** (1158 → 1307); the one-test gap between those deltas
  is the new integration export smoke, which `make check` deselects (135 → 136
  deselected) and a plain subset run collects. **No failures and no regressions**;
  the skipped count is unchanged at 3.
- **Verify:** the commands above; `docs/phase-7.2/README.md` now reads
  "Wave A complete".
- **Deviations:** none. The gate is "no new errors / no regressions" against the
  recorded counts, as AM-21 requires, not an absolute test count.
- **Commit hash:** `a42b535`

---

## Step 0 — ten-page router smoke (permanent)

- **Files:** `tests/unit/dashboard/test_all_pages_smoke.py` (new),
  `docs/plans/phase-7.2-dashboard-redesign.md` (Gate line).
- **Build:** The Wave A gate used a throwaway `/tmp` test that renders every
  `PageSpec` through the router with the fake repository. This commit makes it
  permanent: `test_every_page_renders_through_the_router` is parametrized over
  `PAGES`, each page driven through `app_smoke.app_test(use_router=True)`, the
  only assertion `not app.exception`. The id carries `group-key` so a failure
  names the page.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py
  -q --no-cov` → 10 passed; `ruff check` / `mypy` clean; full dashboard subset
  → 501 passed (491 + 10 new), no regressions.
- **Deviations:** none.
- **Commit hash:** `ebf35eb`

---

## Task 25 — Material nav icons

- **Files:** `dashboard/navigation.py`, `tests/unit/dashboard/test_navigation.py`,
  `docs/plans/phase-7.2-dashboard-redesign.md` (checkboxes),
  `docs/phase-7.2/wave-b-assets/task-25-icons/` (10 PNGs).
- **Build:** Replaced all ten emoji `PageSpec.icon` values with validated
  `:material/<name>:` shortcodes: `overview`, `compare_arrows`, `menu_book`,
  `show_chart`, `analytics`, `swap_horiz`, `home`, `currency_exchange`,
  `trending_up`, `work`. Each name was validated against
  `streamlit.material_icon_names.ALL_MATERIAL_ICONS` and
  `streamlit.string_util.validate_material_icon`.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_navigation.py -q --no-cov` → 13 passed
    (10 existing + 3 new: shortcode validation, uniqueness, fx_gold/trade_energy
    distinctness).
  - `poetry run mypy src dashboard` → 0 errors.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → 504 passed, no regressions.
  - `poetry run python scripts/dashboard_screenshots.py --out-dir
    docs/phase-7.2/wave-b-assets/task-25-icons` → all 10 PNGs produced; the
    `[data-testid="stSidebarNavLink"]:has-text(...)` selector still works with the
    new icon element present in the link markup.
- **Deviations:** none. `trade_energy` uses `swap_horiz` rather than `bolt`; both
  are distinct from `fx_gold`'s `currency_exchange`.
- **Commit hash:** `1f06944`

## Task 26 — ADD the freshness-query TTL (D7)

- **Files:** `dashboard/queries.py`, `tests/unit/dashboard/test_queries_ttl.py`
  (new), `docs/plans/phase-7.2-dashboard-redesign.md` (checkboxes).
- **Build:**
  - Added module-level constant `FRESHNESS_CACHE_TTL_SECONDS: int = 900` (15
    minutes) to `dashboard/queries.py` with a docstring noting that staleness is
    measured in days and that an explicit refresh control is deferred.
  - Changed only `cached_source_freshness` to
    `@st.cache_data(show_spinner=False, ttl=FRESHNESS_CACHE_TTL_SECONDS)` and
    expanded its docstring. The other six cached wrappers are unchanged.
  - Wrote `tests/unit/dashboard/test_queries_ttl.py` with AST-based tests:
    `test_freshness_ttl_is_a_positive_number_of_seconds`,
    `test_freshness_wrapper_passes_the_ttl` (asserts the `ttl` keyword is the
    `Name` node `FRESHNESS_CACHE_TTL_SECONDS`),
    `test_other_wrappers_do_not_pass_a_ttl` (asserts the other six wrappers
    have no `ttl` keyword), and a `_decorator_keywords` helper plus a
    `CACHED_WRAPPERS` tuple.
- **Verify:**
  - `poetry run ruff check tests/unit/dashboard/test_queries_ttl.py
    dashboard/queries.py` → clean.
  - `poetry run mypy dashboard/queries.py tests/unit/dashboard/test_queries_ttl.py`
    → 0 errors.
  - `poetry run pytest tests/unit/dashboard/test_queries_ttl.py -q --no-cov` →
    3 passed.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → 507 passed, no
    regressions.
- **Deviations:** none. Chose 900 s (15 min) because staleness is measured in
  days; the TTL is short enough to reflect a new collection run quickly without
  re-querying on every Streamlit rerun.
- **Commit hash:** `00024ba`

## Task 27 — BUILD the sidebar shell (brand, DB status)

- **Files:** `dashboard/components/direction.py`, `dashboard/app.py`,
  `dashboard/i18n.py`, `docs/phase-7.2/design-system.md`,
  `tests/unit/dashboard/test_direction.py`, `tests/unit/dashboard/test_app_router.py`.
- **Build:**
  - Added `app.brand`, `app.db_status_label`, `app.db_status_online`,
    `app.db_status_offline` to `dashboard/i18n.py`.
  - Added a pure `_escape_css_string` helper and `brand_sidebar_css(brand_text)`
    builder to `dashboard/components/direction.py`. The brand mark is a CSS-drawn
    accent square in `stSidebarHeader::before`; the brand text is escaped and
    interpolated into `stSidebarHeader::after`. `inject_direction_css` accepts an
    optional `brand_text` and appends the brand rules when provided.
  - Updated the `sidebar_header` chrome rule to `display: flex; align-items:
    center; gap: 10px; padding: 1.25rem 1rem 0.75rem;`.
  - Replaced `st.success`/`st.error` in `render_database_status` with the shared
    `render_status_dot` component, using tones `ok`/`err` and short labels.
  - `app.py` now calls `inject_direction_css(brand_text=t("app.brand"))`.
  - Recorded the brand fallback (2) recipe and DB-status pin in
    `docs/phase-7.2/design-system.md` §6.
- **Verify:**
  - `poetry run ruff check` on modified files → clean.
  - `poetry run ruff format --check` on modified files → clean.
  - `poetry run mypy src dashboard` → 0 errors.
  - `poetry run pytest tests/unit/dashboard/test_direction.py
    tests/unit/dashboard/test_app_router.py -q --no-cov` → 27 passed.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → 518 passed, no
    regressions.
  - Visual check: `python scripts/dashboard_screenshots.py --out-dir
    docs/phase-7.2/wave-b-assets/task-27-sidebar` → 10 PNGs at 1440×900; the
    default page shows the brand block (accent mark + "داده‌های اقتصاد کلان
    ایران") and the DB status dot at the sidebar bottom.
- **Deviations:**
  - The mockup's brand glyph is replaced by a CSS-drawn accent square because no
    brand asset exists and `st.html` strips inline SVG.
  - The brand text wraps in the 256px sidebar; the mark and first line sit on
    one row, and the remaining text wraps below.
- **Commit hash:** `59e1a25`

## Task 28 — BUILD the top bar / breadcrumb with the last-collection stamp

- **Files:** `dashboard/components/layout.py` (`render_top_bar`),
  `dashboard/components/direction.py` (`top_bar` CSS selector + rules,
  `main_block_container` padding-top raised to 120 px),
  `dashboard/app.py` (`_current_page_spec` helper + `render_top_bar` call),
  `dashboard/i18n.py` (`shell.*` namespace + `"shell."` added to `KEY_PREFIXES`),
  `.streamlit/config.toml` (`[client] toolbarMode = "viewer"`),
  `docs/phase-7.2/design-system.md` (§3, §4.1, §6, §9, §14, §15),
  `pyproject.toml` (per-file-ignores for `layout.py` RUF001),
  `tests/unit/dashboard/test_layout.py` (5 new tests),
  `tests/unit/dashboard/test_app_router.py` (2 new tests),
  `tests/unit/dashboard/test_direction.py` (padding-top test updated),
  `tests/unit/dashboard/test_tokens.py` (toolbarMode config test),
  plan checkboxes.
- **Build:**
  - `render_top_bar(group_label, page_label, *, key="top-bar")` renders a keyed
    `st.container` with one `st.columns([1, 1])` row. The breadcrumb (root › group
    › page) is an escaped `st.html` fragment in the first column (RTL start);
    the last-collection stamp is in the second column (RTL end). The stamp reads
    `cached_source_freshness()`, takes the max `collection_timestamp`, and
    formats it through `to_tehran` → `jalali_date_label` + the clock portion of
    `tehran_timestamp_label`. An empty or unparseable frame falls back to
    `t("value.unknown")`.
  - `_current_page_spec(selected_page)` maps the `Page` returned by
    `st.navigation` back to a `PageSpec` by matching `selected_page.title`
    against `t(f"nav.{spec.key}")`, so the breadcrumb is derived from the
    registry, not a literal.
  - `main_block_container` chrome rule changed to `padding-top: 120px` (60 px
    native header + 48 px top bar + 12 px breathing room), up from 96 px.
  - `[client] toolbarMode = "viewer"` added to `.streamlit/config.toml` with a
    comment documenting `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` for local dev.
  - `"shell."` added to `KEY_PREFIXES` in `dashboard/i18n.py` for the three new
    `shell.*` keys.
- **Verify:**
  - `poetry run ruff check` / `ruff format` on all touched files → clean.
  - `poetry run mypy src dashboard` → 0 errors (68 source files).
  - `poetry run pytest tests/unit/dashboard/test_layout.py
    tests/unit/dashboard/test_app_router.py tests/unit/dashboard/test_direction.py
    tests/unit/dashboard/test_tokens.py tests/unit/dashboard/test_i18n.py
    -q --no-cov` → 105 passed.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **525 passed** (518
    + 7 new), no regressions.
  - `poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov`
    → 10 passed (all pages still render through the router with the top bar).
- **Deviations:**
  - No non-bleed deviation: the top bar sits inside the 1360 px max-width main
    container, consistent with the mockup's content alignment.
  - `dashboard/components/layout.py` added to `pyproject.toml`
    `per-file-ignores` for `RUF001`/`RUF002`/`RUF003` because the breadcrumb
    separator `›` (U+203A) is an intentional RTL glyph, matching the existing
    convention for Persian-text dashboard modules.
  - The breadcrumb separator is `›` (single right-pointing angle quotation
    mark), the RTL-appropriate separator; the LTR `>` was not used because it
    would render incorrectly in the RTL context.
- **Commit hash:** `715712c`

## Step 0a — brand text + single-line sidebar brand

- **Files:** `dashboard/i18n.py`, `dashboard/components/direction.py`,
  `pyproject.toml`, `tests/unit/dashboard/test_i18n.py`,
  `tests/unit/dashboard/test_direction.py`,
  `docs/phase-7.2/wave-b-assets/step-0a-brand/` (3 PNGs).
- **`pyproject.toml`:** added `tests/unit/dashboard/test_direction.py` to
  `per-file-ignores` for `RUF001`/`RUF002`/`RUF003` — the new brand literal
  `سامانهٔ داده‌ها` contains the combining-hamza sequence `هٔ` (HEH U+0647 +
  HAMZA ABOVE U+0654), which ruff flags as an ambiguous character, and the
  file now carries a Persian fixture like the other Persian-fixture test files
  already listed there.
- **Build:** `app.brand` changed from the full app title
  (`داده‌های اقتصاد کلان ایران`) to the plan/mockup value (`سامانهٔ داده‌ها`).
  In `brand_sidebar_css` the `::after` text is now the flexible flex child
  (`flex: 1 1 auto; min-width: 0`) carrying
  `white-space: nowrap; overflow: hidden; text-overflow: ellipsis`, and the
  `sidebar_header` chrome rule gained `flex-wrap: nowrap`. A brand wider than
  the 256 px sidebar therefore ellipsizes on one line instead of wrapping into
  the navigation below.
- **Measured (Step 0b probe, 1440×900):** sidebar 256 px; `stSidebarHeader`
  **201 px** wide, inset **27.5 px** each side by `stSidebarContent`'s
  `padding: 0 17.5px`; header padding `17.5px 10.5px 10.5px`, `gap: 8px`;
  `stSidebarCollapseButton` 28 px. The `::after` text box is **97 px** and the
  string's natural width at 15px/700 is **84 px**, so the full brand fits on
  one line and the ellipsis is defensive only — it never triggers at this
  length.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_direction.py
    tests/unit/dashboard/test_i18n.py tests/unit/dashboard/test_app_router.py
    -q --no-cov` → 45 passed (2 new in `test_direction.py`:
    `test_brand_text_is_pinned_to_a_single_line`,
    `test_sidebar_header_does_not_wrap`; 1 new assertion in `test_i18n.py`).
  - `poetry run ruff check dashboard tests` → clean;
    `ruff format --check dashboard tests` → 119 files already formatted.
  - `poetry run mypy dashboard` → 0 errors.
  - A 4× DPI clip of `stSidebarHeader`
    (`wave-b-assets/step-0a-brand/brand-after.png`, with
    `brand-before.png` cropped from the pre-0a baseline for contrast) shows the
    full brand on one line, the accent mark at the RTL start (right) and the
    text beside it — no wrap, no truncation.
- **Deviations:** none. The 15 px / 700 brand typography is unchanged from the
  mockup; no font-size reduction was needed once the natural width was
  measured.

## Step 0b — top-bar geometry (re-measured and fixed)

- **Files:** `dashboard/components/direction.py` (`_CHROME_COMMENT`,
  `main_block_container` padding, top-bar row rule),
  `tests/unit/dashboard/test_direction.py`,
  `tests/unit/dashboard/test_layout.py`, `docs/phase-7.2/design-system.md`
  (§6, §9, §14),
  `docs/phase-7.2/wave-b-assets/step-0b-topbar/` (4 PNGs).
- **Build:**
  - **Re-measured (Playwright, 1440×900, shipped app).** `stHeader` is
    `position: absolute`, `z-index 999990`, **52.5 px** tall at `y = 0`;
    `stMainBlockContainer` `x = 256`, `width = 1184`, `max-width 1360px`;
    before the fix its `padding-top` was `120px`, so the top bar sat at `y = 120`
    — a **67.5 px** empty gap below the header (`h1` at `y = 154.8`).
  - **52.5 vs 60 reconciled.** Both are 3.75 rem: 52.5 = 3.75 rem × the themed
    14 px root; 60 = 3.75 rem × the browser's default 16 px root. **52.5 px is
    correct for the shipped app.** A second server run with
    `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` also measured **52.5 px**, so
    toolbar mode is not the cause; the 60 px figure predates the 14 px themed
    base. Task 9's 52.5 px was right.
  - **48 px bar height was inert.** The row's `height: 48px` never applied:
    Streamlit's `.stHorizontalBlock` sets `flex: 1 1 0%` and the keyed container
    is a *column* flex parent, so the vertical main axis takes `flex-basis: 0%`
    over `height`. Measured row height **20.8 px** with `height: 48px`; changed
    to `min-height: 48px`, which constrains a flex item → **48 px**.
  - **Gap fixed.** `main_block_container` `padding-top` `120px → 64px`
    (52.5 px header + 12 px gap).
  - **Non-bleed correction recorded.** The bar is the main container's first
    child, so it is **inside the 1360 px content column, not full-bleed**
    (`x = 326, width = 1044`, identical to the `h1` column) — this corrects
    Task 28's "no non-bleed deviation" statement. It is **not visible at
    1440 px** (main area 1184 px < 1360 px cap); it only shows above a
    1616 px viewport.
- **After (measured):** `padding-top 64px`; top bar `y = 64`, `height = 48px`,
  `bottom = 112`; `h1` `y = 126`; **header-bottom → bar-top gap = 11.5 px**
  (target ≤ 24 px). Content moved up 28.8 px.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_direction.py
    tests/unit/dashboard/test_layout.py tests/unit/dashboard/test_app_router.py
    -q --no-cov` → 81 passed.
  - `poetry run ruff check`/`format --check` on the touched files → clean;
    `poetry run mypy src dashboard` → 0 errors.
  - Screenshots (`wave-b-assets/step-0b-topbar/`): `overview-after.png` plus
    `topbar-before.png` / `topbar-after.png` (top 260 px strip). The bar is now
    directly under the header; the mockup crop shows the same order
    (breadcrumb at the RTL start, stamp at the far end).
- **Deviations:** the real bar has no `surface` background or bottom border
  (the mockup draws a white strip with a `border-bottom`); that is Task 28's
  accepted styling, unchanged here — Step 0b is geometry only.

## Step 0c — page-spec lookup is registry-derived, not display-text-derived

- **Files:** `dashboard/app.py`, `tests/unit/dashboard/test_app_router.py`.
- **Build:**
  - `_build_page` now passes `url_path=_page_url_path(spec)` to `st.Page`, so
    each page carries a stable registry-derived identifier.
  - `_page_url_path(spec)` returns `spec.key`, **except** for the default page,
    where it returns `""` — `StreamlitPage.url_path` short-circuits to the empty
    string when `default=True`, regardless of the value passed in.
  - `_current_page_spec` matches the selected page on `url_path`
    (`getattr(selected_page, "url_path", "")`) instead of `t(f"nav.{key}")`.
    The breadcrumb can no longer be broken by a translated nav label.
  - A page outside the registry (or a stub with no `url_path`) now **falls back
    to the default page's spec** rather than raising. The breadcrumb is chrome;
    a missing label must not take down an otherwise-rendering page.
  - `_PageLike` is a structural `Protocol` declaring `url_path` as a
    **read-only property** (matching `StreamlitPage.url_path`, which is one) so
    the lookup is unit-testable without a Streamlit script run.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_app_router.py
    tests/unit/dashboard/test_layout.py -q --no-cov` → 59 passed.
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → 531 passed (no
    regression; 525 baseline + the 0a/0b/0c additions).
  - `poetry run mypy src dashboard` → 0 errors; `ruff check`/`format --check`
    on both files → clean.
  - New tests: two distinct keys resolve by `url_path`; `_page_url_path` returns
    `""` for the default and the key otherwise; a non-registry page and a
    `url_path`-less stub both fall back to the default spec.
- **Deviations:** none. The prior `RuntimeError` on a lookup miss is replaced by
  a documented fallback, which is the intended robustness change.

## Step 0d — Wave B gate records

- **Files:** `docs/phase-7.2/VALIDATION.md` (new "Wave B" section + status),
  `docs/phase-7.2/README.md` (status → "Wave B complete"),
  `docs/phase-7.2/wave-b-assets/all-pages/` (10 PNGs).
- **Build:**
  - **Gate runs.** `make check` → **1347 passed, 3 skipped, 136 deselected** in
    167.4 s, coverage **89.22 %**; `poetry run mypy src dashboard` → **0 errors**;
    dashboard subset → **531 passed**; export integration smoke
    (`test_exports.py -m integration`) → **1 passed**; ten-page AppTest smoke
    (`test_all_pages_smoke.py`) → **10 passed**.
  - **All-pages capture.** Restarted the Streamlit server on the 0c tree, then
    `poetry run python scripts/dashboard_screenshots.py --out-dir
    docs/phase-7.2/wave-b-assets/all-pages` → 10 PNGs at 1440×900, one per
    registered page. Each page shows the full shell (single-line brand, nav
    icons, active item, pinned DB status, seated top bar with the correct
    breadcrumb + stamp). Per-page pass/defect lines and the breadcrumb text are
    recorded in `VALIDATION.md`.
  - **Observations (not Wave B defects).** Filter multiselects still show the
    untranslated `Choose options` placeholder (page-composition, Waves C–G);
    the GDP chart legend title still reads `label` (already filed Wave A defect
    1); `welfare.png` was captured mid-run and shows the transient `Stop` widget
    (capture timing, not a page defect).
  - **Plan checkboxes.** Tasks 25–28 acceptance boxes are all `[x]` in
    `docs/plans/phase-7.2-dashboard-redesign.md`; Tasks 29–31 remain `[ ]` (Wave
    C, not started).
- **Verify:** all gate commands above are green; `git status --short` clean apart
  from the new assets/docs being committed.
- **Deviations:** none new. The Wave B accepted deviations (48 px non-bleed top
  bar; CSS-pinned text brand) are restated in `VALIDATION.md`.

## Step 0e — type scale pinned to the mockup

- **Files:** `.streamlit/config.toml`, `dashboard/components/tokens.py`,
  `tests/unit/dashboard/test_tokens.py`, `docs/phase-7.2/design-system.md`
  (§3, §14, §15), `docs/phase-7.2/wave-c-assets/type-scale/` (10 PNGs).
- **Build:**
  - **Mockup scale read.** `overview-redesign-mockup.html`: h1 `28px/700`
    (line-height 1.4), section title `18px/600` (h2, line-height 1.5), KPI value
    `28px/600`, KPI label `13px/500`, body `14px/400` (line-height 1.85).
  - **Option names confirmed** via `streamlit.config.get_config_options()`:
    `theme.headingFontSizes` (h1–h6 array), `theme.headingFontWeights`,
    `theme.metricValueFontSize`, `theme.metricValueFontWeight`,
    `theme.baseFontWeight`. `headingFontSizes`/`headingFontWeights` are arrays of
    up to six; `metricValueFontWeight`/`baseFontWeight` are ints.
  - **Measured before (live, 1440×900):** h1 **38.5px/700** (2.75rem × 14px root),
    section header — `st.subheader`, rendered as `<h3>` — **24.5px/600**,
    `st.metric` value **31.5px/400**, metric label 12.25px/400, body 14px/400.
  - **Change.** Added `TYPE_SCALE` to `tokens.py` (sizes as px strings, weights as
    integer strings) and pinned the theme to it: `headingFontSizes = ["28px",
    "18px", "18px"]`, `headingFontWeights = [700, 600, 600]`,
    `metricValueFontSize = "28px"`, `metricValueFontWeight = 600`,
    `baseFontWeight = 400`. The section header renders as `<h3>`, so the mockup's
    18px/600 section scale is carried on both `h2` and `h3`.
  - **Measured after:** h1 **28px/700**, `<h3>` **18px/600**, `st.metric` value
    **28px/600**, body 14px/400 — all three match the mockup exactly.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_tokens.py -q --no-cov` → 16
    passed (4 new: heading sizes, heading weights, metric value, body weight).
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **535 passed**;
    `make check` → **1351 passed, 3 skipped, 136 deselected**, coverage 89.22 %;
    `poetry run mypy src dashboard` → 0 errors; ruff check/format clean.
  - Screenshots (`wave-c-assets/type-scale/`): 10 pages at 1440×900; the page
    title, section headings and KPI values are visibly smaller and the KPI values
    bolder, and more content fits above the fold (e.g. the Overview freshness
    table now reaches it) — the intended effect of the smaller heading scale.
- **Deviations / remaining gaps (not theme options).** The mockup's line-heights
  (h1 1.4, section 1.5, body 1.85), the KPI label's 13px/500 (`stMetricLabel`
  computes 12.25px/400) and the secondary KPI value's 20px (the theme sets one
  metric-value size, 28px) cannot be expressed by the theme; they are recorded in
  `design-system.md` §15 as Task 19/29 component work.

## Step 0f — screenshot-script reliability

- **Files:** `scripts/dashboard_screenshots.py`,
  `docs/phase-7.2/wave-b-assets/all-pages/welfare.png` (replaced).
- **Build:**
  - **Why.** The Wave B `welfare.png` was captured mid-run and froze the
    transient running indicator (the toolbar's "Stop" button) into the frame.
  - **Change.** `_TRANSIENT_SELECTORS` now lists the three transient states —
    `[data-testid="stStatusWidget"]` (the running indicator), `stSpinner` and
    `stSkeleton`. `transient_selectors(page)` returns those present in the DOM;
    `wait_until_settled(page, page_key)` polls them clear, re-checks once more
    after a 500 ms quiet delay (a rerun can start during the delay) and, after
    `_SETTLE_RETRIES = 20` polls at 250 ms, raises `ScreenshotNotReadyError`
    naming the page instead of writing a bad image. `capture` calls it twice per
    page: inside `wait_ready` (after the app root and main block exist) and again
    **immediately before** `page.screenshot`, because `neutralise` can trigger a
    rerun. `main` already catches the exception, prints it and returns 1, so a
    page that never settles fails the run loudly.
- **Verify:**
  - `poetry run ruff check` / `ruff format --check` / `mypy scripts/dashboard_screenshots.py`
    → clean (1 file, no issues).
  - Full capture against the running app (1440×900): `poetry run python
    scripts/dashboard_screenshots.py --out-dir /tmp/wave-c-step0f` → **10 PNGs**,
    every page settled on the first pass. The new `welfare.png` no longer shows
    the "Stop" widget (top-right carries only the kebab and the expand control);
    the captured frame is byte-different from the flawed Wave B file and was
    copied over `docs/phase-7.2/wave-b-assets/all-pages/welfare.png`.
- **Deviations:** none. The other nine Wave B PNGs are left untouched, so the
  asset diff is exactly the one replaced file.

## Task 29 — (C) Overview KPI band (6 cells)

- **Files:** `dashboard/page_view.py` (new `series_inventory_counts` and
  `overview_kpi_cells`; `_render_series_inventory` removed),
  `dashboard/components/direction.py` (KPI label/secondary-value rules, main-block
  heading line-heights, body line-height), `tests/unit/dashboard/test_app_overview.py`,
  `tests/unit/dashboard/test_layout.py`, `tests/unit/dashboard/test_direction.py`,
  `docs/phase-7.2/design-system.md` (§3, §14, §15),
  `docs/phase-7.2/wave-c-assets/task29/` (`overview.png`, `band-live.png`,
  `band-mockup.png`).
- **Build:**
  - **One band replaces two rows.** The 4-column metric row and the separate
    `_render_series_inventory` row are replaced by one `render_kpi_band(key="overview")`
    of six cells in mockup order (right to left): sources, domains, active
    indicators, Gold observations (tooltip), derived series (tooltip, muted,
    secondary) and series without a catalog row (tooltip, muted, secondary, tag).
    `overview_kpi_cells` is a pure builder; `series_inventory_counts` returns the
    two counts from separate expressions and **does not dedupe** them (D2). The
    cached `series_inventory` call is kept; `_render_series_inventory` is deleted.
  - **Typography the theme cannot express** (carried from Step 0e), all as scoped
    CSS in `direction.py` — never via the theme:
    - KPI label `13px/500` on `[class*="st-key-kpi-band-"] [data-testid="stMetricLabel"]`
      (was 12.25 px/400);
    - secondary-group value `20px` on the new `kpi_secondary_cell` hook
      (`[class*="st-key-kpi-"][class*="-secondary-"] [data-testid="stMetricValue"]`),
      distinct from the existing `kpi_secondary_group` boundary hook so only the
      former sizes the value; primary values keep the theme's 28px/600;
    - heading line-heights on `[data-testid="stMainBlockContainer"] h1` (1.4) and
      `h3` (1.5) — the main-block scope and specificity are needed because
      Streamlit's own heading rule (1.2) outranks a bare `h1`/`h3`;
    - body line-height **changed 1.9 → 1.85** to match the mockup (measured 1.9
      before, so the mockup value was not in effect).
  - **Computed styles, live app (1440×900)** — before → after: h1 line-height
    33.6 px (1.2) → **39.2 px (1.4)**; `<h3>` 21.6 px (1.2) → **27 px (1.5)**;
    metric label 12.25 px/400 → **13 px/500**; primary metric value **28 px/600**
    (unchanged); secondary metric value → **20 px**; body paragraph 26.6 px (1.9)
    → **25.9 px (1.85)**. Band container `direction: rtl`, **6** cells keyed
    `kpi-overview-primary-0..3` then `kpi-overview-secondary-0..1`, labels in
    mockup order.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_app_overview.py test_layout.py
    test_direction.py -q --no-cov` → **95 passed** (7 new: band order, annotation
    + tag, separate derived/orphan counts, empty-safe inventory, KPI typography
    CSS, heading line-heights, body line-height). The pre-existing `app.metric`
    assertions passed **unchanged** — the new structure still renders the three
    labels they check.
  - `poetry run mypy src dashboard` → 0 errors; ruff check/format clean.
  - **Visual.** `band-live.png` vs `band-mockup.png` (same six cells): order
    identical; a separator between every pair of cells and a stronger boundary at
    the start of the secondary group, as the mockup; tooltip markers on exactly
    the three annotated cells; values right-aligned at the RTL start of each cell;
    the tag beneath the orphan metric.
- **Deviations (recorded in `design-system.md` §14):**
  1. **Tag placement.** The mockup's `نیازمند بررسی` tag is inline in the label
     row; the shipped band renders a real `st.badge` **beneath** the metric (the
     pre-existing §14 deviation, now attributed to Task 29).
  2. **Tooltip glyph.** Streamlit's native `help=` marker (circled `?`) rather
     than the mockup's circled `i`; the marker is a native element that cannot be
     restyled without a hashed class.
  3. **Secondary cell width.** The two secondary cells are equal-width, not the
     mockup's `flex: 1.35`. This is `render_kpi_band`'s equal-weight `st.columns`
     row (Task 19 component geometry), so it was **not** changed in Task 29;
     flagged for the Task 34 owner review.

## Task 30 — (C) Overview freshness table

- **Files:** `dashboard/page_view.py` (`FreshnessTable`, `_freshness_dot_tone`,
  `build_freshness_rows`; the section wired through `render_section_header` +
  `render_html_table`), `dashboard/components/html_table.py` (`TwoLine.primary_tone`),
  `dashboard/components/layout.py` (`status_chip_cell` + the total
  `_STATUS_CHIP_TABLE_TONES` map), `dashboard/formatting.py` (`tehran_clock_label`),
  `dashboard/i18n.py` (`table.run_status`), `tests/unit/dashboard/`
  (`test_app_overview.py`, `test_html_table.py`, `test_layout.py`,
  `test_formatting.py`), `docs/phase-7.2/design-system.md` (§4.1, §8, §14),
  `docs/phase-7.2/wave-c-assets/task30/` (`overview.png`, `freshness-live.png`,
  `freshness-mockup.png`).
- **Build:**
  - **Pure builder.** `build_freshness_rows(frame, *, now) -> FreshnessTable`
    returns the localized headers plus one tuple of typed cells per source:
    `Text` (source, via `labels.source_label`), `Dot` (verdict; amber stale /
    green fresh / **neutral unknown** — an unknown cadence is not dressed as
    either verdict), `TwoLine` (Jalali date; `time · relative age`, the date
    coloured by the verdict via the new `primary_tone`), `Text` (formatted
    record count, unknown rather than an invented zero) and `StatusChip`
    (`status_chip_cell`). Ordering is Task 12's: stale rows first, stable within
    a verdict.
  - **No duplicated chip mapping.** `status_chip_cell` reads the same
    `STATUS_CHIPS` slug → (label key, colour) mapping `render_status_chip` uses
    and converts only the tone vocabulary (`BadgeColor` → table `Tone`) through a
    total map. An unrecognised slug still renders the unknown chip.
  - **One `now` per render.** `render_overview_page` captures `now = datetime.now(UTC)`
    once and passes it to both `freshness_summary` (the header's trailing text)
    and `build_freshness_rows`, so the verdict, the summary and every relative age
    agree. The page no longer renders `freshness_display`; that function stays
    (it is still exercised by the unit tests and
    `tests/integration/test_dashboard_repository.py`, which must pass unchanged).
  - **Empty log** → `render_empty("empty.no_collection_runs")` (the shared state),
    and the header omits the trailing summary rather than claiming "۰ … ۰".
  - Rendered as a **full-width** section; Task 31 composes the two-column row.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **555 passed** (13 new:
    stale-first typed-cell order, neutral dot for an unknown cadence, unknown
    status slug, empty frame, the Overview markup + header summary + "no
    dataframe" migration, `status_chip_cell` mapping, `tehran_clock_label`,
    `TwoLine` primary tone + default + rejection, and the extended hostile-payload
    sweep). `test_overview_staleness_verdict_is_rendered` was **migrated** to the
    markup strategy (Task 16 map) — it was the only assertion the new structure
    required changing. The four `freshness_display` unit tests are untouched and
    pass.
  - `poetry run mypy src dashboard` → 0 errors; ruff check/format clean.
  - **Visual.** `freshness-live.png` vs `freshness-mockup.png`: column order and
    the RTL reading order identical; amber "کهنه" dots on the stale rows and green
    "بهروز" dots on the fresh ones; the two-line cell shows the Jalali date above
    `time · relative age` with the date amber only when stale; the run chip is a
    green "موفق"; the section header carries `۴ بهروز · ۳ کهنه` at the far end.
- **Deviations:**
  1. **i18n keys.** The plan listed `table.freshness_dot`, `table.relative_age` and
     `table.run_status`. `table.freshness_dot` would duplicate the existing
     `table.staleness` (`وضعیت تازگی`, the same value), so the existing key is
     reused; `table.relative_age` is unused (the age sits inside the two-line
     cell, not a column) and was not added; only `table.run_status` is new.
  2. **Last-collection header wording.** `زمان گردآوری` (reused
     `table.collection_timestamp`) instead of the mockup's `آخرین گردآوری`.
  3. **Header summary colour.** The trailing `{fresh} بهروز · {stale} کهنه` is one
     muted run; the mockup colours the stale count amber (the trailing slot is
     markdown).
  4. **`TwoLine.primary_tone`** was added (an optional trailing field, so existing
     call sites are unchanged) to match the mockup's amber stale date; recorded in
     `design-system.md` §8.

## Task 31 — (C) Overview domain bars + the two-column row

- **Files:** `dashboard/page_view.py` (`_render_domain_counts` now delegates to
  `render_bar_list`; `render_overview_page` composes the row),
  `dashboard/components/direction.py` (`overview_row` hook),
  `dashboard/i18n.py` (`metric.indicator_count`), `tests/unit/dashboard/test_app_overview.py`,
  `docs/phase-7.2/design-system.md` (§14),
  `docs/phase-7.2/wave-c-assets/task31/` (`overview.png`, `row-live.png`,
  `row-mockup.png`).
- **Build:**
  - **Bars.** `_render_domain_counts` keeps its name and signature (the Task 20
    `render_bar_list` owner-link test monkeypatches it) but now builds `BarRow`s
    from `available_domains` and calls `render_bar_list`. The owner link stays a
    native `st.page_link` (inside `render_bar_list`, per AM-17); an unowned domain
    would stay plain text; the footer total is the **sum of the rows**, formatted
    with Persian digits. The old `st.page_link` list and its bullet markdown are
    gone, as is the now-unused `page_for_domain` import from `page_view`.
  - **The row.** `st.container(key="overview-row")` + `st.columns([7, 5])`, with
    the freshness section in the first column and the domain bars in the second.
    The new hook declares `direction: rtl` (`direction.py`), so the first column is
    the **rightmost**, exactly as the mockup's 7fr/5fr grid under
    `body{direction:rtl}`. Each column opens with its own
    `render_section_header`: freshness carries the summary trailing text, bars
    carry `table.indicator_count` (`تعداد شاخص`), matching the mockup's `.sec-h`.
  - **i18n.** The footer's "N شاخص" needed a count phrase the catalog did not have
    (`table.indicator_count` is the *label* "تعداد شاخص"), so `metric.indicator_count`
    = `{count} شاخص` was added — a deviation from the plan's Task 31 key list.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard -q --no-cov` → **559 passed** (4 new:
    one page link per owned domain + proportional bars + footer total, the bars
    header's count label, freshness-before-bars column order, the row's RTL hook).
  - `poetry run mypy src dashboard` → 0 errors; ruff check/format clean.
  - **AppTest visibility.** `app.get("page_link")` returns one entry per owned
    domain (AppTest exposes the element type through `app.get(...)`; there is no
    `app.page_link` attribute on `AppTest`). No raw `<a href>` is emitted for an
    internal page.
  - **Visual.** `row-live.png` vs `row-mockup.png`: identical column order
    (freshness right, bars left), identical bar proportions (15/15/8/4/3/2/1/1/1),
    fills anchored to the rail's right edge, the footer's `جمع` at the RTL start
    and `۵۰ شاخص` at the far end, and both section headers on one baseline.
    Measured at 1440 px: row `direction: rtl`, freshness column
    `x=768, w=602`, bars column `x=326, w=428` — a 1.406 ratio against the
    mockup's 7:5 = 1.4 (the absolute widths differ only by the main container's
    70 px side padding, the known Step 0b shell deviation).
- **Deviations:**
  1. **Bar order.** Rows keep `available_domains`' alphabetical domain order; the
     mockup's bars are count-descending. Not specified by the task and not changed
     (recorded in `design-system.md` §14 for the Task 34 owner review).
  2. **`metric.indicator_count`** added for the footer's "N شاخص" (see above).

## Wave C part 1 gate — Overview page (Step 0f + Tasks 29–31)

- **Files:** `docs/phase-7.2/VALIDATION.md` (new "Wave C part 1" section + status),
  `docs/phase-7.2/wave-c-assets/part1-all-pages/` (10 PNGs).
- **Build:**
  - **Gate runs.** `make check` → **1375 passed, 3 skipped, 136 deselected** in
    170.5 s, coverage **89.22 %** (≥ 80 %); `poetry run mypy src dashboard` →
    **0 errors**, 68 source files; dashboard subset → **559 passed**; export
    integration smoke (`test_exports.py -m integration`) → **1 passed**;
    ten-page AppTest smoke (`test_all_pages_smoke.py`) → **10 passed**.
  - **All-pages capture.** With the hardened `scripts/dashboard_screenshots.py`
    (Step 0f) and the Streamlit server running the `bba20ae` tree, captured ten
    PNGs at 1440×900 into `docs/phase-7.2/wave-c-assets/part1-all-pages/`. Every
    page shows the shell with **no `Stop` widget, spinner or skeleton** (the
    settle assertion). Per-page pass/defect lines are recorded in `VALIDATION.md`.
  - **Overview delta visible in the capture.** Six-cell KPI band in mockup order
    (sources / domains / active indicators / Gold observations ‖ derived / orphan
    with the `نیازمند بررسی` tag), the two-column `[7, 5]` row (freshness right,
    bars left) with trailing section summaries, stale-first freshness ordering,
    and the coverage table below.
  - **Computed typography (mockup vs live DOM).** `h1` 39.2 px / lh **1.4**;
    `h3` 27 px / lh **1.5**; KPI label **13 px / 500**; primary value 28 px / 600;
    secondary value **20 px**; body **1.85** (was 1.9 before this task); band
    `direction: rtl` with 6 cells; row ratio measured **1.406** vs the mockup's
    7:5. The heading rules are main-block-scoped because Streamlit's own
    `h1`/`h3` lh-1.2 rule outranks a bare element selector.
  - **Against the Wave B gate.** Wave B ended at 1351/3 (full) and 535 (subset);
    part 1 ends at 1375/3 and 559 — the **+24** is the Step 0f–31 tests and
    **nothing regressed**.
  - **Plan checkboxes.** Tasks 29–31 acceptance boxes are `[x]`; Task 32 remains
    `[ ]`.
- **Verify:** all gate commands above are green; `git status --short` clean apart
  from the new assets/docs being committed.
- **Deviations:** none new. Carry items restated for Tasks 32–34: (1) top bar has
  no surface/border; (2) English `Choose options` placeholder (adopt
  `render_filter_bar`); (3) chart legend title `label`.

## Wave C part 2 — Scope A polish (P1–P5) and Task 32

### P1 — bar order (count-descending)

- **Files:** `dashboard/page_view.py` (new pure `ordered_domain_rows` +
  `_domain_count`; `_render_domain_counts` now delegates),
  `tests/unit/dashboard/test_app_overview.py`, `docs/phase-7.2/design-system.md`
  (§14 row updated from "flagged for review" to "resolved by P1").
- **Build:** `ordered_domain_rows(domain_counts) -> list[BarRow]` sorts by
  indicator count descending, ties by the domain's **Persian display name**
  ascending (`domain_label`), which reproduces the mockup's own tie order
  (`تورم` before `رفاه` at 15; `ارز` before `بازار …` at 1). A missing or
  non-numeric count is treated as zero and never dropped; the sort is stable.
  `_render_domain_counts` keeps its name and signature (the Task 20 owner-link
  test monkeypatches it) and calls the helper.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_app_overview.py test_layout.py
    -q --no-cov` → **81 passed** (3 new: count-desc/name-asc fixture order,
    missing-count-as-zero stability, and the rendered `page_link` label order
    against the fake repository). The existing proportional-width test was
    updated to compare the widths against the sorted rows (they were previously
    zipped with the frame's own order).
  - `poetry run ruff check` / `ruff format --check` / `mypy dashboard/page_view.py`
    → clean.
- **Deviations:** none. The bar order now matches the mockup; the §14 note is
  resolved rather than carried.
- **Commit:** `16aefda`.

### P2 — secondary KPI cell width (mockup `flex: 1.35`)

- **Files:** `dashboard/components/layout.py` (new pure `kpi_column_weights`
  + `_KPI_PRIMARY_WEIGHT`/`_KPI_SECONDARY_WEIGHT`; `render_kpi_band` passes the
  weights to `st.columns`), `tests/unit/dashboard/test_layout.py`,
  `docs/phase-7.2/design-system.md` (§14 row resolved, §15 note updated).
- **Build:** `kpi_column_weights(cells)` returns `1.35` for a cell flagged
  `secondary` and `1.0` otherwise; `render_kpi_band` renders
  `st.columns(kpi_column_weights(cells))` instead of an equal-weight row. The
  ratio lives in the component (not CSS) because `st.columns` owns the geometry.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_layout.py -q --no-cov` → 55
    passed (3 new: the 1.35/1.0 spec on a mixed band, all-primary default, and a
    mixed 6-cell band still rendering every cell).
  - **Measured (live DOM, 1440 px):** the four primary cells render
    **143.85 px** and the two secondary cells **198.30 px** — a rendered ratio of
    **1.378**. The `flex-basis` percentages Streamlit derives from the weights are
    **14.9254 %** (primary) and **20.1493 %** (secondary), i.e. exactly **1.35×**;
    the rendered widths diverge from 1.35 only because Streamlit's basis is
    `calc(<pct>% - 14px)`, so a fixed 14 px gap is subtracted from every cell.
    The spec is exact; the rendered ratio is ~1.38.
- **Deviations:** none. The `1.378` rendered ratio (vs the spec's exact `1.35`) is
  an artifact of Streamlit's `calc(% - gap)` column basis, recorded here rather
  than worked around.
- **Commit:** `3dd58c0`.

### P3 — last-collection column header

- **Files:** `dashboard/i18n.py` (new `table.last_collection` = `آخرین گردآوری`),
  `dashboard/page_view.py` (`build_freshness_rows` uses the new key for its third
  column), `tests/unit/dashboard/test_app_overview.py`.
- **Build:** the Overview freshness table's header is now the mockup's
  `آخرین گردآوری`. The generic `table.collection_timestamp` (`زمان گردآوری`) is
  deliberately **not** changed: `freshness_display` and the exports keep it, so
  the two headers no longer share one wording.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_overview.py
  test_i18n.py -q --no-cov` → **44 passed** (1 new: the table uses the new key,
  the generic key is absent from its columns, and `freshness_display` still
  carries `table.collection_timestamp`). The two existing header assertions were
  updated to the new key.
- **Deviations:** none. This resolves the §14 "Freshness last-collection header"
  row (the plan's "reuse the existing key" instruction is superseded by P3).
- **Commit:** `4528e56`.

### P4 — amber stale count in the freshness summary

- **Files:** `dashboard/i18n.py` (`section.freshness_summary` becomes
  `{fresh} بهروز · :orange[{stale}] کهنه`), `tests/unit/dashboard/test_app_overview.py`
  (new `test_freshness_summary_string_colours_only_the_stale_count`),
  `docs/phase-7.2/design-system.md` (§14 "Freshness section summary" row).
- **Build:** only the stale count is wrapped in the markdown orange directive.
  The section header's trailing slot is a markdown string (`render_section_header`
  `trailing=`), so the directive is the native route to the mockup's amber
  number — no HTML fragment, no CSS hook. The theme maps `orange` to the warn
  palette (`orangeColor = #9A5B00`), so `:orange[…]` renders the mockup's amber.
  The fresh count stays uncoloured. The tuple return of `freshness_summary` and
  the empty-log behaviour are untouched: `page_view.py` still passes
  `trailing=None` when `freshness.empty`, so the empty state keeps its
  `render_empty` branch with no summary.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_app_overview.py
    tests/unit/dashboard/test_i18n.py -q --no-cov` → **45 passed** (1 new; the
    new test asserts the directive wraps the stale number only, that the fresh
    number is not wrapped, and that the string still ends with `value.stale`).
    `dashboard/page_view.py` needed no change for P4 — the summary string is the
    whole edit.
  - **Measured (live DOM).** The summary renders three runs; the `کهنه` count's
    span computes `color: rgb(154, 91, 0)` (= `--warn` / `orangeColor`), and its
    text is `۳` — the fresh count's span is the muted body colour.
- **Deviations:** the §14 doc row was written during P4 but landed in the P5
  commit (`4a5995f`) because P5's `design-system.md` edit was staged after it;
  the row is present and correct, so P4's own commit carries only the i18n key
  and the test.
- **Commit:** `c8fcb6f`.

### P5 — top bar surface, border and full-bleed

- **Files:** `dashboard/components/direction.py` (main container declares
  `--main-pad-x` and reads it for its horizontal padding; top bar gains the
  surface, bottom border and the full-bleed width/margin/padding triple),
  `tests/unit/dashboard/test_layout.py`, `tests/unit/dashboard/test_direction.py`,
  `docs/phase-7.2/design-system.md` (§9 paragraph rewritten, §14 non-bleed row
  resolved), `docs/phase-7.2/wave-c-assets/p5/` (`overview.png`,
  `topbar-live.png`, `topbar-mockup.png`, `kpi-live.png`, `kpi-mockup.png`).
- **Build:** the bar gets `background: var(--surface)` and
  `border-bottom: 1px solid var(--border)`. For the full-bleed variant the main
  container now declares `--main-pad-x: 70px` and reads it for
  `padding-left`/`padding-right`; the top bar reads the same property for
  `width`, `max-width`, `margin-inline` and `padding-inline`. The `width`/
  `max-width` pair is needed because the bar's containing block is Streamlit's
  inner `stLayoutWrapper` (already inside the main padding) and Streamlit sets
  `max-width: 100%`, so a negative margin alone shifts the bar left without
  widening it — measured `x=256, width=1044` before the width pair, i.e. an
  asymmetric bar. All four values read the one property, so they cannot drift.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_direction.py test_layout.py
    -q --no-cov` → **84 passed** (1 new: the `--main-pad-x` one-place guarantee,
    including `css.count("--main-pad-x:") == 1`; the two top-bar chrome
    assertions were updated to the new rule).
  - **Measured (live DOM).** 1440 px: bar `x=256, width=1184` (right edge 1440),
    `background: rgb(255,255,255)` (= `--surface`), `border-bottom: 1px solid
    rgb(225,229,235)` (= `--border`); `scrollWidth == clientWidth == 1440`. Bar
    content stays aligned with the page content — `breadcrumb right = 1370 =
    h1 right`, `stamp left = 326 = h1 left`. 1280 px: bar `x=256, width=1024`,
    `scrollWidth == clientWidth == 1280`. No horizontal page scroll at either
    width, so the **full-bleed variant shipped**.
  - **Visual.** `topbar-live.png` (1184×49) vs `topbar-mockup.png` (1184×48):
    both white with a bottom hairline, breadcrumb at the RTL start and the stamp
    at the far end, content aligned to the page column. Differences (all
    pre-existing, outside P5, carried to the Task 34 review): the breadcrumb
    separator is `›` live vs `/` in the mockup, the current-page crumb is not
    bold live, and the live bar is 49 px (48 px row + 1 px border) vs the
    mockup's 48 px box. `kpi-live.png` (1044×104) vs `kpi-mockup.png`
    (1104×101) re-confirm P2's wider secondary cells.
- **Deviations:** the three breadcrumb/height differences above are recorded for
  the Task 34 owner review; the surface, border and full-bleed themselves match.
- **Commit:** `4a5995f`.

### Task 32 — the Overview coverage table with filters and calendar opt-in

- **Files:** `dashboard/page_view.py` (`CoverageTable`, `build_coverage_rows`,
  `filter_coverage_frame`, `_coverage_range_cell`, `_coverage_count_cell`,
  `_label_cell`, `_optional_cell_text`, `_optional_cell_number`,
  `_exact_range_title`, `_coverage_option_label`, `_render_coverage_section`, the
  four coverage session-state keys and `_COVERAGE_DENSITIES`;
  `render_overview_page` now calls `_render_coverage_section`),
  `dashboard/components/html_table.py` (`Text.num`, `Ltr.num`/`Ltr.mono_id`,
  `TABLE_VARIANTS`, the `variant` and `wrap_headers` options, `_header_markup`,
  `_validated_variant`), `dashboard/components/direction.py` (the four `.dt.cov`
  rules and the scoped `coverage_footnote` hook), `dashboard/formatting.py`
  (`_compact_jalali_daily`, the `compact` opt-in on `range_label`,
  `RANGE_SEPARATOR` exported), `dashboard/i18n.py` (`table.indicator`,
  `table.coverage_range`, `table.observed_range`, `table.chained_rows`,
  `table.average_confidence`, `empty.no_coverage_rows`),
  `tests/unit/dashboard/test_html_table.py`, `test_formatting.py`,
  `test_app_overview.py`, `docs/phase-7.2/design-system.md` (sections 4.2, 8, 9 and
  four new section 14 rows), `docs/phase-7.2/wave-c-assets/task32/`.
- **Build:** the coverage grid is now the typed HTML table instead of
  `st.dataframe`. Ten columns in the mockup's order, with the three right-hand
  headers two-line (`wrap_headers`), the indicator name above its raw id in the
  mockup's block-level `idl` line, unit chips, and the em-dash for every null.
  - **Calendar (D3).** `build_coverage_rows` takes the calendar map as a
    parameter (default `SOURCE_CALENDAR`): a Gregorian source's range is an `Ltr`
    cell carrying the exact stored bounds in its `title`, a Jalali source's is a
    `Text` cell. `range_label(..., compact=True)` — opt-in, default unchanged —
    collapses a same-month/same-year daily Jalali range to `۱۸ – ۲۰ شهریور ۱۴۰۵`.
  - **Filter bar (Task 21's first consumer).** Three `st.selectbox` controls with
    an `None`/"همه" option filter the already-loaded frame **in memory** (no extra
    query), plus the row-count echo and an `st.segmented_control` density toggle.
    The three selections and the density are read from `st.session_state` before
    the bar renders, so the frame the table renders is the one the controls
    describe in the same run.
  - **Footnote.** `st.caption(t("table.coverage_footnote"))`, and the coverage
    section is wrapped in `st.container(key="overview-coverage-section")` so the
    section has one addressable boundary (the Task 34 per-region crops need it).
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/ -q --no-cov` → **610 passed**
    (baseline 568 after P1–P5; +42 new across the three files). `poetry run mypy
    src dashboard` → **no issues in 68 source files**. `ruff check`/`ruff format`
    clean.
  - **Measured (live DOM).** Page-level `scrollWidth == clientWidth` at **1440,
    1280 and 1024 px** (1440/1440, 1280/1280, 1024/1024), so the page never
    scrolls sideways; the coverage wrapper's `scrollWidth` stays 1169 against
    client widths 1042 / 882 / 626, so the table scrolls **inside its own box**
    (AM-26, including the Task 15 deferral). The rendered table is
    `dt cov comfortable`, 1169×3450 px, **54 rows**. Header cells measure
    `font-size: 12px`, `white-space: normal`, `vertical-align: bottom`; the first
    cell `min-width: 230px`; body cells 13.5px. Density toggle measured
    **64 px → 60 px** row height on the same table.
  - **Visual.** `coverage-viewport.png` (1440×900) plus element-by-element crops
    against the mockup: `header-live.png` (1056×50) vs `header-mockup.png`
    (1104×28) — same title, same RTL start; `filter-bar-live.png` (1056×73) vs
    `filter-bar-mockup.png` (1104×55) — same control order (domain/source/frequency
    at the RTL start, the count echo and the density toggle at the far end, "راحت"
    selected); `table-live.png` / `table-live-top.png` vs `table-mockup.png`
    (1102×493) — same ten headers, same two-line headers, same id line, and the
    same per-row values (`۱۹۶۰ – ۲۰۲۵`, `فروردین ۱۳۶۱ – بهمن ۱۴۰۱`,
    `۱۸ – ۲۰ شهریور ۱۴۰۵`, `—` for the SCI row's observed/count/chained/
    confidence cells); `footnote-live.png` vs `footnote-mockup.png` — same
    sentence, same RTL start.
- **Deviations:** four, all recorded in design-system section 14 and carried to the
  Task 34 review — (a) the three filter selects are native `st.selectbox` controls,
  not the mockup's 32 px inline-label chips (D13; the bar is 73 px vs 55 px);
  (b) the real table needs 1169 px in a 1042 px wrapper, so the last column is
  partly scrolled out where the mockup's shorter sample fits (AM-26 accepts the
  in-box scroll); (c) the footnote reads `راهنمای هر خانه` where the mockup says
  `tooltip`, the Task 13 key's Persian wording; (d) a native `st.caption` inherits
  the LTR main block, so the Persian footnote hugged the left edge — **fixed
  scoped** by the `coverage_footnote` hook, with the shell-wide caption gap filed
  for Task 34 rather than fixed (a global rule would move every un-migrated page).
  One addition beyond the plan's key list: `table.indicator` (`شاخص`), the mockup's
  own first header, and `empty.no_coverage_rows` for the filtered-to-zero state.
- **Commit:** `3191e2f`.

### Wave C part 2a gate — Scope A close-out

- **Files:** `docs/phase-7.2/VALIDATION.md` (new "Wave C part 2a" section + the
  status line), `docs/phase-7.2/wave-c-assets/part2a-all-pages/` (11 PNGs: the ten
  registry pages plus `overview-coverage.png`), plus the five P1–P5 `Commit:`
  lines above filled in with their real hashes.
- **Build:**
  - **Gate runs.** `make check` → **1426 passed, 3 skipped, 136 deselected** in
    177.2 s, coverage **89.22 %** (≥ 80 %); `poetry run mypy src dashboard` →
    **0 errors**, 68 source files; dashboard subset → **610 passed**; export
    integration smoke (`test_exports.py -m integration`) → **1 passed**;
    ten-page AppTest smoke (`test_all_pages_smoke.py`) → **10 passed**.
  - **All-pages capture.** The Streamlit server was restarted against the
    committed `3191e2f` tree (it does not hot-reload), then
    `scripts/dashboard_screenshots.py --out-dir
    docs/phase-7.2/wave-c-assets/part2a-all-pages` captured ten 1440×900 PNGs.
    Every page shows the shell with **no `Stop` widget, spinner or skeleton** (the
    Step 0f settle assertion). An eleventh scrolled capture,
    `overview-coverage.png`, shows the coverage section (filter bar, two-line
    headers, em-dash nulls) in the committed tree.
  - **Overview delta visible in the capture (vs part 1).** Top bar now white with
    a bottom hairline (P5); KPI band with the wider secondary group (P2); the
    freshness header reads `آخرین گردآوری` (P3) and the stale count is amber
    (P4); the domain bars read **15, 15, 8, 4, 3, 2, 1, 1, 1** (P1, was
    unsorted); the coverage `st.dataframe` is gone.
  - **Against the part 1 gate.** Part 1 ended at 1375/3 (full) and 559 (subset);
    part 2a ends at 1426/3 and 610 — the **+51** is the P1–P5 and Task 32 tests,
    and **nothing regressed**. Per-page pass/defect lines are in `VALIDATION.md`;
    the only per-page defect is the pre-existing `label` legend title on `gdp`.
  - **Plan checkboxes.** Tasks 29–32 acceptance boxes are now all `[x]`.
- **Verify:** all gate commands above are green; `git status --short` clean apart
  from the assets/docs being committed.
- **Deviations:** none new in the gate itself. The four Task 32 deviations and the
  three P5 breadcrumb/height differences are restated in `VALIDATION.md` under
  "Accepted deviations and carry items" and carried to the Task 34 review.
- **Commit:** this entry is committed with the part 2a gate commit.

## Wave C part 2 — Scope B (Tasks 33–34)

### Task 33 — page header + methodology callout and the D11 guard

- **Files:** `dashboard/page_view.py` (`render_overview_page` opens with
  `render_page_header`; the conditional empty-catalog warning becomes
  `render_callout`), `dashboard/components/layout.py` (`render_page_header` gains
  an optional `label_key`), `tests/unit/dashboard/test_layout_guard.py` (new, 10
  tests), `tests/unit/dashboard/test_layout.py` (2 new header-label tests),
  `tests/unit/dashboard/test_app_overview.py` (the disclaimer assertion becomes a
  substring check), `docs/phase-7.2/design-system.md` (§4.1 signature + worked
  example, §11 row, §12 status, §14 new row, §15 item),
  `docs/plans/phase-7.2-dashboard-redesign.md` (Task 33 acceptance boxes),
  `docs/phase-7.2/wave-c-assets/task33/`.
- **Build:**
  - **The header.** `render_overview_page` now opens with
    `render_page_header("page.overview", callout_key="warn.forecasts_indistinguishable", label_key="note.methodology_label")`,
    replacing the raw `st.title` + `st.warning`. The conditional
    `st.warning(t("warn.catalog_empty"))` on the empty-catalog path becomes
    `render_callout("warn.catalog_empty")` — same warn tone, same text, same early
    return, but no longer a raw call the guard would flag.
  - **The label.** The mockup's callout carries a bold `یادداشت روش‌شناسی` prefix
    (`.note b{font-weight:600}`). `render_page_header`'s Task 18 signature had no
    way to pass one, so it gained an optional `label_key` forwarded straight to
    `render_callout`. The parameter is additive and defaults to `None`, so the
    ratified Task 18 shape is unchanged for every other caller — **the plan's
    Task 33 file list named only `page_view.py` and the new guard**, and this
    `layout.py` addition is recorded as a §14 deviation rather than a silent
    expansion of scope.
  - **The guard.** `tests/unit/dashboard/test_layout_guard.py` walks the migrated
    functions with an AST, exactly as `test_literal_guard.py` walks the dashboard
    tree. `MIGRATED_PAGES` maps module → **function names** (function-scoped
    because every page composition lives in one module, AM-14) and starts with the
    Overview: `render_overview_page`, `_render_domain_counts`,
    `_render_coverage_section` — the page's whole composition, not just its entry
    call. `BANNED_FUNCTIONS` is exactly the §12 list (`st.title`, `st.metric`,
    `st.warning`/`st.info`/`st.error`) plus the `unsafe_allow_html` keyword.
    `LAYOUT_WHITELIST` is the four shared-component modules, and
    `test_the_whitelist_matches_the_design_system_contract` derives the §12 list
    from the document and asserts set equality, so the guard and the contract
    cannot drift.
- **Verify:**
  - `poetry run pytest tests/unit/dashboard/test_layout_guard.py
    tests/unit/dashboard/test_app_overview.py tests/unit/dashboard/test_layout.py
    -q --no-cov` → **117 passed**. Full dashboard subset → **622 passed** (was
    610; **+12** = the 10 guard tests and the 2 header-label tests).
    `poetry run mypy src dashboard` → **no issues in 68 source files**;
    `ruff check`/`ruff format` clean.
  - **Guard is not vacuous, in both directions.** `test_no_layout_violation_in_a_migrated_function`
    runs the guard over the real `page_view.py` and finds nothing;
    `test_guard_flags_a_raw_metric_in_a_migrated_function` plants
    `st.metric("Sources", 7)` in a synthetic `render_overview_page` and gets
    `("render_overview_page", "st.metric")` at line 3;
    `test_guard_ignores_a_banned_call_outside_a_migrated_function` proves the
    scoping (the same call in `render_gdp_page` is **not** reported), and
    `test_guard_ignores_a_banned_call_in_an_unlisted_module` proves a module
    absent from the map is not scanned at all.
  - **Measured (live DOM, 1440 px).** The callout container is
    `st-key-callout-warn-forecasts_indistinguishable`; the bold run is
    `یادداشت روش‌شناسی` at `font-weight: 600`, `color: rgb(154, 91, 0)`
    (= `--warn`); the alert computes `background: rgb(251, 241, 220)`
    (= `--warn-bg`), `border-inline-start: 3px solid currentColor`, `gap: 10px`,
    `padding: 14px`. The alert's full text is the label, a space, then the
    disclaimer. `scrollWidth == clientWidth == 1184` — no sideways page scroll.
  - **Visual.** `header-live.png` (1044×150) shows the `h1` (`مرور کلی`, RTL start)
    above the amber callout with the info glyph and the bold label;
    `methodology-callout-live.png` (1044×80) vs `methodology-callout-mockup.png`
    (1915×65): same sentence, same bold prefix, same amber tint, same glyph at the
    RTL start. Differences (all the callout component's ratified Task 17 styling,
    outside Task 33): the live text wraps to two lines where the mockup's wider
    crop fits one; the accent bar is `currentColor` (`--warn`, `#9A5B00`) vs the
    mockup's lighter `#C98A1B`; the live font is the native alert's 14px/21px vs
    the mockup's 13.5px/1.8; padding 14px vs 10px 14px.
- **Deviations:** one — `render_page_header` gained `label_key`, which the plan's
  Task 33 file list did not anticipate (recorded in design-system §14). The
  callout's remaining pixel differences are Task 17's ratified native-alert
  styling and are carried to the Task 34 review, not fixed here.
- **Commit:** recorded in the "Wave C part 2b gate" entry below.

### Task 34 — the AM-23 owner visual review (prepared, not signed off)

- **Files:** `docs/phase-7.2/validation/reference-overview.md` (new),
  `docs/phase-7.2/wave-c-assets/task34/` (17 PNGs),
  `docs/plans/phase-7.2-dashboard-redesign.md` (Task 34's first acceptance box
  ticked, with a note that the other two are the owner's act),
  `docs/phase-7.2/VALIDATION.md` (status line + the "Wave C part 2b" section),
  `docs/phase-7.2/README.md` (status → "Wave C awaiting owner review").
  **No code changed.**
- **Build (AM-23):**
  - **Evidence.** Captured the Overview at **1440×2200** (`overview-1440x2200.png`,
    the requested frame), the whole page at 1440×4900 (the page is 4637 px tall),
    and per-region crops — top bar, header (title + callout), callout, KPI band,
    the two-column row, and the coverage section — each paired with a
    like-for-like crop of the mockup PNG cut at the same band boundaries
    (`region-*-mockup.png`). `region-coverage-section-full.png` (1044×3613) shows
    the whole coverage section, which does not fit in 2200 px.
  - **Method.** The mockup PNG is a scaled render (2520 px wide, content column
    1915 px), so pixel equality is not the test. Each row is judged
    **structurally** (same elements, order, counts, RTL start), **token-level**
    (computed colours/weights/sizes against the mockup's CSS declarations) and
    **measured** (`getBoundingClientRect`/`getComputedStyle`).
  - **The comparison.** `reference-overview.md` walks all **34 rows** of the
    plan's mockup traceability table, each with live evidence and a verdict:
    **30 PASS, 4 PASS-with-approved-deviation, 1 FIX recommended**. No element of
    the mockup is missing and none was silently dropped.
  - **Findings needing the owner.** **F1** the main content padding is 70 px where
    the mockup's `.wrap` uses 40 px, so the content column is 60 px narrower at
    every width (measured 1044 vs 1104 at 1440 px; 1220 vs 1280 at 1920 px) —
    recommend **FIX** as its own shell task, since the 70 px restates Streamlit's
    own default and a one-line change moves every page at once. **F2** the
    breadcrumb separator is `،` where the mockup writes `/` and the current crumb
    is not bold — recommend **FIX** with F1. **F3** the `gdp` legend title reads
    `label` (pre-existing) — recommend **FIX** against the chart builders. **F4**
    the English `Choose options` placeholder on un-migrated pages — recommend
    **FIX in Waves D–G**. **F5** the shell-wide `st.caption` LTR direction —
    recommend **FIX** with F1.
  - **Recommended approvals (A1–A9).** The callout's native-alert styling; the KPI
    tooltip marker; the native filter selects; the coverage table's in-box scroll;
    the footnote wording; the 49 px bar (48 px row + 1 px border); the freshness
    counts and the 54-row table (both **data**, not design); and Task 33's
    `label_key` addition.
  - **Measured shell geometry (live, 1440 px).** Sidebar exactly **256 px**;
    main block `x=256, w=1184, max-width: 1360px`; content column `x=326, w=1044`;
    top bar `x=256, w=1184, h=49`, `background: rgb(255,255,255)`; `h1` 28 px /
    lh 1.4; KPI band `1044×103`; row `1044×462` at the measured 1.406 ratio;
    coverage section `1044×3613`; `scrollWidth == clientWidth == 1184` at 1440 px
    and `1664 == 1664` at 1920 px, where the block measures exactly 1360 px so the
    content cap is real.
- **Verify:** the review document and all 17 PNGs are in place; every traceability
  row carries a verdict; the plan's Task 34 box 1 is ticked and boxes 2–3 are left
  for the owner; `git status --short` clean apart from the assets/docs committed
  here.
- **Deviations:** none new in code. Task 34 **deliberately applies none of F1–F5**
  — it is the decision document, and the fixes are shell/chart-builder work that
  must not ride along with a review.
- **Commit:** recorded in the "Wave C part 2b gate" entry below.

### Wave C part 2b gate — Scope B close-out

- **Files:** `docs/phase-7.2/VALIDATION.md` (the "Wave C part 2b" section + the
  status line), `docs/phase-7.2/README.md` (status), plus the Task 33 entry above.
- **Build:**
  - **Gate runs.** `make check` → **1438 passed, 3 skipped, 136 deselected** in
    173.5 s, coverage **89.22 %** (≥ 80 %); `poetry run mypy src dashboard` →
    **0 errors**, 68 source files; the Task 33 verify → **117 passed**; the
    dashboard subset → **622 passed** (part 2a ended at 610); the export smoke →
    **1 passed**; the ten-page AppTest smoke → **10 passed**;
    `ruff check`/`ruff format` clean.
  - **Against part 2a.** Part 2a ended at 1426/3 (full) and 610 (subset); part 2b
    ends at 1438/3 and 622. The **+12** is the 10 D11-guard tests and the 2
    header-label tests; **nothing regressed**.
  - **Plan checkboxes.** Task 33's acceptance boxes are `[x]`; Task 34's first box
    is `[x]` and the two owner boxes are left `[ ]` by design.
  - **README.** Status is now "Wave C awaiting owner review", with the sign-off
    recorded as pending and Waves D–H blocked on it.
- **Verify:** all gate commands above are green; `git status --short` clean apart
  from the assets/docs being committed.
- **Deviations:** none new.
- **Commit:** this entry is committed with the part 2b gate commit.

**Wave C is complete except for the AM-23 owner sign-off. Per the execution rules,
this session stops here and does not start Task 35.**

---

## Wave D — generic domain explorer (A2)

Wave D covers the four A2 pages (`gdp`, `trade_energy`, `fx_gold`, `labor`):
Tasks 35 (composition), 36 (headers + guard) and 37 (owner visual review).

## Step 0a — Gregorian range cells take the table body font

- **Files:** `dashboard/components/direction.py` (`_TABLE_RULES`: the `.dt .ltr`
  rule split into `.dt .ltr` + `.dt .ltr.idl`), `tests/unit/dashboard/test_direction.py`
  (new `test_ltr_range_cells_inherit_the_body_font_but_ids_stay_mono`),
  `docs/phase-7.2/design-system.md` (§8 typed-cell model),
  `docs/phase-7.2/wave-d-assets/step-0a/{before,after}/*.png` (4 new).
- **Build:** the Overview coverage table renders a Gregorian range
  (World Bank / IMF / EIA) as an `Ltr(num=True)` cell — `<bdi class="ltr num">` —
  and a Jalali range as a `Text(num=True)` cell. The bare `.dt .ltr` rule carried
  the mockup's **id** style (`font-family: var(--font-mono); font-size: 11.5px`),
  so the Gregorian ranges rendered smaller than the Jalali ranges and the count
  cells. The mockup renders those ranges as a plain `td.num`
  (`overview-redesign-mockup.html:215`: `<td class="num">۱۹۶۰ – ۲۰۲۵</td>`) and
  reserves `.ltr` for the id (`<bdi class="ltr idl">`), so the mono/11.5 px style
  now hangs off `.dt .ltr.idl` and the bare rule keeps only the LTR direction,
  `unicode-bidi: isolate`, the inline-block box and the 24ch ellipsis. Direction,
  ordering, tooltips and every other column are unchanged; the unit chip keeps
  its own mono 11.5 px rule.
- **Measured (live app, 1440 px, coverage table, `getComputedStyle`)**
  — identical for the Gregorian range, the Jalali range and the count cell after
  the fix:

  | Cell | `font-family` | `font-size` | `font-weight` | `line-height` | `letter-spacing` | direction / bidi |
  |---|---|---|---|---|---|---|
  | **Before** Gregorian range (`bdi.ltr.num`) | `"DejaVu Sans Mono", monospace` | **11.5 px** | 400 | 17.825 px | normal | ltr / isolate |
  | **Before** Jalali range (`span.num`) | Vazirmatn, IRANSans, Tahoma, … | **13.5 px** | 400 | 20.925 px | normal | rtl / normal |
  | **Before** count (`span.num`) | Vazirmatn, IRANSans, Tahoma, … | **13.5 px** | 400 | 20.925 px | normal | rtl / normal |
  | **After** Gregorian range | Vazirmatn, IRANSans, Tahoma, … | **13.5 px** | 400 | 20.925 px | normal | ltr / isolate (unchanged) |
  | **After** Jalali range | Vazirmatn, IRANSans, Tahoma, … | 13.5 px | 400 | 20.925 px | normal | rtl / normal |
  | **After** count | Vazirmatn, IRANSans, Tahoma, … | 13.5 px | 400 | 20.925 px | normal | rtl / normal |
  | **After** indicator id (`bdi.ltr.idl`) | `"DejaVu Sans Mono", monospace` | 11.5 px | 400 | 17.825 px | normal | ltr / isolate |

  The Gregorian range gained **+2 px** of font size and switched family from the
  mono stack to Vazirmatn, so it now matches the Jalali range and the count cell
  exactly; the id is byte-identical to before.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_direction.py -q --no-cov`
  → **30 passed**; the dashboard subset → **623 passed** (622 before, +1 new
  test); `poetry run mypy src dashboard` → **0 errors**; `ruff check`/`ruff
  format --check` clean. Before/after crops of one World Bank row and one TGJU
  row are in `wave-d-assets/step-0a/`: the TGJU (Jalali) row is byte-identical
  and only the two Gregorian range cells in the World Bank row change size.
- **Deviations:** none new. The remaining difference between a Gregorian (LTR)
  and a Jalali (RTL) range cell is **direction only**, which is the D3 bidi
  decision and stays as recorded (the owner lists it as an optional Wave H
  polish candidate).
- **Commit:** this entry is committed with the Step 0a commit.

## Step 0b — Wave C AM-23 sign-off recorded

- **Files:** `docs/phase-7.2/validation/reference-overview.md`,
  `docs/phase-7.2/VALIDATION.md`, `docs/phase-7.2/README.md`,
  `docs/plans/phase-7.2-dashboard-redesign.md` (Task 34 boxes + Deferred Scope
  items 15–16), `docs/phase-7.2/execution-log.md`.
- **Build (docs only, no code):** the owner's Task 34 decisions are recorded
  verbatim in a new `reference-overview.md` §6a and summarised in a new
  `VALIDATION.md` "Wave C part 2c" section:
  - **Owner sign-off: APPROVED**; deviations **A1–A9** approved as recommended.
  - **Fixed on the owner's request:** Gregorian range font size (Step 0a,
    `a239d2f`).
  - **Scheduled:** **F3** (chart legend title `label`) and **F4** (English
    "Choose options" placeholder) in Waves D–G, starting with Task 35.
  - **Not requested now** (optional Wave H polish candidates, **not scheduled**):
    F1 content padding 70 px vs 40 px; F2 breadcrumb separator and bold current
    crumb; F5 shell-wide `st.caption` direction; F7 no-wrap in the short
    categorical coverage columns; the direction difference between Gregorian
    (LTR) and Jalali (RTL) range cells.
  - **ETL/catalog findings** (presentation correct, recorded as plan Deferred
    Scope 15–16): D1 the TGJU snapshot rows declare a coverage window
    (`۲۰ – ۲۰ شهریور`) narrower than the observed range (`۱۸ – ۲۰ شهریور`);
    D2 several SCI monthly rows declare coverage but have no Gold observations.
  - The plan's Task 34 boxes 2 and 3 are ticked; the README status is now
    "Wave C complete; Wave D in progress".
  - **F7 is introduced by this record** (it was not in the prepared review) and
    the owner's numbering **skips F6**; no F6 finding was raised, so the label is
    left unassigned rather than reused. Flagged in §4 "F6 — not raised" and in
    the final report.
- **Verify:** docs-only; `git status --short` shows only the four documents and
  this log. The Step 0a gate results (mypy 0 errors, dashboard subset 623
  passed, ruff clean) stand unchanged.
- **Deviations:** none new in code. The `F6` numbering gap is recorded rather
  than invented.
- **Commit:** this entry is committed with the Step 0b commit.

## Wave D — Task 35: the generic domain composition migrates to the layout contract

- **Files:** `dashboard/page_view.py` (`render_domain_body`, `_render_series_section`,
  `_render_scaled_chart`, `_render_capped_rows`, `_render_market_figure_and_rows`,
  `_render_chain_linking_section`), `dashboard/components/quality.py`
  (`build_quality_rows`, `QualityTable`, `render_quality_summary`),
  `dashboard/components/tables.py` (`OBSERVATIONS_ROW_HEIGHT`),
  `dashboard/components/filters.py` (F4 placeholders),
  `dashboard/components/direction.py` (F3 legend title),
  `dashboard/components/layout.py` (`render_callout(body=…)`), `dashboard/i18n.py`
  (`section.chart`, `section.quality`, `filter.placeholder`),
  `docs/phase-7.2/design-system.md`, and the tests
  (`test_quality.py`, `test_app_labor.py`, `test_derived_series.py`,
  `test_scaling.py`, `test_filters.py`, `test_charts.py`).
- **Build (AM-10):** the A2 archetype is now composed from the shared components.
  - **Quality table → the shared RTL HTML table (D1).** `render_quality_summary`
    no longer calls `st.dataframe`; `build_quality_rows` turns the frame into
    typed cells and `render_html_table` renders it. The values are produced by
    `localize_table_frame` — the same localizer the observation grid and the
    exports use — so **every column, value, Persian digit, Jalali date and
    em-dash is byte-identical** to the old grid; only the presentation changes.
    The indicator id is an `Ltr` cell (isolated LTR token) and the
    `NUMBER_COLUMNS` columns are `Text(num=True)` (tabular figures).
  - **Variant choice (measured).** The summary is eleven columns, so it uses the
    `coverage` variant. Measured in Chromium at the page's 1042 px column with the
    real markup: `default`/comfortable **1324 px** and `default`/compact
    **1242 px** both overflow (sideways scroll); `coverage` **1040 px** fits, so
    all eleven columns are visible without scrolling. `.dt.cov` is exactly the
    variant for a wide table with a name column.
  - **Section headers.** `_render_series_section` now renders
    `render_section_header("section.chart")` above the chart-mode control and the
    figure, and `render_section_header("section.quality")` above the summary; the
    observations stay in their `st.expander`. Chart mode, filters, downloads,
    row cap and values are untouched.
  - **Shared empty states.** Every `st.info` in the composition became
    `render_empty` (`empty.no_indicators_for_page`, `empty.select_indicators`,
    `empty.no_observations`), and the two value-carrying notices (chart-mode
    fallback, row-cap hint) became `render_callout(…, body=…)`, which is the
    pattern `render_callout`'s docstring already documented for them. The row-cap
    callout takes a `container_key` derived from the caller's key prefix, because
    the Market page renders several grids in one run and a repeated container key
    raises.
  - **Observations grid density (D1).** `st.dataframe(row_height=…)` is now set
    from the new `OBSERVATIONS_ROW_HEIGHT` = 40 px, the `.dt.compact` row height,
    so a dense grid and a dense HTML table read at one density. No row, column or
    value changes.
  - **F3 — legend title.** `apply_plotly_typography` now blanks
    `legend_title_text`. Every time-series builder passes `color="label"` (the
    Persian display-label column), and Plotly Express names the legend after that
    column, so the rendered legend carried a literal English `label` heading.
    Fixed at the shared lever (the figure-level `legend.title` outranks the
    template's), so **every** chart that funnels through it is fixed at once:
    `build_time_series_chart`, `build_overlay_chart`,
    `build_small_multiples_chart`, `build_survey_year_chart` and, through them,
    every page that draws a time series — the four Wave D pages plus Inflation,
    Welfare, Market and Correlation. Series names and colours are unchanged.
  - **F4 — placeholder.** `render_filters` passes
    `placeholder=t("filter.placeholder")` ("انتخاب کنید") to its four
    multiselects and its two Jalali selectboxes, so Streamlit's English default
    ("Choose options") can no longer appear. Affected pages (every page that
    renders `render_filters`): gdp, trade_energy, fx_gold, labor, inflation,
    welfare, market, correlation, catalog. The Overview is unaffected — its
    coverage bar uses explicit "همه" options and no placeholder.
- **Verify:** the plan's command —
  `poetry run pytest tests/unit/dashboard/test_app_economy.py
  tests/unit/dashboard/test_app_trade_welfare.py
  tests/unit/dashboard/test_app_fx_gold.py tests/unit/dashboard/test_app_labor.py
  tests/unit/dashboard/test_quality.py -q --no-cov` → **66 passed**; the wider dashboard
  subset → **628 passed** (623 before, +5 new tests); `make check` → **1444
  passed, 3 skipped**, coverage **89.22 %**, `ruff` clean, `mypy src dashboard`
  **0 errors**; the export smoke → **1 passed**.
- **Visual evidence** (`docs/phase-7.2/wave-d-assets/`): ten-page 1440×900 sets
  `partA-all-pages-before/` (pre-Task-35) and `partA-all-pages/` (post-Task-35),
  plus scrolled detail shots of the four pages in
  `task-35/before-scroll/` and `task-35/after-scroll/` (four offsets each). A
  pixel diff of the ten pairs:
  - `overview` — **0 changed pixels** (untouched).
  - `correlation`, `catalog`, `inflation`, `welfare`, `market` — **1977–2636
    changed pixels**, all inside one 87 px-wide strip at x≈335–422: the six filter
    widgets' placeholder text (F4). Nothing else on those pages moves.
  - `gdp`, `trade_energy`, `fx_gold`, `labor` — the four Wave D pages: the F4
    placeholders plus the new section headers, the HTML quality table and (for
    the two pages with no default selection) the shared empty-state callout.
  - Read from the crops: the GDP page's quality table now shows all eleven
    columns with Persian digits (`۶۶`, `۰`, `خیر`, `سالانه`) and no sideways
    scroll; the Labor page's single-quarter row reads `۱ / ۱ / خیر / ۰` with the
    Jalali dates; the chart legend no longer carries the `label` heading.
- **Deviations / interpretations recorded:**
  1. **"one filter bar" is the shared `render_filters`.** The archetype line
     says "filter bar"; the domain filter set is `render_filters`, which renders
     its own stacked native widgets (the `render_filter_bar` component lays out
     the Overview coverage bar). Task 35 does not restructure it: the plan's file
     list does not include a filter-bar refactor, no mockup prescribes a
     domain-page bar, and the widgets, labels, keys and returned `FilterState` are
     unchanged. Flagged for the owner's Task 37 review.
  2. **`_render_capped_rows` gained a required `key_prefix`** (the callout
     container key). `test_scaling.py`'s probe passes `"capped-probe"`; the three
     production call sites pass their own prefix. One line, no behaviour change.
  3. **`RecordingStreamlit` in `test_quality.py` gained an `html` recorder.**
     The plan states `test_quality.py` "stays green (pure-helper assertions
     only)"; it in fact has three render-path tests using that stub, and
     `render_html_table` emits through `html_table`'s own `st`, so the stub is
     extended (and the module patched) rather than the render path left
     uncovered. Three new tests cover the builder and the markup.
  4. **The quality table's id cell is capped at 24ch** by the shared
     `.dt .ltr` rule, so `SCI.UNEMPLOYMENT.QUARTERLY` renders as
     `SCI.UNEMPLOYMENT.QUAR...`. The cell now carries the full id as its `title`,
     so the truncated token is recoverable on hover — the same tooltip practice
     the coverage table's range cells use, and the same 24ch cap the coverage
     table's id line already has. Raised for the owner's review rather than
     widening a global rule.
  5. **`render_domain_page` still calls `st.title`.** Task 36 routes the four
     pages' titles and the FX/Gold and Labor caveats through
     `render_page_header`/`render_callout` and enables the D11 guard for the
     migrated functions; Task 35 deliberately stops at the composition.
  6. **Observation (not fixed, out of scope):** `scripts/dashboard_screenshots.py`
     `neutralise()` scrolls `[data-testid="stMainBlockContainer"]`, which is not
     the scroll container (`stMain` is), so its scroll-to-top is a no-op. The
     captures are still correct because each page navigation starts at the top;
     recorded here for the script's owner (Task 47).
- **Commit:** `054af58`.

## Wave D part A gate — Step 0 + Task 35 closed

- **Files:** `docs/phase-7.2/VALIDATION.md` (new "Wave D part A" section),
  `docs/phase-7.2/execution-log.md`.
- **Gate:** `make check` → **1444 passed, 3 skipped**, coverage **89.22 %**
  (≥ 80 %), `ruff check`/`ruff format --check` clean; `poetry run mypy src
  dashboard` → **0 errors**, 68 source files; `poetry run pytest
  tests/unit/dashboard -q --no-cov` → **628 passed** (623 at the Step 0a
  baseline, +5 new); `poetry run pytest tests/unit/dashboard/test_exports.py -m
  integration -q --no-cov` → **1 passed**; all-pages smoke
  (`test_all_pages_smoke.py`, in the dashboard subset) green.
- **Visual evidence:** the hardened ten-page capture script
  (`scripts/dashboard_screenshots.py`) wrote `wave-d-assets/partA-all-pages/`
  (post-Task-35) against `wave-d-assets/partA-all-pages-before/` (pre-Task-35),
  with four-page scrolled detail crops in `wave-d-assets/task-35/`. A pixel diff
  of the ten pairs isolates the change exactly: Overview 0 px; the five other
  non-Wave-D pages 1977–2636 px inside one placeholder strip; the four Wave D
  pages the full composition change.
- **Carry into Scope B (Tasks 36–37):** the four pages' titles and the FX/Gold
  and Labor caveats are still raw (`render_domain_page`'s `st.title`,
  `render_fx_gold_page`, `render_labor_page`); the D11 guard is not yet enabled
  for them.
- **Commit:** this entry is committed with the Wave D part A gate commit.

## Wave D — Task 36: the domain-page headers migrate, and the D11 guard covers A2

- **Files:** `dashboard/page_view.py` (`render_domain_page`, `render_fx_gold_page`,
  `render_labor_page`), `dashboard/pages/3_GDP_Economy.py`,
  `dashboard/pages/4_Trade_Welfare_Energy.py`,
  `tests/unit/dashboard/test_layout_guard.py`, `docs/phase-7.2/design-system.md`.
- **Build:** each of the four pages now opens with the shared page header.
  - `render_domain_page(title, …)` became `render_domain_page(title_key, …)` and
    calls `render_page_header(title_key)`; the two page modules pass the catalog
    key (`"page.gdp"`, `"page.trade_energy"`) instead of `t(...)`, so the title
    resolves in exactly one place. Their rendered output is unchanged —
    `render_page_header` calls `st.title(t(key))`.
  - `render_fx_gold_page` — `st.title` + `st.warning` became
    `render_page_header("page.fx_gold", callout_key="warn.tgju_snapshot")`.
  - `render_labor_page` — `st.title` + `st.info` became
    `render_page_header("page.labor", callout_key="warn.labor_publication",
    tone="info")`, and its own catalog-empty `st.info` became
    `render_empty("empty.no_indicators_for_page")` (the guard found it; it was the
    last raw alert in a migrated path).
  - `MIGRATED_PAGES` grows by the A2 archetype's whole composition:
    `render_domain_page`, `render_domain_body`, `_render_series_section`,
    `_render_scaled_chart`, `_render_capped_rows`, `render_fx_gold_page`,
    `render_labor_page`.
- **Review — caveat text vs the Task 17 bold label.** The TGJU and Labor caveats
  are routed **without** a `label_key`, so their rendered text is byte-identical
  to before and every existing assertion stands unchanged: the component-level
  `test_layout.py::test_page_header_honours_the_callout_tone` already pins
  `render_page_header("page.labor", callout_key="warn.labor_publication",
  tone="info")` to exactly `[t("warn.labor_publication")]` in `app.info`, and
  `test_app_labor.py`'s `in [info.value …]` check matches it. The bold label stays
  the Overview methodology callout's feature (Task 33): inventing Persian label
  copy for these two caveats would be new product copy, not a migration.
- **The four page modules.** `3_GDP_Economy.py`, `4_Trade_Welfare_Energy.py`,
  `5_FX_Gold.py` and `10_Labor.py` are thin delegates: no function of their own,
  no Streamlit import, one call to a migrated composition function. The plan asks
  to "add the four page modules … to the mapping", but the guard is
  function-scoped and these modules contain no function, so the equivalent is two
  new tests that pin the shape: `test_the_four_a2_page_modules_are_thin_delegates`
  (no `FunctionDef`, no `st.` access, exactly one call, and that call is a listed
  entry point) and `test_the_guard_covers_the_a2_archetype` (the listed names exist
  in the module, so a rename cannot leave the guard checking a stale name). A page
  module that grows a composition of its own now fails instead of silently
  escaping the guard.
- **Verify:** the plan's command —
  `poetry run pytest tests/unit/dashboard/test_layout_guard.py
  tests/unit/dashboard/test_app_economy.py
  tests/unit/dashboard/test_app_trade_welfare.py
  tests/unit/dashboard/test_app_fx_gold.py tests/unit/dashboard/test_app_labor.py
  -q --no-cov` → **41 passed**; the dashboard subset → **630 passed** (628 before,
  +2 new guard tests); `make check` → **1446 passed, 3 skipped**, coverage
  **89.22 %**; `poetry run mypy src dashboard` → **0 errors**; `ruff
  check`/`ruff format --check` clean; the export smoke → **1 passed**. Grep of the
  four page modules for `st.` / `streamlit` → none.
- **Visual evidence** (`docs/phase-7.2/wave-d-assets/`): the ten-page 1440×900 set
  `partB-all-pages/` (post-Task-36), diffed against `partA-all-pages/`
  (post-Task-35), plus four-page scrolled crops in `task-36/after-scroll/`.
  - `correlation`, `catalog`, `inflation`, `welfare`, `market`, `gdp`,
    `trade_energy` — **0 changed pixels**. The two `render_domain_page` pages are
    byte-identical, confirming `render_page_header` reproduces `st.title`.
  - `fx_gold` — 5980 px inside y 198–252: the amber TGJU caveat callout (accent bar
    and glyph) replacing the plain `st.warning`.
  - `labor` — 12774 px inside y 198–277: the blue SCI caveat callout replacing the
    plain `st.info` (taller because the caveat wraps to two lines).
  - `overview` — 819 px in three small digit regions (rows 531–539, 583–594,
    844–855) at the freshness table's relative-age column. **Not a code change:**
    `relative_time_label` floors the elapsed seconds, and the three collections
    stamped 19:44 / 19:43 / 19:42 UTC on 2026-09-13 crossed their exact 8/10-day
    boundary at 19:44 UTC — between the Task 35 capture (≈19:13 UTC) and this one.
    The Overview code path is untouched (its Task 35 before/after diff was 0 px).
- **Deviations:** none in behaviour. The `MIGRATED_PAGES` page-module question
  above is the one interpretation recorded.
- **Commit:** this entry is committed with the Task 36 commit.

---

## Wave D — Task 37 (owner visual review — generic domain explorer)

- **Files:** `docs/phase-7.2/validation/archetype-domain.md` (new),
  `docs/phase-7.2/README.md` (status → "Wave D awaiting owner review").
- **Build:** walked the four A2 pages (GDP, Trade & Energy, FX & Gold, Labor) in
  the browser against the design system's page-layout contract (§11–§12) and
  against the Overview, element by element, and wrote the review. The document
  carries a 16-row contract matrix (verdicts MATCH / DEVIATION / DEFECT / N/A per
  the four pages), a cross-page consistency table, an Overview comparison, the
  F3/F4 verification, the defect list and the owner checklist ending
  `Owner sign-off: PENDING`.
- **Result — 14 MATCH, 1 DEVIATION, 1 N/A, 0 layout defects:**
  - MATCH: page header, section headers, empty states, no raw alerts, no
    `unsafe_allow_html`, one callout slot, F4 placeholder, F3 legend title, the
    HTML quality table, the native observations grid, table semantics, escaping,
    `t()` coverage, CSS scoping.
  - **DEVIATION (carried):** the shared filter set is `render_filters` (four
    multiselects + Jalali presets + date inputs), not the Overview's three-select
    `render_filter_bar` — the recorded Task 35 interpretation, for the owner.
  - **N/A:** no KPI band — a domain page has no aggregate metric to band.
  - **DEFECT 1 (content, not layout):** `warn.single_observation` names TGJU, but
    it fires on the Labor page where the lone observation is SCI's quarterly
    unemployment. Recommended as a later-wave string fix (Wave H / ETL side), not
    a Wave D change.
  - **Carried:** the 24ch quality-table id cap (`SCI.UNEMPLOYMENT.QUART…`) with the
    full id in the `title`.
- **Evidence:** the Task 36 ten-page 1440×900 set (`partB-all-pages/`) and the
  four-page scroll crops (`task-36/after-scroll/`), plus the Task 35 before/after
  pixel diff and the Step 0a range-cell crops.
- **Verify (Scope B gate):** `make check` → **1446 passed, 3 skipped**, coverage
  **89.22 %**, ruff clean; `poetry run mypy src dashboard` → **0 errors**, 68
  source files; dashboard subset `pytest tests/unit/dashboard -q --no-cov` →
  **630 passed**; export smoke → **1 passed**. `git status --short` clean before
  the commit.
- **Deviations:** the plan's Task 37 acceptance box stays **unticked** — its
  acceptance is "owner sign-off recorded", and the sign-off is PENDING. The
  document is delivered for the owner's review; Wave E does not start until the
  decision is recorded.
- **Commit:** this entry is committed with the Task 37 commit.

---

## Wave E — Step 0a (record the Wave D owner sign-off)

- **Files:** `docs/phase-7.2/validation/archetype-domain.md` (status →
  OWNER REVIEW COMPLETE / APPROVED; new "Owner decision" block; §7 DEFECT 1
  recommendation → fix now in Step 0b; §8 checklist ticked; final line →
  `Owner sign-off: APPROVED`), `docs/phase-7.2/VALIDATION.md` (Task 37 bullets →
  sign-off APPROVED + the Wave H carry-forward list), `docs/phase-7.2/README.md`
  (status → "Wave D complete; Wave E in progress"; archetype-domain bullet →
  APPROVED), `docs/plans/phase-7.2-dashboard-redesign.md` (Task 37 acceptance box
  ticked).
- **Build (docs only, no code):** recorded the owner's Wave D decision verbatim —
  **APPROVED**; the domain pages **keep the shared `render_filters` filter set**
  (aligning it with `render_filter_bar` is an **optional Wave H polish candidate**,
  not scheduled); the **24-character** quality-table id cap (full id in the
  `title`) is **approved**; the **absence of a KPI band** on domain pages is
  **approved (N/A)**; **DEFECT 1** (`warn.single_observation` names TGJU while
  shown on the Labor page) is **fixed now** in Step 0b.
- **Carry-forward list for Wave H:** the filter-bar shape; optional polish **F1**
  (content padding 70 vs 40 px), **F2** (breadcrumb separator and bold current
  crumb), **F5** (shell-wide caption direction), **F7** (no-wrap short coverage
  columns); the Gregorian(LTR)/Jalali(RTL) range direction; and
  `scripts/dashboard_screenshots.py` `neutralise()` scrolls
  `stMainBlockContainer` (not the real scroll container `stMain`), so its
  scroll-to-top is a no-op (**Task 47**).
- **Verify:** docs-only change; `git status --short` staged by explicit path and
  committed. No code touched.
- **Deviations:** none.
- **Commit:** this entry is committed with the Step 0a commit.

---

## Wave E — Step 0b (source-neutral single-observation notice)

- **Files:** `dashboard/i18n.py` (`warn.single_observation`), 
  `tests/unit/dashboard/test_i18n.py` (new
  `test_single_observation_notice_is_source_neutral`).
- **Build:** grepped every use of `warn.single_observation`. There is exactly one
  code use — `dashboard/components/quality.py:511`
  (`st.warning(t("warn.single_observation"))` in `render_quality_summary`); no
  call-site logic changed and no other string touched. The notice fires on any
  page whose selection contains a lone observation, so it must not name a source.
- **Old wording (owner-visible):**
  «یک یا چند سری انتخاب‌شده تنها یک مشاهده دارد. **TGJU** منبعی لحظه‌ای است و
  تاریخچه از طریق گردآوری روزانه انباشته می‌شود.»
- **New wording (source-neutral):**
  «یک یا چند سری انتخاب‌شده تنها یک مشاهده دارد. این سری‌ها به‌صورت دوره‌ای
  گردآوری می‌شوند و تاریخچه‌شان به‌تدریج انباشته می‌شود.»
- **Test:** the new test asserts the string contains none of the source display
  names in `labels.SOURCE_LABELS` **nor** any `source_name` slug,
  case-insensitively (so the original Latin `TGJU` leak is caught as well as a
  future Persian-name leak).
- **Verify:** `poetry run pytest tests/unit/dashboard/test_i18n.py -q --no-cov`
  → **15 passed** (was 14). `grep` for the old clause returns nothing under
  `dashboard/`/`tests/`.
- **Deviations:** none. This closes Wave D DEFECT 1.
- **Commit:** this entry is committed with the Step 0b commit.

---

## Wave E — Task 38 (Inflation page emphasis sections)

- **Files:** `dashboard/page_view.py` (`render_inflation_page`,
  `_render_cpi_decile_section`, `_render_cpi_canonical_section`,
  `_render_chain_linking_section`, new `build_chain_linking_provenance_rows` +
  `ChainLinkingProvenanceTable` + `_provenance_cell`),
  `tests/unit/dashboard/test_layout_guard.py` (MIGRATED_PAGES += the four
  Inflation functions), `tests/unit/dashboard/test_app_economy.py` (imports
  `html_texts` + `build_chain_linking_provenance_rows`; rewrote two caption
  assertions to `app.info`; added the provenance markup assertion and two
  builder tests).
- **Build (Task 35 pattern):**
  - `render_inflation_page` opens with `render_page_header("page.inflation")`;
    the catalog-empty `st.info` is `render_empty`; the "all indicators"
    subheader is `render_section_header`.
  - The CPI decile / canonical / chain-linking section subheaders are
    `render_section_header`; every empty `st.info` is `render_callout(...,
    tone="info", container_key=...)` (distinct keys, because
    `empty.no_observations` / `empty.select_indicators` / the two
    `empty.no_chain_linked_observations` occurrences can legitimately fire on
    the same run as the generic composition's `render_empty`, and the callout
    container key derives from the body key — a bare `render_empty` would raise
    on a repeated key). The chart notice `st.info(scaled.notice)` is
    `render_callout("chart.notice", tone="info", body=scaled.notice,
    container_key="cpi-deciles-chart-notice")`.
  - The three explanatory `warn.*` captions (`warn.cpi_deciles_shared_base`,
    `warn.chain_linking_stored`, `warn.chain_linking_overlap`) became
    `render_callout(..., tone="info")` notices — the plan's "callouts
    (chain-linking stored/overlap)" read literally, and the rule "render_callout
    for every notice" applied to the shared-base caption for consistency. The
    Overview reference keeps its coverage *footnote* as a `st.caption` (a
    footnote is not a notice); the Inflation captions were notices, so they
    converted. **Interpretation for the owner.**
  - The provenance table is a `render_html_table` with typed cells built by the
    pure `build_chain_linking_provenance_rows(frame)` from the already-localized
    `chain_linking_provenance` frame; every cell is plain `Text` (the frame is
    Persian display text, Persian-digit years and joined segment labels), and a
    null falls back to the shared em-dash. The grid stays a `st.dataframe` only
    for the observations expander (`_render_capped_rows`,
    `row_height=OBSERVATIONS_ROW_HEIGHT`).
  - **Table variant chosen by measured width:** the provenance table measured
    **1232 px** in the `default` variant inside the 1042 px content column
    (190 px of sideways scroll inside its own `overflow-x: auto` wrapper), and
    **1042 px** in the `coverage` variant (`.dt.cov`, no sideways scroll). The
    `coverage` variant is chosen so the table fits the page column. `.cov` is
    documented for the two wide coverage/quality tables; the provenance table's
    long segment-ancestry column makes it wide, so `coverage` is the
    width-fitting choice. **Recorded for the owner.**
- **Changed test assertions (Wave E):**
  - `test_inflation_page_states_that_the_deciles_share_a_unit_and_base_year`:
    `app.caption` → `app.info` (the notice is a callout now).
  - `test_inflation_page_renders_the_chain_linking_section`: the two
    `app.caption` assertions → `app.info` (stored/overlap are callouts now).
  - New `test_the_provenance_table_is_an_html_table_with_localized_headers`
    (markup via `html_texts`: four `<th scope="col">` headers + the Urban row's
    yes flag and both segment labels).
  - New `test_build_chain_linking_provenance_rows_maps_every_cell_to_plain_text`
    (pure builder: every cell is `Text`; values equal the frame's cells).
  - New `test_build_chain_linking_provenance_rows_is_empty_safe`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_economy.py
  tests/unit/dashboard/test_layout_guard.py -q --no-cov` → **34 passed**;
  dashboard subset → **634 passed** (was 630; +4 new Inflation tests);
  `poetry run mypy src dashboard` → **0 errors**, 68 source files.
- **Visual evidence:** `docs/phase-7.2/wave-e-assets/task-38/` — `before-top/`
  (copied from `wave-d-assets/partB-all-pages/inflation.png`, the pre-Wave-E
  reference), `after-top/inflation.png` (page header + filters + decile section
  with the shared-base info callout), and `after-scroll/{cpi-decile,
  cpi-canonical,chain-linking}.png`. The chain-linking crop shows the section
  header, the stored/overlap info callouts, the `coverage`-variant provenance
  HTML table (Urban row, no sideways scroll) and the chain-linking chart.
- **Note:** the dev Streamlit server was stale against the migration (started
  Sep 21, not reloading on save in this sandbox); it was restarted once to
  capture the migrated renders. The AppTest gate runs the fresh code
  regardless.
- **Deviations:** the `coverage` variant on the provenance table and the
  caption→callout conversion are recorded above for the owner.
- **Commit:** this entry is committed with the Task 38 commit.

## Wave E — Task 39 (Welfare page emphasis sections)

- **Files:** `dashboard/page_view.py` (`render_welfare_page`,
  `_render_hbsir_sections`, new `build_survey_year_panel_rows` +
  `SurveyYearPanelTable` + `_survey_year_cell`),
  `tests/unit/dashboard/test_layout_guard.py` (MIGRATED_PAGES +=
  `render_welfare_page` + `_render_hbsir_sections`),
  `tests/unit/dashboard/test_app_welfare.py` (imports `html_texts` +
  `build_survey_year_panel_rows`; rewrote the `app.dataframe` survey-year
  assertion to the markup strategy; added a markup assertion, a builder test
  and an empty-safe test).
- **Build (Task 35 pattern):**
  - `render_welfare_page` opens with `render_page_header("page.welfare")`;
    the relative-poverty `st.warning` is
    `render_callout("warn.hbsir_relative_poverty", tone="warn",
    body=_relative_poverty_note())` (the note carries the `{k}` placeholder,
    so its resolved text passes through `body=` and the key is the container
    hook only); the computed-values `st.info` is
    `render_callout("warn.hbsir_computed_values", tone="info")`; the
    catalog-empty `st.info` is `render_empty`; the "other indicators"
    subheader is `render_section_header`.
  - `_render_hbsir_sections` opens with `render_section_header` for each of
    the three sections; every empty `st.info` is `render_callout(...,
    tone="info", container_key=...)` with distinct keys (`hbsir-gini-poverty`,
    `hbsir-deciles`, `hbsir-survey-years`), because the same
    `empty.no_hbsir_observations` key can legitimately fire in more than one
    section on the same run.
  - The survey-year panel `st.dataframe` becomes
    `render_html_table(table.columns, table.rows)` fed by the pure builder
    `build_survey_year_panel_rows(panel)` — a `NamedTuple` of typed cells,
    every value is a `Text` so the rendered table is byte-identical to the
    grid it replaces. The panel uses the `default` variant (five short
    columns; measured 957 px in the 1042 px column — well within the column,
    no sideways scroll needed).
- **Changed assertions in `test_app_welfare.py`:**
  - `test_welfare_page_renders_with_the_hbsir_sections`: the
    `any(frame.value.equals(expected) for frame in app.dataframe)` survey-year
    panel assertion was removed; the panel is now a `render_html_table` and is
    read through `html_texts`. The `app.title` / `app.subheader` /
    `app.plotly_chart` assertions stay — `render_page_header` keeps the
    native `st.title` and `render_section_header` keeps the native
    `st.subheader`, so `app.title` / `app.subheader` are unchanged.
  - `test_welfare_page_states_that_the_poverty_rate_is_relative`: no change.
    `render_callout(..., tone="warn")` calls `st.warning(text)` and
    `render_callout(..., tone="info")` calls `st.info(text)`, so the
    `app.warning` / `app.info` assertions still see the same values.
  - New `test_the_survey_year_panel_is_an_html_table_with_localized_headers`
    (markup strategy: reads the panel through `html_texts`, asserts the five
    `<th scope="col">` headers and the survey-year/coverage values from
    `survey_year_panel`'s output).
  - New `test_build_survey_year_panel_rows_maps_every_cell_to_plain_text`
    (pure builder: every cell is `Text`; values equal the frame's cells).
  - New `test_build_survey_year_panel_rows_is_empty_safe`.
- **Verify:** `poetry run pytest
  tests/unit/dashboard/test_app_welfare.py
  tests/unit/dashboard/test_layout_guard.py -q --no-cov` → **29 passed**
  (12 guard + 17 welfare); dashboard subset → **637 passed** (was 634; +3 new
  Welfare tests); `poetry run mypy src dashboard` → **0 errors**, 32 source
  files; `poetry run ruff format` → one file reformatted (whitespace).
- **Visual evidence:** `docs/phase-7.2/wave-e-assets/task-39/` — `before-top/`
  (copied from `wave-d-assets/partB-all-pages/welfare.png`, the pre-Wave-E
  reference), `after-top/welfare.png` (page header + two HBSIR callouts with
  their accent bars + filter bar — the same layout the wave-d crop had,
  with the callouts now carrying the scoped CSS), and
  `after-scroll/{hbsir-gini-poverty,hbsir-deciles,survey-year-panel}.png`.
  The survey-year-panel crop shows the section header, the `default`-variant
  RTL HTML table (Persian-digit coverage counts, Jalali Esfand 29/30 ends,
  no sideways scroll) and the generic composition below it.
- **Note:** the dev Streamlit server was restarted once (the prior run was
  stale and would not reload the new `page_view.py`/`test_app_welfare.py`
  edits in this sandbox). AppTest runs the fresh code regardless.
- **Deviations:** none — the panel is the `default` variant by measurement
  (957 px in a 1042 px column).
- **Commit:** this entry is committed with the Task 39 commit.

## Wave E — Task 40 (Market page emphasis sections)

- **Files:** `dashboard/components/layout.py` (new `render_callout_stack` +
  `__all__`), `dashboard/page_view.py` (`render_market_page`,
  `_render_market_notes`, `_render_market_level`, `_render_market_derived_panels`;
  import of `render_callout_stack`),
  `tests/unit/dashboard/test_layout_guard.py` (MIGRATED_PAGES += the four Market
  functions), `tests/unit/dashboard/test_layout.py` (+2 `render_callout_stack`
  tests), `docs/phase-7.2/design-system.md` (§4.1 component row, §11 testing
  rule, §12 whitelist mention).
- **Build (Task 35 pattern):**
  - New `render_callout_stack(callouts)`: renders a sequence of
    `(catalog_key, tone)` pairs, each through `render_callout`. The container key
    derives from the catalog key, so the stack is safe while no key repeats.
  - `render_market_page` opens with `render_page_header("page.market")`; the
    catalog-empty `st.info` is `render_empty`; the no-selection and no-observation
    `st.info`s are `render_callout(..., tone="info", container_key=...)` with
    distinct keys.
  - `_render_market_notes`: the five TSETMC caveats become one
    `render_callout_stack` (one `warn` + four `info`) — the page header's caveat
    block is now the D11 shared component.
  - `_render_market_level`: `st.subheader` → `render_section_header`; the
    sessions `st.metric` → a one-cell `render_kpi_band`; the empty `st.info` →
    `render_callout(..., container_key="market-level")`.
  - `_render_market_derived_panels` is listed in the guard; its per-series
    `st.subheader(market_series_label(rows))` stays (the label is a **resolved**
    display string, not a catalog key, so it cannot go through
    `render_section_header`'s `t(title_key)`; `st.subheader` is not a banned
    call, so the guard is satisfied and the labels are unchanged).
  - The quality table already uses `render_html_table` (`render_quality_summary`,
    `coverage` variant) from Task 35 — confirmed, no change needed.
- **Changed assertions in `test_app_market.py`:** **none.** Every existing
  assertion still passes unchanged:
  - `test_market_page_renders_a_labelled_panel_per_tsetmc_series` reads
    `app.title`/`app.subheader`/`app.get("plotly_chart")` — `render_page_header`
    keeps the native `st.title`, and `_render_market_level` /
    `_render_market_derived_panels` keep the native `st.subheader`, so the panel
    count and labels are unchanged.
  - `test_market_page_states_the_tsetmc_semantics` reads `app.warning`/`app.info`
    — `render_callout_stack` calls `render_callout`, which calls the native
    `st.warning`/`st.info`, so the five caveats are still seen.
  - `test_market_page_reports_the_observed_session_count` reads `app.metric` —
    `render_kpi_band` calls `st.metric` inside its columns/containers, which
    `AppTest` still surfaces.
- **New component tests:** `test_callout_stack_renders_each_pair_with_its_tone`
  and `test_callout_stack_keeps_distinct_container_keys` in `test_layout.py`.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_app_market.py
  tests/unit/dashboard/test_layout_guard.py
  tests/unit/dashboard/test_design_system_doc.py tests/unit/dashboard/test_states.py
  -q --no-cov` → **44 passed**; `test_layout.py` → **59 passed** (was 57; +2);
  dashboard subset → **637 passed**; `poetry run mypy src dashboard` → **0
  errors**, 68 source files; `ruff format --check`/`ruff check` → clean.
- **Visual evidence:** `docs/phase-7.2/wave-e-assets/task-40/` — `before-top/`
  (copied from `wave-d-assets/partB-all-pages/market.png`), `after-top/market.png`
  (page header + five TSETMC caveats with accent bars/glyphs + filter bar) and
  `after-scroll/market-level.png` (the level section header, the one-cell KPI
  band and the level chart).
- **Note:** the dev Streamlit server was restarted once for the capture.
- **Deviations:** the derived-panel subheaders stay raw `st.subheader` because
  their titles are resolved display strings, not catalog keys (recorded for the
  owner). The `render_callout_stack` component and the design-system doc rows are
  new public surface.
- **Commit:** this entry is committed with the Task 40 commit.

## Wave E — Task 41 (emphasis-domain owner review, PREPARED — not signed off)

- **Files:** `docs/phase-7.2/validation/archetype-emphasis.md` (new),
  `docs/phase-7.2/README.md` (status → "Wave E awaiting owner review").
- **Build (documentation only — no code change):** the emphasis owner review doc
  for the three A3 pages (Inflation, Welfare, Market), modelled on
  `validation/archetype-domain.md`. It records the inventory, the D11
  contract matrix (§3), cross-page consistency (§4), the Overview/Wave-D
  comparison (§5), the pixel-diff evidence and the changed-assertions list (§6),
  the carried decisions and one cosmetic observation (§7), and the owner
  checklist (§8). The checklist boxes are **unticked** and the doc ends
  `Owner sign-off: PENDING.` — the task is to **prepare** the review, not to sign
  it off.
- **Verdict tally:** 15 MATCH, 3 DEVIATION (the shared `render_filters` filter set
  on all three pages; Market's derived-panel subheaders), 1 N/A (no KPI band on
  Inflation/Welfare), **0 presentation-layer DEFECT**.
- **Carried for the owner:** row 4 (filter set), row 3 (Market derived-panel
  titles), §4 (Welfare's two top-level caveats could use `render_callout_stack` —
  cosmetic, no rendered difference). The Wave D carry list is unchanged.
- **Plan acceptance box:** left unticked — the acceptance is "owner sign-off
  recorded, or defects filed", and neither has happened; the doc is prepared and
  awaiting the owner.
- **Verify:** the review cites the committed evidence under
  `wave-e-assets/task-38|39|40/` and `wave-e-assets/partA-all-pages/`; the pixel
  diffs are inflation 0 %, welfare 30.2 %, market 3.0 % (callout strips only).
  No test run is needed for a docs-only task; the Scope B gate re-runs the suite.
- **Commit:** this entry is committed with the Task 41 commit.

## Wave F — Step 0a (record the Wave E owner sign-off; docs only)

- **Files:** `docs/phase-7.2/validation/archetype-emphasis.md` (status →
  SIGNED OFF — APPROVED; new §10 sign-off record), `docs/phase-7.2/VALIDATION.md`
  (new "Wave E part C — owner sign-off" section), `docs/phase-7.2/README.md`
  (status → "Wave E complete; Wave F/G in progress"; archetype-emphasis added to
  the Documents list), `docs/plans/phase-7.2-dashboard-redesign.md` (Task 41 box
  ticked with the 2026-09-22 APPROVED note).
- **Recorded verbatim:** owner sign-off **APPROVED**, the 15 MATCH rows accepted;
  three approved deviations (shared `render_filters` set on the three pages —
  Wave H polish candidate; Market's derived-panel `st.subheader` titles; Inflation's
  three explanatory captions as info callouts); the Welfare callout-stack routing
  is **not needed** (no rendered difference).
- **Verify:** docs-only; no code or test change. The Wave F gate re-runs the full
  suite.
- **Deviations:** none.
- **Commit:** Step 0a commit.
