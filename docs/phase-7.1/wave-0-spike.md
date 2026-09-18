# Wave 0 Spike Report — Phase 7.1 Dashboard Refresh (Task 1)

**Date:** 2026-09-17
**Scope:** validation only. No production code, dashboard page, localization, or
ETL change was made. `git status` after the spike shows no tracked modification.

**Method:** a throwaway two-page `st.navigation` prototype (entrypoint + two pages
+ a plain-data registry) outside the production dashboard, driven by `AppTest`.
All findings below are measured output, not inference. Nothing in `dashboard/`,
`src/`, `alembic/`, or `airflow/` was touched.

## Findings

### Navigation

- **The router works.** `st.navigation({section: [st.Page, ...]})` +
  `page.run()` renders from a registry: the page declared `default=True` rendered
  on first `run()` even though it was *not* the first entry in the registry
  (`SPIKE-SECOND` rendered; `SPIKE-HOME` was declared first). Grouping (dict of
  section → pages) and per-page Persian titles both worked.
- **A registry must be data, not `st.Page` objects.** `st.Page(...)` called
  outside a Streamlit script run *silently returns a stub*: only `_default`,
  `_visibility`, `_external_url` are set, `_page`/`_title` never exist and no
  exception is raised (`streamlit/navigation/page.py:256-258`, early `return` when
  `get_script_run_ctx()` is falsy). A registry holding `st.Page` instances would
  therefore import "successfully" in tests and behave as garbage. Shape that
  works: frozen `PageSpec` rows (path/title/icon/group/domains/default) plus a
  `build_pages()` called inside the running entrypoint.
- **Paths are entrypoint-relative.** `st.Page("pages/1_home.py")` resolves against
  the *running entrypoint's* directory, so the registry must keep the
  `pages/...` form (not `dashboard/pages/...`).
- **Nav chrome is frontend-rendered and invisible to `AppTest`.** After
  `st.navigation`, `at.get("page_link")` is empty and `at.sidebar.children` is
  empty. Sidebar labels, ordering and section grouping **cannot** be asserted
  through `AppTest`; registry assertions must read the registry data structure.
- Per Streamlit docs, once any session executes `st.navigation`, the `pages/`
  directory is ignored app-wide — the registry becomes the only IA declaration,
  so a missing entry is a missing page.

### AppTest

Installed version **1.61.1**. All three entry points exist and were exercised:

| Call | Result |
|---|---|
| `AppTest.from_file("app.py").run()` | renders the registry's **default** page through the router |
| `.switch_page("pages/1_home.py").run()` | renders that page; `at.title == ["SPIKE-HOME"]` |
| `FakeDashboardRepository` seam | still applies through the router (`catalog_rows=3`) |

- `default_timeout` is an **init keyword / attribute**, not a chainable method:
  `AppTest.from_file(path, default_timeout=20)` (the old
  `at.default_timeout(20)` form is gone).
- **Harness gotcha (important).** Because the entrypoint sits next to a `pages/`
  directory, AppTest resolves page switching through Streamlit's **MPA-v1
  pages-directory emulation** (`script_runner._mpa_v1`). A spy showed `_mpa_v1`
  invoked twice for two runs, and an entrypoint trace line appeared **only in
  run 1**: the switch run executes the page file directly and does **not**
  re-execute `app.py` / `st.navigation`. Consequence: per-page `AppTest` smoke
  tests do **not** exercise the router — a page left in `pages/` but dropped from
  the registry would still pass.
- `switch_page()` requires a prior `run()` and matches the page by its
  **filename-derived** name (`1_home.py` → `home`), not by any custom `url_path`
  (documented on the current `AppTest.switch_page` docs page). A registry
  `url_path` is therefore invisible to the test harness; empirically the switch
  still resolved the file. Keep `url_path` unset.
- **Current harness stays valid.** `AppTest.from_file(dashboard/pages/X.py)`
  (a page file as main script) is explicitly supported by the docs and still
  works with a router present. Baseline: `tests/unit/dashboard` = 24 passed in
  ~2s, of which 7 invocations across 6 files use the `app_test()` helper.
- The monkeypatch seam (`dashboard.queries.repository_session`, chart-download
  stub) is unaffected by the router.

### Dependency Strategy

- `pyproject.toml` declares `streamlit = "^1.29.0"`; `poetry.lock` and the
  installed wheel are **1.61.1**; Poetry is **2.4.1**.
- `st.Page` / `st.navigation` were introduced in **1.36.0** (GitHub release notes,
  PR #8744, published 2024-06-20), so `^1.36` is the correct floor and 1.61.1
  satisfies it.
- Scratch experiment (both files restored byte-identically afterwards, md5
  verified, `git diff` empty):
  1. `poetry check --lock` at ^1.29.0 → clean.
  2. Edit the constraint to `^1.36` → `Error: pyproject.toml changed
     significantly since poetry.lock was last generated. Run poetry lock`.
  3. `poetry lock` → **same package set and versions**, `streamlit = "1.61.1"`,
     identical 7552-line lock; only `content-hash` changes
     (`47aa1b88…` → `edcf87b9…`). `poetry check --lock` clean afterwards.
  4. `poetry install --dry-run` → every package "Already installed"; no env change.
  - **Conclusion: a lock refresh alone is sufficient. No dependency upgrade, no
    reinstall.**
- **`poetry.lock` is gitignored and untracked** (`.gitignore:37`), so the plan's
  "commit the refreshed `poetry.lock`" is not possible — only the two
  `pyproject.toml` lines are committable.
- Poetry 2.x: use `poetry check --lock`; the old `poetry lock --check` no longer
  exists.

### Risks

1. **The router is not covered by per-page `AppTest` tests** (see above). It has
   exactly one automatable coverage point: an entrypoint run asserting the
   default page.
2. **Registry shape.** Storing `st.Page` objects (or constructing them at import
   time) silently yields stubs outside a script run.
3. **Default page.** If no page sets `default=True`, Streamlit promotes the first
   non-external page in declaration order. The registry test must assert exactly
   one default rather than rely on order.
4. **`url_path`.** Irrelevant to switching, but it is the page's public URL and
   the hash key for direct navigation; Persian/derived slugs would make
   `switch_page` name-matching and URL entry unintuitive. Leave it inferred.
5. **Nav assertions must be data-level**, which also means the Task 16 domain
   ownership test cannot be an `AppTest` assertion.
6. Page modules must not call `st.set_page_config` (today only `app.py` does, and
   page titles are rendered by `page_view`), otherwise the router run raises.
7. The **fallback is proven and cheap**: targeting page files directly keeps all
   24 dashboard tests green before and after the router lands.

## Decision

**APPROVE**:

- `st.navigation` — APPROVE (required for Persian sidebar labels, grouping, order
  and default-page control; no architectural conflict).
- Page registry — APPROVE, **as plain data + an in-app builder**, consumed by both
  `st.navigation` and data-level tests.
- AppTest migration — **PARTIALLY SUPPORTED**: `from_file` + `switch_page` + `run`
  render pages correctly and the repository seam survives, but switching bypasses
  the router, so the router itself is not testable per page. Per-page test
  migration is optional, not required.
- Streamlit floor bump to `^1.36` — APPROVE, with a **`poetry lock` refresh only**.

## Required Adjustments To Phase 7.1

1. **Task 1/2 (dependency step):** drop "commit the refreshed `poetry.lock`" (the
   file is gitignored/untracked); record the step as `poetry lock` +
   `poetry check --lock`, and note that no package version changes.
2. **Task 2 (registry):** specify the registry as plain data (`PageSpec` rows)
   plus a builder invoked inside `app.py`; do not set `url_path`; keep page
   modules standalone-runnable (they render their own title).
3. **Task 2/16 (tests):** state explicitly that nav labels/order/grouping and
   domain ownership are asserted **against the registry**, not via `AppTest`.
   Add: exactly one `default=True`; every registry path exists on disk; page
   paths unique; owned domains unique across pages.
4. **Task 2/27 (smoke tests):** choose one path and document it — keep
   `app_test(page_filename)` targeting page files (zero churn, still supported)
   **plus one new entrypoint test** for the router's default page; or migrate the
   6 page tests to `switch_page` (no added router coverage, more churn).
5. **Docs/patterns:** add the two harness facts to the plan's Patterns/External
   Documentation notes: `AppTest` cannot see nav chrome, and `switch_page`
   resolves by filename (needs a prior `run()`).

No other adjustment is needed: nothing found contradicts the plan's layering,
Gold-only data contract, or localization strategy.

## Recommended Next Step

**Proceed to Wave A (Task 2)** with adjustments 1–5 applied. The Wave-0 fallback
(direct page-file `AppTest` harness) is proven and should be noted in
`docs/phase-7.1/IMPLEMENTATION.md` as the documented fallback.

### Reproduction recipe (prototype was deleted after the spike)

1. `.spike/wave0/`: `registry.py` (`PageSpec` frozen dataclass, `PAGES` tuple,
   `grouped_pages()` building `st.Page(..., default=spec.is_default)`),
   `app.py` (`st.set_page_config` → `st.navigation(grouped_pages(), position="sidebar")`
   → `page.run()`), `pages/1_home.py` (calls `cached_list_indicators`),
   `pages/2_second.py` (calls `cached_load_series`, `default=True`), `conftest.py`
   re-exporting `tests.unit.dashboard.app_smoke.fake_streamlit_connection`, and
   the 7-case test file.
2. `poetry run pytest .spike/wave0/test_spike.py -q --no-cov` → **7 passed**.
   Note: the prototype must live outside the linted tree (or be deleted) because
   `ruff check .` lints it and Persian literals trip `RUF001`.
