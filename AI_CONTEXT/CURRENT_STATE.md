# Current State

**Last Updated:** 2026-08-12  

## Overall Status

Functional Windows desktop BCC for inventory, deploy, schedules, backup trigger, files browse, disk pie, SMTP notifications, daily report UI, Webmin button, and **backup arrival scan** (detect new archives on backup host → `run_history`). Packaged build **0.1.0-11**.

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

## In Progress

- None formal in repo (see TASKS.md)

## Broken

- None verified open bugs in docs (re-verify if EXE/user reports)

## Known Bugs / pitfalls

- Arrival scan sees **files on backup host**, not VPS cron FAIL without upload (fase 2: parse source logs — not done)
- First scan per source/kind is **baseline only** (no flood of old archives)
- Detection only while BCC runs scan (button / refresh throttle ~15 min)
- Daily auto-email only when GUI opens/refreshes dashboard and SMTP password is configured
- Tk: never set widget attribute `_root` (historical files_view crash)
- Git public: must not commit live credentials

## Technical Debt

- No automated test suite (arrival has local helper smoke only)
- Root-level ops scripts partially gitignored
- Windows-PC backup path incomplete vs Linux templates
- Event email volume can be high with inventory thrash / arrivals if notify enabled

## Recently Changed

- Backup arrival detection → laporan (`arrival_service.py`, dashboard Scan, report summary)
- Notify, pie labels, daily report, Webmin, AI_CONTEXT, build 10

## Blockers

- SMTP password must be set by operator before emails work
- Tailscale/network access required for live SSH checks / arrival scan

## Next Recommended Actions

1. Commit/push uncommitted work (arrival + prior features + AI_CONTEXT) if user wants
2. Rebuild EXE after arrival feature for operators on packaged build
3. Smoke-test Scan backup masuk against live backup host
4. Optional fase 2: parse VPS backup logs for FAIL without files
