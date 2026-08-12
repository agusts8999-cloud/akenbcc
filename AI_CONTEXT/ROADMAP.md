# Roadmap

High-level directions only — detailed work in `TASKS.md`.

## Near term

- Stabilize daily report + SMTP operationally (password set, verify delivery)
- Keep EXE build cadence with `__build__` bumps
- Ensure AI_CONTEXT stays updated with code

## Medium term

- Optional: remote cron hook/script endpoint so pure VPS jobs report into BCC or email without GUI
- Filter/debounce event notifications (importance levels)
- Windows-PC backup path parity with Linux templates
- Lightweight automated tests for repository query/report builders

## Long term

- Optional multi-operator shared inventory (would need ADR — currently local SQLite only)
- Richer monitoring (email digest of disk thresholds without only GUI)

## Explicit out of scope (unless ADR)

- Rewrite to web multi-tenant SaaS
- Reintroduce PySide6 as primary UI
- Storing production passwords in the public repository
