# EIA fixtures

Captured from the EIA Open Data API v2 (`/v2/international/data/`) on
2026-09-12.

| File | What it is |
|------|------------|
| `CRUDE_PRODUCTION_normal.json` | Iran monthly crude/NGPL production (`productId=55`, `activityId=1`), 2024-01..2026-05 |
| `TOTAL_LIQUIDS_normal.json` | Iran monthly total liquids (`productId=53`, `activityId=1`), 2024-01..2026-05 |
| `unknown_facet.json` | The HTTP 200 `total: "0"` response for a facet that matches nothing |
| `API_KEY_MISSING.json` / `API_KEY_INVALID.json` | The real HTTP 403 error bodies |

**Provenance.** The payload schema, field names/types, auth error bodies, facet
ids, paging (`length`/`offset`), sorting, and the `start`/`end` bounds were
verified against the live API. The `2024-01..2026-05` values were captured with
the public `DEMO_KEY`; where its rate limit blocked a complete capture the
monthly numbers are representative of Iran's production levels rather than
byte-for-byte. The parser and connectors only depend on the schema and types.
