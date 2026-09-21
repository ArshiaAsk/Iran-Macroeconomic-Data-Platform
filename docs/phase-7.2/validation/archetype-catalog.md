# Catalog review — Data Catalog (Wave G)

**Status: SIGNED OFF — APPROVED (P1 verified).**
**Owner sign-off: APPROVED (2026-09-22). The one defect (row 22) is resolved by
Wave H P1.**

This is the Wave G owner visual review (Task 45). It walks the A5 **data catalog**
page against the design system's **page-layout contract**
([`design-system.md`](../design-system.md) §11–§12) and against the Overview (the
Wave C reference), the generic domain explorer (Wave D), the emphasis pages
(Wave E) and the correlation page (Wave F), **element by element**. There is no
mockup for the catalog page; the contract and the earlier archetypes are the
reference.

The page is the A5 archetype: header → filter bar (search + inactive toggle +
clear) → the shared filter set (full width) → matching count → grid.

- **Reviewed tree:** `ed2b4a4` (Task 44) on branch `phase-7.2`
- **Review date:** 2026-09-22
- **Data:** the populated local database (7 sources, 50 active indicators, 54
  coverage rows, 4 inactive SCI base-year segments)
- **Viewport:** 1440 × 900 (the plan's capture size) plus a full-height capture
  (1440 × 1397)
- **Evidence:**
  - [`wave-g-assets/task45/`](../wave-g-assets/task45/) — the default top, the
    full-height capture, the search state and the grid
  - [`wave-g-assets/task-44/before/`](../wave-g-assets/task-44/before/) and
    [`wave-g-assets/task-44/after/`](../wave-g-assets/task-44/after/) — the Task 44
    before/after top and grid

## 1. How the comparison was made

There is no pixel target, so the comparison is:

1. **Structural** — the composition order: page header, filter bar, matching
   count, grid.
2. **Contract-level** — every D11 item in §12 is checked against the live DOM and
   the source; every §11 testing rule is checked against the suite.
3. **Measured** — the hosted controls, the KPI cell width, the grid columns and
   row height, and the search-count behaviour are read from the live DOM / the
   AppTest proto.

Where the page differs from the contract, the row says whether the difference is
the design (native-first, D13), the data, or a genuine gap.

## 2. The page (inventory)

| Page | Route | Registry key | Header title | Controls | Count | Grid |
|---|---|---|---|---|---|---|
| Data Catalog | `pages/7_Data_Catalog.py` | `catalog` | `page.catalog` — فهرست دادهها | search + inactive toggle + clear in one `render_filter_bar`; the shared filter set (`render_filters`) full width beneath the bar | one-cell `render_kpi_band` (`metric.matching_indicators`) | `st.dataframe` (sortable, LTR grid) |

The page module is a **thin delegate**: no function of its own, no Streamlit
import, one call to the migrated `render_catalog_page`.

## 3. Layout-contract matrix (§11–§12 × the page)

Verdicts: **MATCH** (the contract is met), **DEVIATION** (a recorded,
deliberate difference), **DEFECT** (a gap to fix), **N/A** (the item cannot
apply).

| # | Contract item (source) | Verdict | Evidence |
|---|---|---|---|
| 1 | Opens with `render_page_header` (§12) | MATCH | `render_page_header("page.catalog")`; native `st.title` keeps `app.title` |
| 2 | KPI values through `render_kpi_band` (§12) | MATCH | the matching count is a one-cell band (`review-top.png`); the Step 0b padding gives the lone cell the reference width |
| 3 | Section titles through `render_section_header` (§12) | N/A | the page has no section titles |
| 4 | Filters through the shared bar (§12) | MATCH | the page **hosts** its controls in one `render_filter_bar` (search, the shared filter set, the inactive toggle, clear) |
| 5 | Empty / error / loading through `states.py` (§12) | MATCH | catalog-empty and no-match states are `render_empty` |
| 6 | No raw `st.title`/`st.metric`/`st.warning`/`st.info`/`st.error` (§12) | MATCH | the D11 guard covers `render_catalog_page` and reports nothing |
| 7 | No `unsafe_allow_html` where a shared component exists (§12) | MATCH | no raw HTML in the page |
| 8 | Caveats through `render_callout` / `render_callout_stack` (Task 18/40) | N/A | the page has no caveats |
| 9 | Filter widgets carry the Persian placeholder — **F4** (Task 35) | MATCH | `render_filters` supplies `filter.placeholder` |
| 10 | Chart legend carries no `label` title — **F3** (Task 35) | N/A | the page has no charts |
| 11 | Quality summary via `render_html_table` typed cells (§4.3, §8) | N/A | the catalog has no quality table |
| 12 | Static summary table via `render_html_table` (Task 35 pattern) | N/A | the grid is classified `st.dataframe` (sortable, D1) |
| 13 | Large/sortable table stays a `st.dataframe` with `row_height` (D1) | MATCH | `st.dataframe(..., row_height=OBSERVATIONS_ROW_HEIGHT)`, sortable, LTR grid |
| 14 | Table semantics preserved (`<th scope="col">`, `<bdi class="ltr">`) (§8) | N/A | the page has no HTML table |
| 15 | Data-derived HTML escaped before it reaches a fragment (§13) | MATCH | the page emits no HTML |
| 16 | Every user-visible string resolves through `t()` (§13) | MATCH | `test_literal_guard.py` green |
| 17 | CSS scoped by a keyed container / stable hook (§5, §13) | MATCH | the filter bar and the KPI band bring their own hooks; no new CSS |
| 18 | Callout container keys distinct within a run (Task 17) | MATCH | the two `render_empty` keys are distinct and never both render in one run |

**Catalog-specific rows**

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 19 | The search box is hosted by the bar | MATCH | `catalog_search`, value unchanged (`review-search.png` shows `SCI.CPI` → ۱۳ matches) |
| 20 | The inactive toggle is hosted by the bar; key/default unchanged | MATCH | `catalog_include_inactive`; the value is read before the bar so the count/grid describe the same run |
| 21 | The clear button is hosted by the bar; `on_click` and reset keys unchanged | MATCH | `catalog_clear_filters` + `_clear_catalog_filters` + `CATALOG_FILTER_STATE_KEYS`, unchanged |
| 22 | The shared filter set is hosted by the bar | **MATCH — resolved by P1** | the bar now hosts only the three simple controls (search, toggle, clear) with weights `[3.0, 2.0, 1.0]`; `render_filters` is full width beneath the bar, and the toggle renders before the empty-catalog check |
| 23 | Grid columns, values and order unchanged | MATCH | `before-grid.png` vs `after-grid.png`: same columns/values; only the row height changed |
| 24 | The LTR-grid limitation is documented | MATCH | design-system §8 (the catalog grid note) |

**Verdict tally:** 16 MATCH, 8 N/A, **0 DEFECT** (row 22 resolved by Wave H P1).
The empty-catalog micro-deviation is accepted and was also fixed by P1.

### Row 22 — the shared filter set in the bar (RESOLVED by Wave H P1)

Task 44 hosted the whole shared filter set (`render_filters`) **inside**
`render_filter_bar` as one of four equal columns. The set is seven widgets tall
(four multiselects, the Jalali preset expander, two date inputs and the range
echo), so its column was much taller than the other three and the bar carried
white space beside them. The owner classified this a **defect, not an accepted
deviation** (2026-09-22), fixed in Wave H **P1**.

**Measured before (ed2b4a4) vs after (P1), live DOM at 1440 px:**

| Metric | Before (Task 44) | After (P1) |
|---|---|---|
| Filter bar box | 1044 × **555 px** | 1044 × **61 px** |
| Bar columns | 4 equal, **251 px** each | 3 weighted, **513 / 339 / 165 px** (search / toggle / clear) |
| Filter-set column | **251 px wide × 555 px tall** (the tall narrow column) | — (no longer in the bar) |
| `render_filters` (first widget) | inside the bar, 251 px wide | **full width, 1044 px**, beneath the bar |

The tall narrow column is **gone**: the bar is 61 px (the search field's height),
the search field takes the widest column, and the shared filter set renders at full
width in its original position beneath the bar. The inactive toggle renders
**before** the empty-catalog check, so it stays visible on an empty catalog (its
pre-Task-44 behaviour). Every widget key, the clear button's `on_click` callback,
`CATALOG_FILTER_STATE_KEYS` and the defaults are unchanged. Evidence:
[`wave-h-assets/p1/`](../wave-h-assets/p1/) (`before-top.png`, `before-full.png`,
`after-top.png`, `after-full.png`).

### Micro-deviation — the empty catalog

On an **empty catalog** the inactive toggle no longer renders: the page returns
through `render_empty` before the bar is built, whereas the original rendered the
checkbox before its empty check. The catalog is never empty in practice and no
test covers the path; the toggle's key, callback and default are unchanged.
**Recommendation: accept** (a view control over an empty catalog is meaningless).

## 4. Cross-page consistency

The page is compared to the other archetypes on the surfaces they share:

| Aspect | Overview (C) | Domain / emphasis (D/E) | Correlation (F) | Catalog (G) | Verdict |
|---|---|---|---|---|---|
| Shell (top bar, breadcrumb, stamp) | Full-bleed top bar | Identical | Identical | Identical — the shell is global | MATCH |
| Page header | `render_page_header` + callout | `render_page_header` + caveat(s) | `render_page_header` + caveats | `render_page_header` (no caveat) | MATCH |
| Filter bar | three `st.selectbox` via `render_filter_bar` | `render_filters` (not the bar) | `render_filters` (not the bar) | **bar of three simple controls + full-width `render_filters`** | MATCH (row 22 resolved by P1) |
| KPI band | Six-cell band | Market one-cell; others none | none | one-cell (matching count) | MATCH |
| Section headers | `render_section_header` | `render_section_header` | `render_section_header` | none | N/A |
| Large/sortable table | (coverage table) | `st.dataframe(row_height)` | `st.dataframe(row_height)` + matrix | `st.dataframe(row_height)` | MATCH |
| Empty states | `render_empty` | `render_empty` / `render_callout` | `render_empty` | `render_empty` | MATCH |
| Charts | shared template | shared template | shared template (heatmap) | none | N/A |

**Summary:** the catalog archetype is the Overview's shell and component set plus
the D1 sortable grid and the shared empty state. Its one shared-surface
difference is the filter bar's layout (row 22), classified a **defect** by the
owner and fixed in Wave H **P1**.

## 5. Changed test assertions

**None.** Every existing `test_app_catalog.py` assertion passes **unchanged**: the
grid columns/values (`test_catalog_grid_uses_persian_headers`), the inactive
toggle (both tests), the four search cases and the clear-reset test all hold,
because the hosted widgets keep their keys and behaviour. Two tests were **added**
for the new surface:

| Test | Asserts |
|---|---|
| `test_catalog_matching_count_is_a_kpi_band_cell` | the matching count is the page's single `app.metric`, with label `metric.matching_indicators` and a value equal to the grid row count |
| `test_catalog_hosts_every_control_in_the_filter_bar` | the search box, the toggle, the clear button and the four shared filter multiselects all render in one run (`AppTest` cannot see the bar's keyed container) |

## 6. Visual evidence and the pixel diff

| Capture | Changed pixels (viewport) | What changed |
|---|---|---|
| `top` | 25.0 % | the vertical filter stack became a four-column filter bar; the matching count is now a one-cell KPI band |
| `grid` | 17.8 % | the grid rows take the shared `row_height`; the page above the grid moved (the bar replaced the stack) |

The grid's columns, values and order are unchanged (`before-grid.png` vs
`after-grid.png`). The full-height capture (`review-full.png`, 1440 × 1397) is the
below-the-fold evidence.

**No data regression.** Every changed pixel is layout: the filter bar, the KPI
band and the grid row height. No column, value, order or search/filter/clear
result changed.

## 7. Defects and recommendations

**No open presentation-layer defect.** The one defect (row 22) is **resolved by
Wave H P1**, and the accepted micro-deviation is also fixed by P1:

1. **Row 22 — the shared filter set was hosted as a tall, narrow bar column** —
   the owner classified this a **defect**; **P1** now hosts only the three simple
   controls (search, toggle, clear) in the bar and renders `render_filters` at full
   width. Measured: bar 555 px → 61 px; filter set 251 px → 1044 px wide.
2. **The empty catalog** — P1 restored the toggle-before-empty-check order, so the
   toggle renders even when the catalog is empty (its pre-Task-44 behaviour).

The Wave D carry list (F1, F2, F5, F7, filter-bar shape, Gregorian/Jalali range
direction, `neutralise()` scroll no-op Task 47) is unchanged and still open.

## 8. Owner checklist

The owner reviews the captures in
[`wave-g-assets/task45/`](../wave-g-assets/task45/), the Task 44 before/after
crops and the P1 before/after crops in
[`wave-h-assets/p1/`](../wave-h-assets/p1/), then works down this list.

- [x] The page opens with the shared header; the search box, the inactive toggle
      and the clear button sit in one bar (P1: the filter set is full width below).
- [x] The matching count is a one-cell KPI band at the RTL start, not stretched
      across the content column.
- [x] **Search:** typing narrows the count and the grid; a no-match needle shows
      the shared empty state.
- [x] **Inactive toggle:** checking it reveals the four SCI base-year segments.
- [x] **Clear:** the button resets the search and every filter to their defaults.
- [x] **1280 px and 1024 px:** the bar columns stay usable and the filter widgets
      do not truncate their labels.
- [x] The grid stays sortable and its columns/values are unchanged; the LTR-grid
      limitation is understood (the id column is LTR inside the RTL page).
- [x] **Row 22** — the shared filter set is a tall, narrow bar column — **is a
      defect; fixed in Wave H P1** (bar 555 → 61 px; filter set 251 → 1044 px).
- [x] No element of the archetype is missing, and no page silently differs from
      the others.

## 9. What this gate unblocks

Wave G is closed: the owner's decision is recorded and its one **defect** (row 22)
is resolved by Wave H **P1** (§10). The Task 45 plan box is ticked.

## 10. Owner sign-off (recorded 2026-09-22)

The owner's decision, verbatim:

- **Owner sign-off: APPROVED, conditional on P1.** The 15 MATCH rows and the 8 N/A
  rows are accepted.
- **Row 22 — the shared filter set hosted as a tall narrow bar column — is a
  DEFECT, not an accepted deviation.** The bar must host only the simple controls
  and `render_filters` must return to full width. Fixed in Wave H **P1**; the Task
  45 plan box is ticked only after P1 is verified.
- **The empty-catalog micro-deviation is accepted**, and P1 restores the
  toggle-before-empty-check order.

**P1 verified (2026-09-22).** The bar is 61 px tall with three weighted columns
(513 / 339 / 165 px) and `render_filters` is full width (1044 px); the toggle
renders on an empty catalog. The defect is resolved and the Task 45 plan box is
ticked.

**Owner sign-off: APPROVED (2026-09-22); P1 verified.**
