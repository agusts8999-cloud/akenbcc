# AGENTS.md — Entry Point for AI Agents

**Read this file first** before changing any code in this repository.

---

## 1. Project identity

| Field | Value |
|-------|--------|
| Name | **Backup Control Center (BCC)** |
| Package | `bcc` |
| Version | See `bcc/__init__.py` (`__version__`, `__build__`) |
| Runtime | Python 3 desktop app (Windows primary) |
| Repo (public) | https://github.com/agusts8999-cloud/akenbcc.git |

---

## 2. Purpose

BCC is a **support & monitoring** desktop GUI for autonomous remote backups:

- Sources: Linux VPS (aaPanel) and Windows PCs → copy data to a **backup server** (e.g. Webmin host) over SSH/Tailscale.
- Backup execution lives on the **source servers** (cron / scripts). BCC deploys scripts, pushes schedules, monitors, logs history, and sends reports.
- BCC is **not** the long-running backup worker for every VPS cron job; email reports only cover events that hit the local SQLite `run_history`.

---

## 3. Technology

| Layer | Stack |
|-------|--------|
| UI | CustomTkinter only (do **not** reintroduce PySide6/Qt) |
| SSH | Paramiko |
| Secrets | Fernet (`cryptography`) via `bcc/services/secrets.py` — key in AppData |
| DB | SQLite at `%AppData%\BackupControlCenter\bcc.db` |
| Email | stdlib `smtplib` SSL |
| Charts | Pillow pie chart |
| Build | PyInstaller one-file EXE via `build_exe.py` |

Dependencies: `requirements.txt`.

---

## 4. Project context location

```text
AGENTS.md                 ← you are here (entry)
AI_CONTEXT/               ← full project knowledge base
  INDEX.md                ← context router (read after this file)
  PROJECT.md
  ARCHITECTURE.md
  DATABASE.md
  MODULES.md
  CONVENTIONS.md
  DECISIONS.md
  CURRENT_STATE.md
  ROADMAP.md
  TASKS.md
  CHANGELOG.md
  HANDOFF.md
  agents/                 ← onboarding, workflow, and handoff protocol
```

**Source of truth:** repository code + AI_CONTEXT. Do not rely on chat memory or prior agents.

---

## 5. Reading protocol (mandatory)

1. Read `AGENTS.md` (this file).
2. Read `AI_CONTEXT/INDEX.md`.
3. Read at minimum:
   `AI_CONTEXT/PROJECT.md`, `CURRENT_STATE.md`, `ARCHITECTURE.md`, `MODULES.md`, `CONVENTIONS.md`, `DECISIONS.md`, `TASKS.md`, `HANDOFF.md`.
4. Inspect the real tree (`bcc/`, scripts, `.gitignore`).
5. If docs ≠ code: **code wins**; then update AI_CONTEXT.
6. Only then implement the smallest safe change.

---

## 6. Coding rules

- Prefer **minimal surface** changes.
- Reuse existing services (`DeployService`, `BackupService`, `NotifyService`, `ReportService`, repository hooks).
- CustomTkinter UI only.
- **Never** name a widget attribute `_root` (breaks Tkinter `nametowidget`).
- Do not add heavy frameworks without an ADR + user approval.
- Indonesian UI copy is existing style; keep consistent.

---

## 7. Database rules

- Schema: `bcc/db/schema.py` + idempotent `_migrate()` in `repository.py`.
- Secrets columns: `*_enc` encrypted with `SecretBox`; never log plaintext passwords.
- Soft delete via `deleted=1` on sources/targets.
- AppData DB is outside git — do not commit `*.db` or vault keys.

---

## 8. Testing / verification

- Dev run: `python -m bcc` or `python run_bcc.py`.
- After UI/service changes: smoke-test relevant tab; SSH tests only if environment has Tailscale/targets.
- Build: `python build_exe.py` → `dist/BackupControlCenter-{ver}-{build}.exe`.
- Bump `__build__` in `bcc/__init__.py` on each package release.
- Do not claim “production ready” without relevant verification.

---

## 9. Security rules

- Never commit live passwords (`config.sh`, `seed_existing_servers.py`, SMTP password, etc.).
- Public GitHub: treat all commits as world-readable.
- Encrypted secrets only under `%AppData%\BackupControlCenter\`.
- Do not print secrets in UI logs or handoff docs.

---

## 10. Documentation rules

After significant changes update:

```text
CODE → verify → AI_CONTEXT (CURRENT_STATE, CHANGELOG, HANDOFF, TASKS, and ARCH/DB/MODULES if needed)
```

Do not delete obsolete knowledge; mark **Deprecated** or **Superseded by ADR-xxx**.

---

## 11. Handoff rules

Before finishing a work session, update `AI_CONTEXT/HANDOFF.md` so the next agent can continue without this chat.

---

## 12. Destructive actions

Ask user first before:

- Drop/reset DB, delete mass data, force-push main, large rewrites, production config wipe, removing major modules.

---

## Universal join prompt (short)

> Continue this project. Read AGENTS.md then AI_CONTEXT. Code is truth. Smallest safe change. Update context when done.
