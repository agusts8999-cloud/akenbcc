"""SQLite schema for BCC inventory."""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backup_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 22,
    username TEXT NOT NULL,
    password_enc TEXT,
    key_path TEXT,
    base_path TEXT NOT NULL DEFAULT '/home/backupuser/backups',
    notes TEXT DEFAULT '',
    last_ssh_ok INTEGER,
    last_ssh_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('linux_vps', 'windows_pc')),
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 22,
    username TEXT NOT NULL,
    password_enc TEXT,
    key_path TEXT,
    target_id INTEGER,
    deploy_path TEXT DEFAULT '/www/backup-scripts',
    web_root TEXT DEFAULT '/www/wwwroot',
    source_label TEXT,
    mysql_user TEXT DEFAULT 'root',
    mysql_password_enc TEXT,
    aapanel INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    last_ssh_ok INTEGER,
    last_ssh_at TEXT,
    last_deploy_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (target_id) REFERENCES backup_targets(id)
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL UNIQUE,
    web_hour INTEGER NOT NULL DEFAULT 2,
    web_minute INTEGER NOT NULL DEFAULT 0,
    db_hour INTEGER NOT NULL DEFAULT 3,
    db_minute INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    estimated_web_minutes INTEGER NOT NULL DEFAULT 60,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS deploy_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    template_version TEXT NOT NULL,
    remote_hash TEXT,
    deployed_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS run_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    run_type TEXT,
    status TEXT,
    message TEXT,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);
"""
