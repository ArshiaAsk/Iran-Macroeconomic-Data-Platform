# Phase 7.2 design system (first draft)

The reference for the dashboard's presentation layer: the tokens, the theme
mapping, the shared components, the layout contract, the CSS ownership model and
the testing rules.

**Status: first draft (Task 23).** It covers what exists after Wave A
(Tasks 1–22). Task 47 extends the component catalogue with the pieces that land
later — the top bar (Task 28), the sidebar shell (Task 27) and the dev-only
screenshot script (Task 10) — and with the per-archetype review outcomes.

- Mockup: [`docs/design/phase-7.2/overview-redesign-mockup.html`](../design/phase-7.2/overview-redesign-mockup.html)
- Plan and decisions: [`docs/plans/phase-7.2-dashboard-redesign.md`](../plans/phase-7.2-dashboard-redesign.md)
- Wave 0 verification: [`docs/phase-7.2/wave-0-spike.md`](wave-0-spike.md)
- Per-task record: [`docs/phase-7.2/execution-log.md`](execution-log.md)
- Wave A validation: [`docs/phase-7.2/VALIDATION.md`](VALIDATION.md)

Everything below was verified against the installed **Streamlit 1.61.1** unless a
line says otherwise.

---

## 1. Layering: native, then CSS, then HTML (D6, D13)

A dashboard feature is built in this order, and only falls through when the layer
above cannot express it:

1. **A native Streamlit element** styled by the `[theme]` options in
   [`.streamlit/config.toml`](../../.streamlit/config.toml). This is the default
   and it is what keeps `AppTest` able to see the UI.
2. **Scoped CSS** owned by
   [`dashboard/components/direction.py`](../../dashboard/components/direction.py),
   targeting a keyed container or a stable `data-testid` (sections 5 and 6).
3. **An escaped `st.html` fragment**, only where no native element exists: the
   RTL table cells, the bar inside a bar-list row, the standalone status dot, the
   brand block.

The rule behind the order is **D13 (native-first)**: `st.html` content is
invisible to `AppTest`, so every fragment is a surface that unit tests cannot
read. Where a native element must sit beside an HTML fragment, the row is
composed with native `st.columns` — a bar-list row is a native `st.page_link`
beside an escaped `st.html` bar, because `st.page_link` cannot live inside
`st.html`.

## 2. Design tokens

[`dashboard/components/tokens.py`](../../dashboard/components/tokens.py) is the
single source for the palette, the radii and the font families. It mirrors the
mockup's `:root` block exactly, and
`tests/unit/dashboard/test_tokens.py` parses the mockup and fails when the two
drift — so a token added to the mockup cannot be silently forgotten in code.

| Token | Value | Used for |
|---|---|---|
| `bg` | `#F6F7F9` | App background |
| `surface` | `#fff` | Panels, tables, alerts |
| `surface-2` | `#F1F3F6` | Table headers |
| `hover` | `#F3F6FA` | Table row hover |
| `border` | `#E1E5EB` | Hairlines, cell separators, chart grid |
| `border-strong` | `#C9D0DA` | Group boundaries, missing-value dash, chart zero line |
| `text-1` | `#1B2430` | Primary text |
| `text-2` | `#4A5566` | Secondary text, units |
| `text-3` | `#667385` | Tertiary text, section sub-labels, footers |
| `accent` | `#1D4E89` | Brand, links, active nav, bar fill |
| `accent-soft` | `#E8EFF8` | Active nav background, accent chip background |
| `ok` / `ok-bg` | `#1F7A4D` / `#E6F3EC` | Success tone |
| `warn` / `warn-bg` | `#9A5B00` / `#FBF1DC` | Warning tone (the methodology callout) |
| `err` / `err-bg` | `#B42318` / `#FDECEA` | Error tone |
| `neutral-bg` | `#EEF1F5` | Bar rail, unit chip background |
| `radius` | `6px` | Alerts, inputs, chips |
| `radius-lg` | `8px` | Panels, KPI band, table wrapper |
| `font-ui` | `"Vazirmatn",Tahoma,system-ui,sans-serif` | All UI text |
| `font-mono` | `"DejaVu Sans Mono",monospace` | Indicator ids, units |

`CHART_CATEGORICAL_COLOR_TOKENS` names the seven tokens that make up the chart
palette, in order, and `CHART_CATEGORICAL_COLORS` derives their values from
`TOKENS` — so the palette cannot drift from the theme and no literal colour
exists in the chart layer.

`token(name)` raises on an unknown name; `css_custom_properties()` emits the
`--name: value;` block that `direction_css()` puts in `:root`.

**How the tokens reach the browser.** Three consumers, one source: the
`[theme]` block in `config.toml` (Streamlit-rendered elements), the `:root`
custom properties emitted by `direction_css()` (component CSS), and
`plotly_template()` (charts).

## 3. Theme mapping

[`.streamlit/config.toml`](../../.streamlit/config.toml) holds the options that
Streamlit can only apply through the theme. It never restates a token value that
the tests can compare — `test_tokens.py` asserts the chart palette equals
`CHART_CATEGORICAL_COLORS` in order.

| Theme option | Value / source |
|---|---|
| `base` | `light` (locked — section 9) |
| `primaryColor` | `accent` |
| `backgroundColor` | `bg` |
| `secondaryBackgroundColor` | `surface` |
| `textColor` | `text-1` |
| `borderColor` | `border` |
| `baseRadius` / `buttonRadius` | `radius` |
| `baseFontSize` | `14` (`TYPE_SCALE["body-size"]`) |
| `baseFontWeight` | `400` (`TYPE_SCALE["body-weight"]`) |
| `headingFontSizes` | `["28px", "18px", "18px"]` (`TYPE_SCALE` h1/h2/h3 sizes) |
| `headingFontWeights` | `[700, 600, 600]` (`TYPE_SCALE` h1/h2/h3 weights) |
| `metricValueFontSize` | `"28px"` (`TYPE_SCALE["metric-value-size"]`) |
| `metricValueFontWeight` | `600` (`TYPE_SCALE["metric-value-weight"]`) |
| `font` / `headingFont` | The Persian-first family list with an OS fallback tail (`Vazirmatn, IRANSans, Tahoma, Segoe UI, sans-serif`) |
| `codeFont` | The mono list (`"DejaVu Sans Mono", "SFMono-Regular", Menlo, Consolas, monospace`) |
| `[[theme.fontFaces]]` | `Vazirmatn`, `app/static/Vazirmatn.ttf`, weight `100 900` |
| `dataframeHeaderBackgroundColor` | `surface-2` |
| `chartCategoricalColors` | `CHART_CATEGORICAL_COLORS`, in order |
| `showWidgetBorder`, `showSidebarBorder` | enabled |
| `theme.{red,orange,yellow,blue,green}{Color,BackgroundColor,TextColor}` | `Color`/`TextColor` = the tone token, `BackgroundColor` = its `*-bg` token, so `st.warning`/`st.info`/`st.error` match the callout tones |
| `server.enableStaticServing` | `true` (serves `app/static/Vazirmatn.ttf`) |

The `font`/`codeFont` values are **not** the `font-ui`/`font-mono` token
strings: the theme takes a richer family list (with `IRANSans`/`Menlo` before the
generic tail), while `direction.py` repeats the token stack as `FONT_STACK` for
the CSS that must not depend on the theme. The palette, the radii, the base size
and the **type scale** are asserted token-equal (`test_tokens.py`).

**Type scale (Step 0e).** `tokens.py` holds `TYPE_SCALE` (sizes in px, weights as
integer strings) and the theme is pinned to it. Measured on the live app:
`st.title` (h1) is **28px/700** (the mockup's page title), `st.subheader` (h3 —
the section header) is **18px/600** (the mockup's section title; `h2` carries the
same value so `st.header` would match), `st.metric` values are **28px/600** (the
mockup's KPI value) and body text is **14px/400**. Before Step 0e the live sizes
were h1 38.5px, h3 24.5px and metric 31.5px/400, so all three now match the
mockup. The mockup's `line-height` values (h1 1.4, section 1.5, body 1.85) and
the KPI label's 13px/500 are **not** theme options, so **Task 29** pins them as
scoped CSS in `direction.py` (section 14): measured after, h1 **39.2 px**
(28 × 1.4), section `<h3>` **27 px** (18 × 1.5), body paragraph **25.9 px**
(14 × 1.85), KPI label **13 px/500** and the secondary KPI value **20 px**. The
heading overrides are scoped to `[data-testid="stMainBlockContainer"] h1` / `h3`
because Streamlit's own heading rule (line-height 1.2) outranks a bare element
selector.

`client.toolbarMode` is set to `"viewer"` (Task 28). The custom `[theme]`
already hides the theme toggle (section 9), so this suppresses the native Deploy
button and developer options while keeping the viewer options the analyst needs.
For local development the developer override is the environment variable
`STREAMLIT_CLIENT_TOOLBAR_MODE=developer`.

**The font is vendored, not fetched.** `dashboard/static/Vazirmatn.ttf` (241 328 B,
variable, wght 100–900, from the official `vazirmatn` npm package 33.0.3) plus its
licence `dashboard/static/OFL.txt` are committed; static serving resolves
`app/static/<file>`. The OS stack in `font-ui` is a graceful-fallback safety net
only, and `FONT_STACK` in `direction.py` repeats it for the CSS that must not
depend on the theme. Verified in Wave 0: the URL returns HTTP 200 `font/ttf` and
`document.fonts` reports `Vazirmatn` loaded.

## 4. Component catalogue

Every public `render_*` and `build_*` in `dashboard/components/` is listed here;
`tests/unit/dashboard/test_design_system_doc.py` scans that package and fails when
one is missing. Unless a row says otherwise, the component is **native-first** and
needs no `unsafe_allow_html`.

### 4.1 Layout and states — `components/layout.py`, `components/states.py`

| Component | Signature | Purpose |
|---|---|---|
| `render_page_header` | `(title_key, *, callout_key=None, label_key=None, tone="warn")` | The one page-header pattern: a native `st.title` plus an optional callout (with an optional bold label, e.g. the methodology note). |
| `render_callout` | `(key, *, tone="warn", label_key=None, detail=None, container_key=None, body=None)` | The mockup's callout as a native `st.warning`/`st.info`/`st.error`. |
| `render_callout_stack` | `(callouts)` | A stack of callouts from `(catalog_key, tone)` pairs, each through `render_callout`. The D11 way to render a page's several caveats (the Market page's five TSETMC notes) under one `render_page_header`. |
| `render_kpi_band` | `(cells, *, key="default")` | One bordered row of metric cells, with an optional separated secondary group. A band with fewer than three cells is padded to the four-cell reference width (Step 0b). |
| `render_section_header` | `(title_key, *, subtitle=None, trailing=None, key=None)` | A native `st.subheader` with optional secondary text, laid out as one baseline-aligned row. |
| `render_filter_bar` | `(controls, *, trailing=(), key="default")` | One filter-bar row over an arbitrary number of control callables. |
| `render_status_chip` | `(status)` | A standalone collection-run chip (`st.badge`), for use **outside** tables. |
| `status_chip_cell` | `(status)` | The same slug → (label, tone) mapping as `render_status_chip`, as an RTL-table `StatusChip` cell (Task 30). Not a renderer: it returns a cell. |
| `render_status_dot` | `(label, tone)` | A standalone coloured dot with a label; the one escaped fragment here. |
| `render_bar_list` | `(rows, total_label, *, key="default")` | The indicators-by-domain bar panel. |
| `render_top_bar` | `(group_label, page_label, *, key="top-bar")` | The shell top bar: breadcrumb (root › group › page) and last-collection stamp (Jalali date · clock · Tehran zone). The stamp reads `cached_source_freshness()` and formats the latest `collection_timestamp` through the Tehran/Jalali helpers; an empty or unparseable frame falls back to `t("value.unknown")`. |
| `render_empty` | `(key)` | The shared empty state for any `empty.*` message. |
| `render_error` | `(key, *, detail=None)` | The shared error state: message, retry hint, optional detail. |
| `render_loading` | `()` | The shared loading placeholder. |

```python
from dashboard.components.layout import KpiCell, render_kpi_band, render_page_header
from dashboard.components.states import render_empty

render_page_header(
    "page.overview",
    callout_key="warn.forecasts_indistinguishable",
    label_key="note.methodology_label",
)
render_kpi_band(
    [
        KpiCell("metric.sources", "۷"),
        KpiCell("metric.gold_observations", "۸٬۱۹۵", help_key="metric.gold_observations_help"),
        KpiCell("metric.derived_series", "۳۲", tone="muted", secondary=True),
    ],
    key="overview",
)
if frame.empty:
    render_empty("empty.no_observations")
```

**Contract details that are easy to get wrong.**

- **Tones are closed sets.** `CALLOUT_TONES`, `KPI_TONES` and the table `TONES`
  reject an unknown value with `ValueError` before it can reach a class attribute,
  so a data value can never inject a CSS class. `render_status_chip` is the one
  deliberate exception: its slug is a data value, so an unrecognised collection
  status falls back to the "unknown" chip instead of blanking a page.
- **Already-formatted vs catalog input.** `title_key`, `callout_key`, `label_key`,
  `help_key` and `tag_key` are **catalog keys** and go through `t()`. `value`,
  `subtitle`, `trailing`, `detail`, `label` and `total_label` are **already
  resolved** text (call `t()` or a label map first); numbers must already be
  formatted with `dashboard.formatting`.
- **Container keys.** A keyed container is the CSS hook, and Streamlit raises on a
  repeated container key. `render_callout` derives its key from the body key and
  takes `container_key` to disambiguate; `render_section_header` derives it from
  the title; the components that a page may render more than once
  (`render_kpi_band`, `render_bar_list`, `render_filter_bar`) take an explicit
  `key`. The states inherit the callout's rule, so one state key must not render
  twice in a run.
- **`st.badge` cannot live inside `st.html`.** A chip or dot *inside* the RTL
  table is the typed `StatusChip`/`Dot` cell (section 8); `render_status_chip` is
  for standalone use.
- **The page header emits no keyed class of its own** — `st.title` already takes
  the theme's heading font and size, and the optional callout brings its own hook.
- **A small KPI band keeps the full-band cell width (Step 0b).** `render_kpi_band`
  takes its `st.columns` spec from `kpi_band_column_weights`, not from
  `kpi_column_weights` directly. A band with fewer than three cells appends one
  **empty spacer column** so the cells keep the width they would have in the
  reference four-cell band, aligned to the RTL start (the spacer takes the far
  end). Without it a lone cell stretches across the whole content column: the
  Market one-cell band measured **1042 px of a 1044 px band (99.8 %)** before,
  **253.5 px (24.3 %, one quarter)** after. A band of three or more cells is
  returned unchanged, so every full band is byte-identical. The padding is a pure
  column-weight spec (`kpi_band_column_weights`, unit-tested in the style of
  `kpi_column_weights`); `render_kpi_band` renders the spacer empty and only the
  leading `len(cells)` columns carry a cell.

### 4.2 Tables — `components/html_table.py`

| Component | Signature | Purpose |
|---|---|---|
| `render_html_table` | `(columns, rows, *, density="comfortable", null_placeholder="—", variant="default", wrap_headers=())` | Render an RTL HTML table from typed cells. |
| `build_html_table` | `(columns, rows, *, density=…, null_placeholder=…, variant=…, wrap_headers=…)` | The same table as a markup string (used by the tests). |

`variant` is a closed set — `default` (no modifier class) or `coverage` (the
mockup's `.dt.cov`, Task 32), used by the two wide tables: the Overview coverage
table and the quality summary. `wrap_headers` names the **localized** headers that
break onto two lines at their last space (the mockup's `تعداد<br>مشاهدات`); a
header that is not among `columns` raises, so a typo cannot silently do nothing.

### 4.3 Filters and diagnostics — `components/filters.py`, `components/quality.py`

| Component | Signature | Purpose |
|---|---|---|
| `render_filters` | `(catalog, key_prefix, default_indicators=None)` | The common domain/frequency/source/indicator/date filter set; returns the exact selection. |
| `build_quality_rows` | `(quality)` | The quality summary as typed cells (`QualityTable`), for `render_html_table`. One row per indicator, the columns `summarize_quality` returns. |
| `render_quality_summary` | `(quality)` | Quality diagnostics for the selected series: the shared RTL HTML table plus the single-observation and material-gap warnings. |

### 4.4 Downloads — `components/exports.py`

| Component | Signature | Purpose |
|---|---|---|
| `render_data_downloads` | `(frame, file_prefix)` | CSV/Excel download buttons for a frame. |
| `render_chart_downloads` | `(figure, file_prefix)` | PNG/SVG/HTML download buttons for a figure. |

### 4.5 Charts — `components/charts.py`

`build_time_series_chart`, `build_overlay_chart`, `build_small_multiples_chart`,
`build_scaled_time_series_chart`, `build_survey_year_chart`,
`build_chain_linking_chart` and `build_correlation_chart` are figure builders, not
renderers; every one funnels through `apply_plotly_typography`, so the shared
template is the single lever for chart typography and palette (section 10).

## 5. CSS ownership and the hook pattern

`dashboard/components/direction.py` is the **only** module that emits a
`<style>` block, once per run through `inject_direction_css()`. No component emits
its own. The stylesheet has five sections: the `:root` token block, the RTL
typography rules, a comment-marked chrome block (section 6), the RTL table rules,
and the shared-component hook rules.

**`CSS_SELECTORS` is the one selector registry.** Every selector the module styles
is declared there, so the internal `data-testid`s that are the real instability
live in one mapping instead of being scattered through rule strings.
`test_direction.py::test_every_declared_selector_is_styled` fails when an entry is
declared but unused, so the registry stays honest.

**The keyed-container hook.** Never target a hashed `st-emotion-cache-*` class.
Use `st.container(key="…")`, which Streamlit 1.61.1 renders as
`class="stVerticalBlock st-key-<sanitized key> …"`, and scope the rule with an
attribute-substring selector:

```python
with st.container(key=f"bar-list-{key}"):
    ...
```

```css
[class*="st-key-bar-list-"] { direction: rtl; }
```

Verified on 1.61.1: the class lands on the container's `stVerticalBlock`, and
Streamlit **sanitizes the key into a CSS identifier** — `.` becomes `-`, `_` is
kept — so a catalog key such as `warn.forecasts_indistinguishable` becomes
`st-key-callout-warn-forecasts_indistinguishable`. A component whose key can
legitimately repeat in one run derives it from its argument and accepts an
override.

**Every component container declares `direction: rtl`.** Streamlit's main block is
`dir: ltr`, so an inherited `inline-start` / `flex-start` is the *left* edge and a
`st.columns` row reads left-to-right. A component that places an accent bar, a
cell order, a row order or a bar fill at the "start" must declare the direction on
its own container, exactly as the mockup's `body{direction:rtl}` does and as the
table does with `dir="rtl"` on its wrapper. Without it every such component
mirrors to the left of the mockup. A **global** main-block flip is deliberately
not used: it would reorder every un-migrated page's columns.

Measured consequences of that rule (live DOM, 1.61.1):

| Component | What the direction fixes |
|---|---|
| callout | `border-inline-start` accent bar and the first flex child (the CSS glyph) land on the **right** |
| KPI band | "first cell" means the **rightmost** cell, so a caller passes cells in mockup order; separators resolve to the right edge of each following cell |
| bar list | the domain label is rightmost, the bar is in the middle and the count is leftmost; the footer's `جمع` caption is on the right; the fill grows from the right |
| section header | the title is at the RTL start and the trailing text at the far end |
| filter bar | the first control is the rightmost |

A **`dir="rtl"` attribute** is the equivalent move for an `st.html` fragment whose
content is inline-level and would otherwise anchor to the host block's LTR start
(the standalone status dot uses this).

`:has()` is available in the app's Chromium and is used for the KPI band's
secondary-group boundary. It is a CSS feature, not a Streamlit API, so it does not
raise the version floor.

## 6. Streamlit-chrome selectors (version-fragile)

Chrome rules are isolated in one comment-marked block naming the tested version
(1.61.1), because `AppTest` cannot see chrome and only a manual browser checklist
can catch a break. **Do not extend the block without re-running the selector
probe** (Task 2's recipe, `wave-0-spike.md` §4).

Stable hooks — use these:

| Element | Hook | Verdict |
|---|---|---|
| Sidebar container | `[data-testid="stSidebar"]` | STABLE |
| Sidebar content (the flex parent) | `[data-testid="stSidebarContent"]` | STABLE |
| Sidebar header (**above** the nav) | `[data-testid="stSidebarHeader"]` | STABLE |
| Nav container / items | `[data-testid="stSidebarNav"]`, `…NavItems` | STABLE |
| Nav link | `[data-testid="stSidebarNavLink"]` | STABLE |
| **Active** nav link | `[data-testid="stSidebarNavLink"][aria-current="page"]` | STABLE (attribute) |
| Nav group header | `[data-testid="stNavSectionHeader"]` | STABLE |
| Sidebar user content (DB status) | `[data-testid="stSidebarUserContent"]` | STABLE |
| Main block container | `[data-testid="stMainBlockContainer"]` | STABLE |
| Native header | `[data-testid="stHeader"]` | STABLE |
| Toolbar / deploy / kebab | `[data-testid="stToolbar"]`, `…stAppDeployButton`, `…stMainMenuButton` | STABLE |
| Alert body / tint | `[data-testid="stAlertContainer"]` | STABLE |
| Alert kind | `[data-testid="stAlertContentWarning"\|"…Info"\|"…Error"]` | STABLE |
| Metric / metric value | `[data-testid="stMetric"]`, `…stMetricValue` | STABLE |
| Column | `[data-testid="stColumn"]` | STABLE |
| Horizontal row | `[data-testid="stHorizontalBlock"]` | STABLE |
| Segmented control | `[data-testid="stButtonGroup"]` | STABLE |
| Keyed container | `class*="st-key-<key>"` | STABLE (documented API) |

Fragile — **do not use**:

| Element | Hook | Why |
|---|---|---|
| Active nav link styling | `st-emotion-cache-1yak103` (hashed) | Hash changes between builds; use `[aria-current="page"]` |
| Anything requiring a width/max-width | — | Streamlit sets inline widths, so a `!important` override is unavoidable and must stay in the chrome block |

**Known gaps.** The native `[data-testid="stHeader"]` is **52.5 px** at the
themed 14 px base — not the mockup's 48 px top bar — so Task 28 builds the
mockup's bar as a new keyed container (`st.container(key="top-bar")`) and Step 0b
sets the main block's `padding-top` to **64 px** (52.5 px header + 12 px gap).
The native alert ships **no icon element**, which is why the callout glyph is
drawn in CSS.

**Sidebar brand + DB status (Task 27, fallback 2).** The sidebar brand and the
DB-status indicator are CSS-pinned, not rendered by `st.logo` or
`st.markdown` brand calls:

- **Brand:** `[data-testid="stSidebarHeader"]` is empty chrome when no `st.logo`
  is used, so the mark and the brand text are CSS pseudo-elements:
  `::before` is a CSS-drawn accent square (24 px, no SVG — `st.html` strips
  `<svg>`), and `::after` carries the escaped brand text from `t("app.brand")`.
  The header is a flex row (`display: flex; align-items: center; gap: 8px;
  flex-wrap: nowrap`) so the mark and text line up at the RTL start. The text
  stays on **one line**: `::after` is the flexible child
  (`flex: 1 1 auto; min-width: 0`) with `white-space: nowrap` and
  `overflow: hidden; text-overflow: ellipsis`, so a longer brand ellipsizes
  instead of wrapping into the navigation below (Step 0a). The brand value is
  the short plan string `سامانهٔ داده‌ها`, which fits the 256 px sidebar in full.
  The text is escaped by `_escape_css_string` (backslashes, double quotes and
  control characters) before interpolation into the `content` declaration. The
  pure builder is `brand_sidebar_css(brand_text)` in `direction.py`; the text is
  resolved by the entrypoint (`t("app.brand")`) and passed to
  `inject_direction_css(brand_text=…)`.
- **DB status:** `[data-testid="stSidebarUserContent"]` is pinned to the sidebar
  bottom by `order: 2; margin-top: auto` (the spike's corrected recipe). The
  status is the shared `render_status_dot` component (Task 11), not a native
  `st.success`/`st.error` alert: the sidebar footer needs a compact dot + label,
  not a full alert banner. The tone is `ok` (connected) or `err` (unavailable).

**Deviation from the mockup.** The mockup's brand block shows a custom logo
glyph; the fallback uses a plain accent-coloured square because no brand asset
exists and `st.html` strips inline SVG. The square is a CSS shape, not a glyph,
so it scales with the font size and stays within the accent token.

## 7. `st.html` survival (DOMPurify, `USE_PROFILES:{html:true}`)

`st.html` is not iframed and ignores JavaScript by default. What survives, verified
in Wave 0 (`wave-0-spike.md` §6):

| Probe | Survives? | Alternative when it does not |
|---|---|---|
| `<style>` block, class rules | **yes — applies** | — |
| `class`, inline `style`, `data-*` | yes | — |
| `title` attribute | yes | native tooltip; the fallback if a browser drops it is a `data-` attribute + CSS `::after` |
| `dir="rtl"` | yes | — |
| `<bdi>` | yes | — |
| `<a href>` | yes | for an **internal** page use a native `st.page_link`, never a raw anchor — a plain anchor is a full browser navigation, not the supported in-app switch |
| `<td title="…">` | yes | — |
| `<svg>` | **no — stripped** | a Material `:material/…:` glyph, a Unicode glyph, or a CSS-drawn shape (borders / `::before`) |
| `st.markdown(..., unsafe_allow_html=True)` CSS | yes — applies | this is how `direction.py` injects the stylesheet |

Because `<svg>` is stripped, the mockup's inline-SVG nav and brand glyphs are
**accepted deviations**.

**`st.html` and `AppTest`.** `AppTest` exposes no `html` accessor; a fragment is
reachable only as `element.proto.body`, which is why
`tests/unit/dashboard/app_smoke.py` provides the `html_texts(app)` helper. Assert
`st.html` output through that helper, never through `app.markdown`.

## 8. Tables: classification and the typed-cell model (D1)

**The rule.** A table that is *small, static and presentation-only* is an RTL HTML
table (`render_html_table`); a table that must sort, scroll or scale is a
`st.dataframe` styled by the theme and `column_config`.

| Table (page) | Rows (observed) | Class | Component |
|---|---|---|---|
| Freshness (overview) | 7 | small/static | HTML table |
| Coverage (overview) | 50 | small/static | HTML table |
| Survey-year panel (welfare) | 2 | small/static | HTML table |
| Chain-linking provenance (inflation) | ~3 | small/static | HTML table |
| Quality summary (all domain pages) | = indicator count | small/static | HTML table (`coverage` variant) |
| Catalog (catalog) | 50–54 | sortable | `st.dataframe` (theme only; shared `row_height`; **LTR grid**) |
| Observations (all domain pages) | capped 500 (underlying up to ~20 074) | large/scrollable | `st.dataframe` |
| Join counts (correlation) | N×N | matrix | `st.dataframe` |
| Overlap summary (correlation) | N | small/sortable | `st.dataframe` |

**Why the split exists.** `st.dataframe` keeps its documented **LTR grid** and
cannot express a status dot, a tone chip, a mono LTR id beneath a name, or a
date/time/age stack. The HTML table can, and pays for it with `st.html`
invisibility to `AppTest`.

**The catalog grid (Task 44).** The catalog keeps the native `st.dataframe` (a
sortable 50–54-row grid) with the theme only — no `column_config` is needed,
because `localize_table_frame` already produces display-ready columns — and the
shared `OBSERVATIONS_ROW_HEIGHT` density. It therefore keeps the **LTR grid**:
the indicator id column stays left-to-right inside an otherwise RTL page. That is
the documented D1 limitation, not a defect; converting the grid to the HTML table
would lose sorting and the column-header menu.

**The typed-cell model.** A cell is one of six frozen dataclasses, so a cell's kind
is checked by the type checker rather than by a format string:

| Cell | Renders |
|---|---|
| `Text(value, title=None, num=False)` | Plain text; `None` renders the missing-value em-dash. `num=True` adds the mockup's `num` class (tabular figures; Task 32) |
| `Ltr(value, title=None, num=False, mono_id=False)` | A left-to-right token, `unicode-bidi: isolate` so it cannot flip the table. `num=True` adds `num` (a Gregorian range is numeric *and* LTR); `mono_id=True` adds the block-level muted `idl` line the coverage table puts an id on (Task 32). **The mono family and the 11.5 px size belong to the id line only** (`.dt .ltr.idl`, Step 0a): a Gregorian range cell is also `Ltr` but inherits the table body cell font, exactly like the Jalali range and the count cells, so the two calendars render at the same size |
| `UnitChip(value, title=None)` | A left-to-right mono chip for a unit (`current US$`) |
| `StatusChip(label, tone, title=None)` | An HTML/CSS chip with a tone dot — **never** `st.badge` |
| `Dot(label, tone, title=None)` | An HTML/CSS status dot |
| `TwoLine(primary, secondary_parts=(), title=None, primary_tone=None)` | A bold primary line above inline parts joined by the mockup's `·`; `primary_tone` colours the primary line (the stale freshness date is amber) |

`TONES` (`ok`/`warn`/`err`/`accent`/`neutral`), `DENSITIES`
(`comfortable`/`compact`) and `TABLE_VARIANTS` (`default`/`coverage`) are closed
sets; an unknown value raises. Density is a CSS class on the table, and it is the
HTML table's density control — the `st.dataframe` class uses `row_height`
instead (`OBSERVATIONS_ROW_HEIGHT` = 40 px in `components/tables.py`, the
`.dt.compact` row height, so a dense grid and a dense HTML table read at one
density). A density can only shorten a row down to its `height` floor, so a table
whose cells wrap to two lines (the coverage table) changes height by less than
the floor suggests — measured 64 px → 60 px on the Overview coverage table.

**Every data-derived value is escaped** through `escape_html` before
interpolation, and the whole table is emitted inside an `overflow-x: auto` wrapper
so a wide table scrolls **inside its own box** and the page never scrolls
sideways.

## 9. Calendar rule (D3) and the theme lock (D14)

**Calendar.** Timestamps are stored timezone-aware **UTC** and Gregorian. Jalali is
a **display** concern. `SOURCE_CALENDAR` in
[`dashboard/labels.py`](../../dashboard/labels.py) maps a source to
`"gregorian"` or `"jalali"`: `world_bank`, `imf` and `eia` are Gregorian; `tgju`,
`sci`, `tsetmc` and `hbsir` are Jalali. A range formatter is calendar-aware only
when the caller opts in, so an un-migrated page's output is unchanged, and a test
pins the opt-in behaviour. `Asia/Tehran` is applied only when a value is rendered
or a selected day is interpreted; `tehran_day_bounds` / `jalali_day_bounds` are
the only bounds constructors. The Plotly grid stays LTR (time flows left to
right) — only the legend and titles are RTL-aligned.

The Overview coverage table (Task 32) is the first opted-in surface. Each range
cell is placed by its source's calendar: a Gregorian source's range is an `Ltr`
cell whose `title` carries the exact stored bounds (the display is a bare year),
and a Jalali source's is a `Text` cell that collapses a same-month daily span to
the mockup's `۱۸ – ۲۰ شهریور ۱۴۰۵` (`range_label(..., compact=True)`, also
opt-in). The calendar map is a **parameter** of `build_coverage_rows`, so a test
injects `{}` and gets the all-Jalali form.

**Theme lock.** `base="light"` is locked; dark mode is not supported in 7.2 and is
deferred. A custom `[theme]` in `config.toml` already removes the settings-menu
theme toggle in 1.61.1 (verified: no `stMainMenuItem-theme-*` at any
`toolbarMode`), so the lock is enforced today with **no CSS hacks on the native
menu**. Task 28 sets `client.toolbarMode = "viewer"` — to hide the native Deploy
button and developer options while keeping the viewer options the analyst needs.
For local development the developer override is the environment variable
`STREAMLIT_CLIENT_TOOLBAR_MODE=developer`.

**Measured shell geometry (Task 28; corrected in Step 0b).** Measured at
1440×900 in the shipped app:

| Element | Value |
|---|---|
| Native `[data-testid="stHeader"]` | `position: absolute`, `z-index: 999990`, **52.5 px** tall (3.75 rem at the themed 14 px root), `y = 0` |
| `stMainBlockContainer` | `x = 256`, `width = 1184`, `padding-top: 64px`, `max-width: 1360px` |
| Top bar keyed container | `y = 64`, **48 px** tall (via `min-height`), `x = 326`, `width = 1044` |
| First content block (`h1`) | `y = 126` |
| Header bottom → bar top gap | **11.5 px** (target ≤ 24 px) |

**The 52.5 px vs 60 px reconciliation.** Both figures are 3.75 rem: **52.5 px**
is 3.75 rem at the theme's `baseFontSize = 14`, and **60 px** is the same 3.75 rem
at the browser's default 16 px root. The 60 px figure was measured before the
14 px themed base applied (or without the custom theme); **52.5 px is correct for
the shipped app**, and it holds in both `toolbarMode = "viewer"` and the
`STREAMLIT_CLIENT_TOOLBAR_MODE=developer` override (both measured 52.5 px).

**The 48 px bar height needs `min-height`, not `height`.** Streamlit's own
`.stHorizontalBlock` rule sets `flex: 1 1 0%` and the keyed container is a
**column** flex parent, so the main axis is vertical and `flex-basis: 0%`
overrides a plain `height`. Measured: the row computed **20.8 px** with
`height: 48px` and **48 px** with `min-height: 48px`; `align-items: center` was
unaffected. Task 28's `height: 48px` was therefore inert.

**The bar is full-bleed (P5; Step 0b recorded it as contained).** The bar's
containing block is Streamlit's inner `stLayoutWrapper`, which sits *inside*
`stMainBlockContainer`'s 70 px side padding, so Step 0b's plain bar inherited
that padding and its content column was `x = 326, width = 1044` at 1440 px —
the same column as the page title, but not the mockup's full-width bar. P5
makes it full-bleed without letting the two numbers drift: the main container
declares `--main-pad-x: 70px` and its horizontal padding reads that property,
and the bar's `width`, `max-width`, negative inline margin and matching inline
padding all read the same property. Measured at 1440 px: the bar spans
`x = 256, width = 1184` (right edge 1440), its content stays aligned with the
page content (`breadcrumb right = 1370 = h1 right`, `stamp left = 326 =
h1 left`), and `scrollWidth == clientWidth == 1440`. At 1280 px: the bar spans
`x = 256, width = 1024` and `scrollWidth == clientWidth == 1280`. No
horizontal page scroll at either width, so the full-bleed variant is kept. The
max content width stays 1360 px, so above 1616 px the bar tracks the capped
container.

## 10. Charts and exports

**One template.** `plotly_template()` in `direction.py` builds the shared template
from the tokens: the Persian font, the token `colorway`, token grid/border colours,
and RTL-friendly legend (horizontal, top, right-aligned) and title placement.
Sizing and margins stay with the individual builders. Every builder funnels through
`apply_plotly_typography`, so the template is the single lever.

The time axis is **not** reversed: time flows left to right on the LTR canvas,
per the project's LTR-grid rule. This is asserted in the contract test
(`xaxis.autorange is None`).

Streamlit injects the theme's `chartCategoricalColors` into every chart
client-side, so the browser's trace colours come from the theme while the
**server-side/export** path renders with the figure's own template — which is why
the template's `colorway` is asserted in tests and exercised by the export smoke.

**The export engine is Kaleido v1, not Playwright.**
`components/exports.py` imports `from kaleido import Kaleido` and calls
`Kaleido(path=find_chromium_executable())` → `await renderer.open()` →
`renderer.calc_fig(...)`. Playwright is only the *source of the Chromium binary*:
`find_chromium_executable()` scans `~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome`
and then the system Chrome.

That smoke needs a Chromium executable, so it is marked `@pytest.mark.integration`
and is **deselected by `make check`** (`pytest -m "not integration"`). Run it
explicitly after any change to the template or the export path:

```bash
poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov
```

## 11. Testing rules

| Rule | Why |
|---|---|
| **Subset runs use `--no-cov`.** | `pyproject.toml`'s `addopts` carries `--cov=src --cov-fail-under=80`. Coverage is measured on `src`, so a dashboard-only subset reports a near-zero number and fails the gate for the wrong reason. `make check` runs the full suite and keeps the gate. |
| **The export smoke is opt-in.** | It needs Chromium; `make check` deselects `integration`. Run it explicitly (section 10). |
| **Live API tests are opt-in.** | `@pytest.mark.live`, gated behind `RUN_LIVE_API_TESTS=1`. |
| **`st.html` output is asserted through `html_texts(app)`.** | `AppTest` has no `html` accessor; `element.proto.body` is the only route. |
| **`st.badge` surfaces as Markdown.** | `st.badge("tag", color="orange")` appears to `AppTest` as `app.markdown == [":orange-badge[tag]"]`. |
| **The literal guard scans the dashboard tree.** | `test_literal_guard.py` fails on `st.<display>(<literal>)`, so every user-visible string resolves through `t()`. The shared-component modules are whitelisted for the D11 guard but **not** for the literal guard. |
| **The D11 layout guard is function-scoped.** | Every page composition lives in one large module, so `MIGRATED_PAGES` maps module → migrated function names and grows per wave. It landed in Task 33 as `tests/unit/dashboard/test_layout_guard.py`. |
| **A callout stack needs distinct keys.** | `render_callout_stack` derives each container key from its catalog key, so a repeated key raises in Streamlit. A stack whose members share a key must pass explicit `container_key` values through `render_callout` instead (the Welfare/Market empty-state pattern). |

## 12. The page-layout contract (D11)

A **migrated** page function opens with `render_page_header`, renders KPI values
through `render_kpi_band`, section titles through `render_section_header`, filters
through `render_filter_bar`, and empty/error/loading through
`components/states.py`. It does not call raw `st.title`, `st.metric`,
`st.warning`/`st.info`/`st.error`, or `unsafe_allow_html` where a shared component
exists.

The guard is an AST check modelled on `test_literal_guard.py`. Because every page
composition lives in `dashboard/page_view.py`, the guard is **function-scoped**:

```python
MIGRATED_PAGES = {"dashboard/page_view.py": {"render_overview_page", ...}}
```

The whitelist is the shared-component modules —
`components/layout.py` (including `render_page_header`, `render_callout`,
`render_callout_stack`, `render_kpi_band`, `render_section_header`,
`render_filter_bar`), `components/states.py`, `components/html_table.py` and
`components/direction.py` — not the page modules, because the components
themselves must call those APIs.

**Status:** the contract above is ratified (D11) and **enforced** since Task 33 by
`tests/unit/dashboard/test_layout_guard.py`, whose `MIGRATED_PAGES` map starts
with the Overview's migrated functions and grows once per wave — Task 36 added the
A2 archetype's whole composition (`render_domain_page`, `render_domain_body`,
`_render_series_section`, `_render_scaled_chart`, `_render_capped_rows`,
`render_fx_gold_page`, `render_labor_page`). Until a function is listed, it is not
checked. A page module that is a **thin delegate** (no function of its own, one
call to a migrated composition function, no direct Streamlit call) has nothing
for a function-scoped guard to inspect; two tests in that file pin the four A2
page modules to that shape, so a page module that grows a composition of its own
fails rather than silently escaping the guard. The guard's whitelist is pinned
against the list above by its own test, so the two cannot drift.

## 13. Do / Don't

**Do**

- Build with a native element first; add scoped CSS second; reach for `st.html`
  third and only where nothing native exists.
- Put every user-visible string in `dashboard/i18n.py` and resolve it through
  `t()`; put every display name in `dashboard/labels.py`.
- Scope CSS with a keyed container or a stable `data-testid`, and register the
  selector in `CSS_SELECTORS`.
- Declare `direction: rtl` on any component container whose geometry depends on
  the inline start.
- Escape every data-derived value with `escape_html` before it reaches an HTML
  fragment.
- Keep tones in closed sets and raise on an unknown value — except where the value
  is data (the collection-run status chip), which falls back instead.
- Format numbers with `dashboard.formatting` before handing them to a component.
- Add a new selector to the chrome block's version note when you touch chrome.

**Don't**

- Don't target `st-emotion-cache-*`; the hash changes between builds.
- Don't emit a `<style>` block outside `direction.py`.
- Don't use `st.badge` inside `st.html`, or a raw `<a href>` for an internal page.
- Don't render the same state or callout key twice in one run — Streamlit raises
  on a repeated container key; pass `container_key`/`key` instead.
- Don't interpolate a data value into a class name.
- Don't reverse the Plotly time axis or flip the dataframe grid: both stay LTR.
- Don't change anything under `src/`, `alembic/` or `airflow/` for a presentation
  change. If a dashboard feature seems to need an ETL change, it is a new phase.
- Don't restyle the native `stHeader` or the native settings menu.

## 14. Accepted deviations from the mockup

| Mockup element | Deviation | Why |
|---|---|---|
| Inline-SVG nav and brand glyphs | A CSS-drawn shape or a Material/Unicode glyph | DOMPurify strips `<svg>` (`st.html` HTML profile) |
| Callout glyph | A CSS-drawn ring with the "i" dot and stem | The native alert ships no icon element |
| 48 px top bar | The native header stays 52.5 px; the mockup's bar is a new keyed container | Task 28 — the bar is `st.container(key="top-bar")` with `st.columns`; Step 0b seats it 12 px under the header (`padding-top: 64px`) |
| Non-bleed top bar | **Resolved by P5 (Wave C part 2)** — the top bar is full-bleed: the main container declares `--main-pad-x: 70px` and the bar's width, negative inline margin and matching inline padding all read that one property | Step 0b recorded the bar as contained; P5 measured the full-bleed variant at 1440 px and 1280 px with `scrollWidth == clientWidth` and kept it |
| Metric/subheader type scale | **Resolved by Step 0e** — the theme is now pinned to `TYPE_SCALE` (h1 28px/700, section 18px/600, metric value 28px/600); the mockup's line-heights and the KPI label's 13px/500 are not theme options, and **Task 29** pinned them in `direction.py` | `tokens.py` now holds `TYPE_SCALE`, so the scale is no longer "the theme's own"; the remaining three values are scoped CSS |
| KPI tag placement | A real `st.badge` beneath the metric, not the mockup's inline label tag (Task 29) | The `:orange-badge[…]` markdown shorthand leaks its syntax into the metric label and the tooltip's accessible name |
| KPI tooltip glyph | Streamlit's native `help=` marker (a circled `?`) rather than the mockup's circled `i` (Task 29) | The tooltip is the native `st.metric(help=…)`; `st.html` strips `<svg>`, and the native marker cannot be restyled without targeting a hashed class |
| Secondary KPI cell width | **Resolved by P2 (Wave C part 2)** — `kpi_column_weights` gives each secondary cell weight `1.35` against `1` for a primary cell, matching the mockup's `.kpi.sec{flex:1.35}` | `st.columns` owns the geometry and takes the ratio as weights; Task 29 left the cells equal-width and flagged it, and P2 made the ratio explicit and unit-tested |
| Freshness last-collection header | **Resolved by P3 (Wave C part 2)** — the Overview freshness table uses the new `table.last_collection` (`آخرین گردآوری`); the generic `table.collection_timestamp` (`زمان گردآوری`) stays for every other surface | The mockup's header is `آخرین گردآوری`; Task 30 reused the generic key and flagged it, and P3 added the dedicated key without changing the shared one |
| Freshness section summary | **Resolved by P4 (Wave C part 2)** — the stale count carries the markdown orange directive (`:orange[۲]`), which the theme maps to the warn palette (`orangeColor = #9A5B00`); the fresh count stays uncoloured | Task 30 left the summary one muted run; the section header's trailing slot is markdown, so the colour directive is the native route and needs no HTML fragment |
| Bar-list domain order | **Resolved by P1 (Wave C part 2)** — `ordered_domain_rows` sorts the rows count-descending, ties by the domain's Persian display name ascending, so the bars match the mockup's order | The mockup's bars are count-descending; Task 31 left `available_domains`'s order and flagged it here, and P1 made the sort explicit and unit-tested |
| Standalone `st.badge` chip at the top of the main block | Anchors to the host block's inline start (left in the LTR main block) | It is a native element, so its position follows the surrounding block. Its planned homes are RTL contexts (the sidebar, an RTL component container); wrap it in a keyed container declaring `direction: rtl` if a page needs it elsewhere |
| Filter-bar spacer | A `st.columns` weight, not `flex: 1` | `st.columns` expresses fixed proportions, not "absorb the remainder" |
| Coverage filter-bar selects | Native `st.selectbox` controls (label above, full column width) rather than the mockup's 32 px `.sel` chips with the label inline (`حوزه: همه`) | D13 native-first: the bar is the native widgets laid out by `render_filter_bar`. A chip-shaped control would need a custom widget, which this phase does not build. Measured: the bar is 73 px tall vs the mockup's 55 px |
| Coverage table width | The ten columns need 1169 px inside a 1042 px wrapper at 1440 px, so the last column is partly scrolled out; the mockup's shorter sample fits in 1102 px | Real data: 54 catalog rows with longer Persian names than the mockup's eight. The wrapper scrolls the table inside its own box and the page never scrolls sideways (AM-26, measured at 1440/1280/1024 px) |
| Coverage footnote wording | `تاریخ دقیق در راهنمای هر خانه است.` rather than the mockup's `تاریخ دقیق در tooltip است.` | The Task 13 catalog key predates Task 32 and keeps the Persian UI free of the English word "tooltip"; the literal guard forbids a hardcoded replacement |
| Native `st.caption` direction (shell-wide) | A caption inherits the main block's LTR direction, so a Persian sentence hugs the left edge. **Fixed for the coverage footnote only** by the scoped `coverage_footnote` hook; every other page's captions are unchanged | A shell-wide caption rule would move every un-migrated page's captions, which the wave discipline forbids. Filed for the Task 34 review as a shell defect |
| `render_page_header`'s callout label | **Added in Task 33** — the component gained an optional `label_key` forwarded to `render_callout`, so the header renders the mockup's bold `یادداشت روش‌شناسی` prefix | The plan's Task 33 file list named only `page_view.py` and the new guard, but the acceptance requires the Overview's amber callout to carry the bold label and Task 18's signature had no way to pass one. The parameter is additive and defaults to `None`, so the ratified Task 18 shape is unchanged for every other caller |

## 15. Open items

- **Task 27** records which sidebar-brand fallback shipped and extends section 6.
- **Task 28** ships the top bar/breadcrumb and the last-collection stamp (done).
- **Task 33** landed the D11 AST guard with its first `MIGRATED_PAGES` entry (done).
- **Task 47** extends this document with the top bar, the sidebar shell and the
  screenshot script, plus the per-archetype review outcomes.
- **Type-scale gaps (Step 0e → closed by Task 29).** The theme matches the
  mockup's font sizes and weights, and Task 29 pinned the three values the theme
  cannot express as scoped CSS in `direction.py`: the heading/body **line-heights**
  (h1 1.4, section 1.5, body 1.85 — measured 39.2 / 27 / 25.9 px), the **KPI
  label** (13px/500, was 12.25px/400) and the **secondary KPI value** (20px, the
  theme sets one 28px size). All five values are asserted in
  `test_direction.py`/`test_layout.py` and measured live (section 3).
- **KPI band fidelity for the Task 34 owner review.** The "نیازمند بررسی" tag
  renders beneath the metric rather than inline in the label (section 14). The
  secondary-cell width is now the mockup's `flex: 1.35` ratio (P2,
  `kpi_column_weights`), so only the tag placement remains an open deviation.
- **Deferred:** dark mode (D14), the explicit refresh control, indicator search on
  domain pages, the IMF forecast/actual labeling (needs an ETL change), and the
  cache-TTL item.
