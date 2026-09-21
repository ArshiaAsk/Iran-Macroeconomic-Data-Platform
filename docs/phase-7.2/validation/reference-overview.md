# Reference review — the shell and the Overview vs the mockup (AM-23)

**Status: SIGNED OFF.**
**Owner sign-off: APPROVED (2026-09-21).**

This is the AM-23 reference review that closes Wave C. It compares the shipped
shell (Wave B) and the Overview page (Wave C, Tasks 29–32 plus the P1–P5 polish)
against `docs/design/phase-7.2/overview-redesign-mockup.png` **element by
element**, using the plan's mockup traceability table
([`docs/plans/phase-7.2-dashboard-redesign.md`](../plans/phase-7.2-dashboard-redesign.md),
"Traceability — mockup element → task"). Every row below is a row of that table.

The owner reviewed the document and the 1440 px captures and recorded the
decisions in **§6a** below. The deviations **A1–A9** are approved as
recommended; one finding was fixed (Step 0a), two are scheduled in Waves D–G,
and four are recorded as optional Wave H polish candidates without a schedule.

- **Reviewed tree:** `e5fdef3` (Task 33), branch `phase-7.2`
- **Review date:** 2026-09-21
- **Data:** the populated local database (7 sources, 50 active indicators,
  8,195 Gold observations, 54 coverage rows)
- **Viewport:** 1440 px (plus 1920 px and the 1280/1024 px AM-26 checks)
- **Evidence:** [`wave-c-assets/task34/`](../wave-c-assets/task34/), plus the
  per-task crops under `task29/`–`task33/` and `p5/`

## 1. How the comparison was made

The mockup PNG is a **scaled render** (2520 px wide, content column 1915 px), so
pixel equality with a 1440 px live viewport is not the test. The comparison is:

1. **Structural** — same elements, same order, same counts, same RTL start.
2. **Token-level** — computed colours, weights and sizes read from the live DOM
   against the mockup's CSS declarations in `overview-redesign-mockup.html`.
3. **Measured** — geometry read from `getBoundingClientRect()` /
   `getComputedStyle()` in the live DOM, recorded below.

Where a value differs, the row says whether the difference is the design
(native-first, D13), the data, or a genuine gap.

## 2. Measured geometry (live, 1440 px)

| Element | Live | Mockup (its own scale) |
|---|---|---|
| Sidebar width | **256 px** | `.side{width:256px}` → 256 px |
| Main block | `x=256, w=1184`, `max-width: 1360px` | `.main` flex-1, `.wrap{max-width:1360px}` |
| Main block horizontal padding | **70 px** each side (`--main-pad-x`) | `.wrap{padding:32px 40px 64px}` → **40 px** |
| Content column | `x=326, w=1044` | 1360 − 80 = **1280 px** at the cap |
| Top bar | `x=256, w=1184, h=49` (48 + 1 px border), `background: rgb(255,255,255)` | 48 px, `--surface` + `border-bottom` |
| `h1` | 28 px / lh 1.4 (39.2 px line box), `x=326, w=1044` | `.wrap h1` 28 px |
| Callout | `w=1044, h=80`, `background: rgb(251,241,220)`, `border-inline-start: 3px solid currentColor`, `gap: 10px`, `padding: 14px` | `.note`: `--warn-bg`, `3px solid #C98A1B`, `gap:10px`, `padding:10px 14px`, 13.5px / 1.8 |
| KPI band | `w=1044, h=103`, 6 cells | 6 cells |
| Two-column row | `w=1044, h=462`, `[7, 5]` → measured 1.406 | `.row` 7:5 = 1.4 |
| Coverage section | `w=1044, h=3613` | section + 8 sample rows |
| Coverage table | `dt cov`, 1169 × 3450 px, 54 rows | 10 columns, 8 sample rows |
| Page overflow | `scrollWidth == clientWidth == 1184` (1440); `1664 == 1664` (1920) | no sideways scroll |

The content column is **1044 px where the mockup's equivalent would be 1104 px**
at a 1440 px viewport, and **1220 px where the mockup caps at 1280 px** — the
30 px-per-side padding difference in row 4 of the table above. That single number
explains most of the width differences in the rows below.

## 3. Element-by-element comparison (the traceability table)

| # | Mockup element | Task | Live evidence | Verdict |
|---|---|---|---|---|
| 1 | Sidebar width 256 px | 9 | `[data-testid="stSidebar"]` measures exactly **256 px** | **PASS** |
| 2 | Sidebar brand (icon + "سامانهٔ داده‌ها") | 27, 9 | Text brand block at the sidebar's RTL start, `سامانهٔ دادهها` beside the accent glyph, collapse chevron outside it | **PASS** |
| 3 | Nav groups ("مرور و تحلیل", "حوزهها") | 27 | Both group labels present, in registry order, above their items | **PASS** |
| 4 | Material nav icons | 25 | One Material shortcode per nav item (Overview active, `compare_arrows`, `menu_book`, …) | **PASS** |
| 5 | Active-item accent bar | 9 | `مرور کلی` carries `background: var(--accent-soft)`, `color: var(--accent)`, `font-weight: 600`, `border-inline-start: 3px solid var(--accent)` | **PASS** |
| 6 | Pinned DB status dot | 20, 27 | `متصل` with the green dot, pinned at the sidebar's bottom | **PASS** |
| 7 | Top-bar breadcrumb | 28 | `سامانه ، مرور و تحلیل ، مرور کلی` at the RTL start; the mockup writes `سامانه / مرور و تحلیل / مرور کلی` and bolds the current crumb | **FIX** (recommended) — the separator glyph and the bold current crumb are a small, low-risk chrome change. See finding **F2** |
| 8 | Last-collection stamp (date · time · Tehran) | 28 | `آخرین گردآوری: ۲۶ شهریور ۱۴۰۵ · ۱۰:۱۷ · منطقهٔ زمانی تهران` at the far end, same field order and separators as the mockup | **PASS** |
| 9 | Page header (title) | 18, 33 | `مرور کلی` as a native `h1`, 28 px / lh 1.4, RTL start, aligned with the top bar's breadcrumb (`h1 right = 1370 = breadcrumb right`) | **PASS** |
| 10 | Methodology callout (bold label + icon) | 17, 18, 33 | Amber callout beneath the title; bold `یادداشت روششناسی` at `font-weight: 600`, `color: rgb(154,91,0)`; glyph at the RTL start; same sentence as the mockup | **PASS** with approved styling differences — see **A1** |
| 11 | KPI band (6 cells, secondary group) | 19, 29 | Six cells in mockup order and with the mockup's own values: `منابع ۷`, `حوزهها ۹`, `شاخصهای فعال ۵۰`, `مشاهدات لایهٔ طلایی ۸٬۱۹۵`, `سریهای مشتقشده ۳۲`, `سریهای بدون ردیف فهرست ۳۲`; a stronger separator at the start of the secondary group; secondary cells weighted 1.35 (P2, measured 1.378 rendered) | **PASS** |
| 12 | KPI tooltips (3 annotated cells) | 19, 29 | All three annotated cells carry `help=`; the marker is Streamlit's circled `?` where the mockup draws a circled `i` | **PASS** — approved deviation **A2** (native marker, cannot be restyled) |
| 13 | "نیازمند بررسی" review tag | 19, 29 | Orange `st.badge` beneath the catalog-less-series cell | **PASS** |
| 14 | Freshness dot | 20, 30 | Green `موفق`-tone dot per source; the stale sources carry the amber verdict dot | **PASS** |
| 15 | Freshness two-line date (date + time · relative age) | 15, 30 | `TwoLine` cell: `۲۲ شهریور ۱۴۰۵` over `۱۹:۴۴ · ۷ روز پیش`, LTR-mono clock line | **PASS** |
| 16 | Freshness records + run chip | 15, 20, 30 | Numeric records cell (`۴٬۲۸۶`) and a `موفق` `StatusChip` | **PASS** |
| 17 | Freshness stale-first order | 12, 30 | Three `کهنه` rows first (مرکز آمار ایران، تیجیجیبیو، بورس تهران), then the fresh ones | **PASS** |
| 18 | Freshness header summary | 12, 30, P4 | `۴ بهروز · ۳ کهنه` with the stale count amber (`rgb(154,91,0)`). The mockup shows `۵ بهروز · ۲ کهنه` — a **data** difference (4 sources are inside the cadence today), not a design one | **PASS** |
| 19 | Domain bars with total | 20, 31, P1 | Nine bars, count-descending with ties by Persian domain name (15, 15, 8, 4, 3, 2, 1, 1, 1), owner `st.page_link` beside each owned domain, footer `جمع` at the RTL start and `۵۰ شاخص` at the far end | **PASS** |
| 20 | Filter bar (3 selects) | 21, 32 | Three native `st.selectbox` controls (حوزه / منبع / تواتر) with an `همه` option, in the mockup's order; the bar is 73 px where the mockup's chip row is 55 px | **PASS** — approved deviation **A3** (D13 native-first) |
| 21 | Density toggle (راحت/فشرده) | 15, 21 | `st.segmented_control` with `راحت` selected; changes the same table's row height 64 px → 60 px | **PASS** |
| 22 | "نمایش N ردیف" | 21, 32 | `نمایش ۵۴ ردیف` at the bar's far end, updating with the filters | **PASS** |
| 23 | Coverage table columns | 15, 32 | Ten columns, mockup order: شاخص، حوزه، منبع، تواتر، واحد، بازهٔ پوشش، بازهٔ مشاهدهشده، تعداد مشاهدات، ردیفهای زنجیرهشده، میانگین اطمینان | **PASS** — with the width deviation **A4** |
| 24 | Coverage LTR ids (`<bdi class="ltr">`) | 15, 32 | Raw catalog id on a block-level LTR mono line beneath the Persian name (`NY.GDP.MKTP.CD`, `TGJU.USD.FREE`, …) | **PASS** |
| 25 | Coverage unit chips | 15, 32 | `UnitChip` per row (`current US$`, `constant 2015 US$`, `index`, `IRR`, `Percent`, …) | **PASS** |
| 26 | Coverage em-dash for nulls | 15, 32 | The SCI row renders `—` in the observed-range, count, chained-rows and confidence cells | **PASS** |
| 27 | Gregorian-year rule + tooltip | 13, 32 | World Bank/IMF/EIA ranges render Gregorian in an `Ltr` cell (`۱۹۶۰ – ۲۰۲۵`) with the exact stored bounds in the `title`; Iranian sources stay Jalali in a `Text` cell (`فروردین ۱۳۶۱ – بهمن ۱۴۰۱`) | **PASS** |
| 28 | Coverage footnote | 13, 32 | Persian footnote under the table at the RTL start; reads `راهنمای هر خانه` where the mockup says `tooltip` | **PASS** — approved deviation **A5** |
| 29 | Vazirmatn font | 7 | Vendored via `[[theme.fontFaces]]` + static serving; no CDN | **PASS** |
| 30 | Design tokens (`:root`) | 5 | `tokens.py` → `TOKENS`; colours read back from the live DOM match the mockup's `:root` values | **PASS** |
| 31 | Max content width 1360 px | 9, 28 | `stMainBlockContainer` computes `max-width: 1360px`; at 1920 px the block measures exactly 1360 px, so the cap is real and binding above 1616 px | **PASS** |
| 32 | Top bar height 48 px | 28 | `min-height: 48px` → measured **49 px** (48 px row + the 1 px `border-bottom`) | **PASS** — approved deviation **A6** |
| 33 | Brand SVG glyph | 27 | **Accepted deviation** (already ratified): `st.Page` cannot take inline SVG text and `st.logo` is image-only, so the brand is a text block with a CSS-drawn glyph | **PASS** (accepted) |
| 34 | Nav SVG glyphs | 25 | **Accepted deviation** (already ratified): nav uses Material shortcodes only | **PASS** (accepted) |

**Verdict tally:** 30 PASS, 4 PASS-with-approved-deviation, 1 FIX recommended
(breadcrumb separator + bold current crumb). No element is missing, and no
element was silently dropped.

## 4. Findings that needed an owner decision

Each finding below carries the executing engineer's recommendation and, after it,
the **owner's decision** (see §6a for the consolidated record).

### F1 — Main content padding is 70 px where the mockup uses 40 px (recommend FIX)

`stMainBlockContainer` declares `--main-pad-x: 70px` (P5) and reads it for its
horizontal padding. The mockup's `.wrap` declares `padding: 32px 40px 64px`.
The result is a content column **60 px narrower at every viewport width**:

| Viewport | Live content column | Mockup content column |
|---|---|---|
| 1440 px | 1184 − 140 = **1044 px** | 1184 − 80 = **1104 px** |
| 1920 px | 1360 − 140 = **1220 px** | 1360 − 80 = **1280 px** |

The 70 px was not chosen for the design — it **restates Streamlit's own
default**, which P5 had to name so the top bar's full-bleed negative margin could
not drift from it. It was already noted as "the known Step 0b shell deviation" in
the part 1 gate, but it never reached the design system's accepted-deviation
table.

**Recommendation: FIX**, as its own shell task rather than inline here. Setting
`--main-pad-x: 40px` is a one-line change and would move the content column to
the mockup's width on every page at once — which is why it must not be slipped
into a page wave. It would also narrow, but not close, the coverage-table gap in
A4 (1104 px still cannot hold 1169 px).

**Owner decision: NOT REQUESTED NOW.** Recorded as an optional Wave H polish
candidate; not scheduled.

### F2 — Top-bar breadcrumb separator and current-crumb weight (recommend FIX)

The mockup writes `سامانه / مرور و تحلیل / مرور کلی` with the current page in
`<b>`. The live bar writes `سامانه ، مرور و تحلیل ، مرور کلی` (Arabic comma) and
does not bold the current crumb. Everything else about the bar matches: same RTL
start, same stamp at the far end, same alignment with the page column.

**Recommendation: FIX** in the same shell task as F1 — it is chrome, it touches
no page, and it is the last visible difference in the bar.

**Owner decision: NOT REQUESTED NOW.** Recorded as an optional Wave H polish
candidate; not scheduled.

### F3 — The `gdp` chart legend title reads `label` (recommend FIX)

Pre-existing, carried from the part 1 gate: the GDP chart's legend title is the
literal `label` because the chart builders pass `color="label"`. Unchanged by
Wave C and unrelated to the Overview.

**Recommendation: FIX** — file it against the chart builders.

**Owner decision: SCHEDULED in Waves D–G, starting with Task 35** (the fix lands
on the shared chart builders, so it moves every page that draws a legend).

### F4 — English `Choose options` placeholder on un-migrated pages (recommend FIX in Waves D–G)

Every page that has not adopted `render_filter_bar` still shows Streamlit's
untranslated default placeholder. The Overview no longer does (Task 32), so the
fix is already proven; it lands per page as each wave migrates.

**Recommendation: FIX in Waves D–G** — no separate task needed, but it should be
on the wave checklist so it is not forgotten.

**Owner decision: SCHEDULED in Waves D–G, starting with Task 35.**

### F5 — Shell-wide `st.caption` direction (recommend FIX)

A native `st.caption` inherits the main block's LTR direction, so a Persian
sentence hugs the left edge. Task 32 fixed this **scoped** for the coverage
footnote only; every other page's captions are unchanged, because a global rule
would move every un-migrated page's captions mid-wave.

**Recommendation: FIX** in the shell task (with F1/F2), so the rule lands once
the pages have migrated.

**Owner decision: NOT REQUESTED NOW.** Recorded as an optional Wave H polish
candidate; not scheduled.

### F6 — not raised

The owner's numbering runs F1–F7; **no F6 finding was raised** in this review.
The label is left unassigned rather than reusing the number for a different
item, so a later finding can take it.

### F7 — No-wrap on the short categorical coverage columns (new; recommend FIX)

The coverage table's three short categorical columns (حوزه / منبع / تواتر) wrap
onto a second line at 1440 px, because the `coverage` variant turns wrapping on
for every cell (`white-space: normal`) and only the numeric cells are held on one
line (`.dt.cov .num`). The mockup keeps those three columns on one line and lets
only the long indicator name wrap.

**Owner decision: NOT REQUESTED NOW.** Recorded as an optional Wave H polish
candidate; not scheduled.

### The Gregorian-vs-Jalali range-cell direction (new; recommend accept)

A Gregorian range renders in an `Ltr` cell (`direction: ltr`,
`unicode-bidi: isolate`) and a Jalali range in a `Text` cell (`direction: rtl`),
so the two range columns read from opposite edges. That is the D3 bidi decision
and is required to keep the Gregorian year token from flipping inside the RTL
row. The **font-size** half of this difference was a genuine defect and is fixed
(Step 0a); the direction half is by design.

**Owner decision: NOT REQUESTED NOW.** Recorded as an optional Wave H polish
candidate; not scheduled.

## 4a. Data-quality findings (ETL / catalog side; presentation is correct)

Both findings are **data**, not presentation: the dashboard renders the stored
values faithfully and needs no change. They are handed to the ETL/catalog side
and recorded in the plan's Deferred Scope as items 15 and 16.

- **D1 — TGJU snapshot coverage window contradicts the observed range.** The
  TGJU snapshot rows declare a catalog coverage window of `۲۰ – ۲۰ شهریور ۱۴۰۵`
  (a single day) while the range they actually observed is
  `۱۸ – ۲۰ شهریور ۱۴۰۵` (three days). Both are rendered as stored, so the
  coverage table shows a declared range narrower than the observed one. The
  cause is on the catalog/connector side (the declared bounds and the stored
  observations come from different runs).
- **D2 — SCI monthly rows declare coverage but have no Gold observations.**
  Several Statistical Centre of Iran monthly catalog rows declare availability
  and have no Gold observations, so their observed-range, count, chained-rows and
  confidence cells render the em-dash. The em-dash is the documented null
  rendering, so the presentation is correct; the gap is in the Silver→Gold
  publication for those indicators.

## 5. Approved deviations (recommended to accept as-is)

**A1–A9 were approved by the owner as recommended (2026-09-21).**

| # | Deviation | Why it should be accepted |
|---|---|---|
| A1 | The callout's accent bar is `currentColor` (`--warn`, `#9A5B00`) where the mockup uses `#C98A1B`; the live font is the native alert's 14 px / 21 px and padding 14 px where the mockup declares 13.5 px / 1.8 and `10px 14px`; the live sentence wraps to two lines where the mockup's wider crop fits one | Task 17's ratified native-first callout (D13). The amber tint (`rgb(251,241,220)` = `--warn-bg`), the 3 px accent at the RTL start, the 10 px gap, the bold 600 label and the glyph all match; only the values Streamlit's own alert owns differ |
| A2 | KPI tooltip marker is Streamlit's circled `?`, not the mockup's circled `i` | The tooltip is the native `st.metric(help=…)`; the marker cannot be restyled without targeting a hashed class, and `st.html` strips `<svg>` |
| A3 | The three coverage filter controls are native `st.selectbox` widgets (73 px bar) rather than the mockup's 32 px inline-label chips (55 px) | D13 native-first: the bar is native widgets laid out by `render_filter_bar`. A chip-shaped control would need a custom widget, which this phase does not build |
| A4 | The coverage table needs 1169 px inside a 1044 px column, so the leftmost column is partly scrolled out; the mockup's 8-row sample fits | Real data: 54 rows with longer Persian names. AM-26 accepts the in-box scroll, verified at 1440/1280/1024 px with `scrollWidth == clientWidth` at the page level. F1 would narrow the gap to 1104 vs 1169 |
| A5 | The coverage footnote reads `راهنمای هر خانه` where the mockup says `tooltip` | The Task 13 catalog key predates Task 32 and keeps the Persian UI free of the English word "tooltip"; the literal guard forbids a hardcoded replacement |
| A6 | The top bar measures 49 px where the mockup's box is 48 px | 48 px row + the 1 px `border-bottom`; the border is part of the mockup's own design, so the box is 48 px in both |
| A7 | The Overview's freshness summary reads `۴ بهروز · ۳ کهنه` where the mockup shows `۵ بهروز · ۲ کهنه` | Data, not design: four sources are inside their cadence today. The string, the separator and the amber stale count all match |
| A8 | The coverage table renders 54 rows where the mockup shows 8 | Data, not design: the catalog holds 54 indicators |
| A9 | `render_page_header` gained an optional `label_key` (Task 33) | A plan deviation, not a visual one: the plan's Task 33 file list named only `page_view.py` and the guard, but the acceptance requires the bold methodology label and Task 18's signature had no way to pass one. The parameter is additive and defaults to `None` |

## 6. Owner checklist

The owner reviews `overview-1440x2200.png` (and `overview-1440x4900.png` for the
full page) against `overview-redesign-mockup.png`, then works down this list.

- [ ] The shell reads as the mockup's: 256 px sidebar, brand, grouped nav with
      Material icons, active-item accent bar, pinned DB status, full-bleed top
      bar with the breadcrumb and the last-collection stamp.
- [x] The page header reads as the mockup's: `مرور کلی` title, then the amber
      methodology callout with the bold `یادداشت روش‌شناسی` label and its glyph.
- [x] The KPI band matches: six cells, mockup order, the separated secondary
      group, the `نیازمند بررسی` tag, tooltips on the three annotated cells.
- [x] The two-column row matches: freshness right and wider, domain bars left,
      stale-first freshness, both section headers carrying their trailing summary.
- [x] The coverage section matches: section title, the three-filter bar with the
      row-count echo and the density toggle, the ten columns with the three
      two-line headers, unit chips, LTR ids, the em-dash nulls, and the footnote.
- [x] **F1** main content padding 70 px vs 40 px — **not requested now** (optional
      Wave H candidate).
- [x] **F2** breadcrumb separator `،` vs `/` and the unbolded current crumb —
      **not requested now** (optional Wave H candidate).
- [x] **F3** the `gdp` legend title `label` — **scheduled** in Waves D–G, starting
      with Task 35.
- [x] **F4** the English `Choose options` placeholder — **scheduled** in Waves D–G,
      starting with Task 35.
- [x] **F5** the shell-wide `st.caption` direction — **not requested now**
      (optional Wave H candidate).
- [x] **F7** the short categorical coverage columns wrap — **not requested now**
      (optional Wave H candidate).
- [x] The Gregorian-vs-Jalali range-cell direction — **not requested now**
      (optional Wave H candidate). The font-size half is **fixed** (Step 0a).
- [x] Deviations **A1–A9** are approved as recorded.
- [x] No element of the mockup was silently dropped.

## 6a. Owner sign-off (recorded 2026-09-21)

The owner's decisions, verbatim:

- **Owner sign-off: APPROVED.** Approved deviations A1–A9 as recommended.
- **Fixed on the owner's request:** Gregorian range font size (Step 0a).
- **Scheduled:** **F3** (chart legend title "label") and **F4** (English "Choose
  options" placeholder) in Wave D–G, starting with Task 35.
- **Not requested now (recorded as optional Wave H polish candidates, not
  scheduled):** F1 content padding 70 px vs the mockup's 40 px; F2 breadcrumb
  separator and bold current crumb; F5 shell-wide `st.caption` direction; F7
  no-wrap in short categorical coverage columns; the direction difference between
  Gregorian (LTR) and Jalali (RTL) range cells.
- **Data-quality findings for the ETL/catalog side** (presentation is correct):
  D1 TGJU snapshot rows declare a coverage window (20 – 20 Shahrivar) narrower
  than the observed range (18 – 20 Shahrivar); D2 several Statistical Centre of
  Iran monthly rows declare coverage but have no Gold observations. Recorded in
  the plan's Deferred Scope as items 15 and 16.

**Owner sign-off: APPROVED (2026-09-21).**

## 7. What this gate unblocks

Wave C is **closed**. The sign-off above unblocks every task in Waves D–H: the
four A2 pages (Tasks 35–36), then the A3 pages (38–40), the A4 page (42), the A5
page (44), and the final close-out (46). The two **scheduled** fixes (F3, F4)
land inside those waves starting with Task 35; the **not-requested-now** items
(F1, F2, F5, F7 and the range-cell direction) are optional Wave H polish
candidates and are not scheduled.
