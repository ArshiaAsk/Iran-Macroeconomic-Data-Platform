# Emphasis-domain review — Inflation, Welfare, Market (Wave E)

**Status: PREPARED — AWAITING OWNER REVIEW.**
**Owner sign-off: PENDING.**

This is the Wave E owner visual review (Task 41). It walks the three A3
**emphasis-domain** pages — Inflation, Welfare & Household Survey, and Market —
against the design system's **page-layout contract**
([`design-system.md`](../design-system.md) §11–§12) and against the Overview (the
Wave C reference) and the generic domain explorer (the Wave D reference),
**element by element**. There is no mockup for the emphasis pages; the contract
and the two earlier archetypes are the reference.

The three pages are one **archetype**: each opens with the shared page header,
adds **emphasis sections** above the generic domain composition, and reuses the
A2 building blocks. This review is one contract walk applied to three routes,
not three independent designs.

- **Reviewed tree:** `757080c` (Scope A gate) + the Task 40 commit on branch
  `phase-7.2`
- **Review date:** 2026-09-22
- **Data:** the populated local database (7 sources, 50 active indicators,
  8,195 Gold observations, 54 coverage rows)
- **Viewport:** 1440 × 900 (the plan's capture size)
- **Evidence:**
  - [`wave-e-assets/task-38/`](../wave-e-assets/task-38/) — Inflation
    before/after (top + the decile, canonical and chain-linking scroll crops)
  - [`wave-e-assets/task-39/`](../wave-e-assets/task-39/) — Welfare
    before/after (top + the HBSIR sections and the survey-year panel crops)
  - [`wave-e-assets/task-40/`](../wave-e-assets/task-40/) — Market before/after
    (top + the level section crop)
  - [`wave-e-assets/partA-all-pages/`](../wave-e-assets/partA-all-pages/) — the
    ten-page set after Tasks 38–39 (the Scope A gate)
  - [`wave-d-assets/partB-all-pages/`](../wave-d-assets/partB-all-pages/) — the
    pre-Wave-E baseline the before-crops are copied from

## 1. How the comparison was made

There is no pixel target, so the comparison is:

1. **Structural** — the same composition order on every page: page header,
   caveat(s), filter set, emphasis sections, generic domain body.
2. **Contract-level** — every D11 item in §12 is checked against the live DOM and
   the source; every §11 testing rule is checked against the suite.
3. **Measured** — the placeholder text, the callout tones, the table variants and
   their widths, the section titles and the panel labels are read from the live
   DOM / the AppTest proto.

Where a page differs from the contract, the row says whether the difference is
the design (native-first, D13), the data, or a genuine gap.

## 2. The three pages (inventory)

| Page | Route | Domain | Header title | Caveats | Emphasis sections | Generic body |
|---|---|---|---|---|---|---|
| Inflation | `pages/2_Inflation.py` | `inflation` | `page.inflation` — تورم | shared-base (info), chain-linking stored/overlap (info) — **in-section** | CPI deciles, CPI canonical, chain-linking | `render_domain_body` |
| Welfare & Survey | `pages/8_Welfare_Survey.py` | `welfare` | `page.welfare` — رفاه و آمارگیری خانوار | relative-poverty (warn), computed-values (info) — **top** | HBSIR trend, decile shares, survey-year panel | `render_domain_body` |
| Market | `pages/9_Market.py` | `market` | `page.market` — بازار سرمایه | five TSETMC caveats (one warn + four info) — **top, stacked** | market level (KPI band + chart) | (its own derived panels) |

All three page modules are **thin delegates**: no function of their own, no
Streamlit import, one call to a migrated composition function.

## 3. Layout-contract matrix (§11–§12 × the three pages)

Verdicts: **MATCH** (the contract is met), **DEVIATION** (a recorded,
deliberate difference), **DEFECT** (a gap to fix), **N/A** (the item cannot
apply).

| # | Contract item (source) | Inflation | Welfare | Market |
|---|---|---|---|---|
| 1 | Opens with `render_page_header` (§12) | MATCH | MATCH | MATCH |
| 2 | KPI values through `render_kpi_band` (§12) | N/A | N/A | MATCH |
| 3 | Section titles through `render_section_header` (§12) | MATCH | MATCH | DEVIATION |
| 4 | Filters through the shared bar (§12) | DEVIATION | DEVIATION | DEVIATION |
| 5 | Empty / error / loading through `states.py` (§12) | MATCH | MATCH | MATCH |
| 6 | No raw `st.title`/`st.metric`/`st.warning`/`st.info`/`st.error` (§12) | MATCH | MATCH | MATCH |
| 7 | No `unsafe_allow_html` where a shared component exists (§12) | MATCH | MATCH | MATCH |
| 8 | Caveats through `render_callout` / `render_callout_stack` (Task 18/40) | MATCH | MATCH | MATCH |
| 9 | Filter widgets carry the Persian placeholder — **F4** (Task 35) | MATCH | MATCH | MATCH |
| 10 | Chart legend carries no `label` title — **F3** (Task 35) | MATCH | MATCH | MATCH |
| 11 | Quality summary via `render_html_table` typed cells (§4.3, §8) | MATCH | MATCH | MATCH |
| 12 | Static summary table via `render_html_table` (Task 35 pattern) | MATCH | MATCH | N/A |
| 13 | Observations grid stays a `st.dataframe` with `row_height` (D1) | MATCH | MATCH | MATCH |
| 14 | Table semantics preserved (`<th scope="col">`, `<bdi class="ltr">`) (§8) | MATCH | MATCH | MATCH |
| 15 | Data-derived HTML escaped before it reaches a fragment (§13) | MATCH | MATCH | MATCH |
| 16 | Every user-visible string resolves through `t()` (§13) | MATCH | MATCH | MATCH |
| 17 | CSS scoped by a keyed container / stable hook (§5, §13) | MATCH | MATCH | MATCH |
| 18 | Callout container keys distinct within a run (Task 17) | MATCH | MATCH | MATCH |

**Verdict tally:** 15 MATCH, 3 DEVIATION (the shared filter set on all three
pages, row 4; the derived-panel subheaders on Market, row 3), 1 N/A (no KPI band
on Inflation/Welfare), **0 DEFECT in the presentation layer**.

### Row 2 — the KPI band (Market MATCH; Inflation / Welfare N/A)

Market bands one cell — the observed trading-session count
(`metric.market_sessions`) — through `render_kpi_band`, replacing the raw
`st.metric`. Inflation and Welfare have no aggregate metric to band (the
emphasis sections are charts and a metadata panel), so `render_kpi_band` is not
called and nothing is missing. This is the archetype's intended shape: only a
page with a single headline number gets a band.

### Row 3 — the derived-panel subheaders (Market DEVIATION, recorded)

Market's derived panels (`RET1D`, `MA30`, `.ME`) are titled by
`market_series_label(rows)`, a **resolved Persian display string** built by the
label layer from the parent id and the derivation — not a catalog key.
`render_section_header` resolves its title through `t(title_key)`, so it cannot
take an already-resolved label without a new override parameter. The panels
therefore keep the native `st.subheader(market_series_label(rows))`.

`st.subheader` is **not** a banned call (the D11 guard bans `st.title`,
`st.metric`, `st.warning`/`st.info`/`st.error` and `unsafe_allow_html`), so the
guard is satisfied and the panel labels and count are unchanged. The level
section (`section.market_level`) **is** a catalog key and does go through
`render_section_header`. **Recommendation: accept as-is**; a `title=` override
on `render_section_header` is a small Wave H candidate if the owner wants every
panel title through the component.

### Row 4 — the shared filter set (DEVIATION, carried)

The three pages render their filter set through `render_filters`
(`components/filters.py`), the shared component that owns the multiselects, the
Jalali preset expander and the Gregorian date inputs. The Overview's coverage
section instead lays three `st.selectbox` controls out through
`render_filter_bar` (Task 21).

This is the **same recorded interpretation as Wave D** (VALIDATION.md, Wave D
part A): the emphasis tasks do **not** restructure the filter set onto
`render_filter_bar`. The plan's Task 38/39/40 file lists have no filter-bar
refactor, no mockup prescribes an emphasis-page bar, and the widgets, labels,
keys and the returned `FilterState` are unchanged. The row is **DEVIATION**
rather than MATCH — the filter set is shared, but it is not the Overview's
three-select bar.

**Recommendation: accept as-is**, or schedule one bar shape across the app for
Wave H (bundled with the Wave D carry item).

### Row 12 — the static summary tables (Inflation / Welfare MATCH; Market N/A)

Inflation's chain-linking **provenance table** and Welfare's **survey-year
panel** are both `render_html_table`, built by a pure builder from the
already-localized frame (the Task 35 pattern: every cell is a `Text`, values
byte-identical). Variants were chosen by **measurement**:

- Inflation provenance — `coverage` variant. Measured `default` = 1232 px
  (190 px overflow in the 1042 px column); `coverage` = 1042 px, **no sideways
  scroll**.
- Welfare survey-year panel — `default` variant. Five short columns, measured
  957 px in the 1042 px column — **no sideways scroll** needed.

Market has no static summary table of this kind (its derived panels are charts
and observation grids), so the row is N/A.

## 4. Cross-page consistency (the three pages vs each other)

Because all three share the header, the filter set and the generic body, they
agree by construction. Spot checks confirm it:

| Aspect | Observation across the three pages |
|---|---|
| Header | Same `h1` shape (28 px / 700), same RTL start, aligned with the top bar's breadcrumb |
| Caveat placement | Inflation places section-specific notices **inside** their sections; Welfare and Market place page-level caveats at the **top** (Market as a `render_callout_stack`) |
| Caveat tones | The amber `warn` tone is reserved for a genuine warning (Welfare relative-poverty, Market derived-not-official); every other caveat is blue `info` |
| Filter set | Same controls, same Persian placeholder, same Jalali expander, same date inputs (shared `render_filters`) |
| Emphasis sections | Each opens with `render_section_header`; the generic body is always last, under its own header |
| Generic body | Same `render_domain_body` composition below the emphasis sections (Inflation, Welfare); Market composes its own derived panels |
| Quality table | Same `coverage`-variant HTML table from `render_quality_summary` |
| Empty states | Same shared callout with a distinct `container_key` per occurrence |
| Downloads | Same CSV/Excel buttons and chart-download pair |

**One consistency observation for the owner:** now that
`render_callout_stack` exists (Task 40), Welfare's two top-level caveats
(`warn.hbsir_relative_poverty` + `warn.hbsir_computed_values`) could be rendered
through it as well. They currently use `render_callout` directly — identical
rendered output, just not routed through the new component. This is **cosmetic,
not a defect**; the two calls predate the component (Task 39 vs Task 40).
**Recommendation: leave as-is** (no behaviour or visual difference) unless the
owner prefers every multi-caveat block to go through the stack.

## 5. Overview comparison

The three pages are compared to the Wave C Overview (the reference
implementation) and the Wave D domain explorer on the surfaces they share:

| Aspect | Overview (Wave C) | Domain explorer (Wave D) | The three emphasis pages | Verdict |
|---|---|---|---|---|
| Shell (top bar, breadcrumb, stamp) | Full-bleed top bar | Identical | Identical — the shell is global | MATCH |
| Page header | `render_page_header` + methodology callout with a bold label | `render_page_header` + one caveat | `render_page_header` + caveat(s) (Welfare/Market at top, Inflation in-section) | MATCH — the bold label is the Overview's methodology note |
| KPI band | Six-cell band | none | Market one-cell; Inflation/Welfare none | MATCH / N/A |
| Section headers | `render_section_header` with trailing summaries | `render_section_header` | `render_section_header` (Market's derived panels are the exception, row 3) | MATCH (one recorded DEVIATION) |
| Filter bar | three `st.selectbox` via `render_filter_bar` | `render_filters` | `render_filters` | DEVIATION (row 4) |
| Quality / coverage table | HTML `coverage` variant | HTML `coverage` variant | HTML `coverage` variant | MATCH (same component) |
| Static summary table | (Overview uses the coverage table) | (none) | HTML table, variant by measurement (Inflation/Welfare) | MATCH (same component) |
| Observations grid | (coverage table) | `st.dataframe(row_height)` | `st.dataframe(row_height)` | MATCH |
| Empty states | `render_empty` | `render_empty` | `render_empty` / `render_callout` | MATCH |
| Charts | shared template, legend title blank | shared template | shared template | MATCH |

**Summary:** the emphasis archetype is the Overview's shell and component set
plus the Wave D generic body, with a per-domain emphasis section on top. The
only shared-surface differences are the filter bar (row 4, carried) and Market's
derived-panel titles (row 3, recorded).

## 6. Visual evidence and the changed-assertions list

### 6.1 Pixel diff (Wave E part A/B vs the Wave D part B baseline)

| Page | Changed pixels | What changed |
|---|---|---|
| `inflation` | 0 % | the emphasis sections are below the fold; the top viewport (title + filters) is unchanged |
| `welfare` | 30.2 % (whole page) | the two HBSIR caveats now carry the scoped accent bars and glyphs; the survey-year panel is the shared HTML table |
| `market` | 3.0 % (y 198–549) | the five TSETMC caveats now carry the accent bars and glyphs (one strip) |
| the other seven pages | 0 % | not migrated in Wave E (the Scope A gate confirms byte-identical) |

**No regressions.** Every changed pixel is a callout accent bar/glyph or the
migrated table; no value, column, panel or download changed.

### 6.2 Changed test assertions (per page)

| Page (task) | Assertions changed | Reason |
|---|---|---|
| Inflation (Task 38) | `test_inflation_page_states_that_the_deciles_share_a_unit_and_base_year`: `app.caption` → `app.info`; `test_inflation_page_renders_the_chain_linking_section`: two `app.caption` → `app.info` | the three explanatory `warn.*` captions became `render_callout(tone="info")` notices |
| Inflation (Task 38) | **added** `test_the_provenance_table_is_an_html_table_with_localized_headers`, `test_build_chain_linking_provenance_rows_maps_every_cell_to_plain_text`, `test_build_chain_linking_provenance_rows_is_empty_safe` | the provenance table moved to `render_html_table` (markup strategy) |
| Welfare (Task 39) | `test_welfare_page_renders_with_the_hbsir_sections`: the `app.dataframe` survey-year panel assertion was **removed** and replaced by the markup assertion below | the survey-year panel moved to `render_html_table` |
| Welfare (Task 39) | **added** `test_the_survey_year_panel_is_an_html_table_with_localized_headers`, `test_build_survey_year_panel_rows_maps_every_cell_to_plain_text`, `test_build_survey_year_panel_rows_is_empty_safe` | the panel moved to `render_html_table` (markup strategy) |
| Welfare (Task 39) | `test_welfare_page_states_that_the_poverty_rate_is_relative`: **unchanged** | `render_callout(tone="warn")`/`(tone="info")` keep the native `st.warning`/`st.info`, so `app.warning`/`app.info` still see the values |
| Market (Task 40) | **none** | every existing assertion passes unchanged (`app.title`, `app.subheader`, `app.warning`/`app.info`, `app.metric` all survive the shared components) |

No assertion lost its intent: each rewrite checks the same headers and values it
checked before, through the markup strategy the Task 16 map prescribes.

## 7. Defects and recommendations

**No presentation-layer defect is filed.** Two carried decisions and one
consistency observation are recorded for the owner:

1. **Row 4 — the shared filter set is `render_filters`, not `render_filter_bar`**
   — accept, or schedule one bar shape for Wave H (same as the Wave D carry
   item).
2. **Row 3 — Market's derived-panel subheaders stay raw `st.subheader`** because
   their titles are resolved display strings, not catalog keys — accept, or add a
   `title=` override to `render_section_header` in Wave H.
3. **§4 — Welfare's two top-level caveats could use `render_callout_stack`** now
   that it exists — cosmetic, no rendered difference; recommend leaving as-is.

The Wave D carry list (F1, F2, F5, F7, filter-bar shape, Gregorian/Jalali range
direction, `neutralise()` scroll no-op Task 47) is unchanged and still open.

## 8. Owner checklist

The owner reviews the three 1440×900 captures and the scroll crops in
[`wave-e-assets/task-38/`](../wave-e-assets/task-38/),
[`wave-e-assets/task-39/`](../wave-e-assets/task-39/) and
[`wave-e-assets/task-40/`](../wave-e-assets/task-40/), then works down this list.

- [ ] The three pages share one header shape: the Persian title at the RTL start,
      aligned with the top bar's breadcrumb.
- [ ] Inflation's emphasis sections (CPI deciles, CPI canonical, chain-linking)
      open with the shared section header and carry their caveats as info
      callouts.
- [ ] Welfare's HBSIR sections (trend, decile shares, survey years) open with the
      shared section header; the survey-year panel is the shared RTL HTML table
      with Persian-digit coverage counts and Jalali Esfand 29/30 ends.
- [ ] Market's five TSETMC caveats render as one stacked block (one amber, four
      blue); the sessions metric is a one-cell KPI band; the derived panels are
      labelled with parent + derivation.
- [ ] The quality summary is the shared RTL HTML table on every page.
- [ ] Empty states read as the shared callout (`render_empty` /
      `render_callout`), not a hand-rolled alert.
- [ ] **Row 4** — the shared filter set is `render_filters`, not the Overview's
      `render_filter_bar` — **accept or schedule for Wave H**.
- [ ] **Row 3** — Market's derived-panel titles stay raw `st.subheader` —
      **accept or schedule for Wave H**.
- [ ] **§4** — Welfare's two top-level caveats could use `render_callout_stack` —
      **accept as-is or request the cosmetic change**.
- [ ] No element of the archetype is missing, and no page silently differs from
      the others.

**Owner sign-off: PENDING.**

## 9. What this gate unblocks

When the owner records the decision above, Wave E closes and **Wave F** starts.
The two carried decisions (rows 3 and 4) and the §4 observation do **not** block
Wave F: each is either a Wave H polish candidate or a cosmetic non-difference.
