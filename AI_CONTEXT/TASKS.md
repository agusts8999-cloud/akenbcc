# Tasks

## NOW

- [ ] Keep AI_CONTEXT in sync after each significant feature
- [ ] Operator: smoke-test **Scan backup masuk** on live backup host (baseline then new file)
- [ ] Rebuild EXE if operators use packaged build (arrival not in 0.1.0-10 binary unless rebuilt)
- [ ] Git commit + push when user requests

## NEXT

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

## Task: Backup arrival detection

**Goal:** Detect archives arriving on backup server and include in daily reports  
**Status:** Implemented  
**Files:** `bcc/services/arrival_service.py`, `bcc/ui/dashboard_view.py`, `bcc/services/report_service.py`, AI_CONTEXT updates  
**Acceptance:** Baseline first scan; second scan with new files creates `backup_arrival*`; report shows arrival count; throttle on refresh  
