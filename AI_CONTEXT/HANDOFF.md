# AI Agent Handoff

## Last Agent

Cursor

## Date

2026-10-02

## Task

Split OMV access: LAN for BCC, Tailscale plus keepalive for VPS, package build 19.

## Completed

- Added `AI_CONTEXT/INDEX.md` and progressive context routing.
- Added `AI_CONTEXT/agents/{README,onboarding,workflow,handoff}.md`.
- Added scalable README entry points under `modules/`, `architecture/`, and `database/`.
- Updated `AGENTS.md` to make `INDEX.md` mandatory after the entry file.
- Recorded documentation drift resolution in `CURRENT_STATE.md`.
- Added remote storage registration, retention scan, candidate grouping, and explicit archive/delete UI.
- Added scan-only retention scheduler while BCC is running.
- Added idempotent schema/repository support for storage policies and candidate state.
- Added show-all/pending toggle, select all, clear selection, move all, and delete all controls.
- Bulk actions affect visible pending candidates only and require confirmation.
- Move refuses to overwrite an existing destination filename.
- Added explicit scan-age choices with `> 3 hari` initially selected; the same threshold filters displayed and bulk-action candidates.
- Removed ambiguous visible `default` wording and migrated legacy archive group metadata to `arsip`.
- Added global process spinner and `MainWindow.run_async()` wrapper for long-running UI operations.
- Routed long-running work across dashboard, files, monitor, settings, targets, sources, schedules, storage, and storage scheduler through the wrapper.
- Replaced every worker-thread widget `.after()` call with `MainWindow.post_ui()`, backed by a thread-safe queue polled only by Tk's main thread.
- Changed `run_async()` from concurrent execution to a serialized FIFO queue with duplicate job-key suppression.
- Added a full-window modal loader with operation label, elapsed seconds, queued-work count, and disabled navigation/F5.
- Changed startup/manual refresh to refresh only the visible view; hidden tabs no longer trigger remote work.
- Moved Tailscale CLI status off the Tk thread and added a 60-second cache.
- Added retention pagination (50 rows/page) and file browser pagination (100 rows/page).
- “Move/delete all” retention actions now cover all pending candidates in the current filter, not just the rendered page.
- Scheduled retention polling opens the loader only when at least one job is due and deduplicates the scheduled scan key.

## Changed Files

- `AGENTS.md`
- `AI_CONTEXT/INDEX.md`
- `AI_CONTEXT/agents/*`
- `AI_CONTEXT/modules/README.md`
- `AI_CONTEXT/architecture/README.md`
- `AI_CONTEXT/database/README.md`
- `AI_CONTEXT/CURRENT_STATE.md`, `CHANGELOG.md`, `TASKS.md`, `HANDOFF.md`
- `bcc/db/schema.py`, `bcc/db/repository.py`
- `bcc/services/storage_service.py`, `bcc/ui/storage_view.py`, `bcc/ui/main_window.py`, `bcc/app.py`
- Responsiveness pass also changed `bcc/ui/{dashboard,files,monitor,schedules,settings,sources,targets}_view.py`.

## Database Changes

Added `backup_storages`, `retention_jobs`, and `retention_items`. Existing databases are upgraded idempotently; no existing tables are dropped.

## Configuration Changes

Storage policy defaults to 3 days, review mode, and 24-hour interval. Scheduler is disabled until explicitly enabled per storage.

## Tests

Python 3.12 `compileall` passed. Static audit found no remaining view-level `self.after()` calls. An isolated-AppData GUI startup smoke ran for 10 seconds without worker/Tk exceptions. Temporary SQLite smoke tests previously verified pending/all-status queries and migration from `group_key=default` to `arsip`; fake SSH previously verified two-item bulk move and no-overwrite commands. Live SSH actions were not run because no safe remote test storage was provided.

Python 3.13.15 is installed at `%LOCALAPPDATA%\Programs\Python\Python313`. Requirements and PyInstaller were installed there.

Latest package is `dist/BackupControlCenter-0.1.3-17.exe` (about 25 MB), built with Python 3.13.15. Desktop shortcut was recreated after the shortcut script description was changed to ASCII. A 10-second isolated-AppData EXE smoke stayed running, then the process was stopped. Live inventory was not used for that smoke.

AppData target id 1 was updated in place: label `OMV NAS`, host `100.107.205.80`, user `aken`, base path `/srv/dev-disk-by-uuid-B004D6B804D68130/NAS/backups`, panel URL `http://100.107.205.80`. Storage id 1 `OMV NAS backups` is review-only. SSH mkdir confirmed `webs`, `dbs`, and `logs` on the 954G NTFS disk. Password round-trip through SecretBox succeeded. Later the same day, four VPS rows were restored from the local seed and linked to this target.

## Known Issues

- First scan per source/kind is baseline (expected empty history)
- Cron FAIL without files still invisible
- Packaged EXE 0.1.0-10 may predate this feature until rebuild
- Cross-server archive is intentionally rejected; only same-target storage archive is implemented
- Real high-volume retention pagination still needs operator validation with the AppData inventory.

## Not Completed

- Commit/push (await user)
- Fase 2 VPS log parse

## Important Discoveries

- Remote layout expected: `{base_path}/{source_label}/webs|dbs/*.(tar.gz|sql.gz)`
- Aggregate one history row per source per scan to limit notify/email spam

## Next Agent Should

1. Build 19 is the current package: `dist/BackupControlCenter-0.1.3-19.exe`. Desktop shortcut points at that EXE. BCC tries OMV LAN `192.168.0.110` first (3s), then Tailscale `100.107.205.80`.
2. Keepalive redeploy of all four VPS succeeded on 2026-10-02. On `46.250.233.39`, `REMOTE_HOST` is still `100.107.205.80` and `SSH_OPTS` includes `ServerAliveInterval=15`. Do not point VPS `REMOTE_HOST` at the LAN address.
3. Build 18 behavior remains: scripts append logs, manual full backup starts detached `backup-all.sh`, source `46.250.233.39` has `alt_host` `100.121.63.114`. Do not start a manual backup while cron holds `.lock-webs` or `.lock-dbs`.
4. Do not store backups on `/` or `/home/aken` (28G OS disk). Do not use `/srv/nas` — that directory is on the OS disk.
5. Panel URL on the target is `http://100.107.205.80`. The button label still says Webmin.
6. Do not enable destructive retention workflows without operator review.

## OMV destination (verified 2026-10-02)

SSH as `aken` to Tailscale `100.107.205.80` succeeded. Host `raspberrypi-nas`, Debian 13, OpenMediaVault 8.5.9, `rsync` present, password and pubkey SSH enabled. Data disk `/dev/sda1` is NTFS (`fuseblk`), about 954G free, mounted at `/srv/dev-disk-by-uuid-B004D6B804D68130`. Folder `NAS` exists there and user `aken` can create files. Password stays out of this file.

## Warnings

- Public repo: no secrets
- Arrival scan uses target SSH credentials from AppData
- Packaged EXE `0.1.3-16` includes this responsiveness pass.
