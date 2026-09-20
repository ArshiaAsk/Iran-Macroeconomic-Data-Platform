# Phase 7.2 — Dashboard Redesign

Runbook and validation records for Phase 7.2 (design system, shell, all pages).

Status: **Wave 0 in progress** (verification spike + baseline). See
[`wave-0-spike.md`](wave-0-spike.md) for the recorded capabilities, the
pre-change baseline and the per-wave gate rule. Implementation waves A–H follow.

Planned documents (added by later waves):

- `design-system.md` — tokens, theme table, shell CSS, component reference.
- `README.md` — this file, completed in Wave H.
- `VALIDATION.md` — verification record (Wave H), separating "verified in this
  run" from "not automated".
- `execution-log.md` — per-task execution log (files, Verify result, deviations,
  commit hash).

Local-development note (D14): the settings-menu theme toggle is already absent
because the app defines a custom `[theme]`; the toolbar can be restored for
development with `STREAMLIT_CLIENT_TOOLBAR_MODE=developer`.
