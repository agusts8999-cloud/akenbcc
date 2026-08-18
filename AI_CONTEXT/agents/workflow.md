# AI Agent Workflow

```text
DISCOVER → UNDERSTAND → PLAN → IMPLEMENT → TEST → VERIFY → DOCUMENT → HANDOFF
```

- Discover the relevant module, architecture, dependencies, tests, and known issues.
- Understand behavior from source code and schema before editing.
- Plan explicitly for multi-file or risky work.
- Implement the smallest safe change using existing services and conventions.
- Run the narrowest relevant checks, then inspect the diff and documentation drift.
- Update `CURRENT_STATE.md`, `TASKS.md`, and `HANDOFF.md`; update architecture, database, modules, decisions, and changelog when applicable.

Never start coding after reading only one file, and never claim verification that was not run.
