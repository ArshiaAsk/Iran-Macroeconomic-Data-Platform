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

## 4. Results — Task 2 (shell DOM, static serving, toolbar, brand)

Probe app config (`/tmp/phase72-probe/.streamlit/config.toml`):

```toml
[server]
enableStaticServing = true

[theme]
base = "light"
font = "Vazirmatn, Tahoma, sans-serif"

[[theme.fontFaces]]
family = "Vazirmatn"
url = "app/static/Vazirmatn.ttf"
weight = "100 900"
```

### 4.1 Static serving + font

| item | result | evidence | status |
|---|---|---|---|
| Correct URL `/app/static/Vazirmatn.ttf` | **200**, `font/ttf`, **241 328 B** (byte-identical to the file) | `curl -w "%{http_code} %{content_type} %{size_download}"` | VERIFIED |
| Wrong URL `/app/dashboard/static/Vazirmatn.ttf` | **200** but `text/html` **10 951 B** — the SPA index shell, **not** the font. Fails **silently** (no 404) | `curl` | VERIFIED |
| `/static/Vazirmatn.ttf` | 200 `text/html` — also the SPA fallback, not the font | `curl` | VERIFIED |
| `[[theme.fontFaces]]` loads | `document.fonts` entry `Vazirmatn`, status **`loaded`**, weight `100 900`; `document.fonts.check('16px Vazirmatn')` → **true** | browser `document.fonts` | VERIFIED |
| Rendered family | app root computed `font-family: Vazirmatn, Tahoma, sans-serif, "Source Sans", sans-serif`; Persian text renders in Vazirmatn | computed style + screenshot `wave-0-assets/badge-segmented.png` | VERIFIED |

**Conclusion:** `enableStaticServing=true` + a `static/` dir beside the
entrypoint serves `static/<file>` at **`app/static/<file>`**. The URL is the
`app/static/…` form and it resolves. The wrong `app/dashboard/static/…` path
returns the app shell with HTTP 200, so a typo there would **not** be caught by a
status check — verify by content type/size, not status.

### 4.2 `client.toolbarMode` matrix (real app, custom `[theme]`)

`STREAMLIT_CLIENT_TOOLBAR_MODE` override confirmed with `streamlit config show`
(`toolbarMode = "viewer"` / `"minimal"`).

| mode | Deploy button | kebab (main menu) | viewer options (Print, Record screen) | developer options (Rerun, Clear cache) | theme toggle |
|---|---|---|---|---|---|
| `auto` | visible | visible | visible | visible | **absent** |
| `viewer` | **absent** | visible | visible | **hidden** | **absent** |
| `minimal` | **absent** | **absent (menu hidden)** | **hidden** | hidden | absent |

Screenshots: `wave-0-assets/header-{auto,viewer,minimal}.png`.

**Theme toggle is already hidden by the custom theme.** Control test: an
otherwise identical app **without** a `[theme]` section exposes
`stMainMenuItem-theme-System`, `…-theme-Light`, `…-theme-Dark` (all visible) when
the main menu is opened. With the custom `[theme]` (base = light) those elements
are **absent from the DOM**. So D14's requirement is met by the locked theme
alone; **no `toolbarMode` change is needed to hide the theme toggle.**

**Recommendation (per D14 addendum):** set `client.toolbarMode = "viewer"`.
It hides the native **Deploy** button and the developer options (Rerun / Clear
cache) while keeping the kebab and the viewer options (Print, Record screen) —
nothing the analyst needs is removed, so no limitation is accepted. `minimal` is
**not** recommended because it also removes Print/Record screen. `auto` remains
acceptable (local-only app) if the Deploy button is tolerated.

### 4.3 Sidebar DOM hooks (Streamlit 1.61.1)

Sidebar tree: `stSidebar → stSidebarContent → { stSidebarHeader
(stLogoSpacer, collapse button), stSidebarNav (stSidebarNavItems → group divs →
stNavSectionHeader + `li`), stSidebarUserContent }`.

| element | stable hook | verdict |
|---|---|---|
| sidebar container | `[data-testid="stSidebar"]` | STABLE |
| sidebar content (flex parent) | `[data-testid="stSidebarContent"]` | STABLE |
| sidebar header (**above** nav) | `[data-testid="stSidebarHeader"]` | STABLE |
| nav container | `[data-testid="stSidebarNav"]` / `[data-testid="stSidebarNavItems"]` | STABLE |
| nav link | `[data-testid="stSidebarNavLink"]` | STABLE |
| **active** nav link | `[data-testid="stSidebarNavLink"][aria-current="page"]` | STABLE (attribute) |
| active nav link class | `st-emotion-cache-1yak103` (hashed) | **FRAGILE** — do not use |
| nav group header | `[data-testid="stNavSectionHeader"]` | STABLE |
| sidebar user content (DB status) | `[data-testid="stSidebarUserContent"]` | STABLE |
| main block container | `[data-testid="stMainBlockContainer"]` | STABLE |
| native header | `[data-testid="stHeader"]` | STABLE |
| toolbar / deploy / kebab | `[data-testid="stToolbar" / "stAppDeployButton" / "stMainMenuButton"]` | STABLE |

### 4.4 Runtime-injection verdicts

CSS was injected only with `page.add_style_tag` on the running app.

| item | verdict | computed evidence |
|---|---|---|
| (i) sidebar width 256 px | **STABLE** | `[data-testid="stSidebar"]{width:256px!important;min-width:256px!important}` → computed `256px` |
| (ii) active-item accent | **STABLE** | `[data-testid="stSidebarNavLink"][aria-current="page"]{background:…;border-inline-start:3px solid …}` → computed `3px` / `rgba(31,111,235,0.12)` |
| (iii) brand above nav **+** DB status at bottom | **STABLE with a corrected recipe** (see below) | variant B: brand above nav = true; status pinned near sidebar bottom = true |
| (iv) main max-width 1360 px + top padding | **STABLE** | `[data-testid="stMainBlockContainer"]{max-width:1360px!important}` → computed `1360px`; computed `padding-top: 96px` (native header is 60 px, absolute) |

Screenshots: `wave-0-assets/shell-injection.png`,
`wave-0-assets/shell-variant-b.png`.

**(iii) detail — the prescribed recipe is insufficient.** Injecting a brand
element into `stSidebarUserContent` and reordering `stSidebarContent` to
`display:flex` (brand block above nav) **does** put the brand above the nav, but
because the DB status also lives in `stSidebarUserContent`, it lands **above the
nav too**, not at the bottom (`status_is_bottom = false`). A single flex child
cannot straddle the nav.

**Working recipe (variant B, all stable selectors):**

```css
[data-testid="stSidebar"] { width: 256px !important; min-width: 256px !important; }
[data-testid="stSidebarContent"] { display: flex !important; flex-direction: column; }
[data-testid="stSidebarHeader"] { order: 0; }          /* brand lives here (above nav) */
[data-testid="stSidebarHeader"]::after {               /* text from i18n via t() */
  content: "◆ سامانهٔ داده‌ها"; display: block; font-weight: 700;
}
[data-testid="stSidebarNav"] { order: 1; }
[data-testid="stSidebarUserContent"] { order: 2; margin-top: auto; }  /* DB status pinned bottom */
```

This gives brand (top) → nav → DB status (bottom), all via stable
`data-testid` hooks. The brand text must come from `i18n.py` through `t()` (the
literal cannot live in the CSS module), and `st.logo(icon_image=…)` may
optionally supply the icon in `stSidebarHeader`.

**Fragile selectors to isolate (D6 block):** the active-nav `st-emotion-cache-*`
class; any width/max-width that needs `!important`; and the native
`[data-testid="stHeader"]` whose height is **60 px**, not the mockup's 48 px
(see §8 — Task 28).

## 5. Results — Task 3 (page inventory + archetypes)

Re-verified the PAGE INVENTORY and archetypes against the current tree.

| item | result | evidence | status |
|---|---|---|---|
| Page count | **10** page modules under `dashboard/pages/`; **10** `PageSpec` rows in `navigation.py:52-121` | `ls dashboard/pages/`, read `navigation.py` | VERIFIED |
| `render_*` symbols / line numbers | all match the plan: `render_overview_page:742`, `render_correlation_page:1002`, `render_catalog_page:588`, `render_inflation_page:196`, `render_domain_page:138` / `render_domain_body:155`, `render_fx_gold_page:913`, `render_welfare_page:929`, `render_market_page:413`, `render_labor_page:970` | `grep -n "^def render_\|^def _render_" dashboard/page_view.py` | VERIFIED |
| Archetype grouping | A1 = overview; A2 = gdp, trade_energy, fx_gold, labor (`render_domain_page` / `render_domain_body`); A3 = inflation, welfare, market (emphasis sections + `render_domain_body`); A4 = correlation; A5 = catalog | read `page_view.py` (`render_fx_gold_page:913`, `render_labor_page:970`, `render_welfare_page:929`, `render_inflation_page:196`) | VERIFIED |
| `page_for_domain("economy") is None` | true (dead domain) | `navigation.py` docstring + code | VERIFIED |
| `pytest tests/unit/dashboard/test_navigation.py -q` | **10 passed** | command output | VERIFIED |

**No drift found** in the inventory table or archetypes — every symbol and line
number matches. No correction was required to the plan's Context. (The font-path
and Material-icon corrections in §8 come from Tasks 1–2, not from this
inventory.)

## 6. Results — Task 4 (`st.html` and theme switcher)

Probe payload rendered with `st.html` (own probe app, custom theme); read back
from the live DOM and computed styles.

| probe element / attribute | survives? | evidence | status |
|---|---|---|---|
| `<style>` block, class rule | **yes — applies** | `.probe-class` computed `color: rgb(1, 2, 3)` | VERIFIED |
| `class` attribute | yes | `getAttribute("class") == "probe-class"` | VERIFIED |
| inline `style` | yes | computed `background-color: rgb(4, 5, 6)` | VERIFIED |
| `title` attribute | yes | `getAttribute("title") == "tip-text"` | VERIFIED |
| `dir="rtl"` | yes | `getAttribute("dir") == "rtl"` | VERIFIED |
| `<bdi>` | yes | element `tagName == "BDI"` | VERIFIED |
| `data-x` attribute | yes | `getAttribute("data-x") == "hello"` | VERIFIED |
| `<a href="/Inflation">` | yes | anchor present, `href="/Inflation"` | VERIFIED |
| `<td title="cell-tip">` | yes | `getAttribute("title") == "cell-tip"` | VERIFIED |
| `<svg>` | **NO — stripped** | `#probe-svg` absent from the DOM; no red circle rendered | VERIFIED (stripped) |
| `st.markdown(..., unsafe_allow_html=True)` CSS | **yes — applies** | `#md-probe` computed `color: rgb(9, 8, 7)` | VERIFIED |
| iframing | not iframed (`document.querySelectorAll("iframe").length == 0`) | — | VERIFIED |

**Named alternatives for non-surviving items.** `<svg>` is stripped by DOMPurify
(the HTML profile does not enable the SVG profile). Alternatives: a Material
`st.icon`/`:material/…:` glyph, a Unicode/emoji glyph, or a CSS-drawn shape
(borders/`::before`); the mockup's inline-SVG nav glyphs and brand glyph are
therefore **accepted deviations** (already recorded in the plan's traceability
table).

**`title` tooltip on a `<td>`.** The `title` attribute survives, so the native
tooltip mechanism is intact, but the tooltip itself could **not be captured in
headless Chromium** (native tooltips are not rendered in headless screenshots).
Status: **UNVERIFIED (visual)** — see the owner checklist. The fallback if it
does not appear in a real browser: `data-` attribute + CSS `::after` tooltip.

### Theme switcher

| app config | theme choice offered? | evidence | status |
|---|---|---|---|
| **custom `[theme]` (base = light)** | **no** | no `[data-testid^="stMainMenuItem-theme-"]` in the DOM after opening the menu, at `auto`, `viewer` and `minimal` | VERIFIED |
| **no `[theme]` (control)** | **yes** | `stMainMenuItem-theme-System` / `-Light` / `-Dark` present and visible | VERIFIED |

**Conclusion (D14):** a custom `[theme]` already removes the settings-menu theme
toggle in Streamlit 1.61.1, so the theme lock is enforced without any
`toolbarMode` change. Recommended `client.toolbarMode = "viewer"` (hides Deploy +
developer options, keeps viewer options). No CSS hacks on the native menu.

**`st.badge` / `st.segmented_control` under the custom theme:** both render
correctly (orange badge chip; segmented control) — screenshot
`wave-0-assets/badge-segmented.png`. `st.badge` surfaces as Markdown (as the plan
records).

---

## 7. Decisions for Waves A/B

| Decision | Outcome | Evidence |
|---|---|---|
| **Sidebar-brand fallback** | **Fallback (2) — CSS-pinned, with a corrected recipe.** Brand via `[data-testid="stSidebarHeader"]::after` (text from `t("app.brand")`), DB status pinned by `stSidebarContent` flex + `stSidebarUserContent{order:2;margin-top:auto}`. The literal "inject into user content then order" recipe fails to keep the status at the bottom. | §4.4 |
| **`toolbarMode`** | **`"viewer"`** (hide Deploy + developer options, keep kebab + Print/Record screen). Not required for the theme toggle — the custom `[theme]` already hides it. `minimal` rejected (removes viewer options). | §4.2, §6 |
| **Static URL** | **Confirmed:** `app/static/Vazirmatn.ttf` (HTTP 200, `font/ttf`, 241 328 B). Wrong `app/dashboard/static/…` → SPA shell, HTTP 200, silent. | §4.1 |
| **`st.html` survival** | Keeps: `<style>` (applies), `class`, inline `style`, `title`, `dir`, `<bdi>`, `data-*`, `<a href>`, `<td title>`. Stripped: **`<svg>`** → use a Material/Unicode glyph or CSS shape. `st.markdown(unsafe_allow_html=True)` CSS applies. | §6 |
| **Separator verdict** | **U+066C** (ARABIC THOUSANDS SEPARATOR), confirmed in the browser; **not** U+060C. No delta. | §2 (h) |
| **Stable vs fragile selectors** | STABLE: `stSidebar`, `stSidebarContent`, `stSidebarHeader`, `stSidebarNav`, `stSidebarNavLink`, `[aria-current="page"]`, `stNavSectionHeader`, `stSidebarUserContent`, `stMainBlockContainer`, `stHeader`, `stToolbar`/`stAppDeployButton`/`stMainMenuButton`. FRAGILE: active-link `st-emotion-cache-*` class; widths needing `!important`; native header height (60 px, not 48). | §4.3, §4.4 |
| **CSS snippets that worked** | `[data-testid="stSidebar"]{width:256px!important;min-width:256px!important}`; `[data-testid="stSidebarNavLink"][aria-current="page"]{background:…;border-inline-start:3px solid …}`; `[data-testid="stSidebarContent"]{display:flex;flex-direction:column}`; `[data-testid="stSidebarNav"]{order:1}`; `[data-testid="stSidebarUserContent"]{order:2;margin-top:auto}`; `[data-testid="stMainBlockContainer"]{max-width:1360px!important}` | §4.4 |
| **Task 7 change** | No relocation — commit the existing `dashboard/static/Vazirmatn.ttf` / `OFL.txt` and wire static serving. | §8 |
| **Task 9 change** | Chrome block uses the stable hooks above; the active-item accent is `[aria-current="page"]`, never the hashed class. | §4.3 |
| **Task 15 change** | None from Wave 0 (the HTML table wrapper is unaffected); `<svg>` is unavailable inside `st.html`. | §6 |
| **Task 27 change** | Use the corrected brand recipe (header CSS + pinned status), not `st.sidebar` content. | §4.4 |
| **Task 28 change** | The native header is 60 px, not 48 px; the 48 px top bar is a new element or a CSS override. `toolbarMode="viewer"` recommended; theme toggle already hidden. | §4.2, §4.4 |

---

## 8. Plan corrections applied

Minimal edits only (no other plan text changed). All are traceable to Tasks 1–4.

1. **Material icons (Review outcome "Corrected" #5):** the bare-name validation
   claim was wrong — corrected to state membership in `ALL_MATERIAL_ICONS` and
   that `validate_material_icon` requires the `:material/…:` shortcode.
2. **Font location (Review outcome "Corrected" #8, the "Verified in the codebase"
   font bullet, D4, Risks #3, the AGENTS.md NOTES bullet, Task 7):** the font and
   licence are **already under `dashboard/static/`** (untracked);
   `dashboard/Vazirmatn.ttf` / `dashboard/OFL.txt` do not exist. Task 7 now
   **commits** them rather than relocating them.
3. **D5 addendum / Task 27:** the brand fallback (2) recipe corrected (brand in
   `stSidebarHeader`, not `st.sidebar` content; DB status pinned via
   `stSidebarUserContent` flex).
4. **D14 addendum / Task 28:** a custom `[theme]` already hides the theme toggle;
   recommended `toolbarMode="viewer"`; no toolbarMode change required for D14.
5. **Task 28:** native header height noted as 60 px (mockup 48 px) and the
   1360 px max-width confirmed.
6. **Open items:** the two `[ASSUMED]` items (static URL, toolbarMode) marked
   **Resolved** with evidence; the D11 guard item left **open** (Task 33).
7. **Tasks 1–4 acceptance/outcome lines and the Gate section:** Wave 0 outcomes
   recorded; gate rule fixed as **"zero errors"**.

---

## 9. Owner checklist (only what could not be verified)

| Item | Why unverified | Exact manual steps |
|---|---|---|
| Native `title` tooltip on a `<td>` inside `st.html` | Headless Chromium does not render native tooltips; the `title` attribute does survive | Run `make dashboard` (or the probe app), open the `st.html` table, hover the cell, and confirm the browser tooltip appears. If it does not, use `data-` + CSS `::after`. |
| `client.toolbarMode` exact **introducing** version | Not derivable from the installed package (only the allowed values/default are); no network access for release notes | Check the Streamlit release notes for the first version listing `client.toolbarMode` (docs say the `viewer` fix landed in 1.54.0). This does not affect the D9 floor decision (highest requirement remains 1.44.0). |
| `[aria-current="page"]` stability across Streamlit upgrades | Verified only at 1.61.1 | Re-run the Task 2 selector probe after any Streamlit bump; keep the chrome selectors in the D6 isolated block. |

---

## 10. Final tree state

`git status --short` after Wave 0 (all four commits landed):

```
?? dashboard/static/
```

Only the pre-existing, untracked font directory remains. Every Wave 0 change is
committed under `docs/phase-7.2/` plus the single plan file
`docs/plans/phase-7.2-dashboard-redesign.md`; **no production file** was touched
and the font files under `dashboard/static/` are **untouched and uncommitted**
(Task 7 owns them). No leftover servers or background processes.
