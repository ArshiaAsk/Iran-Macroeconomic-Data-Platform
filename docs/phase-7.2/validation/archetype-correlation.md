# Comparison / correlation review — Correlation (Wave F)

**Status: PREPARED — AWAITING OWNER REVIEW.**
**Owner sign-off: PENDING.**

This is the Wave F owner visual review (Task 43). It walks the A4
**comparison / correlation** page against the design system's **page-layout
contract** ([`design-system.md`](../design-system.md) §11–§12) and against the
Overview (the Wave C reference), the generic domain explorer (the Wave D
reference) and the emphasis-domain pages (the Wave E reference), **element by
element**. There is no mockup for the correlation page; the contract and the
earlier archetypes are the reference.

The page is the A4 archetype: header + caveats → filter set → heatmap → two
summary tables → quality → downloads.

- **Reviewed tree:** `f557a45` (Task 42) on branch `phase-7.2`
- **Review date:** 2026-09-22
- **Data:** the populated local database (7 sources, 50 active indicators,
  8,195 Gold observations, 54 coverage rows); five indicators selected
  (free USD rate, two EIA oil series, two World Bank GDP series)
- **Viewport:** 1440 × 900 (the plan's capture size) plus full-page captures
- **Evidence:**
  - [`wave-f-assets/task43/`](../wave-f-assets/task43/) — the default empty state,
    the selected top, the heatmap and the join/overlap tables (viewport + full-page)
  - [`wave-f-assets/task-42/before/`](../wave-f-assets/task-42/before/) and
    [`wave-f-assets/task-42/after/`](../wave-f-assets/task-42/after/) — the Task 42
    before/after crops

## 1. How the comparison was made

There is no pixel target, so the comparison is:

1. **Structural** — the composition order: page header, caveat(s), filter set,
   heatmap, summary tables, quality, downloads.
2. **Contract-level** — every D11 item in §12 is checked against the live DOM and
   the source; every §11 testing rule is checked against the suite.
3. **Measured** — the callout tones and their container keys, the table variants,
   the heatmap's colour scale and colour-bar labels, and the empty state are read
   from the live DOM / the figure / the AppTest proto.

Where the page differs from the contract, the row says whether the difference is
the design (native-first, D13), the data, or a genuine gap.

## 2. The page (inventory)

| Page | Route | Registry key | Header title | Caveats | Figures | Tables |
|---|---|---|---|---|---|---|
| Correlation | `pages/6_Correlation.py` | `correlation` | `page.correlation` — مقایسه و همبستگی | mixed frequencies (warn), low overlap (warn), exact join (info) — top | heatmap (`build_correlation_chart`) | join-count matrix (`st.dataframe`), overlap summary (`st.dataframe`), quality summary (`render_html_table`) |

The page module is a **thin delegate**: no function of its own, no Streamlit
import, one call to the migrated `render_correlation_page`.

## 3. Layout-contract matrix (§11–§12 × the page)

Verdicts: **MATCH** (the contract is met), **DEVIATION** (a recorded,
deliberate difference), **DEFECT** (a gap to fix), **N/A** (the item cannot
apply).

| # | Contract item (source) | Verdict | Evidence |
|---|---|---|---|
| 1 | Opens with `render_page_header` (§12) | MATCH | `render_page_header("page.correlation")`; native `st.title` keeps `app.title` |
| 2 | KPI values through `render_kpi_band` (§12) | N/A | the page has no aggregate metric to band |
| 3 | Section titles through `render_section_header` (§12) | MATCH | `render_section_header("section.exact_join_counts")` replaces the raw `st.subheader` |
| 4 | Filters through the shared bar (§12) | DEVIATION | the page uses `render_filters` (the shared filter set), not the Overview's `render_filter_bar` — same recorded interpretation as Waves D/E |
| 5 | Empty / error / loading through `states.py` (§12) | MATCH | the three states are `render_empty` (catalog-empty, no-selection, no-observations); the no-selection state renders as the shared info callout (`review-empty.png`) |
| 6 | No raw `st.title`/`st.metric`/`st.warning`/`st.info`/`st.error` (§12) | MATCH | the D11 guard covers `render_correlation_page` and reports nothing |
| 7 | No `unsafe_allow_html` where a shared component exists (§12) | MATCH | no raw HTML in the page |
| 8 | Caveats through `render_callout` / `render_callout_stack` (Task 18/40) | MATCH | mixed frequencies + low overlap (warn) and exact join (info) are `render_callout`; the low-overlap text carries values through `body=` |
| 9 | Filter widgets carry the Persian placeholder — **F4** (Task 35) | MATCH | `render_filters` supplies `filter.placeholder` |
| 10 | Chart legend carries no `label` title — **F3** (Task 35) | N/A | the heatmap has a colour bar, not a legend |
| 11 | Quality summary via `render_html_table` typed cells (§4.3, §8) | MATCH | `render_quality_summary` (already migrated) |
| 12 | Static summary table via `render_html_table` (Task 35 pattern) | N/A | the two summary tables are classified `st.dataframe` per D1 (a matrix and a sortable N-row table), not the small-static class |
| 13 | Large/sortable table stays a `st.dataframe` with `row_height` (D1) | MATCH | join-count matrix `st.dataframe`; overlap summary `st.dataframe(row_height=OBSERVATIONS_ROW_HEIGHT)` |
| 14 | Table semantics preserved (`<th scope="col">`, `<bdi class="ltr">`) (§8) | MATCH | the quality summary is the shared typed-cell table |
| 15 | Data-derived HTML escaped before it reaches a fragment (§13) | MATCH | only the shared components emit HTML |
| 16 | Every user-visible string resolves through `t()` (§13) | MATCH | `test_literal_guard.py` green |
| 17 | CSS scoped by a keyed container / stable hook (§5, §13) | MATCH | callouts and section header bring their own hooks; no new CSS |
| 18 | Callout container keys distinct within a run (Task 17) | MATCH | `warn.mixed_frequencies`, `warn.correlation_low_overlap`, `warn.correlation_exact_join` are distinct, so several can render in one run |

**Verdict tally:** 14 MATCH, 1 DEVIATION (the shared filter set, row 4),
3 N/A (no KPI band, no legend, no small-static summary table),
**0 DEFECT in the presentation layer**.

### Row 4 — the shared filter set (DEVIATION, carried)

The page renders its filter set through `render_filters`
(`components/filters.py`), the shared component that owns the multiselects, the
Jalali preset expander and the Gregorian date inputs. The Overview's coverage
section instead lays three `st.selectbox` controls out through
`render_filter_bar` (Task 21).

This is the **same recorded interpretation as Waves D and E** (VALIDATION.md,
Wave D part A; archetype-emphasis.md row 4): the plan's Task 42 file list has no
filter-bar refactor, no mockup prescribes a correlation-page bar, and the
widgets, labels, keys and the returned `FilterState` are unchanged. The row is
**DEVIATION** rather than MATCH — the filter set is shared, but it is not the
Overview's three-select bar.

**Recommendation: accept as-is**, or schedule one bar shape across the app for
Wave H (bundled with the Wave D/E carry item).

### Row 8 — the caveats and the heatmap readability check

The three caveats are all `render_callout` with distinct container keys. The
exact-join note changed from a raw `st.caption` to an **info** callout (contract:
notices are callouts), which is the only new visible element on the page.

The heatmap itself is **unchanged**. The figure's first trace is a `heatmap` with
`zmin=-1`, `zmax=1` and `colorscale=None` (Plotly's default diverging scale); the
colour-bar title `chart.pearson_r` renders; the template's `layout.colorscale` is
an **empty** `Colorscale()` (`sequential=None`, `diverging=None`) and its
`layout.colorway` does not apply to a heatmap trace, so the categorical palette
does **not** override the diverging scale. Visually the red→white→blue scale, the
colour-bar labels (۱، ۰٫۵، ۰، −۰٫۵، −۱) and the axis labels are readable in
`review-heatmap.png`. No axis was reversed.

## 4. Cross-page consistency

The page is compared to the Overview (Wave C), the generic domain explorer
(Wave D) and the emphasis pages (Wave E) on the surfaces they share:

| Aspect | Overview (Wave C) | Domain / emphasis (Waves D/E) | Correlation | Verdict |
|---|---|---|---|---|
| Shell (top bar, breadcrumb, stamp) | Full-bleed top bar | Identical | Identical — the shell is global | MATCH |
| Page header | `render_page_header` + methodology callout | `render_page_header` + caveat(s) | `render_page_header` + three caveats | MATCH |
| KPI band | Six-cell band | Market one-cell; others none | none | N/A |
| Section headers | `render_section_header` with trailing summaries | `render_section_header` | `render_section_header` | MATCH |
| Filter bar | three `st.selectbox` via `render_filter_bar` | `render_filters` | `render_filters` | DEVIATION (row 4) |
| Caveats | callout with a bold label | callouts / callout stack | three callouts (two warn, one info) | MATCH |
| Quality table | HTML `coverage` variant | HTML `coverage` variant | HTML `coverage` variant | MATCH (same component) |
| Large/sortable table | (coverage table) | `st.dataframe(row_height)` | `st.dataframe(row_height)` + a matrix `st.dataframe` | MATCH |
| Empty states | `render_empty` | `render_empty` / `render_callout` | `render_empty` | MATCH |
| Charts | shared template, legend title blank | shared template | shared template (heatmap) | MATCH |

**Summary:** the correlation archetype is the Overview's shell and component set
plus the A2/A3 table and quality building blocks. The only shared-surface
difference is the filter bar (row 4, carried).

## 5. Changed test assertions

| Assertion | Change | Reason |
|---|---|---|
| `test_correlation_page_warns_and_suppresses_a_low_overlap_pair` | the exact-join note assertion moved from `app.caption` to `app.info` | the exact-join note is now an info callout (contract: notices are callouts) |

Every other correlation assertion passes **unchanged**: `app.warning` still sees
the mixed-frequencies and low-overlap caveats (they remain native `st.warning`),
`app.dataframe` still sees the overlap summary (`table.matched_observations` /
`table.meets_minimum_overlap`), and `test_correlation_page_renders` still asserts
`not app.exception`.

## 6. Visual evidence and the pixel diff

| Capture | Changed pixels (viewport) | What changed |
|---|---|---|
| `top` | 4.0 % | the exact-join note became an info callout (added at the foot of the viewport) |
| `heatmap` | larger only from a vertical shift | the added callout pushes the page down; the heatmap, its colour scale, colour-bar labels and axis labels are visually identical |
| `tables` | larger only from a vertical shift | the join-count matrix and overlap summary keep the same columns and values; the overlap summary takes the shared `row_height` |

**No regressions.** Every changed pixel is the new info callout or the vertical
shift it causes; no value, column, panel or download changed, and the suppression
and overlap logic is byte-for-byte unchanged.

## 7. Defects and recommendations

**No presentation-layer defect is filed.** One carried decision is recorded for
the owner:

1. **Row 4 — the shared filter set is `render_filters`, not `render_filter_bar`**
   — accept, or schedule one bar shape for Wave H (same as the Wave D/E carry
   item).

The Wave D carry list (F1, F2, F5, F7, filter-bar shape, Gregorian/Jalali range
direction, `neutralise()` scroll no-op Task 47) is unchanged and still open.

## 8. Owner checklist

The owner reviews the captures in
[`wave-f-assets/task43/`](../wave-f-assets/task43/) and the Task 42 before/after
crops, then works down this list.

- [ ] The page opens with the shared header and the three caveats render as
      callouts (two amber, one blue) with distinct accent bars at the RTL start.
- [ ] The empty state (`review-empty.png`) reads as the shared callout, not a
      hand-rolled alert.
- [ ] The heatmap's colour scale is the diverging red→white→blue scale (not the
      categorical palette), and its colour-bar labels and axis labels are readable.
- [ ] **Hover tooltips:** hovering a heatmap cell shows the Pearson coefficient and
      the axis pair; the colour bar shows its value.
- [ ] **1280 px and 1024 px:** the two summary tables stay side by side and the
      heatmap stays readable at the narrower widths.
- [ ] **Heatmap interaction:** zoom/pan and the Plotly toolbar work; no axis is
      reversed.
- [ ] The join-count matrix and the overlap summary keep their columns and values.
- [ ] **Row 4** — the shared filter set is `render_filters`, not the Overview's
      `render_filter_bar` — **accept or schedule for Wave H**.
- [ ] No element of the archetype is missing, and no page silently differs from
      the others.

**Owner sign-off: PENDING.**

## 9. What this gate unblocks

When the owner records the decision above, Wave F closes. The one carried
decision (row 4) does **not** block Wave G: it is either a Wave H polish candidate
or an accepted shared interpretation.
