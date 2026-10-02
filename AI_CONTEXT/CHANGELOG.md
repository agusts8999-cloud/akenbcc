# Changelog

Significant project changes for AI/human handoff. Package builds may exist without git tag.

## 2026-10-02 OMV paths

### Changed

- Backup target keeps Tailscale as `host` for VPS rsync. New `lan_host` is tried first by BCC with a 3-second timeout, then Tailscale.
- Remote `SSH_OPTS` sends a keepalive every 15 seconds so long rsync sessions stay up. Template version `0.1.2`.
- OMV `lan_host` set to `192.168.0.110`. VPS `REMOTE_HOST` stays `100.107.205.80`.
- Redeployed the four VPS so live `config.sh` has the keepalive options. Confirmed on `46.250.233.39`.

### Package

- Bumped build to `19`.

## 2026-10-02 later

### Fixed

- Backup scripts append logs directly, so a finished website backup no longer holds the SSH session open and blocks the database step.
- Manual full backup starts `backup-all.sh` on the VPS with `nohup` and polls the log. Website then database continue if the PC connection drops.
- Source SSH tries the last successful address, then the primary host, then `alt_host`, only when connect fails.

### Package

- Bumped build to `18`.

## 2026-10-02

### Changed

- Operator inventory: target `OMV NAS` (`100.107.205.80`, user `aken`) base path corrected from `/home/backupuser/backups` to the 954G data disk `/srv/dev-disk-by-uuid-B004D6B804D68130/NAS/backups`.
- Registered storage `OMV NAS backups` in review mode. Remote folders `webs`, `dbs`, and `logs` created.
- Restored four aaPanel VPS sources from the local gitignored seed onto target `OMV NAS`. SSH to each host succeeded. No Windows PC entries existed in that catalog.
- Redeployed Linux scripts, SSH trust to OMV, and aaPanel web/DB cron on all four sources. Each `setup-ssh` reported success.
- Bumped package build to `17`.

### Security

- OMV password stored only in the AppData Fernet vault. It is not in git or this changelog.

## 2026-08-18

### Added

- Storage result controls for **Tampilkan semua**, **Pilih semua**, **Kosongkan pilihan**, **Pindahkan semua**, and **Hapus semua**.
- All-status retention view covering `pending`, `archived`, `deleted`, and `error` records.

### Changed

- Bulk actions are limited to visible pending candidates on the selected storage.
- Move operations refuse to overwrite an existing destination filename.
- Replaced the free-form retention field with explicit age-filter choices; initial selection is `> 3 hari` and applies to both scan and displayed results.
- Renamed visible “default” concepts to clearer review/action and archive-folder labels; migrated legacy `group_key=default` metadata to `arsip`.

### Security

- Bulk move/delete requires an explicit confirmation containing the affected candidate count.

### Package

- Bumped package version to `0.1.1`, build `14`.
- Built `dist/BackupControlCenter-0.1.1-14.exe` with Python 3.12/PyInstaller.
- Desktop shortcut creation and 8-second GUI process smoke test succeeded.

### UI

- Added a global indeterminate process spinner in the MainWindow sidebar/header.
- Routed long-running SSH, browse, deploy, backup, report, scan, and schedule operations through `MainWindow.run_async()`.
- Spinner uses a concurrent-operation counter so it remains visible until all overlapping operations finish.
- Bumped package version to `0.1.2`, build `15`.
- Built `dist/BackupControlCenter-0.1.2-15.exe`; shortcut creation and GUI smoke test succeeded.
- Bumped package version to `0.1.3`, build `16`.
- Built `dist/BackupControlCenter-0.1.3-16.exe` with Python 3.13/PyInstaller and refreshed the desktop shortcut.
- Verified embedded file/product version `0.1.3-16`; isolated-AppData EXE smoke test passed for 10 seconds.
- Replaced direct worker-thread Tk calls with a thread-safe main-thread callback queue.
- Long operations now run serially with duplicate job-key suppression.
- Added a modal process overlay that blocks navigation/F5 and shows elapsed time plus queued work.
- F5 refreshes only the active view; startup no longer refreshes every hidden tab.
- Added 50-row retention pagination and 100-row file-browser pagination.
- Tailscale CLI status now runs asynchronously and is cached for 60 seconds.
- Scheduled retention checks only open the loader when at least one policy is due.

### Verification

- Python 3.12 `compileall` passed.
- Static audit confirmed no view calls widget `.after()` from workers.
- Isolated-AppData GUI startup smoke ran for 10 seconds without thread/Tk exceptions.

## 2026-08-17

### Added

- Storage management tab and `StorageService`
- Remote storage/mount registration and mount test
- Retention scan with default 3-day threshold and persisted candidates
- Candidate grouping plus explicit archive/delete actions
- Scan-only local scheduler for enabled retention jobs while BCC is running

### Database

- Added `backup_storages`, `retention_jobs`, and `retention_items` with idempotent initialization

### Security

- Archive/delete are never performed automatically; delete requires confirmation and selected candidates

### Package

- Built `dist/BackupControlCenter-0.1.0-13.exe` with PyInstaller and Python 3.12.
- Verified Tcl/Tk packaging and completed an 8-second GUI process smoke test.
- Desktop shortcut creation succeeded.

## 2026-08-17

### Added

- `AI_CONTEXT/INDEX.md` as the central context router
- Vendor-neutral onboarding, workflow, and handoff protocol under `AI_CONTEXT/agents/`
- Scalable README entry points for module, architecture, and database context

### Changed

- `AGENTS.md` now explicitly routes agents through `AI_CONTEXT/INDEX.md`
- `CURRENT_STATE.md`, `TASKS.md`, and `HANDOFF.md` record the context-system update

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
