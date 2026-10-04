# Design brief — Iran Macroeconomic Data Platform dashboard

**Audience:** a UI/UX designer (or design team) taking on a redesign of the
dashboard.

**Purpose:** everything you need to design against this product — what it is,
who uses it, what already exists, the hard technical constraints, the content,
and the assets. Read §3 (constraints) before drawing anything; it is the part
that decides whether a design is buildable.

**Status of the current UI:** the dashboard was fully redesigned in **Phase 7.2**
(2026-09-20 → 2026-09-22). It already has a design system, a ratified Overview
mockup and a consistent shell across all ten pages. A redesign is therefore an
**evolution of an existing system**, not a greenfield exercise. §4 documents what
is already there so you extend it instead of re-inventing it.

---

## 1. The product in one page

| | |
|---|---|
| **Name** | Iran Macroeconomic Data Platform |
| **What it is** | A local data platform that collects, cleans, chain-links and visualises 50+ years of Iran's macroeconomic indicators |
| **The dashboard's job** | Let an analyst explore, compare, sanity-check and **export** those indicators |
| **Primary user** | Data analysts and economists doing macroeconomic research |
| **Not the user** | The general public, traders looking for live quotes, mobile users |
| **Deployment** | Local-only (Docker Compose + `make dashboard`); **no cloud, no hosted multi-tenant service** |
| **UI language** | **Persian only** (`fa`), fully **RTL**. The catalog keeps canonical English names as auditable data, but the interface is Persian |
| **Primary viewport** | Desktop, **1440×900** (the size every screenshot and measurement is taken at) |
| **Session shape** | Single analyst at a workstation; long, data-heavy pages |

### What the analyst actually does (the jobs to design for)

1. **Track inflation** across income deciles and the national/urban/rural split.
2. **Relate monetary conditions to FX and gold** prices.
3. **Compare domestic GDP** with international (IMF) forecasts.
4. **Correlate any two indicators** and see whether the overlap is statistically usable.
5. **Check data quality and freshness** — is this series current? does it have gaps? was it chain-linked?
6. **Produce publication-ready output** — PNG/SVG charts and CSV/Excel datasets.

### The domain problem the UI has to carry

The data is genuinely messy, and the UI's credibility depends on saying so:

- **Fragmented sources** — 9+ domestic and international sources, no unified API.
- **Frequency mismatch** — daily (FX, gold, market) to annual (World Bank).
- **Base-year discontinuities** — historical series are **chain-linked**, and the
  UI must show both the linked and the original values without hiding the splice.
- **Publication lag** — domestic sources lag by months; international sources by
  1–2 years. Freshness/staleness is a first-class UI concept.
- **Sanctions-related gaps** — missing periods are **left missing**, never
  interpolated. "No value" and "zero" must never look alike.

> **Design principle that follows from the above:** this is a tool for people who
> will be *criticised* for their numbers. Every caveat the platform knows must be
> visible next to the number it qualifies. Precision and honesty outrank polish.

---

## 2. Current state — what a redesign is starting from

The dashboard is a **Streamlit** app: a `st.navigation` router over a plain-data
page registry (`dashboard/navigation.py`) with ten page modules that delegate
into one composition module (`dashboard/page_view.py`).

Phase 7.2 delivered:

- A **design-token module** (`dashboard/components/tokens.py`) — the single source
  for palette, radii and type scale (§4.1).
- A **theme** (`.streamlit/config.toml`) pinned to those tokens.
- A **shell**: 256 px sidebar with brand + pinned DB-status dot, Material nav
  icons, active-item accent bar, and a 48 px top bar with breadcrumb +
  last-collection stamp.
- **Shared components**: page header, callout, KPI band, section header, filter
  bar, status chip/dot, bar list, RTL HTML table with typed cells, empty/error/
  loading states, download controls, and one Plotly chart template.
- **All ten pages migrated** onto one layout contract, with an AST guard that
  stops a migrated page from calling raw Streamlit display APIs.

**Evidence you should look at before designing** (see §7 for the full asset list):

- `docs/design/phase-7.2/overview-redesign-mockup.html` (+ `.png`) — the ratified
  reference for the Overview page.
- `docs/phase-7.2/wave-0-assets/before/` and `after/` — all ten pages, before and
  after Phase 7.2.
- `docs/phase-7.2/wave-h-assets/partA-all-pages/` — the **current** look of all
  ten pages (this is your true starting point).

---

## 3. Hard constraints — read this before drawing

These are not preferences. A design that violates them cannot ship without a new
engineering phase.

### 3.1 The rendering stack is Streamlit, not HTML/CSS

Every pixel is produced by a Streamlit component, a **theme option**, or a
**scoped CSS rule**. The build order is fixed (**"native-first"**):

1. A **native Streamlit element** styled by `.streamlit/config.toml`.
2. **Scoped CSS** targeting a keyed container (`st.container(key=…)`) or a stable
   `data-testid`.
3. An escaped `st.html` fragment — **only where no native element exists**.

Implications for design:

- **You cannot design arbitrary HTML/CSS components.** If there is no native
  Streamlit element and no CSS hook, the component does not exist.
- The existing UI already reaches the `st.html` layer for exactly: RTL table
  cells, the bar inside a bar-list row, the standalone status dot, and the sidebar
  brand mark. Those are the exception, not the pattern.

### 3.2 `st.html` is sanitised — assume these are unavailable

DOMPurify runs with the HTML profile only:

| Unavailable | Available |
|---|---|
| `<svg>` — **stripped** | `<style>`, `class`, `dir`, inline `style`, `data-*` |
| JavaScript | `<bdi>`, `<a href>` (external only) |
| `<iframe>` | `title` attribute (tooltips) |

So: **no custom SVG iconography** inside HTML fragments. Icons are Material
symbols (`:material/…:`) or Unicode/CSS shapes. The sidebar brand is a CSS-drawn
square for this reason.

### 3.3 The shell is version-fragile CSS on internal DOM

Sidebar width, active-nav bar, pinned status and top bar are styled through
Streamlit `data-testid`s in one comment-marked block naming **Streamlit 1.61.1**
(`dashboard/components/direction.py`). Only a manual browser checklist can catch a
break — automated tests cannot see shell chrome. A redesign that moves shell
elements must accept re-verifying these selectors.

### 3.4 Sortable data grids stay **LTR**

`st.dataframe` (the catalog and the observations tables) keeps Streamlit's
documented **left-to-right grid**, even inside an RTL page. It cannot render a
status dot, a tone chip, a mono id under a name, or a date/age stack. That is why
small static tables use a custom RTL HTML table instead (§4.3). **Do not design an
RTL sortable grid** — it is not achievable.

### 3.5 Light theme only

`base = "light"` is locked; **dark mode is not supported** and is deferred to a
later phase. Do not deliver dark variants.

### 3.6 No custom widgets

The filter controls are native `st.selectbox` / `st.multiselect` /
`st.segmented_control`. A chip-shaped select like the mockup's 32 px `.sel` is
**not built** — the shipped filter bar is 73 px tall vs the mockup's 55 px. If you
want a new control shape, it needs a native equivalent or a new engineering phase.

### 3.7 Persian, RTL, and a two-calendar system

- Every user-visible string is Persian and lives in `dashboard/i18n.py`. A
  **literal guard fails the build** on a hardcoded display string. Adding copy
  means adding a catalog key, not a string in a template.
- Layout is RTL: "first" means the **rightmost**. Component containers declare
  `direction: rtl` individually; the global main block is deliberately LTR so
  un-migrated surfaces do not flip.
- **Calendars are per-source.** International sources (`world_bank`, `imf`, `eia`)
  display Gregorian; domestic sources (`tgju`, `sci`, `tsetmc`, `hbsir`) display
  **Jalali**. Timestamps are stored UTC/Gregorian; Jalali is display-only.
- **Chart time axes stay LTR** (time flows left to right); only legends and titles
  are RTL-aligned. Persian digits are used in display and exports.

### 3.8 The design system is enforced by tests

Three guards mean a redesign must change the *system*, not one-off pages:

| Guard | What it enforces |
|---|---|
| `test_tokens.py` | Parses the mockup's `:root` and fails if `tokens.py` drifts |
| `test_literal_guard.py` | Fails on any hardcoded user-visible string |
| `test_layout_guard.py` | Fails when a migrated page calls raw `st.title` / `st.metric` / `st.warning` / `st.info` / `st.error` |

Practical consequence: **changing a token, a type size or a component signature
changes every page at once** — that is the intended lever.

---

## 4. The existing design system

Extend this. Do not replace it without saying so explicitly.

### 4.1 Design tokens

Single source: `dashboard/components/tokens.py`, mirrored by the mockup's `:root`
and asserted equal by a test.

| Token | Value | Used for |
|---|---|---|
| `bg` | `#F6F7F9` | App background |
| `surface` | `#fff` | Panels, tables, alerts |
| `surface-2` | `#F1F3F6` | Table headers |
| `hover` | `#F3F6FA` | Table row hover |
| `border` | `#E1E5EB` | Hairlines, cell separators, chart grid |
| `border-strong` | `#C9D0DA` | Group boundaries, missing-value dash, zero line |
| `text-1` | `#1B2430` | Primary text |
| `text-2` | `#4A5566` | Secondary text, units |
| `text-3` | `#667385` | Tertiary text, section sub-labels, footers |
| `accent` | `#1D4E89` | Brand, links, active nav, bar fill |
| `accent-soft` | `#E8EFF8` | Active-nav background, accent chip background |
| `ok` / `ok-bg` | `#1F7A4D` / `#E6F3EC` | Success tone |
| `warn` / `warn-bg` | `#9A5B00` / `#FBF1DC` | Warning tone (methodology callout, staleness) |
| `err` / `err-bg` | `#B42318` / `#FDECEA` | Error tone |
| `neutral-bg` | `#EEF1F5` | Bar rail, unit-chip background |
| `radius` / `radius-lg` | `6px` / `8px` | Alerts & inputs / panels & table wrappers |
| `font-ui` | `"Vazirmatn",Tahoma,system-ui,sans-serif` | All UI text |
| `font-mono` | `"DejaVu Sans Mono",monospace` | Indicator ids, units |

**Chart palette (7, in order):** `accent`, `ok`, `warn`, `err`, `text-3`,
`text-2`, `border-strong`.

### 4.2 Type scale

| Element | Size / weight | Line-height |
|---|---|---|
| Page title (`h1`) | 28 px / 700 | 1.4 |
| Section header (`h2`/`h3`) | 18 px / 600 | 1.5 |
| KPI value | 28 px / 600 | — |
| Secondary KPI value | 20 px | — |
| KPI label | 13 px / 500 | — |
| Body | 14 px / 400 | 1.85 |

**Font:** **Vazirmatn**, vendored (variable, weight 100–900) and served locally —
no CDN. `dashboard/static/Vazirmatn.ttf` + `OFL.txt`.

### 4.3 Components (the vocabulary you can compose with)

- **`render_page_header`** — native `st.title` + optional callout.
- **`render_callout` / `render_callout_stack`** — native `st.warning`/`info`/`error`
  tinted to the tone tokens. Tones are a **closed set** (`warn`, `info`, `err`).
- **`render_kpi_band`** — one bordered row of metric cells, optional separated
  secondary group. Bands with <3 cells keep full-band cell width via a spacer.
- **`render_section_header`** — `st.subheader` + optional subtitle + trailing slot.
- **`render_filter_bar`** — one row of arbitrary native controls, weighted widths.
- **`render_status_chip` / `status_chip_cell` / `render_status_dot`** — run status
  and DB connectivity.
- **`render_bar_list`** — the indicators-by-domain bars (native page link + HTML bar).
- **`render_top_bar`** — breadcrumb + last-collection stamp (Jalali · time · Tehran).
- **`render_html_table`** — RTL table with typed cells: `Text`, `Ltr`, `UnitChip`,
  `StatusChip`, `Dot`, `TwoLine`. Density `comfortable` / `compact`; variant
  `default` / `coverage`.
- **`render_empty` / `render_error` / `render_loading`** — shared states.
- **`render_data_downloads` / `render_chart_downloads`** — CSV/Excel, PNG/SVG/HTML.
- **Chart builders** — time series, overlay, small multiples, scaled, survey-year,
  chain-linking, correlation. All share one Plotly template built from the tokens.

### 4.4 Shell geometry (measured at 1440×900)

| Element | Value |
|---|---|
| Sidebar width | 256 px |
| Max content width | 1360 px |
| Native Streamlit header | 52.5 px (untouchable — the 48 px bar is a separate container) |
| Custom top bar | 48 px, full-bleed, aligned to page content |
| Main block top padding | 64 px |
| Content column at 1440 px | x = 326, width = 1044 |

### 4.5 Accepted deviations from the mockup

These are known, deliberate gaps between the mockup and the shipped UI — good
candidates if the redesign's brief includes closing them:

- Brand is a CSS square + text, not the mockup's SVG glyph (`<svg>` is stripped).
- Callout glyph is a CSS ring, not the mockup's icon (native alert ships no icon).
- KPI review tag renders *beneath* the metric, not inline in the label.
- KPI tooltip is Streamlit's native `(?)`, not the mockup's `(i)`.
- Filter bar is 73 px (native selects) vs the mockup's 55 px chip row.
- The Overview coverage table (10 columns, 1169 px) overflows its 1042 px wrapper
  at 1440 px, so the last column is partly scrolled.
- Native `st.dataframe` grids stay LTR.

---

## 5. Information architecture

Ten pages in two sidebar groups. Sidebar labels are Persian; the registry keys are
the stable identifiers.

**Group `overview_analysis` — "مرور و تحلیل"**

| Key | Persian label | Purpose |
|---|---|---|
| `overview` | مرور کلی | Default page. KPI band, source freshness, indicators-by-domain bars, coverage table |
| `correlation` | مقایسه و همبستگی | Filter two+ indicators, correlation heatmap, exact-join counts, overlap summary |
| `catalog` | فهرست داده‌ها | Searchable/sortable catalog of every indicator, with coverage filters |

**Group `domains` — "حوزه‌ها"**

| Key | Persian label | Owns domains |
|---|---|---|
| `inflation` | تورم | inflation (CPI deciles, national/urban/rural, chain-linking) |
| `gdp` | تولید ناخالص داخلی و اقتصاد | gdp |
| `trade_energy` | تجارت و انرژی | trade, energy |
| `welfare` | رفاه و آمارگیری خانوار | welfare (HBSIR Gini, relative poverty, income deciles) |
| `fx_gold` | ارز و طلا | fx, gold |
| `market` | بازار سرمایه | market (TSETMC) |
| `labor` | بازار کار | labor (SCI quarterly unemployment) |

### Page archetypes (the seven domain pages are **not** one template)

| # | Archetype | Pages | Shape |
|---|---|---|---|
| A1 | Overview | `overview` | header → callout → KPI band → 2-col (freshness + bars) → coverage table |
| A2 | Generic domain explorer | `gdp`, `trade_energy`, `fx_gold`, `labor` | header (+callout) → filter bar → chart → quality table → observations expander → downloads |
| A3 | Emphasis-domain | `inflation`, `welfare`, `market` | A2 **plus** domain-specific emphasis sections above the generic body |
| A4 | Comparison | `correlation` | header → filter bar → heatmap → two summary tables → quality → downloads |
| A5 | Catalog | `catalog` | header → search + filters + clear → count → grid |

A redesign should **design per archetype**, not per page: five layouts cover all
ten pages.

---

## 6. Content inventory

### 6.1 Domains (Persian display names)

`gdp` تولید ناخالص داخلی · `inflation` تورم و شاخص قیمت · `trade` تجارت خارجی ·
`energy` انرژی · `fx` ارز · `gold` طلا · `welfare` رفاه و بودجه خانوار ·
`labor` بازار کار · `market` بازار سرمایه · `unclassified` دسته‌بندی‌نشده

### 6.2 Sources

| Slug | Persian label | Calendar | Expected collection cadence |
|---|---|---|---|
| `world_bank` | بانک جهانی | Gregorian | monthly |
| `imf` | صندوق بین‌المللی پول | Gregorian | monthly |
| `eia` | اداره اطلاعات انرژی آمریکا | Gregorian | monthly |
| `tgju` | تی‌جی‌جی‌یو | Jalali | daily |
| `sci` | مرکز آمار ایران | Jalali | weekly |
| `tsetmc` | بورس تهران | Jalali | daily |
| `hbsir` | بررسی بودجه خانوار | Jalali | annual |

### 6.3 Indicators

**54 indicators** across the sources, e.g.:

- **World Bank (12):** GDP in current/constant/base prices, GDP growth, GDP per
  capita, CPI inflation, exports, imports, trade balance, population, population
  growth, energy use per capita.
- **IMF (6):** real GDP growth, CPI inflation, GDP (US$ bn), GDP per capita,
  unemployment rate, current-account balance.
- **EIA (2):** crude production, total liquids.
- **TGJU (3):** free-market USD, Emami gold coin, 18k gold per gram.
- **SCI (18):** canonical national/urban/rural CPI (chain-linked), 4 inactive
  base-year segments, 10 expenditure-decile CPI series, quarterly unemployment.
- **TSETMC (1):** Tehran stock index (TEDPIX) + derived RET1D / MA30 / month-end.
- **HBSIR (12):** weighted Gini, relative poverty rate, 10 income-decile shares.

Full Persian names: `dashboard/labels.py`.

### 6.4 Frequency

`daily` روزانه · `weekly` هفتگی · `monthly` ماهانه · `quarterly` فصلی ·
`annual` سالانه

### 6.5 Recurring content patterns (design targets)

- **Caveat / methodology callouts** — amber `warn` for methodology and data
  caveats, blue `info` for guidance. Long, multi-sentence Persian copy. Examples:
  IMF forecast indistinguishability, TGJU snapshot-only, TSETMC derived-series
  and missing-session caveats, HBSIR computed-values caveat, labor sparse-series
  caveat, correlation exact-join limitation.
- **Tone-coded values** — fresh/stale, success/failed/partial run status,
  confidence scores, chain-linked flags.
- **Missing-value em-dash** `—` (never `0`).
- **Two-line date cells** — display date above, time · relative age below
  (e.g. `۲۲ شهریور ۱۴۰۵` / `۰۹:۴۵ · ۸ روز پیش`).
- **Unit chips** — LTR mono (`current US$`, `constant 2015 US$`, `IRR`, `index`).
- **Two-calendar ranges** — a source's coverage in its own calendar.
- **Capped grids** — observations capped at 500 rows with a visible "showing N of
  M" note; full data in downloads.

### 6.6 Copy rules the designer must respect

- Persian, RTL, **Persian digits** everywhere in display.
- No hardcoded strings — every string is a catalog key in `dashboard/i18n.py`.
- Tone words are closed sets; an unknown tone raises rather than silently styling.
- "Unknown" is a first-class value (`نامشخص`) — design for it, do not hide it.

---

## 7. Assets and references

| Asset | Path |
|---|---|
| **Ratified Overview mockup (HTML)** | `docs/design/phase-7.2/overview-redesign-mockup.html` |
| **Ratified Overview mockup (PNG)** | `docs/design/phase-7.2/overview-redesign-mockup.png` |
| **Current UI — all 10 pages** | `docs/phase-7.2/wave-h-assets/partA-all-pages/*.png` |
| Before Phase 7.2 | `docs/phase-7.2/wave-0-assets/before/*.png` |
| After Phase 7.2 | `docs/phase-7.2/wave-0-assets/after/*.png` |
| Per-wave captures | `docs/phase-7.2/wave-{a,b,c,d,e,f,g,h}-assets/` |
| Design-system reference | `docs/phase-7.2/design-system.md` |
| Redesign plan + decisions D1–D14 | `docs/plans/phase-7.2-dashboard-redesign.md` |
| Validation record | `docs/phase-7.2/VALIDATION.md` |
| Product requirements | `PRD.md` |
| Architecture / data flow | `docs/architecture.md` |
| Data dictionary | `docs/phase-2/data_dictionary.md` |

---

## 8. How to run and see it

```bash
# One-time
poetry install
cp .env.example .env
make db-up            # PostgreSQL + TimescaleDB (host port 5433 by default)

# Run the dashboard
make dashboard        # → http://localhost:8501

# Capture 1440×900 screenshots of all ten pages (app must be running)
make dashboard-screenshots
```

- The screenshot script is `scripts/dashboard_screenshots.py`. Default viewport
  **1440×900**; `--full-height` captures a tall page whole (bounded to 12000 px).
- If the database is empty, pages render their **empty states** — design those
  too, they are a real part of the experience.
- Integration tests silently skip without a database; you do not need the test
  suite to review the UI, but `make check` is the merge gate.

---

## 9. Where a redesign can add value

Known gaps and deferred work, in rough priority order. These are the honest
candidates for a redesign brief:

**Structural / product gaps (deferred to a later phase):**
1. **Dark mode** — explicitly unsupported today.
2. **Indicator detail view** — no page shows full metadata, segment ancestry,
   per-layer counts, or raw `record_metadata`.
3. **Search on domain pages** — search exists only on the catalog.
4. **Explicit refresh control** — data is cached; there is no manual refresh.
5. **Custom Jalali date-entry widget** — today: a Gregorian date input plus
   Jalali preset shortcuts.
6. **Normalised / index-to-100 cross-unit comparison** — overlay is limited to a
   shared unit.
7. **Persian names in the catalog** — the catalog grid still shows canonical
   English indicator names.
8. **Normalised, accessible chart palette** — the 7-colour palette is
   token-derived; a categorical palette with better perceptual separation and
   colour-blind safety would be a genuine improvement.

**Fidelity gaps (mockup vs shipped):**
9. Filter bar density (73 px native selects vs a 55 px chip row).
10. Coverage table overflow at 1440 px (last column clipped).
11. KPI tag placement and tooltip glyph.
12. The **empty / loading / error states** are functional but under-designed.

**Data-presentation findings (need an ETL fix, but the UI must display them
gracefully):**
13. TGJU catalog coverage windows contradict the observed range.
14. Some SCI monthly catalog rows declare coverage but have **no Gold
    observations** — so their range/count/confidence cells render the em-dash.

**Process gap:**
15. There is **no visual-regression tooling**. Screenshots are manual. If the
    redesign lands, adding a visual-diff step would protect it.

---

## 10. What to hand back

For the redesign to be implementable in this codebase, a useful deliverable is:

1. **Per-archetype designs** (A1–A5), not per-page — five layouts, with the
   domain-specific emphasis sections of A3 (inflation, welfare, market) designed
   as reusable blocks.
2. **An updated token set** — any palette, radius, spacing or type change stated
   as token values, so it can land in `tokens.py` and the theme together.
3. **Component specs** for anything new, expressed in terms of the existing
   vocabulary (native element / scoped CSS / `st.html` fragment) with the
   Streamlit constraint named.
4. **Empty, loading and error states** for every archetype.
5. **A responsive/zoom note** — the design targets 1440×900; state what happens
   at 1280 and 1024 (both are measured today with no horizontal page scroll).
6. **A copy list** — new Persian strings as keyed items, ready for `i18n.py`.
7. **Explicit deviation list** — anything in the design that the constraints in
   §3 prevent, so it can be logged as a new phase rather than discovered at
   implementation time.

**Definition of "buildable" here:** the design uses only native Streamlit
elements, theme options, and scoped CSS on keyed containers or stable
`data-testid`s; it introduces no SVG in HTML fragments; it keeps sortable grids
LTR; it is light-theme only; and every string is a catalog key.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| **Gold layer** | Analysis-ready, chain-linked, frequency-harmonised data the dashboard reads |
| **Chain-linking** | Splice of series across base-year changes; both linked and original values are shown |
| **Domain** | Analytical grouping of indicators (inflation, gdp, …) |
| **Source** | A connector: World Bank, IMF, EIA, TGJU, SCI, TSETMC, HBSIR |
| **Jalali** | Iranian solar calendar; display-only, used for domestic sources |
| **Freshness / staleness** | Whether a source's last collection is within its expected cadence |
| **Tone** | Closed semantic set: `ok`, `warn`, `err`, `accent`, `neutral` |
| **Archetype** | One of five page layouts shared across the ten pages |
