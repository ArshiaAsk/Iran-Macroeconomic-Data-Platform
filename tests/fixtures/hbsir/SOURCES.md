# HBSIR Fixture Sources

## Reconnaissance Date

**Captured:** 2026-09-13 (۲۲ شهریور ۱۴۰۵) ~20:17 Iran time (Asia/Tehran, UTC+03:30).

**Tooling:** `hbsir==0.6.6` (+ `bssir==0.6.8`) in the scratch venv
(`/tmp/p6recon`, Python 3.12.3), over an escalated outbound connection. The
package downloads its data automatically; no credentials are required.

**Why this directory exists:** Phase 6 Task 1 (reconnaissance / dependency
gate). These files are the contract for `src/connectors/hbsir_parser.py` /
`hbsir.py` and their tests.

## Package

| Field | Value |
|-------|-------|
| Distribution | `hbsir` (import `hbsir`), depends on `bssir` |
| Version | 0.6.6 (hbsir), 0.6.8 (bssir) |
| Released | 2025-12-07 (hbsir); 2025-11-29 (bssir) — frequent releases through 2025 |
| Wheel | `py3-none-any` — pure Python |
| `Requires-Python` | `>=3.10` (both) — compatible with the project's 3.11–3.12 range |
| License | MIT (hbsir and bssir; `dist-info/licenses/LICENCE`) |
| Project | https://github.com/Iran-Open-Data/HBSIR (and `/BSSIR`) |
| `__version__` attr | present (`hbsir.__version__ == "0.6.6"`) |
| Maintenance | active (5 releases between 2025-09 and 2025-12) |

## Data access

`hbsir` is a **data loader over a local data directory**, not an HTTP client.
It ships metadata + schema but **not** the survey microdata. Calling
`hbsir.load_table(name, years=Y)` transparently **downloads a pre-built
"cleaned" Parquet file per (table, year)** into `./Data/HBSIR/4_cleaned/` from
the Arvan S3 mirror (`https://s3.ir-tbz-sh1.arvanstorage.ir/iran-open-data`,
bucket `iran-open-data`), or builds it from raw SCI files. After the first
download the package works fully offline from that directory.

```python
import hbsir
income = hbsir.load_table("Total_Income", years=1400)   # Year, ID, Income
weight = hbsir.load_table("Weight",       years=1400)   # Year, ID, Weight
```

| Probe | Result |
|-------|--------|
| `load_table("Weight", 1400)` | ✅ 37,988 rows; downloaded ~300 KB of cleaned parquet |
| `load_table("Total_Income", years=[1369,1385,1390,1395,1400,1403])` | ✅ all six years load, 18k–38k rows each |
| `load_table("Total_Expenditure", 1400)` | ✅ 37,988 rows |

## Tables / fields needed

| Table | Columns | Notes |
|-------|---------|-------|
| `Total_Income` | `Year`, `ID`, `Income` | Annual household income (Rial). Can be negative (net losses). |
| `Total_Expenditure` | `Year`, `ID`, `Gross_Expenditure`, `Net_Expenditure` | Expenditure basis alternative to income. |
| `Weight` | `Year`, `ID`, `Weight` | Sampling weight per household. |

`Weight` is derived by the package from province weight shares
(`internal_data/province_weights_*.csv`) and census household counts — it is a
**required** input for any distributional statistic.

## Survey years and temporal alignment

- `Total_Income` is available for **1369 → 1403** (35 Jalali years) — well past
  the 10-year requirement. `hbsir` metadata declares data back to 1363 for some
  expenditure tables.
- Survey years are **Jalali**; 1403 is the latest (Gregorian year-end
  ≈ 2025-03-20). Store the Gregorian year-end and keep the Jalali year in
  `record_metadata`. Note Esfand has 29 or 30 days, so compute the true Iranian
  year-end rather than hardcoding `12-29`.

## Income vs expenditure, and the poverty line

- **Both bases are available** (`Income`, `Gross_Expenditure`,
  `Net_Expenditure`). The plan's decile/Gini target is naturally computed on
  **income**; expenditure is the documented alternative.
- The package exposes weighted quantile helpers (`hbsir.calculate.add_decile`,
  `quantile`, `weighted_average`) but **no Gini and no poverty line** — the
  platform must compute them. Its knowledge base
  (`knowledge_base/minute_summary`, `sci_results/T1xx`) contains decile tables
  and OECD / modified-OECD equivalence scales but **no official (خط فقر)
  poverty line**.
- **Recommended MVP poverty line:** an explicit, configurable **relative** line
  (`k × weighted median equivalized/`household` income`, default 50%), recorded
  in metadata. The official SCI calorie-based line (the package ships
  `internal_data/nnftri_calorie_requirements.csv` for calorie-equivalent
  scales) is a follow-up decision, not assumed here.

## Real computation (validates the parser design)

Merging `Total_Income` + `Weight` (household-weighted, no equivalence scaling)
for four survey years produced a coherent trend; decile shares sum to ~100:

| Jalali year | Gini | Poverty % (`50% × weighted median`) | Weighted households |
|-------------|------|--------------------------------------|---------------------|
| 1390 | 0.3494 | 15.85 | 21.16 M |
| 1395 | 0.3767 | 16.26 | 24.85 M |
| 1400 | 0.3704 | 16.42 | 26.69 M |
| 1403 | 0.3451 | 14.58 | 28.20 M |

(1400 income decile shares, %: 1.88 / 3.86 / 5.21 / 6.38 / 7.58 / 8.92 /
10.54 / 12.60 / 15.81 / 27.22 — sum ≈ 100.0.)

## Fixtures

Provenance + checksums: `_manifest.json`.

| File | Contents |
|------|----------|
| `income_expenditure_weight_1400_sample.csv` | 200 real 1400 rows: `Year, ID, Income, Gross_Expenditure, Net_Expenditure, Weight` |
| `metrics_trend.json` | Computed Gini / relative-poverty / decile shares for 1390/1395/1400/1403 + source column lists |
| `_manifest.json` | Package versions, mirror URL, source Parquet filenames/sizes/sha256 |

Full microdata is **not** redistributed here (MIT package, large survey files);
only small real extracts and derived aggregates are kept. The sample keeps real
IDs because they are opaque survey identifiers, not personal data.
