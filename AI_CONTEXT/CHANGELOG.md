# Changelog

Significant project changes for AI/human handoff. Package builds may exist without git tag.

## 2026-08-12

### Added

- `AI_CONTEXT/*` project knowledge base + root `AGENTS.md` (agent-agnostic handoff protocol)
- Daily backup report on Dashboard (`ReportService`, date filter, send email, once-per-day auto)
- `history_for_date` query on repository
- Target `webmin_url` + dashboard **Buka** Webmin
- Settings/recipient defaults for daily report (`daily_report_to` → `akenprodev@gmail.com`)
- **Backup arrival scan** (`BackupArrivalService`): detect new archives on backup host → `backup_arrival*` history → daily report; dashboard **Scan backup masuk** + refresh throttle

### Changed

- Source package build number → **0.1.0-11** (`bcc/__init__.py`)
- Report summary includes arrival entry count

### Database

- `backup_targets.webmin_url` (schema + migrate)
- Settings keys: `daily_report_enabled`, `daily_report_to`, `report_email_last_day`
- Settings keys (arrival): `arrival_scan_state`, `arrival_scan_on_refresh`, `arrival_scan_interval_min`, `arrival_last_scan_at`

---

## 2026-08-09 (approx.)

### Added

- `NotifyService` SMTP SSL + WhatsApp stub
- Repository hooks on inventory CRUD + `add_run_history`
- Settings UI for email/WA + test buttons
- Disk pie chart label display using inventory `label` (folder still `source_label`)

### Package

- EXE builds through **0.1.0-9** (dist gitignored)

---

## 2026 (initial)

### Added

- BCC CustomTkinter application structure
- SQLite inventory, deploy templates, schedules, backup/monitor/browse
- Git initial public repo + secret gitignore patterns
- PyInstaller packaging (`build_exe.py`)
