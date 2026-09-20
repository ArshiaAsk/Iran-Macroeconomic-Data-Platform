# Phase 7.2 — Execution log

Per-task log. One entry per task with **files**, **Verify result**,
**deviations**, and **commit hash**.

Decisions for Wave A/B live in
[`wave-0-spike.md` §7](wave-0-spike.md#7-decisions-for-waves-ab).

---

## Task 1 — (0) VERIFY Streamlit capabilities/APIs/sanitization/AGENTS; RECORD baseline

- **Files:** `docs/phase-7.2/wave-0-spike.md` (new), `docs/phase-7.2/README.md`
  (new stub), `docs/phase-7.2/execution-log.md` (new),
  `docs/phase-7.2/wave-0-assets/before/*.png` (10 new).
- **Verify:**
  - `streamlit.__version__` → 1.61.1.
  - `make check` → **PASS** (EXIT=0; 1 158 passed, 3 skipped, 135 deselected; cov 89.22 %).
  - `poetry run mypy src dashboard` → **0 errors**.
  - `poetry run pytest tests/unit/dashboard -q` → **341 passed, 0 failed**
    (EXIT=1 from the subset coverage gate only).
  - Separator → U+066C (VERIFIED). Ten before screenshots captured.
  - `git status --short` unchanged by `make check` (format-clean).
- **Deviations:** none to production. Drift recorded in the plan's Material-icon
  claim (bare names do **not** validate; the shortcode does) and corrected in
  Task 3's commit.
- **Commit hash:** `35ce5f6`

## Task 2 — (0) VERIFY shell DOM, static serving, toolbar mode, brand fallbacks

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append),
  `docs/phase-7.2/execution-log.md`,
  `docs/phase-7.2/wave-0-assets/{shell-injection,shell-variant-b,header-auto,header-viewer,header-minimal}.png`.
- **Verify:** `/app/static/Vazirmatn.ttf` → 200 `font/ttf` 241 328 B; font
  `document.fonts` "Vazirmatn" loaded; toolbar matrix (auto/viewer/minimal);
  sidebar selectors via `[data-testid]`/`[aria-current="page"]`; brand fallback
  injection. All manual browser checks passed.
- **Deviations:** none to production.
- **Commit hash:** `834fe38`

## Task 3 — (0) RECORD verified page inventory and archetypes

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append), plan corrections.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_navigation.py -q` →
  10 passed; ten page modules; render symbols/line numbers match the plan.
- **Deviations:** none to production.
- **Commit hash:** `8a0e245`

## Task 4 — (0) VERIFY st.html rendering and theme-switcher behaviour

- **Files:** `docs/phase-7.2/wave-0-spike.md` (append + decisions + owner
  checklist), `docs/phase-7.2/wave-0-assets/badge-segmented.png`.
- **Verify:** `st.html` survival matrix (style/class/inline-style/title/dir/bdi/
  data-/a survive; svg stripped); `st.markdown(unsafe_allow_html=True)` CSS
  applies; custom `[theme]` already hides the theme toggle.
- **Deviations:** none to production.
- **Commit hash:** `f8bbfcd`

---

## Wave 0 commit summary

| Task | Commit |
|---|---|
| 1 — capabilities + baseline | `35ce5f6` |
| 2 — shell/static/toolbar/brand | `834fe38` |
| 3 — page inventory | `8a0e245` |
| 4 — `st.html` + theme switcher + plan corrections | `f8bbfcd` |

All commits are docs-only. The untracked font files under `dashboard/static/`
were never staged or committed (Task 7 owns them).

---

## Task 5 — (A) ADD the design-token module

- **Files:** `dashboard/components/tokens.py` (new),
  `tests/unit/dashboard/test_tokens.py` (new), plan checkboxes.
- **Build:** frozen `MappingProxyType` of the mockup's entire `:root` block
  (22 tokens: palette, soft backgrounds, `surface-2`, `hover`, radii, `font-ui`,
  `font-mono`), with `token()` / `custom_properties()` /
  `css_custom_properties()` helpers. The test parses
  `docs/design/phase-7.2/overview-redesign-mockup.html` and asserts set equality.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_tokens.py -q --no-cov`
  → **6 passed**. `ruff format`/`ruff check` clean. `poetry run mypy src dashboard`
  → **0 errors** (64 source files).
- **Deviations:** the token↔`[theme]` consistency assertion is deferred to
  Task 8: its premise (the Task 8 theme values) does not exist yet, and a
  failing test must not be committed. Task 8 appends it to `test_tokens.py`.
- **Commit hash:** `27df2ec`

## Task 6 — (A) RAISE the Streamlit floor and refresh the lock

- **Files:** `pyproject.toml`, `poetry.lock` (git-ignored, not committed).
- **Build:** `streamlit = "^1.36"` → `">=1.44,<2"`.
- **Verify:** `poetry check` → exit 0 (pre-existing deprecation warnings only).
  `poetry lock` → lock content hash rewritten, **no package version deltas**
  (219 packages before/after; `streamlit` still 1.61.1). `poetry run pytest
  tests/unit/dashboard -q --no-cov` → **347 passed** (341 baseline + 6 token
  tests).
- **Deviations:** `poetry.lock` is git-ignored (`.gitignore:37`) and is not
  tracked, so the refreshed lock is not committed; only `pyproject.toml` lands.
  The D9 implication note in the plan records this.
- **Commit hash:** `7569676`

## Task 7 — (A) VENDOR the Vazirmatn font and wire theme + static serving

- **Files:** `dashboard/static/Vazirmatn.ttf`, `dashboard/static/OFL.txt`
  (committed by path, unchanged), `.streamlit/config.toml`,
  `dashboard/components/direction.py`, plan checkboxes.
- **Build:** `[server] enableStaticServing = true`; `[[theme.fontFaces]]`
  `family="Vazirmatn"`, `url="app/static/Vazirmatn.ttf"`, `weight="100 900"`;
  `theme.font`/`headingFont`/`codeFont` set to full fallback stacks. The two
  stale 7.1 comments in `.streamlit/config.toml` and `direction.py` corrected.
  `.gitignore` has no `static/`/`*.ttf` rule; there is no Dockerfile and
  `docker-compose.yml` mounts only the Postgres data volume + `init-db.sql`,
  so `dashboard/static/` ships in-repo and is served by Streamlit static serving
  (everything in `dashboard/static/` is publicly served — only the font and
  licence live there).
- **Verify:** `curl /app/static/Vazirmatn.ttf` → **200 `font/ttf` 241 328 B**
  (byte-identical; wrong `app/dashboard/static/...` → SPA shell 200 `text/html`
  10 951 B, fails silently). Playwright: `document.fonts.check('16px Vazirmatn')`
  → **true**, Vazirmatn entry **loaded**, computed body family starts with
  `Vazirmatn`. No config error in the streamlit log. `ruff`/`mypy` clean;
  `test_direction.py` + `test_tokens.py` → 15 passed.
- **Deviations:** none.
- **Commit hash:** `7606c01`

## Task 8 — (A) UPDATE the Streamlit theme to the design tokens

- **Files:** `.streamlit/config.toml`, `tests/unit/dashboard/test_tokens.py`,
  plan checkboxes.
- **Build:** set `base="light"`, `primaryColor`, `backgroundColor`,
  `secondaryBackgroundColor`, `textColor`, `borderColor`, `baseRadius=6px`,
  `buttonRadius=6px`, `baseFontSize=14`, `dataframeHeaderBackgroundColor`,
  `showWidgetBorder`, `showSidebarBorder`, `chartCategoricalColors` and the
  red/orange/yellow/blue/green `{Color,BackgroundColor,TextColor}` keys from
  the tokens. Semantic mapping: orange=warn, blue=accent/info, red=err,
  green=ok; **yellow has no mockup token and is folded into the warn palette**
  (recorded). `font`/`fontFaces` kept from Task 7 (not duplicated). Every
  listed option name was confirmed to exist via
  `c.get_config_options()` first.
- **Verify:** `poetry run pytest tests/unit/dashboard/test_tokens.py -q --no-cov`
  → **10 passed** (token equality + `[theme]`↔token consistency + base size +
  chart colours + font-owner checks). App started with the new theme, **no
  config error** in the streamlit log (`curl /` → 200).
- **Deviations:** none.
- **Commit hash:** `2bca541`

## Task 9 — (A) EXTEND the shell CSS owner with tokens and the chrome block

- **Files:** `dashboard/components/direction.py`,
  `tests/unit/dashboard/test_direction.py`, plan checkboxes.
- **Build:** added `css_custom_properties()` to `direction_css()` so the token
  `:root` block is emitted; registered stable chrome selectors in
  `CSS_SELECTORS`; added a comment-marked, version-named `/* Streamlit-chrome
  selectors — verified on Streamlit 1.61.1 ... */` block implementing sidebar
  width 256 px, flex column pinning `stSidebarUserContent` to the bottom via
  `order:2;margin-top:auto`, active-nav accent via `[aria-current="page"]`
  (`border-inline-start:3px solid var(--accent)`), and main-container max-width
  1360 px. No brand or top-bar rules; main top padding untouched. CSS still
  injected via `st.markdown(..., unsafe_allow_html=True)`.
- **Verify:** `poetry run pytest tests/unit/dashboard -q --no-cov` → **356
  passed** (341 baseline + 15 new). `poetry run mypy src dashboard` → **0
  errors**. Visual Playwright check: sidebar computed width **256 px**, main
  container `max-width:1360px`, `--accent` token on `:root` equals
  `#1D4E89`, active nav item has the accent bar, DB status pinned at the
  bottom. Native header computed height **52.5 px** (close to the spike's
  recorded 60 px; recorded as note).
- **Deviations:** none.
- **Commit hash:** _pending_
