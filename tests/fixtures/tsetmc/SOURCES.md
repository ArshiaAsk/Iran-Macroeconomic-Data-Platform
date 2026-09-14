# TSETMC Fixture Sources

## Reconnaissance Date

**Captured:** 2026-09-13 (۲۲ شهریور ۱۴۰۵) ~20:15 Iran time (Asia/Tehran, UTC+03:30).

**Tooling:** `finpy-tse==1.2.10` installed in a scratch venv
(`/tmp/p6recon`, Python 3.12.3), invoked over a direct outbound connection
(escalated approval; the sandbox blocks network by default). No browser or
credentials were required.

**Why this directory exists:** Phase 6 Task 1 (reconnaissance / dependency
gate). These files are the contract for `src/connectors/tsetmc.py` and its
tests; the parser must be written against the real payload documented here.

## Package

| Field | Value |
|-------|-------|
| Distribution | `finpy-tse` (import `finpy_tse`) |
| Version | 1.2.10 |
| Released | 2024-04-24 (previous 1.2.9 the day before) |
| Wheel | `py3-none-any` — pure Python, no compiled extensions |
| `Requires-Python` | not declared; pure-python wheel, verified importable on CPython 3.12 |
| License | BSD 3-clause (`finpy_tse-1.2.10.dist-info/LICENSE.txt`) |
| `__version__` attr | **absent** — read the version via `importlib.metadata.version("finpy-tse")` |
| Homepage/Project-URL | none published on PyPI; contact is the author email in METADATA |
| Maintenance | last release ~2.4 years old at capture time (stable, not actively developed) |
| Transport | `requests` (sync) against `cdn.tsetmc.com` / `old.tsetmc.com`; no API key |

## Live access

The package's index functions were exercised live; **no authentication** is
required and the endpoints answered normally from this environment.

```python
import finpy_tse
df = finpy_tse.Get_CWI_History(ignore_date=True, just_adj_close=True)
# DataFrame indexed by Jalali date (J-Date), one column: "Adj Close"
```

| Probe | Result |
|-------|--------|
| `Get_CWI_History(ignore_date=True, just_adj_close=True)` | ✅ 4,283 rows, 1387-09-14 → 1405-06-22 |
| Raw `Index/GetIndexB2History/32097828799138957` | ✅ HTTP 200, `indexB2` list |
| `Get_MarketWatch(save_excel=False)` | ✅ 1,544 symbols, current-day snapshot |

## Index mapping (verified from source docstrings + `sector_web_id`)

`finpy_tse` wraps the TSETMC **`Index/GetIndexB2History/{insCode}`** endpoint.
The total index function is `Get_CWI_History` ("شاخص کل", *Cap-Weighted Index*
= **TEDPIX**), `insCode = 32097828799138957`.

Several sibling index functions share the exact same shape and can be added
later if the PRD needs them: `Get_CWPI_History` (TEPIX, price-only),
`Get_EWI_History` (equal-weighted), `Get_FFI_History` (free-float),
`Get_MKT1I_History` / `Get_MKT2I_History` (first/second market),
`Get_INDI_History` (industry), `Get_LCI30_History`, `Get_ACT50_History`.

## Data shape and fields

Raw `indexB2` record (one per trading session):

```json
{"insCode": 32097828799138957, "dEven": 20260913,
 "xNivInuClMresIbs": 7431451.1, "xNivInuPbMresIbs": 7431450.0,
 "xNivInuPhMresIbs": 7464390.0}
```

- `dEven` — Gregorian date as `yyyymmdd` integer. Normalize to a UTC session
  timestamp (market close at ~12:30 Iran time → period end in UTC).
- `xNivInuClMresIbs` — closing index level (this is what
  `Get_CWI_History(just_adj_close=True)` returns, mislabelled `"Adj Close"`).
- `xNivInuPbMresIbs` / `xNivInuPhMresIbs` — additional index values (low/high
  of the index), not needed for the MVP level series.
- With `just_adj_close=False` the package additionally merges
  `old.tsetmc.com/tsev2/chart/data/IndexFinancial.aspx` to add
  Open/High/Low/Close/**Volume** columns (index "volume").

## Findings that shape Task 4

1. **TEDPIX history ✅ OPEN.** 4,283 daily sessions from **1387-09-14
   (2008-12-04)** to the capture day — far beyond the 10-year requirement.
2. **Holidays are absent, not filled.** A two-week window
   (`1404-06-01`…`1404-06-15`) returned only **9** rows: the market is closed
   Thu/Fri and on Iranian holidays. The connector must keep these as gaps.
3. **Adjustment semantics.** TEDPIX is a chained *total* index; the "Adj Close"
   label is a naming artifact, there is no adjusted-vs-unadjusted choice for
   the index level itself (`adjust_price` only exists on individual-stock price
   functions such as `Get_Price_History`). Rebasing/corrections of the
   published index, if any, are not flagged by the package — record the source
   and `insCode` in metadata and treat level jumps as data, not a splice.
4. **Market P/E ❌ not available.** No function, column, or `indexB2` field
   exposes a market-level P/E. `Get_MarketWatch()` has per-symbol `EPS` and
   `Close` only. Probed cdn endpoints (`MarketData/GetMarketOverview/{1,2,3}`,
   `MarketWatchInit.aspx`) expose index value, total traded value, and market
   value — **no P/E**.
5. **Historical aggregate trading value ❌ not available.** `Get_MarketWatch()`
   returns a **current-day, per-symbol** `Value`/`Market Cap` snapshot (1,544
   rows); `MarketData/GetMarketOverview/{1,2}` return a **current-day**
   aggregate (`marketActivityQTotTran`, `marketValue`). Neither is a history,
   so there is no backfill path for a "retail trading value" time series.

## Fixtures

Provenance + sha256: `_capture.json`.

| File | Contents |
|------|----------|
| `tedpix_cwi_raw.json` | Full raw `indexB2` payload (4,283 records) for TEDPIX |
| `tedpix_window_1404-06.csv` | `finpy_tse.Get_CWI_History` output, 2-week window (9 sessions) |
| `marketwatch_columns.json` | `Get_MarketWatch` column inventory + sample rows (P/E absence evidence) |
