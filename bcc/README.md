# Backup Control Center (BCC)

Desktop **support & monitoring** untuk backup mandiri VPS (Linux/aaPanel) dan PC Windows ke server backup (mis. Webmin) via SSH/Tailscale.

Backup **tetap berjalan tanpa app ini dibuka** (cron / Task Scheduler di sumber).

## Versi & build

Edit hanya [`bcc/__init__.py`](../bcc/__init__.py):

```python
__version__ = "0.1.0"  # major.minor.patch
__build__ = 1          # naik tiap package
```

- Full string: `0.1.0-1`
- EXE: `BackupControlCenter-0.1.0-1.exe`

## Seed server yang sudah di-backup

```powershell
cd d:\development\backup
python seed_existing_servers.py
```

Mengisi inventori (idempotent): Server Backup `100.110.117.36` + VPS aaPanel `100.116.75.123` (jadwal web 02:00 / DB 03:00).

## Install (dev)

```powershell
cd d:\development\backup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m bcc
```

Judul window: `Backup Control Center 0.1.0-1` — logo di sidebar & icon taskbar.

## Build EXE + shortcut

```powershell
cd d:\development\backup
pip install -r requirements.txt pyinstaller
python build_exe.py
```

Hasil:

- `dist\BackupControlCenter-0.1.0-1.exe` (icon = `bcc/assets/logo.ico`)
- Shortcut desktop **Backup Control Center** (icon logo)
- `dist\logo.ico` (salinan untuk shortcut)

## Fitur (MVP)

1. Inventori server backup + sumber (SQLite terenkripsi password)
2. Cek Tailscale (CLI lokal) & badge IP `100.x`
3. Test SSH, deploy script Linux, setup trust key, daftar cron/aaPanel
4. Export paket Windows (PowerShell + Task Scheduler)
5. Planner jadwal + push cron ke aaPanel (per VPS / massal)
6. Monitor disk tujuan & log sumber

### Jadwal → cron aaPanel

Tab **Jadwal** menyimpan jam web/DB di SQLite, lalu bisa push ke server:

| Aksi | Efek |
|------|------|
| **Simpan lokal** | Hanya DB BCC |
| **Simpan + push** / **Push aaPanel** | Daftarkan Plan Task di aaPanel (atau root crontab jika non-aaPanel) |
| **Push semua ke aaPanel** | Semua sumber `linux_vps` |
| **Auto-stagger + push** | Rentang 90 menit antar VPS, simpan, push semua |
| Checkbox **Auto-push setelah simpan** | Setelah Simpan lokal, push otomatis untuk sumber `aapanel` |

Nama job di panel: `BCC Web Remote · {label}` / `BCC DB Remote · {label}` (hapus job lama dengan nama fixed agar tidak dobel). Riwayat: type `cron_push` di Dashboard.

## Alur tipikal

1. **Server Backup** — tambah host / `backupuser`
2. **Sumber** — tambah VPS, link ke target, isi MySQL password
3. **Deploy Linux** — upload template + setup-ssh + cron aaPanel
4. **Jadwal** — atur jam, **Simpan + push** atau **Push semua ke aaPanel**
5. **Monitor** — disk & log
6. Tutup app — backup harian tetap jalan

## Branding

- Logo: `bcc/assets/logo.png` / `logo.ico`
- Digunakan sebagai: window icon, sidebar, icon EXE, shortcut desktop

## Data lokal

- Windows: `%AppData%\BackupControlCenter\bcc.db`
- Log: `%AppData%\BackupControlCenter\bcc.log`

## Keamanan

Password disimpan terenkripsi (Fernet + key lokal). Jangan commit `bcc.db` / vault key.
