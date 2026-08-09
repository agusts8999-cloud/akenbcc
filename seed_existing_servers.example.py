# Example seed — copy to seed_existing_servers.py and fill real values (gitignored).
# DO NOT put production passwords in committed files.

BACKUP_TARGET = {
    "label": "Webmin Backup Server",
    "host": "100.x.x.x",
    "port": 22,
    "username": "backupuser",
    "password": "CHANGE_ME",
    "base_path": "/home/backupuser/backups",
    "notes": "Server tujuan backup",
}

VPS_SOURCES = [
    {
        "label": "aaPanel VPS example",
        "role": "linux_vps",
        "host": "100.x.x.x",
        "port": 22,
        "username": "root",
        "password": "CHANGE_ME",
        "deploy_path": "/www/backup-scripts",
        "web_root": "/www/wwwroot",
        "source_label": "aapanel-100.x.x.x",
        "mysql_user": "root",
        "mysql_password": "CHANGE_ME",
        "aapanel": True,
        "notes": "",
        "web_hour": 2,
        "web_minute": 0,
        "db_hour": 3,
        "db_minute": 0,
        "estimated_web_minutes": 60,
    },
]
