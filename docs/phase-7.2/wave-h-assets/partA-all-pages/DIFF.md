# Wave H — part A all-pages capture and diff

**Commit under capture:** `2c0977c` (phase-7.2, HEAD).
**Dev server:** restarted fresh at 2026-09-22 02:41:58 UTC.
**Command:** `poetry run python scripts/dashboard_screenshots.py --out-dir
docs/phase-7.2/wave-h-assets/partA-all-pages`
**Reference:** `docs/phase-7.2/wave-g-assets/partB-all-pages/` (the Wave G set,
captured before P1–P3).

Ten PNGs, all **1440 x 900**, one per registered page, captured through the
sidebar by the hardened script (settle-asserted, `stMain` scroll reset).

## Per-page result

| Page | Size (ref / new) | Diff px | Diff % | Diff region | Result |
|---|---|---|---|---|---|
| overview | 1440x900 / 1440x900 | 1 227 | 0.095% | top bar (1168–1331, 81–95) | PASS — breadcrumb only (P3) |
| correlation | 1440x900 / 1440x900 | 6 823 | 0.526% | bar + caption strip | PASS — breadcrumb (P3) + caption RTL (P2) |
| catalog | 1440x900 / 1440x900 | 264 410 | 20.402% | full content (326,81)–(1371,900) | PASS — the P1 filter-bar fix (see below) |
| inflation | 1440x900 / 1440x900 | 5 905 | 0.456% | bar + caption strip | PASS — P3 + P2 |
| gdp | 1440x900 / 1440x900 | 6 996 | 0.540% | bar + caption strip | PASS — P3 + P2 |
| trade_energy | 1440x900 / 1440x900 | 6 371 | 0.492% | bar + caption strip | PASS — P3 + P2 |
| welfare | 1440x900 / 1440x900 | 6 782 | 0.523% | bar + caption strip | PASS — P3 + P2 |
| fx_gold | 1440x900 / 1440x900 | 6 791 | 0.524% | bar + caption strip | PASS — P3 + P2 |
| market | 1440x900 / 1440x900 | 1 064 | 0.082% | top bar (1183–1331, 81–95) | PASS — breadcrumb only (P3); its caption is below the 900 px fold |
| labor | 1440x900 / 1440x900 | 6 574 | 0.507% | bar + caption strip | PASS — P3 + P2 |

**No defects.** Every diff is explained by an intended Wave H change:

- **P3 (breadcrumb)** — the top bar of every page: separator `›` → `/`, current
  crumb bolded. Visible as the small top-right region on all ten.
- **P2 (shell caption RTL)** — the `filter.applied_range` echo on the nine pages
  that have it, now reading RTL (the strip at the bar's baseline). The Overview
  is **0 px** for P2 (its caption was already RTL via the removed scoped hook).
- **P1 (catalog filter bar)** — the catalog's large diff: the bar now hosts only
  the three simple controls (`جست‌وجو در فهرست`, `نمایش سری‌های اصلاح‌شده`,
  `پاک‌کردن فیلترها`) and the shared filter set renders **full width** below it,
  instead of the previous tall narrow left column. This is the Wave G
  sign-off defect fixed.

Pixel comparison was done with Pillow `ImageChops.difference` on the RGB frames
(identical dimensions, no resize).
