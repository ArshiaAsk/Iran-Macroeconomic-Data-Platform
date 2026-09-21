# Catalog review — Data Catalog (Wave G)

**Status: PREPARED — AWAITING OWNER REVIEW.**
**Owner sign-off: PENDING.**

This is the Wave G owner visual review (Task 45). It walks the A5 **data catalog**
page against the design system's **page-layout contract**
([`design-system.md`](../design-system.md) §11–§12) and against the Overview (the
Wave C reference), the generic domain explorer (Wave D), the emphasis pages
(Wave E) and the correlation page (Wave F), **element by element**. There is no
mockup for the catalog page; the contract and the earlier archetypes are the
reference.

The page is the A5 archetype: header → filter bar (search + shared filter set +
inactive toggle + clear) → matching count → grid.

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
| Data Catalog | `pages/7_Data_Catalog.py` | `catalog` | `page.catalog` — فهرست دادهها | search + shared filter set (`render_filters`) + inactive toggle + clear, all in one `render_filter_bar` | one-cell `render_kpi_band` (`metric.matching_indicators`) | `st.dataframe` (sortable, LTR grid) |

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
| 22 | The shared filter set is hosted by the bar | DEVIATION | `render_filters` is hosted as one bar column; the set is tall, so its column is much taller than the other three (layout observation below) |
| 23 | Grid columns, values and order unchanged | MATCH | `before-grid.png` vs `after-grid.png`: same columns/values; only the row height changed |
| 24 | The LTR-grid limitation is documented | MATCH | design-system §8 (the catalog grid note) |

**Verdict tally:** 15 MATCH, 1 DEVIATION (row 22, the tall filter set in a narrow
bar column), 8 N/A, **0 DEFECT in the presentation layer**.

### Row 22 — the shared filter set in the bar (DEVIATION, recorded)

The catalog page is the first page to host the whole shared filter set
(`render_filters`) **inside** `render_filter_bar`, as Task 44 asks. The bar lays
four equal columns (`[search, filters, inactive, clear]`); the filter set is seven
widgets tall (four multiselects, the Jalali preset expander, two date inputs and
the range echo), so its column is much taller than the other three and the bar
carries white space beside them. Nothing about the widgets changes: every key,
the placeholder, the expander and the returned `FilterState` are the same, and the
matching count and grid are unchanged.

This is the **first** page where the filter set is the bar (Waves D/E and the
correlation page record the opposite: `render_filters` is *not* the Overview's
three-select bar). **Recommendation:** accept, or schedule the Wave H bar-shape
work (bundled with the Wave D/E/F carry item) to give the filter column a
two-row or wider layout.

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
| Filter bar | three `st.selectbox` via `render_filter_bar` | `render_filters` (not the bar) | `render_filters` (not the bar) | **`render_filter_bar` hosting `render_filters`** | MATCH (row 22 DEVIATION on the layout) |
| KPI band | Six-cell band | Market one-cell; others none | none | one-cell (matching count) | MATCH |
| Section headers | `render_section_header` | `render_section_header` | `render_section_header` | none | N/A |
| Large/sortable table | (coverage table) | `st.dataframe(row_height)` | `st.dataframe(row_height)` + matrix | `st.dataframe(row_height)` | MATCH |
| Empty states | `render_empty` | `render_empty` / `render_callout` | `render_empty` | `render_empty` | MATCH |
| Charts | shared template | shared template | shared template (heatmap) | none | N/A |

**Summary:** the catalog archetype is the Overview's shell and component set plus
the D1 sortable grid and the shared empty state. Its one shared-surface
difference is the filter bar's layout (row 22, recorded).

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

**No presentation-layer defect is filed.** One layout deviation and one
micro-deviation are recorded for the owner:

1. **Row 22 — the shared filter set is hosted as a tall, narrow bar column** —
   accept, or schedule the Wave H bar-shape work (bundled with the Wave D/E/F
   carry item).
2. **The empty catalog** no longer renders the inactive toggle (the early
   `render_empty` return precedes the bar) — accept (the path is unreachable and
   untested).

The Wave D carry list (F1, F2, F5, F7, filter-bar shape, Gregorian/Jalali range
direction, `neutralise()` scroll no-op Task 47) is unchanged and still open.

## 8. Owner checklist

The owner reviews the captures in
[`wave-g-assets/task45/`](../wave-g-assets/task45/) and the Task 44 before/after
crops, then works down this list.

- [ ] The page opens with the shared header; the search box, the filter set, the
      inactive toggle and the clear button sit in one bar.
- [ ] The matching count is a one-cell KPI band at the RTL start, not stretched
      across the content column.
- [ ] **Search:** typing narrows the count and the grid; a no-match needle shows
      the shared empty state.
- [ ] **Inactive toggle:** checking it reveals the four SCI base-year segments.
- [ ] **Clear:** the button resets the search and every filter to their defaults.
- [ ] **1280 px and 1024 px:** the four bar columns stay usable and the filter
      widgets do not truncate their labels.
- [ ] The grid stays sortable and its columns/values are unchanged; the LTR-grid
      limitation is understood (the id column is LTR inside the RTL page).
- [ ] **Row 22** — the shared filter set is a tall, narrow bar column —
      **accept or schedule the Wave H bar shape**.
- [ ] No element of the archetype is missing, and no page silently differs from
      the others.

**Owner sign-off: PENDING.**

## 9. What this gate unblocks

When the owner records the decision above, Wave G closes. The layout deviation
(row 22) does **not** block Wave H: it is a Wave H polish candidate, bundled with
the existing filter-bar carry item.
