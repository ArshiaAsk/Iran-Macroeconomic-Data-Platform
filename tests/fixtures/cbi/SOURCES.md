# CBI Fixture Sources

## Reconnaissance Date

**Probed:** 2026-09-13 (~10:14–10:23 Iran time, Asia/Tehran, UTC+03:30).

**Outcome:** ⛔ **No genuine CBI fixtures could be captured.** `www.cbi.ir` is
behind an F5 BIG-IP ASM bot-defense layer and `tsd.cbi.ir` does not answer at
all. Per AGENTS.md ("if a source is blocked, do not work around it — record the
evidence and defer") **no attempt was made to solve or bypass the challenge**.
This directory therefore contains only *evidence of the block*, not data.

## Evidence

| Fixture | Probe | Observation |
|---------|-------|-------------|
| `cbi_home.html` | Playwright Chromium, normal browser UA, direct connection, `GET https://www.cbi.ir/` | HTTP **200**, but only **254 bytes**: `<title>Request Rejected</title>` — an F5 ASM rejection page ("The requested URL was rejected… Your support ID is: 7880755047040941175"). No site content. |
| `cbi_robots.html` | Same, `GET https://www.cbi.ir/robots.txt` | Identical 254-byte "Request Rejected" page — even `robots.txt` is not served. |
| `robots.cbi.txt` | `curl -ksS https://www.cbi.ir/robots.txt` | HTTP 200, `text/html`, **42534 bytes** — an F5 **TSPD JavaScript challenge** (`window["bobcmn"] = …`, `TSPD_101`, `failureConfig`), not a robots policy. |
| `robots.cbi.response.txt` | response headers for the above | `Content-Type: text/html`, `Set-Cookie: bci…_session_NGX`, F5 challenge markers. |
| `tsd.cbi.ir` | `curl` (http + https) and Playwright (http + https) | **No response at all.** `curl` exits 28 / HTTP `000` after 25 s connection timeout; the browser navigation times out after 40 s. The TSD subdomain is unreachable from this network. |
| `_gate.json` | Machine-readable gate result | Status/title/final URL/marker flags for each probe. |

Reproduction commands (require outbound network):

```bash
curl -ksS -m 25 -w "%{http_code}\n" -o /dev/null https://www.cbi.ir/       # 200 but challenge/reject
curl -ksS -m 25 -w "%{http_code}\n" -o /dev/null https://tsd.cbi.ir/       # 000, connection timeout
```

## Gate decision

**CBI gate: CLOSED → deferred, not implemented.** A normal browser session
(the plan's gate criterion) does **not** yield genuine data, so CBI tasks 6–7
are skipped. The full gate record lives in `docs/phase-5/VALIDATION.md`. There
is no CBI connector, config, DAG, or parser in the codebase, matching the
Phase 4 OPEC ruling.

## Task 6 re-check (2026-09-13, ~11:30 Iran time)

Re-probed before implementing Task 6 (`cbi_parser.py`), because that task is
conditional on the gate being open. **Result: still CLOSED.** No parser was
created.

| Fixture | Probe | Observation |
|---------|-------|-------------|
| `task6_cbi_home_browser.html` | Playwright Chromium, direct, `GET https://www.cbi.ir/` | HTTP 200, **43882 bytes**, F5 TSPD challenge (`TSPD_101`, `bobcmn`, `support ID`) — no content |
| `task6_cbi_robots_browser.html` | Same, `GET https://www.cbi.ir/robots.txt` | HTTP 200, **40106 bytes**, same challenge |
| `task6_cbi_home_curl.html` | `curl` direct, `GET https://www.cbi.ir/` | HTTP 200, **48138 bytes**, same challenge |
| `task6_cbi_robots_curl.txt` | `curl` direct, `GET https://www.cbi.ir/robots.txt` | HTTP 200, **41210 bytes**, same challenge |
| `_gate_task6.json` | Machine-readable re-check | status / byte length / sha256 / markers per probe, plus the `tsd.cbi.ir` DNS failure |

`tsd.cbi.ir` still does not resolve (`curl` exit 6 "Could not resolve host";
browser `net::ERR_NAME_NOT_RESOLVED`). No bypass was attempted.

## Task 7 re-check (2026-09-13, ~11:45 Iran time)

Task 7 (`cbi_scraper.py`) targets the TSD host, so `tsd.cbi.ir` was re-probed
before implementing. **Still CLOSED:** both `https://tsd.cbi.ir/` and
`http://tsd.cbi.ir/` time out (`curl` exit 28, HTTP `000`, after 20 s); the
`www.cbi.ir` F5 challenge from the Task 6 re-check still applies. No scraper was
created and no bypass was attempted. Machine-readable result:
`_gate_task7.json`.
