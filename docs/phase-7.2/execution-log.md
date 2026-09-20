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
- **Commit hash:** _pending_
