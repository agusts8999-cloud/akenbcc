# Project

## Name

Backup Control Center (BCC) — package `bcc`, product id `BackupControlCenter`.

## Purpose

Desktop control/monitoring app for autonomous remote backup of VPS (aaPanel Linux) and Windows PCs to a central backup host (typically Webmin + `backupuser` over Tailscale/SSH).

## Business Domain

IT operations / infrastructure backup for multi-VPS environments (Akenpro / akenvi-style hosting ops).

## Main Users

- Operators running BCC on Windows
- Admins who manage remote backups without re-SSHing into every box for routine status

## Core Problems

- Inventory of backup targets and source servers
- Deploy/update remote backup scripts and config
- Push aaPanel-compatible cron schedules
- Monitor SSH, disk usage on backup host, action history
- Notify ops via email (and WA stub) when BCC records events
- Daily backup activity report on dashboard + optional auto-email

## Main Features

- Inventory: backup targets + sources (VPS/PC)
- Dashboard: cards, disk pie by source label, tables, conflicts, history, daily report
- Schedules: local edit + remote cron push
- Deploy Linux scripts from templates with placeholders
- Manual backup run (SSH → remote scripts) with `run_history`
- File browser against backup server / web root
- Settings: disk threshold, SMTP, WA placeholder
- Notifications: SMTP SSL async; WA Fonnte-style stub
- Daily report email to configured recipient (default `akenprodev@gmail.com`)
- Webmin open URL per target (button)
- One-file Windows EXE build
- Storage management: register remote mount/path, scan retention candidates, group candidates, archive or permanently delete selected files

## Technology Stack

| Area | Choice |
|------|--------|
| Backend | Python package `bcc` (desktop process, not web API) |
| Frontend | CustomTkinter |
| Database | SQLite (`bcc.db` in AppData) |
| Cache | None |
| Queue | Threading daemon for SSH/email (no Redis) |
| Storage | Remote SSH paths; local AppData for DB/secrets/logs |
| Authentication | SSH passwords/keys; vault key file for encryption |
| Infrastructure | End-user Windows; remotes Linux aaPanel + Webmin backup host |
| Networking | Tailscale CGNAT IPs often used for mesh SSH |
| Build | PyInstaller onefile |

## Repository Structure

```text
backup/                    # workspace root
├── AGENTS.md
├── AI_CONTEXT/            # AI project knowledge
├── README.md
├── requirements.txt
├── build_exe.py           # PyInstaller + desktop shortcut
├── run_bcc.py
├── bcc/                   # main application package
│   ├── __init__.py        # version + build
│   ├── app.py             # logging + MainWindow
│   ├── paths.py           # AppData, templates, freeze paths
│   ├── db/                # schema + repository
│   ├── services/          # SSH, deploy, backup, notify, report, …
│   ├── ui/                # CTk views
│   ├── templates/linux/   # remote scripts (placeholders)
│   └── assets/            # logo.png / logo.ico
├── seed_existing_servers.example.py
├── onboard_vps.py, run_full_backup.py   # ops helpers (local)
├── dist/                  # EXE output (gitignored)
└── shell scripts at root  # historical/local deploy artifacts (gitignore patterns for secrets)
```

## Important URLs

| What | Where |
|------|--------|
| Git origin | https://github.com/agusts8999-cloud/akenbcc.git |
| SMTP (default) | `mail.akenvi.com:465` (settings, not hardcoded password) |
| Local DB | `%AppData%\BackupControlCenter\bcc.db` |
| Daily report default To | `akenprodev@gmail.com` (`settings.daily_report_to`) |

Live host IPs are inventory data (user AppData), not guaranteed in git.

## Deployment

1. Dev: `pip install -r requirements.txt` → `python -m bcc`
2. EXE: bump `__build__` → `python build_exe.py` → `dist/BackupControlCenter-{version}-{build}.exe`
3. Remote scripts: Deploy from GUI or `bcc/templates/linux/` to `/www/backup-scripts` on sources
4. Cron: push via Schedules / DeployService aaPanel job names

## Important Constraints

- Secrets never in git; public repo assumed.
- BCC GUI must not block on SSH/email for long periods (use threads).
- Cron on VPS **without** BCC API hooks does not auto-email.
- Preserve CustomTkinter-only UI.
- Soft-delete inventory; prefer migrations over destructive schema resets.
- Retention scans are non-destructive; archive/delete require explicit selected items and confirmation.
- The local scheduler runs while BCC is open; it scans due policies but never performs automatic destructive actions.
