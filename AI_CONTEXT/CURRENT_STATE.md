# Current State

**Last Updated:** 2026-08-18

## Overall Status

Functional Windows desktop BCC for inventory, deploy, schedules, backup trigger, files browse, disk pie, SMTP notifications, daily report UI, Webmin button, backup arrival scan, and Storage/Retention management. Source and packaged build **0.1.3-16** include the serialized background-work queue, modal busy overlay, and pagination responsiveness fixes.

Remote/real inventory lives in operator AppData (not in git).

## Working

- CustomTkinter app bootstrap + multi-tab UI
- SQLite inventory + soft delete
- Secret encryption (SecretBox)
- Deploy Linux templates + aaPanel schedule push pattern
- Manual full backup with run_history steps
- Dashboard tables, schedule conflict box, history
- Disk pie chart with inventory labels
- NotifyService SMTP SSL + WA stub
- Settings SMTP/WA UI + tests
- ReportService daily text + email + dashboard controls
- Webmin URL field + Buka button
- **BackupArrivalService**: SSH scan `base_path/{source_label}/webs|dbs` for new `*.tar.gz`/`*.sql.gz`; baseline then aggregate `backup_arrival*` into history; dashboard button + throttled refresh scan
- PyInstaller build pipeline + desktop shortcut
- Storage tab: register remote mount/path, retention scan (default 3 days), candidate grouping, explicit archive/delete, and scan-only local scheduler
- Retention result controls: show pending/all statuses, select/clear the current page, move/delete selected items, and move/delete all filtered pending candidates with confirmation
- Storage scan age filter uses explicit choices (`> 1`, `> 2`, `> 3`, `> 7`, `> 14`, `> 30` days), defaults to `> 3 hari`, and also filters the visible/actionable results
- Thread-safe worker-to-UI dispatcher; workers no longer call Tk APIs directly
- Serialized/deduplicated long-operation queue with a modal loader that disables navigation and displays elapsed/queued work
- Retention results paginate at 50 rows and file browser results at 100 rows
- Dashboard Tailscale check is asynchronous and cached for 60 seconds
- Manual F5 refreshes only the visible tab instead of triggering hidden-tab work

## In Progress

- Storage retention feature needs operator validation against a test path; cross-server archive is not implemented.

## Broken

- None verified open bugs in docs (re-verify if EXE/user reports)

## Known Bugs / pitfalls

- Arrival scan sees **files on backup host**, not VPS cron FAIL without upload (fase 2: parse source logs — not done)
- First scan per source/kind is **baseline only** (no flood of old archives)
- Detection only while BCC runs scan (button / refresh throttle ~15 min)
- Daily auto-email only when GUI opens/refreshes dashboard and SMTP password is configured
- Tk: never set widget attribute `_root` (historical files_view crash)
- Git public: must not commit live credentials
- Retention scheduler does not run when the GUI is closed and never auto-deletes/archives.
- Build 16 / version 0.1.3 was packaged with Python 3.13 and passed a 10-second isolated-AppData EXE smoke test.

## Technical Debt

- No automated test suite (arrival has local helper smoke only)
- Root-level ops scripts partially gitignored
- Windows-PC backup path incomplete vs Linux templates
- Event email volume can be high with inventory thrash / arrivals if notify enabled

## Recently Changed

- Replaced unsafe worker `after()` calls with a main-thread dispatcher
- Serialized long operations, added duplicate-job protection, and replaced the sidebar-only indicator with a modal loader
- Added retention/file pagination and visible-tab-only refresh
- Bulk retention actions and all-status result display (`storage_view.py`)
- Backup arrival detection → laporan (`arrival_service.py`, dashboard Scan, report summary)
- Notify, pie labels, daily report, Webmin, AI_CONTEXT, build 10

## Blockers

- SMTP password must be set by operator before emails work
- Tailscale/network access required for live SSH checks / arrival scan

## Next Recommended Actions

1. Commit/push uncommitted work (arrival + prior features + AI_CONTEXT) if user wants
2. Distribute `BackupControlCenter-0.1.3-16.exe` after operator validation
3. Smoke-test Scan backup masuk against live backup host
4. Optional fase 2: parse VPS backup logs for FAIL without files
5. Validate Storage tab on a safe test directory, then consider cross-server archive.

## Documentation Drift

- Found: the repository had the core AI_CONTEXT files but no central `INDEX.md` or agent protocol subdirectory.
- Verified against: repository tree and `AGENTS.md`.
- Resolution: added the context router, onboarding/workflow/handoff protocol, and scalable context directory READMEs on 2026-08-17.
