# Conventions

Prefer **existing** patterns in this repo over new styles.

## Naming

| Kind | Convention |
|------|------------|
| Modules | `snake_case.py` |
| Classes | `PascalCase` (`NotifyService`, `DashboardView`) |
| Methods | `snake_case` |
| Settings keys | `snake_case` strings |
| Encrypted setting values | suffix `_enc` in settings or column `*_enc` |
| Soft delete | integer `deleted` 0/1 |

## Folder layout

- UI only under `bcc/ui/`
- Domain under `bcc/services/`
- Persistence only under `bcc/db/`
- Do not dump one-off business logic into views if a service already owns it

## UI

- CustomTkinter only
- Long network: `threading.Thread` + `self.after(0, …)` to update UI
- Tables: CTk grids/labels where used on dashboard
- **Forbidden:** instance attribute named `_root` on widgets (Tk conflict)
- Primary language for labels: Indonesian (existing screens)

## Database

- All writes through `Repository`
- After successful inventory/history changes: optional `_fire_notify` (lazy import NotifyService)
- Timestamps via `_now()` UTC-like string `"%Y-%m-%d %H:%M:%S"`
- Schema change = update `schema.py` for new installs + `_migrate` for existing AppData DBs

## Services

- Constructor takes `Repository` when needing DB
- Fail soft for notify/report; log with `logging.getLogger(__name__)`
- SSH results: follow existing OK/fail message patterns

## Secrets

- Encrypt before persist; decrypt only at use site
- Never commit `config.sh`, live seeds, vault keys, SMTP passwords
- Public GitHub: assume adversarial readers

## Git

- Commits only when user asks
- Do not force-push main / skip hooks unless user insists
- Secret files stay gitignored
- Commit messages: concise, why-focused English (existing repo style)

## Version / build

- Source: `bcc/__init__.py` `__version__` and `__build__`
- EXE name: `BackupControlCenter-{version}-{build}.exe`
- Increment `__build__` on each release pack

## Testing

- No large automated suite yet — smoke via `python -m bcc` / manual tabs
- Add tests only if project introduces a consistent test harness later

## Dependencies

- Prefer stdlib for email (`smtplib`)
- Avoid new deps without ADR + user buy-in
