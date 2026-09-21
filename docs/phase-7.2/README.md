# Phase 7.2 — Dashboard Redesign

Runbook and validation records for Phase 7.2 (design system, shell, all pages).

Status: **Waves F and G approved; Wave H in progress** (Overview reference
implementation — Step 0f, Tasks 29–33 and the P1–P5 polish are complete, and the
Task 34 AM-23 visual review was **signed off APPROVED on 2026-09-21** with the
deviations A1–A9 approved as recorded; see
[`validation/reference-overview.md`](validation/reference-overview.md) §6a and
the "Wave C part 2c" section of [`VALIDATION.md`](VALIDATION.md)). Wave D (the
four generic domain-explorer pages: GDP, Trade & Energy, FX & Gold, Labor) is
complete through Tasks 35–36 and its owner review is
[`validation/archetype-domain.md`](validation/archetype-domain.md), **signed off
APPROVED on 2026-09-21**. Wave E (the emphasis-domain pages: Inflation Task 38,
Welfare Task 39, Market Task 40, plus Step 0a/0b) is **complete through Task 41**;
the emphasis owner review is
[`validation/archetype-emphasis.md`](validation/archetype-emphasis.md),
**signed off APPROVED on 2026-09-22** (the 15 MATCH rows accepted; the three
approved deviations are recorded in its §10). Wave F (the comparison /
correlation page, Task 42) is **complete through Task 43**; its owner review is
[`validation/archetype-correlation.md`](validation/archetype-correlation.md),
**signed off APPROVED on 2026-09-22** (14 MATCH rows; the shared `render_filters`
deviation accepted). Wave G (the data catalog page, Task 44) is **complete through
Task 45**; its owner review is
[`validation/archetype-catalog.md`](validation/archetype-catalog.md),
**signed off APPROVED on 2026-09-22, conditional on P1** (the tall narrow filter
column is a defect, fixed in Wave H P1). Wave H (the final polish, the consistency
guard, the validation record and the cross-page audit) is **in progress**. Wave 0
is recorded in [`wave-0-spike.md`](wave-0-spike.md) (capabilities, pre-change
baseline and the per-wave gate rule). Per-task evidence lives in
[`execution-log.md`](execution-log.md); the Wave A, Wave B and Wave C visual
reviews and gates are in [`VALIDATION.md`](VALIDATION.md).

Sign-off carry items (2026-09-22): **F3** (chart legend title `label`) and **F4**
(English `Choose options` placeholder) were scheduled in Waves D–G and have
**landed in Wave D (Task 35)** on the shared chart builders and the shared filter
set; the Gregorian range font-size defect is **fixed** (Step 0a). The filter-set
shapes are **not unified** — recorded as an **accepted deviation**: the Overview
uses `render_filter_bar` of selects, the domain/emphasis/correlation pages use
`render_filters`, and the catalog uses a bar of simple controls plus a full-width
`render_filters`. **Not done, accepted deviations (with reasons):** **F1** content
padding 70 px vs the mockup's 40 px (owner did not request; it is a global change);
**F7** no-wrap of the short categorical coverage columns (owner did not request);
the Gregorian ranges read LTR while the Jalali ranges read RTL (the D3 bidi
decision); the `<td title>` hover tooltip is **unverified in a real browser** (an
owner checklist item); and the ETL/catalog findings **D1** (TGJU snapshot coverage
window) and **D2** (SCI rows without Gold observations) are handed to the
ETL/catalog side and recorded in the plan's Deferred Scope.

Documents:

- [`design-system.md`](design-system.md) — tokens, theme table, component
  catalogue, CSS ownership and the hook pattern, the D1 table classification and
  typed cells, the D11 layout contract, and the do/don't list. First draft after
  Wave A; Task 47 extends it with the top bar, the sidebar shell and the
  screenshot script.
- [`wave-0-spike.md`](wave-0-spike.md) — Wave 0 capability probes and the
  pre-change baseline.
- [`VALIDATION.md`](VALIDATION.md) — verification record, separating "verified in
  this run" from "not automated".
- [`validation/reference-overview.md`](validation/reference-overview.md) — the
  Wave C AM-23 review of the shell and the Overview against the mockup (signed
  off APPROVED, 2026-09-21).
- [`validation/archetype-domain.md`](validation/archetype-domain.md) — the Wave D
  review of the four generic domain-explorer pages against the layout contract
  (**owner sign-off APPROVED, 2026-09-21**).
- [`validation/archetype-emphasis.md`](validation/archetype-emphasis.md) — the
  Wave E review of the three emphasis-domain pages (Inflation, Welfare, Market)
  against the layout contract (**owner sign-off APPROVED, 2026-09-22**).
- [`validation/archetype-correlation.md`](validation/archetype-correlation.md) —
  the Wave F review of the comparison / correlation page against the layout
  contract (**owner sign-off APPROVED, 2026-09-22**).
- [`validation/archetype-catalog.md`](validation/archetype-catalog.md) — the
  Wave G review of the data catalog page against the layout contract
  (**owner sign-off APPROVED, 2026-09-22, conditional on Wave H P1**).
- [`execution-log.md`](execution-log.md) — per-task execution log (files, Verify
  result, deviations, commit hash).
- `README.md` — this file, completed in Wave H.

## Runbook

### Pages

Ten pages, declared once in `dashboard/navigation.py` (`PAGES`). Each is a **thin
delegate** under `dashboard/pages/` that calls exactly one composition function in
`dashboard/page_view.py`; the sidebar label is `nav.<key>` and the in-page title
`page.<key>`, both from `dashboard/i18n.py`.

| Key | Path | Archetype | Owns domains |
|---|---|---|---|
| `overview` | `pages/1_Overview.py` | A1 — reference (all-domain) | — (default page) |
| `correlation` | `pages/6_Correlation.py` | A4 — comparison | — |
| `catalog` | `pages/7_Data_Catalog.py` | A5 — catalog | — |
| `inflation` | `pages/2_Inflation.py` | A3 — emphasis | `inflation` |
| `gdp` | `pages/3_GDP_Economy.py` | A2 — generic domain | `gdp` |
| `trade_energy` | `pages/4_Trade_Welfare_Energy.py` | A2 — generic domain | `trade`, `energy` |
| `welfare` | `pages/8_Welfare_Survey.py` | A3 — emphasis | `welfare` |
| `fx_gold` | `pages/5_FX_Gold.py` | A2 — generic domain | `fx`, `gold` |
| `market` | `pages/9_Market.py` | A3 — emphasis | `market` |
| `labor` | `pages/10_Labor.py` | A2 — generic domain | `labor` |

### Layering

Three presentation modules own the display layer and are the only places their
kind of value may live:

- `dashboard/i18n.py` — every Persian UI-chrome string, keyed; `t()` raises on a
  missing key. One locale, no runtime switcher.
- `dashboard/labels.py` — indicator/domain/source/frequency display names, the
  derived-suffix map, and the expected collection cadence map.
- `dashboard/formatting.py` — Persian digits/separators, Jalali dates and periods,
  and the `Asia/Tehran` day-bounds constructors.

CSS lives only in `dashboard/components/direction.py` (scoped, with stable hooks).
Tokens live in `dashboard/components/tokens.py`; the theme in
`.streamlit/config.toml` reads them.

### How to verify

```bash
make check                                                        # format + lint + typecheck + full test
poetry run mypy src dashboard                                     # 68 files, zero errors
poetry run pytest tests/unit/dashboard -q --no-cov                # dashboard subset
poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov
poetry run pytest tests/unit/dashboard/test_all_pages_smoke.py -q --no-cov
poetry run pytest tests/unit/dashboard/test_layout_guard.py tests/unit/dashboard/test_literal_guard.py -q --no-cov
```

The dev-only screenshot script is **not** a CI gate:

```bash
poetry run streamlit run dashboard/app.py            # in one shell
poetry run python scripts/dashboard_screenshots.py --out-dir /tmp/screens
poetry run python scripts/dashboard_screenshots.py --full-height --out-dir /tmp/screens
```

Restart the dev server before a capture set and record the commit under capture.

### How to add or change a page

1. **Register it.** Add a `PageSpec` row to `PAGES` in `dashboard/navigation.py`
   (`key`, `path`, `icon`, `group`, `domains`, `is_default`). A page must claim
   exactly the domains it renders — `page_for_domain()` reads this declaration.
2. **Add the strings.** Add `nav.<key>` and `page.<key>` to `dashboard/i18n.py`,
   plus any `group.<key>`. Never hardcode a user-visible literal; `labels.py` is
   the only place for a name map.
3. **Write the thin delegate.** Create `dashboard/pages/<N>_<Name>.py` with a
   one-line docstring, one `from dashboard.page_view import render_*` and one
   call. It must not call `st.*` or define a function — the layout guard enforces
   this (`test_all_page_modules_are_thin_delegates`).
4. **Compose in `page_view.py`.** Add a `render_<key>_page` (or reuse
   `render_domain_page`) that opens with `render_page_header`, uses
   `render_kpi_band` / `render_section_header` / `render_filter_bar`, and renders
   empty/error/loading through `components/states.py`. Do **not** call raw
   `st.title`/`st.metric`/`st.warning`/`st.info`/`st.error` or pass
   `unsafe_allow_html` — the layout guard rejects it.
5. **Register the guard coverage.** Add every new render function to
   `MIGRATED_PAGES` in `tests/unit/dashboard/test_layout_guard.py`. The
   completeness tests fail until you do (`test_the_mapping_covers_every_render_function`,
   `test_every_registered_page_delegates_to_a_migrated_function`).
6. **Style only through the system.** Add a selector to `direction.py` (and its
   registry) if the native element cannot express it; add a token to `tokens.py`
   if it is a new colour/radius/size. A new container that renders RTL text must
   declare `direction: rtl`.
7. **Test it.** Add an `AppTest` test (see `tests/unit/dashboard/test_app_*.py`)
   and a router smoke row; keep `test_literal_guard.py` and `test_layout_guard.py`
   green.
8. **Verify.** `make check`, then the screenshot script and a browser walk. Record
   the result in `VALIDATION.md` and the per-task detail in `execution-log.md`.
9. **Do not touch `src/`, `alembic/` or `airflow/`.** A presentation change never
   needs an ETL change; if it seems to, that is a new phase.

### Local development

Local-development note (D14): the settings-menu theme toggle is already absent
because the app defines a custom `[theme]`; the toolbar can be restored for
development with `STREAMLIT_CLIENT_TOOLBAR_MODE=developer` (the shipped value is
`viewer`, which hides Deploy and the developer options while keeping Print/Record).

Screenshot capture (dev-only): `scripts/dashboard_screenshots.py` writes one PNG
per registered page. The default run captures the shipped **1440x900** viewport;
`--full-height` captures each page at its own content height (bounded to 12000 px)
for a whole-page view. Restart the dev server before a capture set and record the
commit under capture; see [`design-system.md`](design-system.md) §16 and
[`wave-h-assets/p4/heights.txt`](wave-h-assets/p4/heights.txt).
