# Wave H — cross-page contract audit (Task 48)

**Live app:** dev server restarted for the capture at 2026-09-22 02:41:58; probe
run at HEAD **`4e7c3a8`** (dashboard code unchanged since `2c0977c` — Wave H
Tasks 46–48 are tests/docs only).
**Method:** two independent checks.

1. **Static call graph.** For each registered page, resolve its thin delegate's
   entry function in `dashboard/page_view.py`, walk the intra-module call graph,
   and record which shared contract components the composition reaches. This is
   the definitive "does the page use the component" answer (it is the code path,
   not the current data state).
2. **Live DOM probe** (Playwright, 1440x900). Per page: the `h1` text vs
   `t("page.<key>")`, and the counts of `stPlotlyChart`, `stMainBlockContainer
   table`, `stDataFrame`, `stMetric`, `stAlertContainer`.

## Matrix (page x contract item)

`Y` = the composition uses the shared component; `–` = not applicable to that
page (no such element). "live" columns are the DOM counts observed in the probe.

| Page | header | KPI | section | filter bar | empty | callout | table | chart | exports | live h1 | live plotly / table / grid / metric / alert |
|---|---|---|---|---|---|---|---|---|---|---|---|
| overview | Y | Y | Y | Y | Y | Y | Y | – | – | OK | 0 / 2 / 0 / 6 / 1 |
| correlation | Y | – | Y | Y | Y | Y | Y | Y | Y | OK | 0 / 0 / 0 / 0 / 1 |
| catalog | Y | Y | – | Y | Y | – | – | – | – | OK | 0 / 1 / 1 / 1 / 0 |
| inflation | Y | – | Y | Y | Y | Y | Y | Y | Y | OK | 4 / 2 / 2 / 0 / 4 |
| gdp | Y | – | Y | Y | Y | Y | Y | Y | Y | OK | 1 / 1 / 1 / 0 / 0 |
| trade_energy | Y | – | Y | Y | Y | Y | Y | Y | Y | OK | 0 / 0 / 0 / 0 / 1 |
| welfare | Y | – | Y | Y | Y | Y | Y | Y | Y | OK | 3 / 2 / 1 / 0 / 3 |
| fx_gold | Y | – | Y | Y | Y | Y | Y | Y | Y | OK | 0 / 0 / 0 / 0 / 2 |
| market | Y | Y | Y | Y | Y | Y | Y | Y | Y | OK | 1 / 1 / 1 / 1 / 6 |
| labor | Y | – | Y | Y | Y | Y | Y | Y | Y | OK | 1 / 1 / 1 / 0 / 2 |

## Findings

- **One header pattern — CONFIRMED.** All ten compositions open with
  `render_page_header`, and the live probe shows the `h1` equals
  `t("page.<key>")` on every page. The page modules call no `st.*` (layout guard).
- **One KPI pattern — CONFIRMED.** `render_kpi_band` is used by the three pages
  that show KPI cells (Overview 6 cells, Catalog 1, Market 1); the other seven
  show no metric, so `render_kpi_band` is N/A there, not bypassed. The live
  `stMetric` counts match.
- **One section-header pattern — CONFIRMED.** Nine compositions use
  `render_section_header`; the Catalog has a single grid and no section, so it is
  N/A there.
- **One filter-bar pattern — CONFIRMED.** Every page uses `render_filter_bar`
  (Overview, Catalog) or the shared `render_filters` set (the other eight; the
  Catalog uses both). No page hand-rolls filter widgets outside these two.
- **Shared states — CONFIRMED (empty) / N/A (error, loading).** All ten use
  `render_empty` for their empty cases. `render_error` and `render_loading` are
  defined in `states.py` but **not currently rendered by any page** — errors
  propagate and are handled outside the page composition, so there is no
  error/loading UI path to migrate. Recorded as N/A, not as a bypass.
- **One table pattern — CONFIRMED (typed HTML table) with one documented
  exception.** Eight compositions render the typed RTL HTML table via
  `render_html_table`. The **Catalog** uses a **native `st.dataframe`** — the D1
  sortable LTR grid decision (design-system §8) — so its `table` cell is N/A.
- **Every chart uses the shared template — CONFIRMED.** The eight pages with a
  chart reach a `build_*` builder in `dashboard/components/charts.py`
  (`build_time_series_chart`, `build_scaled_time_series_chart`,
  `build_correlation_chart`, `build_survey_year_chart`, `build_chain_linking_chart`,
  …). No page builds a Plotly figure directly. The Overview and Catalog show no
  chart. In the live probe the domain pages that default to no selection
  (correlation, trade_energy, fx_gold) render the shared empty state instead of a
  chart — the code path is present, the data state is empty.
- **Exports — CONFIRMED.** Eight pages render the shared downloads
  (`render_data_downloads` / `render_chart_downloads`); Overview and Catalog have
  no chart/observation download.

## Export smoke (re-confirmation of Task 14 / AM-25)

```bash
poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov
```

→ **1 passed** (the PNG + SVG render of a figure built with the shared template).
The export image path still renders with the new template.

## Layout guard

`tests/unit/dashboard/test_layout_guard.py` independently proves the negative:
no migrated composition calls a raw `st.title`/`st.metric`/`st.warning`/
`st.info`/`st.error` or passes `unsafe_allow_html`. The audit above is the
positive cross-check.
