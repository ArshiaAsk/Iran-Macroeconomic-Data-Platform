# Generic domain-explorer review — GDP, Trade & Energy, FX & Gold, Labor (Wave D)

**Status: OWNER REVIEW COMPLETE.**
**Owner sign-off: APPROVED.**

## Owner decision (recorded 2026-09-21)

The owner reviewed the four 1440×900 captures and the scroll crops and recorded:

- **Owner sign-off: APPROVED.**
- The domain pages **keep the shared `render_filters` filter set**; aligning it
  with `render_filter_bar` is an **optional Wave H polish candidate**, not
  scheduled.
- The **24-character id cap** in the quality table (full id in the `title`) is
  **approved**; the **absence of a KPI band** on domain pages is **approved**
  (N/A).
- **DEFECT 1** (`warn.single_observation` names TGJU while shown on the Labor
  page) is **fixed now** in Step 0b.
- **Carry-forward list for Wave H** (also added to the execution log): the
  filter-bar shape; optional polish **F1** (content padding 70 vs 40 px), **F2**
  (breadcrumb separator and bold current crumb), **F5** (shell-wide caption
  direction), **F7** (no-wrap short coverage columns); the Gregorian(LTR)/Jalali(RTL)
  range direction; and `scripts/dashboard_screenshots.py` `neutralise()` scrolls
  `stMainBlockContainer` (not the real scroll container `stMain`), so its
  scroll-to-top is a no-op (**Task 47**).

This is the Wave D owner visual review (Task 37). It walks the four A2
generic domain-explorer pages — GDP & Economy, Trade & Energy, FX & Gold, and
Labor — against the design system's **page-layout contract**
([`design-system.md`](../design-system.md) §11–§12) and against the Overview, the
Wave C reference implementation, **element by element**. There is no mockup for
the domain pages; the contract and the Overview are the reference.

The four pages are one **archetype**: they render the same composition
(`render_domain_page` / `render_domain_body`), so this review is one contract
walk applied to four routes, not four independent designs.

- **Reviewed tree:** `203954a` (Task 36), branch `phase-7.2`
- **Review date:** 2026-09-21
- **Data:** the populated local database (7 sources, 50 active indicators,
  8,195 Gold observations, 54 coverage rows)
- **Viewport:** 1440 × 900 (the plan's capture size)
- **Evidence:**
  - [`wave-d-assets/partB-all-pages/`](../wave-d-assets/partB-all-pages/) — the
    ten-page 1440×900 set captured after Task 36 (`gdp.png`, `trade_energy.png`,
    `fx_gold.png`, `labor.png`)
  - [`wave-d-assets/task-36/after-scroll/`](../wave-d-assets/task-36/after-scroll/)
    — the four pages at four scroll offsets each (the chart, the quality table,
    the observations expander and the downloads)
  - [`wave-d-assets/task-35/`](../wave-d-assets/task-35/) — the before/after sets
    that isolate the Task 35 composition change
  - [`wave-d-assets/step-0a/`](../wave-d-assets/step-0a/) — the Gregorian
    range-cell font fix crops

## 1. How the comparison was made

There is no pixel target, so the comparison is:

1. **Structural** — the same composition order on every page: page header, filter
   set, chart section, quality section, observations expander, downloads.
2. **Contract-level** — every D11 item in §12 is checked against the live DOM and
   the source; every §11 testing rule is checked against the suite.
3. **Measured** — the placeholder text, the legend title, the quality-table
   variant and its width, the observations row height, and the rendered section
   titles are read from the live DOM / the AppTest proto.

Where a page differs from the contract, the row says whether the difference is
the design (native-first, D13), the data, or a genuine gap.

## 2. The four pages (inventory)

| Page | Route | Domains | Header title | Caveat | Composition |
|---|---|---|---|---|---|
| GDP & Economy | `pages/3_GDP_Economy.py` | `gdp` | `page.gdp` — تولید ناخالص داخلی و اقتصاد | none | `render_domain_page` |
| Trade & Energy | `pages/4_Trade_Welfare_Energy.py` | `trade`, `energy` | `page.trade_energy` — تجارت و انرژی | none | `render_domain_page` |
| FX & Gold | `pages/5_FX_Gold.py` | `fx`, `gold` | `page.fx_gold` — ارز و طلا | `warn.tgju_snapshot` (warn) | `render_fx_gold_page` |
| Labor | `pages/10_Labor.py` | `labor` | `page.labor` — بازار کار | `warn.labor_publication` (info) | `render_labor_page` |

All four page modules are **thin delegates**: no function of their own, no
Streamlit import, one call to a migrated composition function. The two pages
without a caveat use `render_domain_page`; the two with one compose their own
header through `render_page_header(..., callout_key=…)` and then call
`render_domain_body`, so the title cannot appear twice.

## 3. Layout-contract matrix (§11–§12 × the four pages)

Verdicts: **MATCH** (the contract is met), **DEVIATION** (a recorded,
deliberate difference), **DEFECT** (a gap to fix), **N/A** (the item cannot
apply).

| # | Contract item (source) | GDP | Trade & Energy | FX & Gold | Labor |
|---|---|---|---|---|---|
| 1 | Opens with `render_page_header` (§12) | MATCH | MATCH | MATCH | MATCH |
| 2 | KPI values through `render_kpi_band` (§12) | N/A | N/A | N/A | N/A |
| 3 | Section titles through `render_section_header` (§12) | MATCH | MATCH | MATCH | MATCH |
| 4 | Filters through the shared bar (§12) | DEVIATION | DEVIATION | DEVIATION | DEVIATION |
| 5 | Empty / error / loading through `states.py` (§12) | MATCH | MATCH | MATCH | MATCH |
| 6 | No raw `st.title`/`st.metric`/`st.warning`/`st.info`/`st.error` (§12) | MATCH | MATCH | MATCH | MATCH |
| 7 | No `unsafe_allow_html` where a shared component exists (§12) | MATCH | MATCH | MATCH | MATCH |
| 8 | Header carries at most one callout slot (Task 18) | MATCH | MATCH | MATCH | MATCH |
| 9 | Filter widgets carry the Persian placeholder — **F4** (Task 35) | MATCH | MATCH | MATCH | MATCH |
| 10 | Chart legend carries no `label` title — **F3** (Task 35) | MATCH | MATCH | MATCH | MATCH |
| 11 | Quality summary via `render_html_table` typed cells (§4.3, §8) | MATCH | MATCH | MATCH | MATCH |
| 12 | Observations grid stays a `st.dataframe` with `row_height` (D1) | MATCH | MATCH | MATCH | MATCH |
| 13 | Table semantics preserved (`<th scope="col">`, `<bdi class="ltr">`) (§8) | MATCH | MATCH | MATCH | MATCH |
| 14 | Data-derived HTML escaped before it reaches a fragment (§13) | MATCH | MATCH | MATCH | MATCH |
| 15 | Every user-visible string resolves through `t()` (§13) | MATCH | MATCH | MATCH | MATCH |
| 16 | CSS scoped by a keyed container / stable hook (§5, §13) | MATCH | MATCH | MATCH | MATCH |

**Verdict tally:** 14 MATCH, 1 DEVIATION (the shared filter bar, row 4, carried
for the owner), 1 N/A (no KPI band on a domain page), **0 DEFECT in the
presentation layer**. One **content** defect is filed in §7 (the
single-observation warning names TGJU on the Labor page) — it lives in the shared
string catalog, not in the page composition.

### Row 2 — no KPI band (N/A)

A domain page has no aggregate metric to band: the Overview's KPI cells count
sources, domains, indicators and observations, which are Overview-scoped. The
domain pages open on the page header and the filter set, which is the archetype's
intended shape. `render_kpi_band` is not called and nothing is missing.

### Row 4 — the shared filter set (DEVIATION, carried)

The domain pages render their filter set through `render_filters`
(`components/filters.py`), the shared component that owns the four multiselects
(domain / frequency / source / indicators), the Jalali preset expander and the
two Gregorian date inputs. The Overview's coverage section instead lays three
`st.selectbox` controls out through `render_filter_bar` (Task 21).

This is the **recorded Task 35 interpretation** (VALIDATION.md, Wave D part A,
item 1): Task 35 does **not** restructure the domain filter set onto
`render_filter_bar`. The plan's Task 35 file list has no filter-bar refactor, no
mockup prescribes a domain-page bar, and the widgets, labels, keys and the
returned `FilterState` are unchanged. The row is therefore **DEVIATION** rather
than MATCH — the filter set is shared, but it is not the Overview's three-select
bar.

**Recommendation: accept as-is for Wave D.** A domain-page bar would be new
product design (which controls, which order, what collapses), and the phase's
rule is that a page wave migrates composition, not product copy. If the owner
wants one bar shape across the app, it is a small follow-up task on
`render_filters`, best bundled with the Wave H consistency audit.

### Row 9 — the F4 placeholder (MATCH, scheduled fix landed)

Every empty filter widget now shows the Persian `انتخاب کنید`
(`filter.placeholder`), not Streamlit's English "Choose options". Verified on all
four pages: the four `st.multiselect`s and the two Jalali `st.selectbox`es in
`render_filters` carry `placeholder=t("filter.placeholder")`, and
`test_filters.py::test_filter_widgets_carry_the_persian_placeholder` pins each
one's `proto.placeholder` and asserts it is not the English default. The four
captures show `انتخاب کنید` in each control.

### Row 10 — the F3 legend title (MATCH, scheduled fix landed)

The `gdp` chart's legend no longer carries the literal `label` heading. The fix
is at the single shared lever (`apply_plotly_typography` blanks
`legend_title_text`), so every time-series chart on every page is fixed at once;
`test_charts.py::test_shared_template_blanks_the_plotly_express_legend_title`
pins `not figure.layout.legend.title.text` for the facet, overlay and
small-multiples builders. The `gdp` capture shows the legend as the series entry
alone.

### Row 11 — the quality table (MATCH)

`render_quality_summary` renders the shared RTL HTML table (the `coverage`
variant), built from `localize_table_frame` — the same localizer the grid and the
exports use — so the migration is purely presentational and every value is
byte-identical. The `gdp` capture shows all eleven columns with Persian digits
(`۶۶`, `۰`, `خیر`, `سالانه`); the `labor` capture shows the single-quarter row
(`۱ / ۱ / خیر / ۰`) with Jalali dates. Measured width: `coverage` 1040 px inside
the page's 1042 px column, so there is **no sideways scroll** (contrast the
Overview coverage table's A4 deviation, which has 54 rows and needs 1169 px).

### Row 12 — the observations grid (MATCH)

The observations expander stays a `st.dataframe` with
`row_height=OBSERVATIONS_ROW_HEIGHT` (40 px, the `.dt.compact` density), per the
D1 classification: a large, scrollable, per-row table stays native; only the
small, static quality summary moved to the HTML table. Nothing about the row cap
changed — the truncation notice is now the shared `render_callout`.

## 4. Cross-page consistency (the four pages vs each other)

Because all four run the same composition, they agree by construction. Spot
checks confirm it:

| Aspect | Observation across the four pages |
|---|---|
| Header | Same `h1` shape (28 px / 700), same RTL start, aligned with the top bar's breadcrumb |
| Callout | FX & Gold amber (`warn`), Labor blue (`info`), GDP / Trade & Energy none — one slot, never two |
| Filter set | Same four controls in the same order, same Persian placeholder, same Jalali expander, same date inputs |
| Section titles | `نمودار سری‌های انتخاب‌شده` (`section.chart`) then `کیفیت داده` (`section.quality`), in that order |
| Chart mode | Same `chart.mode` control, default facets; the overlay notice uses `render_callout` when a mixed-unit overlay is refused |
| Quality table | Same `coverage` variant, same eleven columns, same typed cells |
| Observations | Same `st.dataframe` preview with the same row height and the same cap callout |
| Downloads | Same CSV/Excel buttons and the same chart-download pair |

## 5. Overview comparison

The four pages are compared to the Wave C Overview (the reference implementation)
on the surfaces they share:

| Aspect | Overview (Wave C) | The four domain pages | Verdict |
|---|---|---|---|
| Shell (top bar, breadcrumb, stamp) | Full-bleed top bar, breadcrumb, last-collection stamp | Identical — the shell is global | MATCH |
| Page header | `render_page_header` + methodology callout with a bold label | `render_page_header` + one caveat callout (no bold label) | MATCH — the bold label is the Overview's methodology note; the domain caveats are plain sentences (Task 36 review) |
| KPI band | Six-cell band | none | N/A (see §3 row 2) |
| Section headers | `render_section_header` with trailing summaries | `render_section_header` (chart, quality) | MATCH |
| Filter bar | three `st.selectbox` via `render_filter_bar` | four multiselects + dates via `render_filters` | DEVIATION (row 4) |
| Quality / coverage table | HTML `coverage` variant, typed cells | HTML `coverage` variant, typed cells | MATCH (same component) |
| Observations grid | (Overview uses the coverage table) | `st.dataframe(row_height)` | MATCH — same D1 rule, different data shape |
| Empty states | `render_empty` | `render_empty` | MATCH |
| Charts | shared template, legend title blank | shared template, legend title blank | MATCH |

**Summary:** the domain archetype is the Overview's shell and component set
applied to a per-domain selection. The only shared-surface difference is the
filter bar (row 4, carried for the owner).

## 6. Visual evidence

The Task 36 ten-page set and the four-page scroll crops are the evidence for
this review. The pixel diff of the Task 35 before/after pairs (VALIDATION.md,
Wave D part A) is the proof that the composition migration changed only the
presentation:

- `gdp`, `trade_energy` — the two `render_domain_page` pages are **byte-identical**
  to their pre-Task-36 state (0 changed pixels), confirming `render_page_header`
  reproduces `st.title` exactly.
- `fx_gold` — 5980 px in one strip (y 198–252): the amber TGJU caveat callout
  (accent bar and glyph) replacing the plain `st.warning`.
- `labor` — 12774 px in one strip (y 198–277): the blue SCI caveat callout
  replacing the plain `st.info` (taller because the caveat wraps to two lines).
- Task 35 changed the four pages' quality tables (native grid → HTML table), the
  section headers, the F4 placeholders and the shared empty-state callout; no
  value, column or download changed.

## 7. Defects and recommendations

### DEFECT 1 — the single-observation warning names TGJU on the Labor page (content, not layout)

The Labor capture shows the quality summary's single-observation warning:

> یک یا چند سری انتخاب‌شده تنها یک مشاهده دارد. **TGJU** منبعی لحظه‌ای است و
> تاریخچه از طریق گردآوری روزانه انباشته می‌شود.

The Labor page's lone observation is SCI's quarterly unemployment rate, **not**
TGJU. The shared string `warn.single_observation` (`i18n.py:351`) names TGJU as
the explanation, so the sentence is inaccurate on any page whose single-observation
series is not TGJU. The migration did not introduce the string — it was already
used by `render_quality_summary` — but the migration is what surfaced it on the
Labor page.

**Recommendation (owner decision): FIX NOW in Step 0b.** The sentence is made
source-neutral (drop the TGJU clause, keep the "daily collection accumulates the
series" half). This is a **string-catalog** change plus a test; it is applied in
Wave E Step 0b, ahead of the emphasis-domain migrations, so no page shows the
inaccurate sentence.

### Carried items for the owner (no new defect)

1. **The shared filter set is not `render_filter_bar`** (§3 row 4) — accept, or
   schedule one bar shape for Wave H.
2. **The quality-table id cell is capped at 24ch** by the shared `.dt .ltr` rule
   (`SCI.UNEMPLOYMENT.QUARTERLY` → `SCI.UNEMPLOYMENT.QUART…`). The cell carries
   the full id as its `title`, so the token is recoverable on hover — the same
   cap and tooltip practice the Overview coverage table already uses. Widening it
   would touch a global rule, so it is carried rather than changed here.

## 8. Owner checklist

The owner reviews the four 1440×900 captures in
[`wave-d-assets/partB-all-pages/`](../wave-d-assets/partB-all-pages/) and the
scroll crops in
[`wave-d-assets/task-36/after-scroll/`](../wave-d-assets/task-36/after-scroll/),
then works down this list.

- [x] The four pages share one header shape: the Persian title at the RTL start,
      aligned with the top bar's breadcrumb.
- [x] FX & Gold carries the amber TGJU snapshot caveat and Labor the blue SCI
      publication caveat — one callout slot each; GDP and Trade & Energy carry
      none.
- [x] Every filter widget shows `انتخاب کنید`, not Streamlit's English
      "Choose options" (**F4**).
- [x] No chart legend carries a `label` heading (**F3**).
- [x] The quality summary is the shared RTL HTML table: eleven columns, Persian
      digits, LTR mono ids, em-dash nulls, no sideways scroll.
- [x] The observations expander is a native grid with the documented row height
      and the row-cap notice.
- [x] Empty states read as the shared callout (`render_empty`), not a hand-rolled
      alert.
- [x] **Row 4** — the shared filter set is `render_filters`, not the Overview's
      `render_filter_bar` — **accepted as-is**; aligning it is an optional Wave H
      polish candidate.
- [x] The 24ch quality-table id cap with the `title` tooltip is acceptable.
- [x] **DEFECT 1** — the single-observation warning names TGJU on the Labor page —
      **fixed now** in Step 0b (source-neutral string).
- [x] No element of the archetype is missing, and no page silently differs from
      the others.

**Owner sign-off: APPROVED.**

## 9. What this gate unblocks

When the owner records the decision above, Wave D closes and **Wave E** (the
emphasis-domain pages: Inflation, Welfare, Market — Tasks 38–40 and the Task 41
review) starts. The two scheduled Wave D fixes (**F3**, **F4**) have landed;
**DEFECT 1** is filed for a later wave and does not block Wave E.
