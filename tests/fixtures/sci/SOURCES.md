# SCI Fixture Sources

## Reconnaissance Date

**Captured:** 2026-09-13 (۲۲ شهریور ۱۴۰۵) between ~10:13 and ~10:25 Iran time
(Asia/Tehran, UTC+03:30).

**Tooling:** Playwright 1.62 Chromium (headless) with a normal browser
User-Agent. The site rejects the container's default HTTP proxy at the TLS
layer (`ERR_CONNECTION_CLOSED`); captures were made over a **direct**
connection (`--proxy-server=direct:// --proxy-bypass-list=*`) which loads the
site normally. `curl` reaches the same URLs directly.

**Why this directory exists:** Phase 5 Task 1 (reconnaissance checkpoint). These
files are the contract for the SCI parser/scraper tasks (4–5); parsers must be
written against the real structures documented here, not against assumptions.

## robots.txt Check

**URL:** https://www.amar.org.ir/robots.txt
**Status:** ✅ HTTP 200, `text/plain`, 4291 bytes — **permissive for our paths**

Evidence: `robots.amar.txt` (body), `robots.amar.response.txt` (headers).

The `User-agent: *` block disallows only `/admin/`, `/App_*/`, `/bin/`,
`/images/`, `/Resources/…`, `/activity-feed/`, and query patterns. The
publication paths we use (`/Portals/0/Statistics/…`, `/Portals/0/Articles/…`)
are **not** disallowed. `Crawl-delay: 5` applies only to `msnbot`, `Slurp`, and
`Googlebot`, not to `*`; the platform's 1–2 req/sec rule is still honoured.

## TLS certificate

`tls_certificate.txt`. The server presents an **incomplete chain**: the leaf
`CN=amar.org.ir` is issued by `Certum DV TLS G2 R39 CA`, but the server sends
the *older* `Certum Trusted Network CA` intermediates instead, so OpenSSL
returns `Verify return code: 21 (unable to verify the first certificate)`.
TLS 1.3 / `TLS_AES_256_GCM_SHA384` works. A future connector must verify
deliberately (ship/obtain the missing intermediate or pin a CA bundle) rather
than defaulting to `verify=False`.

## CPI publications (`https://amar.org.ir/prices`)

SCI currently publishes CPI as **Excel workbooks** (plus monthly PDF reports).
All dates inside the workbooks are **Jalali** (Persian month names and 13xx/14xx
years); no Gregorian labels are present. The base year is written as `100=1400`
(2021) or `100=1395` (2016).

| Fixture | Base year | Observed coverage | Notes |
|---------|-----------|-------------------|-------|
| `cpi_national_timeseries.xlsx` | 1400 = 2021 | monthly فروردین ۱۳۹۰ – مرداد ۱۴۰۵ | All-household (national) CPI. 12 sheets (`فهرست`, `فراداده`, `جدول 1`–`جدول 10`). |
| `cpi_urban_timeseries.xlsx` | 1400 = 2021 | monthly فروردین ۱۳۸۱ – مرداد ۱۴۰۵ | Urban-household CPI. 14 sheets (`فهرست`, `فراداده`, `جدول 1`–`جدول 12`). |
| `cpi_rural_timeseries.xlsx` | 1400 = 2021 | ۱۳۶۱ – ۱۴۰۵ | Rural CPI (12 sheets, `فهرست`, `فراداده`, `جدول 1`–`جدول 10`); the earliest block is **quarterly** (`بهار/تابستان/پاییز/زمستان`) then becomes monthly — mixed frequency within one file. |
| `cpi_decile_timeseries.xlsx` | 1400 = 2021 | monthly فروردین ۱۳۹۵ – مرداد ۱۴۰۵ | CPI by household **expenditure decile**. 14 sheets (`فهرست`, `فراداده`, `جدول 1`–`جدول 12`): index + monthly/point-to-point/annual inflation, for all goods, food/drink/tobacco, and non-food/services. Rows are the ten deciles (`دهک اول` … `دهک دهم`). |
| `cpi_base1395_timeseries.xlsx` | 1395 = 2016 | monthly ۱۳۸۱ – ۱۴۰۱ | **Explicit base-year-1395 publication** (urban households). 13 sheets. This is the older of the two base-year series available for chain-linking. |
| `cpi_report_1405-05_base1400.pdf` | 1400 = 2021 | مرداد ۱۴۰۵ | Monthly CPI report (PDF). Needs `pdfplumber` (not yet a dependency). |

### Workbook layout (wide sheets)

`جدول 1` in the national/urban/rural/base-1395 workbooks is a **wide** matrix:

- row 1: table title (includes the base, e.g. `… برمبنای سال پایه 100=1400`)
- row 2: Jalali **year** markers, merged across each block of 12 months
  (`1390 … 1405` for national; `1381 … 1405` for urban; `1361 … 1405` for rural;
  `1381 … 1401` for base-1395)
- row 3: Persian **month** names (`فروردین … اسفند`)
- rows 4+: one row per expenditure group / COICOP code, values per month

Subsequent sheets repeat the layout for derived measures (monthly change,
point-to-point, annual inflation).

`cpi_base1395_timeseries.xlsx` additionally contains a tidy **long** sheet
`جدول 3` (`سال | ماه | عدد شاخص`, 2255 rows, ۱۳۶۱-فروردین – ۱۴۰۱-فروردین) —
the cleanest source for a long-format Silver series.

### Base-year availability (important)

Only **two explicit base-year CPI series** are published on the current site:
**1395 = 2016** and **1400 = 2021**. An explicit 1390 = 2011 series was **not
found** on `/prices` or its CPI archives (`catid=3105`) during reconnaissance.
The base-1400 national series is *restated* back to ۱۳۹۰, so 2011 data exists —
but as part of the 2021-base series, not as a separate 2011-base publication.
This is a deviation from the plan's 2011/2016/2021 hypothesis (recorded in
`docs/phase-5/VALIDATION.md`); one real 1395→1400 link is available, with
1390–1395 history reachable through the restated 1400-base series.

## Unemployment publications (`https://amar.org.ir/work`)

SCI publishes the Labour Force Survey as Excel workbooks and PDF reports,
labelled by Jalali **year/season** (not a base year; rates in percent).

| Fixture | Period | Notes |
|---------|--------|-------|
| `unemployment_annual_1404.xlsx` | سال ۱۴۰۴ (annual 2025/26) | 73 sheets, including numbered code sheets (`1404 062`, `1404 061`, …) plus named sheets (`فصل اول`, `فصل دوم`, `شاخصها`, `خلاصه يافتهها`, `تعاريف و مفاهيم`). Layout is section-based and needs per-sheet parsing. |
| `unemployment_spring_1405.xls` | بهار ۱۴۰۵ (spring 2026) | **Legacy `.xls` (BIFF, `application/vnd.ms-excel`)**. `openpyxl` cannot read this; the plan's conditional `xlrd` dependency is therefore **required**. |
| `unemployment_report_1404.pdf` | سال ۱۴۰۴ | Narrative labour-force report (PDF) — `pdfplumber` territory. |

## Page captures

| Fixture | URL | Purpose |
|---------|-----|---------|
| `prices_page.html` | https://amar.org.ir/prices | Price-indices landing page; lists the CPI download links above. |
| `work_page.html` | https://amar.org.ir/work | Labour-force landing page; lists the unemployment download links. |

## Manifest

`_capture.json` holds machine-readable URL / HTTP status / content-type /
byte-length / sha256 for every download. The full sha256 values:

| Fixture | Bytes | sha256 |
|---------|------:|--------|
| `cpi_national_timeseries.xlsx` | 907112 | `155d22eb5958c736bad3ba395dd84e8c06e421b7bbed66a431bdd4c8a77457e1` |
| `cpi_urban_timeseries.xlsx` | 1248356 | `b28e3375b772f37ef5e440ca6ba3378b33173226b0388507953f0c102d259114` |
| `cpi_rural_timeseries.xlsx` | 1394864 | `d445503b87042c014a721da052bf61047b7873cb99a0fc97225bb6f77ec09691` |
| `cpi_decile_timeseries.xlsx` | 306450 | `f49d90a04504e343c1846065fa134cb9bbe72e2f62cf57ab4057016f319fe6f0` |
| `cpi_base1395_timeseries.xlsx` | 617573 | `a417ae40286d982431102af3c02d3d20af064772598e5b8023d2ea2388d74891` |
| `cpi_report_1405-05_base1400.pdf` | 554705 | `570360f8121f43d832bd0cc8fe91866252be357e681d7c8df725121e2e0ad39d` |
| `unemployment_annual_1404.xlsx` | 1429041 | `49a3e7990954c146f5b47e1b0feec253a5532fcdcefa8da3f102299c16ce5d6c` |
| `unemployment_spring_1405.xls` | 370688 | `add2970ec19b336bd4e5504e5532fab6f35815dbe03eb7d720defb30059521cf` |
| `unemployment_report_1404.pdf` | 1023044 | `02a4fae909e1b55ab1514405ef3de73d70be5d3a4dca6318b01eab4c4af92fac` |
| `prices_page.html` | 648927 | `4739f6d7f99389ca1fbbe891c91446303c37ac9986f4656ad20ca70814d32c8e` |
| `work_page.html` | 400467 | `c58ffa086f008e76bd3544628ca4453cb01b70ef5cdf12441595f45e58b557ce` |
| `robots.amar.txt` | 4291 | `dc905811243a60fd…` (robots policy) |

## Re-capture notes

- The site is a DNN/ASP.NET portal; download filenames embed Jalali timestamps
  (e.g. `ts_national_140505-14050618165053.xlsx` → ۱۴۰۵/۰۵, updated ۱۴۰۵/۰۶/۱۸).
  URLs are not stable across updates — fixtures must be re-captured, not
  re-fetched by hard-coded filename, when the parser complains.
- Re-run `curl -ksS -o /dev/null -w "%{http_code}" https://www.amar.org.ir/robots.txt`
  to confirm the policy has not changed.
