# Tasks

## NOW

- [ ] Keep AI_CONTEXT in sync after each significant feature
- [ ] Operator: register a storage mount and validate scan against a non-production/test directory
- [ ] Operator: review retention candidates before enabling archive/delete workflow
- [ ] Operator: smoke-test **Scan backup masuk** on live backup host (baseline then new file)
- [ ] Git commit + push when user requests

## NEXT

- [ ] Add cross-server archive transfer with resumable copy and checksum verification
- [ ] Add explicit editing/persistence for retention group metadata before an action
- [ ] Fase 2: parse VPS `backup-all_*.log` for FAIL without upload
- [ ] Optional notify volume filters
- [ ] Minimal unit tests for arrival fingerprint + ReportService

## BLOCKED

- [ ] Live full mesh verification without Tailscale/operator network

## DONE

- [x] CustomTkinter BCC shell + inventory CRUD
- [x] Deploy templates + schedule push patterns
- [x] Backup service run_history
- [x] Disk pie + inventory labels
- [x] NotifyService SMTP + WA stub + settings
- [x] Daily report UI + auto email once/day
- [x] Webmin URL + open button
- [x] Package EXE through build 10
- [x] Establish AI_CONTEXT + AGENTS.md protocol
- [x] Backup arrival scan → run_history → laporan (ADR-010)
- [x] Add agent-independent context index and onboarding/workflow/handoff protocol
- [x] Add bulk retention controls: show/select/move/delete all visible pending candidates
- [x] Add explicit `> 3 hari` scan filter and remove ambiguous visible `default` labels
- [x] Replace worker Tk calls with a thread-safe main-thread dispatcher
- [x] Serialize/deduplicate long operations and lock navigation with a modal loader
- [x] Paginate retention results (50/page) and file browser results (100/page)
- [x] Move Tailscale checks off the Tk thread and cache status for 60 seconds
- [x] Build `BackupControlCenter-0.1.3-16.exe` with the responsiveness fixes

## Task: Backup arrival detection

**Goal:** Detect archives arriving on backup server and include in daily reports  
**Status:** Implemented  
**Files:** `bcc/services/arrival_service.py`, `bcc/ui/dashboard_view.py`, `bcc/services/report_service.py`, AI_CONTEXT updates  
**Acceptance:** Baseline first scan; second scan with new files creates `backup_arrival*`; report shows arrival count; throttle on refresh  
