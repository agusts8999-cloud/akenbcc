# Modules

## Module: Application bootstrap

**Status:** PRODUCTION  
**Location:** `bcc/app.py`, `bcc/__main__.py`, `run_bcc.py`  
**Responsibilities:** Logging to AppData, ensure deps, init Repository, open MainWindow.  
**Important files:** `bcc/paths.py`, `bcc/version.py`, `bcc/__init__.py`  
**Do Not Change:** AppData path contract without ADR.

---

## Module: Database / Repository

**Status:** PRODUCTION  
**Location:** `bcc/db/`  
**Responsibilities:** Schema, CRUD inventory/schedules/history/settings; fire `NotifyService` after important writes; `history_for_date`.  
**Important files:** `schema.py`, `repository.py`  
**Database tables:** all  
**Known issues:** Soft-delete + overview queries must stay consistent  
**Do Not Change:** Encrypt password fields on write; soft-delete pattern

---

## Module: Secrets

**Status:** PRODUCTION  
**Location:** `bcc/services/secrets.py`  
**Responsibilities:** Fernet encrypt/decrypt for passwords/tokens  
**Dependencies:** cryptography, AppData vault key  
**Do Not Change:** Do not store vault key in repo

---

## Module: SSH

**Status:** PRODUCTION  
**Location:** `bcc/services/ssh_service.py`  
**Responsibilities:** Paramiko run/test connections  
**Used by:** deploy, backup, monitor, browse, targets test

---

## Module: Deploy

**Status:** PRODUCTION  
**Location:** `bcc/services/deploy_service.py`  
**Responsibilities:** Render templates, SFTP upload, setup, aaPanel cron job push  
**Templates:** `bcc/templates/linux/*`  
**run_history:** deploy results  
**Do Not Change:** Placeholder style in template `config.sh` (`{{NAME}}`) casually — deploy filling logic depends on it

---

## Module: Backup (operator-triggered)

**Status:** PRODUCTION  
**Location:** `bcc/services/backup_service.py`  
**Responsibilities:** Remote `backup-webs` / `backup-dbs` / `backup-all` with run_history steps  
**Note:** Distinct from autonomous cron on VPS

---

## Module: Monitor

**Status:** PRODUCTION  
**Location:** `bcc/services/monitor_service.py`  
**Responsibilities:** Target disk check, `target_disk_slices` (pie: Free + inventory labels from `source_label` folders), source log tails, dashboard snapshot  
**UI:** Dashboard pie, Monitor tab

---

## Module: Browse

**Status:** PRODUCTION  
**Location:** `bcc/services/browse_service.py`, `bcc/ui/files_view.py`  
**Responsibilities:** Remote directory listing; UI must not override Tk `_root`  
**Known issues:** Historical bug fixed: attribute `_root` renamed to `_browse_root`

---

## Module: Notify (email + WA stub)

**Status:** PRODUCTION  
**Location:** `bcc/services/notify_service.py`  
**Responsibilities:** Settings defaults; async SMTP_SSL; WA HTTP if enabled+token  
**Hooked from:** repository CRUD + `add_run_history`  
**Do Not Change:** Failure must never break main actions

---

## Module: Report (daily)

**Status:** PRODUCTION (added build 10 era)  
**Location:** `bcc/services/report_service.py`, dashboard report UI  
**Responsibilities:** Build text report for date; send to `daily_report_to`; once-per-day auto on dashboard refresh  
**Dependencies:** history_for_date, NotifyService.send_email_to  
**Settings:** `daily_report_enabled`, `report_email_last_day`, `daily_report_to`

---

## Module: Backup arrival scan

**Status:** PRODUCTION  
**Location:** `bcc/services/arrival_service.py`, dashboard Scan button  
**Responsibilities:** SSH find archives on backup target; fingerprint state in settings JSON `arrival_scan_state`; baseline then `add_run_history` (`backup_arrival` / `_web` / `_db`); throttle via `arrival_scan_on_refresh` + `arrival_scan_interval_min`  
**Dependencies:** SSHService, Repository, target_password  
**Known Issues:** No FAIL detection without new files; folder must match `source_label`  
**Do Not Change:** First-scan baseline behavior (avoid flooding history with old archives)

---

## Module: Schedule planner

**Status:** PRODUCTION  
**Location:** `bcc/services/schedule_planner.py`, `bcc/ui/schedules_view.py`  
**Responsibilities:** Conflict detection, UI save/push

---

## Module: Tailscale

**Status:** PRODUCTION  
**Location:** `bcc/services/tailscale_service.py`  
**Responsibilities:** CLI detect running/IPv4; helper `is_tailscale_ip`

---

## Module: UI shell

**Status:** PRODUCTION  
**Location:** `bcc/ui/main_window.py`  
**Views:** dashboard, targets, sources, schedules, files, monitor, settings  
**Do Not Change:** CustomTkinter-only policy without ADR

**Process feedback:** `MainWindow.run_async()` serializes long work, deduplicates active/queued job keys, and shows a modal spinner with operation label, elapsed time, and queue length. `post_ui()` is the only worker-to-Tk path; navigation and F5 are disabled until the queue is empty.

---

## Module: Dashboard

**Status:** PRODUCTION  
**Location:** `bcc/ui/dashboard_view.py`, `bcc/ui/pie_chart.py`  
**Responsibilities:** Snapshot tables, disk chart, daily report filters, Webmin open button, auto daily email once per day, **Scan backup masuk** + throttled arrival scan on refresh  
**Webmin:** `webmin_url` or `https://{host}:10000`

---

## Module: Settings UI

**Status:** PRODUCTION  
**Location:** `bcc/ui/settings_view.py`  
**Responsibilities:** Disk threshold, SMTP form/test, WA form/test

---

## Module: Packaging

**Status:** PRODUCTION  
**Location:** `build_exe.py`  
**Responsibilities:** ICO, version info, PyInstaller onefile, desktop shortcut  
**Output:** `dist/BackupControlCenter-{version}-{build}.exe` (gitignored)

---

## Module: Ops scripts (repo root)

**Status:** MIXED (local helpers; many secret scripts gitignored)  
**Examples:** `onboard_vps.py`, `run_full_backup.py`, `seed_existing_servers.example.py`  
**Note:** Live seeds/gitignored — never re-add passwords to git

---

## Module: Remote shell templates

**Status:** PRODUCTION  
**Location:** `bcc/templates/linux/`  
**Files:** backup-*.sh, lib.sh, setup-ssh.sh, config.sh (placeholders)  
**Windows templates:** README only under `templates/windows/` (incomplete/planned path)

---

## Module: Storage management

**Status:** DEVELOPMENT / OPERATIONAL REVIEW
**Location:** `bcc/services/storage_service.py`, `bcc/ui/storage_view.py`
**Responsibilities:** Register remote mount/path, test storage, scan files using an explicit age filter (initially `> 3 hari`), persist/filter candidates, display pending/all statuses with 50-row pagination, select page items, and explicitly move/delete selected items or all filtered pending files.
**Database:** `backup_storages`, `retention_jobs`, `retention_items`
**Safety:** Scan is read-only. Scheduler only scans; move/delete require confirmation. “All” actions affect only visible pending candidates for the selected storage. Existing destination filenames are not overwritten. Cross-server archive is rejected until a transfer implementation exists.
