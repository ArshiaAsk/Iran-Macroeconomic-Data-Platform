# Phase 7.2 — Wave 0 spike (Tasks 1–4)

Verification spike + baseline capture for the Phase 7.2 dashboard redesign.
No production file was changed; this note plus the plan corrections are the only
outputs.

Owner: executor (Wave 0). Branch: `phase-7.2`. Date: **2026-09-20** (UTC).

---

## 1. Environment

| Item | Value | Evidence |
|---|---|---|
| Date | 2026-09-20 (UTC) | `date -u` |
| Branch | `phase-7.2` | `git branch --show-current` |
| Python | 3.12.3 | `poetry run python --version` |
| Streamlit | **1.61.1** | `poetry run python -c "import streamlit; print(streamlit.__version__)"` |
| mypy | 1.20.2 (compiled) | `poetry run mypy --version` |
| Plotly / jdatetime | unchanged (not exercised here) | — |
| Browser | Playwright headless Chromium (`chromium-1234` / `chromium_headless_shell-1234`) | `~/.cache/ms-playwright` |
| Viewport | 1440×900 | probe scripts |
| Database | `iran_macro_postgres` Up (healthy), host port **5433** (read-only use) | `docker ps` |
| Real app port | 8501 (`make dashboard` equivalent) | `curl :8501` → 200 |
| Probe app port | 8502 (`/tmp/phase72-probe`, custom theme + static serving) | `curl :8502` → 200 |
| No-theme control port | 8503 (`/tmp/phase72-probe-notheme`) | `curl :8503` → 200 |
| Toolbar variants | 8504 (`viewer`), 8505 (`minimal`) | `curl` → 200 |

All servers started for this spike were stopped before finishing; no streamlit
process or port remained (`ss -ltn`, `ps aux`).

Throwaway probes live under `/tmp/phase72-probe/` (own `.streamlit/config.toml`,
own `static/` with a **copy** of the font). Candidate CSS was tested on the real
app only via runtime injection (`page.add_style_tag` + DOM injection), never by
editing repo files. The ten "before" screenshots were captured by a throwaway
Playwright snippet run from `/tmp` (no script added to the repo).

---

## 2. Results per task

### Task 1 — capabilities + baseline

| item | result | evidence | status |
|---|---|---|---|
| (a) Streamlit version | **1.61.1** | `streamlit.__version__` | VERIFIED |
| (b) font theme options | `theme.font`, `theme.fontFaces`, `theme.headingFont`, `theme.codeFont`, `theme.headingFontSizes`, `theme.headingFontWeights`, `theme.baseFontWeight`, `theme.metricValueFontSize`, `theme.metricValueFontWeight` (+ `theme.{light,dark,sidebar}.*` variants) | `c.get_config_options()` filtered on `font` | VERIFIED |
| (b) alert colour options | `theme.{red,orange,yellow,blue,green,violet,gray}{Color,BackgroundColor,TextColor}` (21 keys) | `c.get_config_options()` | VERIFIED |
| (c) API existence | `st.html`, `st.badge`, `st.segmented_control`, `st.container`, `st.dataframe`, `st.metric`, `st.logo`, `st.navigation`, `st.Page`, `st.page_link` all present; `dataframe(row_height=)` present; `metric(help=)` present | `inspect.signature` | VERIFIED |
| (d) Material icon set | **4 267** names; all ten chosen names are members of `ALL_MATERIAL_ICONS` | `len(ALL_MATERIAL_ICONS)`; membership check | VERIFIED (with drift — see below) |
| (e) `st.logo` | `st.logo(image, *, size="small"\|"medium"\|"large"="medium", link=None, icon_image=None)` — image-only, no text parameter | `inspect.signature(st.logo)` | VERIFIED |
| (f) `client.toolbarMode` | allowed values **`auto` / `developer` / `viewer` / `minimal`**; default `auto`; `scriptable=True` | `streamlit/config.py` `_create_option("client.toolbarMode", …)` | VERIFIED |
| (f) exact introducing version | not derivable from the installed package | — | **UNVERIFIED** (owner step) |
| (g) AGENTS wording | `AGENTS.md:620` = "**Local-only deployment:** No cloud infrastructure; all services run via Docker Compose" | `grep -n` | VERIFIED |
| (g) offline convention | `dashboard/components/direction.py:14` ("no `@font-face`, no CDN, no downloaded font asset") and `.streamlit/config.toml:5` ("the offline rule (no CDN, no webfont, no vendored font file)") | `grep -n` | VERIFIED |
| (h) thousands separator | rendered Overview KPI is `۸٬۱۹۵`; the separator is **U+066C** (ARABIC THOUSANDS SEPARATOR), **not U+060C**. Source constant `PERSIAN_THOUSANDS_SEPARATOR = "٬"` is also U+066C | browser `stMetricValue` innerText + `ord()`; `dashboard/formatting.py:73` | VERIFIED |
| (i) baseline | see §3 | logs | VERIFIED |

**Drift found in (d).** The plan's "Corrected" item #5 states that
`validate_material_icon` validates the bare names (`overview`, …). It does **not**:
`validate_material_icon` expects a full shortcode and **raises**
`StreamlitAPIException` for a bare name (`"overview"` → raised). What is true:
each name is a member of `ALL_MATERIAL_ICONS` (4 267 names) and
`validate_material_icon(":material/overview:")` returns `":material/overview:"`.
So `st.Page(icon=":material/overview:")` is valid; the bare-name phrasing in the
plan is misleading and was corrected (see §5).

---

## 3. Baseline (Task 1 (i)) and the per-wave gate rule

`git status --short` **before** `make check`:

```
?? dashboard/static/
```

`git status --short` **after** `make check`:

```
?? dashboard/static/
?? docs/phase-7.2/
```

Only the two allowed untracked paths; **no tracked file was modified**. The
format step did **not** dirty the tree → **baseline is format-clean**.

| Baseline command | Result |
|---|---|
| `make check` | **PASS** (`EXIT=0`). `ruff format` + `ruff check` clean; `mypy src/` clean; `pytest -m "not integration"` → **1 158 passed, 3 skipped, 135 deselected** in 117.51s; coverage **89.22 %** (≥80 % gate). |
| `poetry run mypy src dashboard` | **0 errors** (`Success: no issues found in 63 source files`). |
| `poetry run pytest tests/unit/dashboard -q` | **341 passed, 0 failed**; `EXIT=1` **only** because the subset run trips the project-wide `--cov-fail-under=80` gate (subset coverage 33.66 %). Per `Makefile:27-28` a subset run must not be judged by that gate; `test`/`test-all` enforce it. |
| Before screenshots | Ten PNGs, 1440×900, in `docs/phase-7.2/wave-0-assets/before/` (`overview, correlation, catalog, inflation, gdp, trade_energy, welfare, fx_gold, market, labor`). |

**Per-wave gate rule: `mypy src dashboard` = "zero errors".**
The Task 1 baseline had **zero** pre-existing errors, so the AM-21 gate is
**"zero errors"**, not "no new errors". For `make check`/`pytest`, the rule is
**"no regressions"** against the recorded counts above (1 158 passed full suite;
341 passed dashboard subset, ignoring the subset coverage gate).

---

## 4. Results — Task 2 (appended in commit 2)

_Pending._

## 5. Results — Task 3 (appended in commit 3)

_Pending._

## 6. Results — Task 4 (appended in commit 4)

_Pending._

## 7. Decisions for Waves A/B (appended in commit 4)

_Pending._

## 8. Plan corrections applied (appended in commit 4)

_Pending._

## 9. Owner checklist (appended in commit 4)

_Pending._
