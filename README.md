# Backup Control Center & skrip backup remote

## GUI (dev)

```powershell
cd d:\development\backup
pip install -r requirements.txt
python -m bcc
```

## Build EXE

```powershell
pip install pyinstaller pillow
python build_exe.py
# → dist\BackupControlCenter-{version}-{build}.exe
# + shortcut Desktop (logo icon)
```

Bump versi/build di [`bcc/__init__.py`](bcc/__init__.py).

Dokumentasi: [bcc/README.md](bcc/README.md)

## Skrip shell standalone

Template di `bcc/templates/linux/` — deploy ke aaPanel `/www/backup-scripts` (langsung atau lewat GUI **Deploy Linux**).

## Git & secrets

- Password nyata **tidak di-commit** (lihat `.gitignore`): `/config.sh`, `/seed_existing_servers.py`, dll.
- Contoh seed: `seed_existing_servers.example.py`
- Inventori BCC: `%AppData%\BackupControlCenter\` (di luar repo)
- Template `bcc/templates/linux/config.sh` memakai placeholder `{{...}}` (diisi saat Deploy)
- **Jangan** push secret ke GitHub public
