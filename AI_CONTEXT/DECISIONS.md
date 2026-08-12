# Architecture Decision Records

## ADR-001

**Date:** 2026 (early project)  
**Decision:** BCC is a Windows desktop GUI (CustomTkinter), not a web SaaS.  
**Context:** Single operator needs control center for multi-VPS backups.  
**Chosen solution:** Python + CustomTkinter + local SQLite.  
**Alternatives:** Web dashboard, Qt/PySide only, Electron.  
**Reason:** Fast local shipping, SSH from operator machine, AppData inventory.  
**Impact:** No multi-user concurrent server; AppData machine-bound.  
**Status:** Accepted  

---

## ADR-002

**Date:** 2026  
**Decision:** Backup engines run **on the sources** (cron/scripts); BCC supports/monitor only.  
**Context:** Jobs must survive without operator GUI open.  
**Reason:** Resilience on VPS; BCC can be offline.  
**Impact:** Reports/emails only see history recorded via BCC repository unless observation paths exist. Arrival scan (ADR-010) observes new files on the backup host when BCC runs Scan/refresh; FAIL-without-upload still needs fase 2 log parse.  
**Status:** Accepted  

---

## ADR-003

**Date:** 2026  
**Decision:** Secrets encrypted with machine-local Fernet key in AppData; never in git.  
**Reason:** Public GitHub target (`akenbcc`); password UI convenience without repo secrets.  
**Status:** Accepted  

---

## ADR-004

**Date:** 2026  
**Decision:** Reject PySide6 for main UI after conflict with CustomTkinter packaging; schedules rewritten for CTk.  
**Problem:** Mixed toolkits broke EXE UX.  
**Chosen:** CustomTkinter-only.  
**Status:** Accepted  

---

## ADR-005

**Date:** 2026-08  
**Decision:** Event notifications via `NotifyService` fired from repository after CRUD/`add_run_history` (async, non-failing).  
**Alternatives:** View-layer only sends (easy to miss).  
**Reason:** One door for notify consistency.  
**Impact:** High volume of emails if SMTP enabled and operators churn inventory.  
**Status:** Accepted  

---

## ADR-006

**Date:** 2026-08  
**Decision:** Daily backup report is separate from event notify: `ReportService`, once per local calendar day on dashboard refresh, recipient `daily_report_to` (default `akenprodev@gmail.com`).  
**Reason:** Avoid depending on per-event spam for “daily digests”; still allow manual send for any date.  
**Status:** Accepted  

---

## ADR-007

**Date:** 2026-08  
**Decision:** Disk pie **display** uses inventory `sources.label`; disk math still keys folders by `source_label`.  
**Reason:** Operators recognize VPS/PC titles more than remote folder names.  
**Status:** Accepted  

---

## ADR-008

**Date:** 2026-08  
**Decision:** Optional `webmin_url` on targets; default open `https://{host}:10000`.  
**Reason:** Quick browser access to Webmin without hardcoding UI per host.  
**Status:** Accepted  

---

## ADR-009

**Date:** 2026  
**Decision:** No WhatsApp send until token present (Fonnte-style stub).  
**Reason:** Product wants WA placeholder phone now without gateway commitment.  
**Status:** Accepted  

---

## ADR-010

**Date:** 2026-08-12  
**Decision:** Detect cron backups by **polling the backup server filesystem** (new `*.tar.gz` / `*.sql.gz` under `base_path/{source_label}/webs|dbs`), write aggregated `backup_arrival*` into `run_history`, reuse daily ReportService.  
**Context:** ADR-002 — remotes execute backup; BCC must observe results without becoming the cron.  
**Chosen solution:** `BackupArrivalService` + fingerprint baseline (first scan no flood) + one history row per source per scan.  
**Alternatives:** Parse VPS logs (fase 2); push webhook from scripts (needs always-on endpoint).  
**Impact:** Misses FAIL with zero upload until fase 2; needs BCC scan while app open.  
**Status:** Accepted  
