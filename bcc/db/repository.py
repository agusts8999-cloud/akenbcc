"""SQLite repository."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Iterable, Optional

from bcc.db.schema import SCHEMA_SQL
from bcc.paths import db_path
from bcc.services.secrets import SecretBox


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Repository:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = str(path or db_path())
        self.secrets = SecretBox()

    def initialize(self) -> None:
        from pathlib import Path

        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate(conn)
            conn.commit()
        try:
            from bcc.services.notify_service import NotifyService

            NotifyService(self).ensure_defaults()
        except Exception:
            pass

    def _fire_notify(
        self,
        event: str,
        status: str,
        subject: str,
        body: str,
        source_id: Optional[int] = None,
    ) -> None:
        """Async notify; never raise into CRUD callers."""
        try:
            from bcc.services.notify_service import NotifyService

            NotifyService(self).notify(
                event=event,
                status=status,
                subject=subject,
                body=body,
                source_id=source_id,
            )
        except Exception:
            pass

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Idempotent column adds for existing DBs."""
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(backup_targets)").fetchall()
        }
        if "last_ssh_ok" not in cols:
            conn.execute("ALTER TABLE backup_targets ADD COLUMN last_ssh_ok INTEGER")
        if "last_ssh_at" not in cols:
            conn.execute("ALTER TABLE backup_targets ADD COLUMN last_ssh_at TEXT")
        if "webmin_url" not in cols:
            conn.execute(
                "ALTER TABLE backup_targets ADD COLUMN webmin_url TEXT DEFAULT ''"
            )

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- settings ---
    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    # --- targets ---
    def list_targets(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backup_targets WHERE deleted=0 ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_target(self, target_id: int) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM backup_targets WHERE id=? AND deleted=0", (target_id,)
            ).fetchone()
            return dict(row) if row else None

    def add_target(
        self,
        label: str,
        host: str,
        username: str,
        base_path: str,
        port: int = 22,
        password: str = "",
        key_path: str = "",
        notes: str = "",
        webmin_url: str = "",
    ) -> int:
        now = _now()
        pwd = self.secrets.encrypt(password) if password else ""
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO backup_targets
                (label,host,port,username,password_enc,key_path,base_path,webmin_url,notes,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    label,
                    host,
                    port,
                    username,
                    pwd,
                    key_path,
                    base_path,
                    webmin_url or "",
                    notes,
                    now,
                    now,
                ),
            )
            tid = int(cur.lastrowid)
        self._fire_notify(
            "target_add",
            "ok",
            f"BCC: target ditambah — {label}",
            f"Target id={tid} label={label} host={host} path={base_path}",
        )
        return tid

    def update_target(self, target_id: int, **fields: Any) -> None:
        if not fields:
            return
        if "password" in fields:
            pw = fields.pop("password")
            fields["password_enc"] = self.secrets.encrypt(pw) if pw else ""
        fields["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [target_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE backup_targets SET {cols} WHERE id=?", vals)
        keys = ", ".join(k for k in fields if k != "updated_at")
        self._fire_notify(
            "target_update",
            "ok",
            f"BCC: target diubah — id {target_id}",
            f"Target id={target_id} fields: {keys or '-'}",
        )

    def soft_delete_target(self, target_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE backup_targets SET deleted=1, updated_at=? WHERE id=?",
                (_now(), target_id),
            )
        self._fire_notify(
            "target_delete",
            "ok",
            f"BCC: target dihapus — id {target_id}",
            f"Target id={target_id} soft-deleted",
        )

    def target_password(self, target: dict[str, Any]) -> str:
        return self.secrets.decrypt(target.get("password_enc") or "")

    def list_targets_overview(self) -> list[dict[str, Any]]:
        """Backup targets with linked source count (no secrets)."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT t.id, t.label, t.host, t.port, t.username, t.base_path,
                       t.webmin_url, t.notes, t.last_ssh_ok, t.last_ssh_at,
                       (SELECT COUNT(*) FROM sources s
                        WHERE s.target_id = t.id AND s.deleted = 0) AS source_count
                FROM backup_targets t
                WHERE t.deleted = 0
                ORDER BY t.id
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def list_sources_overview(self) -> list[dict[str, Any]]:
        """Sources with target label, schedule, last history (no secrets)."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.label, s.role, s.host, s.port, s.username,
                       s.source_label, s.aapanel, s.notes,
                       s.last_ssh_ok, s.last_ssh_at, s.last_deploy_at,
                       t.label AS target_label, t.host AS target_host,
                       sch.web_hour, sch.web_minute, sch.db_hour, sch.db_minute,
                       sch.enabled AS schedule_enabled,
                       h.run_type AS last_run_type,
                       h.status AS last_run_status,
                       h.recorded_at AS last_run_at
                FROM sources s
                LEFT JOIN backup_targets t ON t.id = s.target_id AND t.deleted = 0
                LEFT JOIN schedules sch ON sch.source_id = s.id
                LEFT JOIN run_history h ON h.id = (
                    SELECT h2.id FROM run_history h2
                    WHERE h2.source_id = s.id
                    ORDER BY h2.id DESC LIMIT 1
                )
                WHERE s.deleted = 0
                ORDER BY s.id
                """
            ).fetchall()
            return [dict(r) for r in rows]

    # --- sources ---
    def list_sources(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sources WHERE deleted=0 ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_source(self, source_id: int) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE id=? AND deleted=0", (source_id,)
            ).fetchone()
            return dict(row) if row else None

    def add_source(
        self,
        label: str,
        role: str,
        host: str,
        username: str,
        target_id: Optional[int] = None,
        port: int = 22,
        password: str = "",
        key_path: str = "",
        deploy_path: str = "/www/backup-scripts",
        web_root: str = "/www/wwwroot",
        source_label: str = "",
        mysql_user: str = "root",
        mysql_password: str = "",
        aapanel: bool = True,
        notes: str = "",
    ) -> int:
        now = _now()
        pwd = self.secrets.encrypt(password) if password else ""
        mpwd = self.secrets.encrypt(mysql_password) if mysql_password else ""
        if not source_label:
            source_label = f"aapanel-{host}" if role == "linux_vps" else f"windows-{host}"
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO sources
                (label,role,host,port,username,password_enc,key_path,target_id,deploy_path,web_root,
                 source_label,mysql_user,mysql_password_enc,aapanel,notes,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    label,
                    role,
                    host,
                    port,
                    username,
                    pwd,
                    key_path,
                    target_id,
                    deploy_path,
                    web_root,
                    source_label,
                    mysql_user,
                    mpwd,
                    1 if aapanel else 0,
                    notes,
                    now,
                    now,
                ),
            )
            sid = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO schedules (source_id,web_hour,web_minute,db_hour,db_minute,enabled,estimated_web_minutes,updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (sid, 2, 0, 3, 0, 1, 60, now),
            )
        self._fire_notify(
            "source_add",
            "ok",
            f"BCC: sumber ditambah — {label}",
            f"Source id={sid} label={label} host={host} role={role}",
            source_id=sid,
        )
        return sid

    def update_source(self, source_id: int, **fields: Any) -> None:
        if not fields:
            return
        if "password" in fields:
            pw = fields.pop("password")
            fields["password_enc"] = self.secrets.encrypt(pw) if pw is not None else ""
        if "mysql_password" in fields:
            mp = fields.pop("mysql_password")
            fields["mysql_password_enc"] = self.secrets.encrypt(mp) if mp else ""
        if "aapanel" in fields:
            fields["aapanel"] = 1 if fields["aapanel"] else 0
        fields["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [source_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE sources SET {cols} WHERE id=?", vals)
        # Soft-delete uses dedicated event via soft_delete_source
        if fields.get("deleted") == 1 or set(fields.keys()) <= {"deleted", "updated_at"}:
            if fields.get("deleted") == 1:
                return
        keys = ", ".join(k for k in fields if k != "updated_at")
        self._fire_notify(
            "source_update",
            "ok",
            f"BCC: sumber diubah — id {source_id}",
            f"Source id={source_id} fields: {keys or '-'}",
            source_id=source_id,
        )

    def soft_delete_source(self, source_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE sources SET deleted=1, updated_at=? WHERE id=?",
                (_now(), source_id),
            )
        self._fire_notify(
            "source_delete",
            "ok",
            f"BCC: sumber dihapus — id {source_id}",
            f"Source id={source_id} soft-deleted",
            source_id=source_id,
        )

    def source_password(self, source: dict[str, Any]) -> str:
        return self.secrets.decrypt(source.get("password_enc") or "")

    def source_mysql_password(self, source: dict[str, Any]) -> str:
        return self.secrets.decrypt(source.get("mysql_password_enc") or "")

    # --- schedules ---
    def get_schedule(self, source_id: int) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM schedules WHERE source_id=?", (source_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_schedules_joined(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id AS source_id, s.label, s.host, s.role,
                       sch.web_hour, sch.web_minute, sch.db_hour, sch.db_minute,
                       sch.enabled, sch.estimated_web_minutes
                FROM sources s
                JOIN schedules sch ON sch.source_id = s.id
                WHERE s.deleted=0
                ORDER BY sch.web_hour, sch.web_minute
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def update_schedule(
        self,
        source_id: int,
        web_hour: int,
        web_minute: int,
        db_hour: int,
        db_minute: int,
        enabled: int = 1,
        estimated_web_minutes: int = 60,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE schedules SET web_hour=?,web_minute=?,db_hour=?,db_minute=?,
                enabled=?,estimated_web_minutes=?,updated_at=? WHERE source_id=?""",
                (
                    web_hour,
                    web_minute,
                    db_hour,
                    db_minute,
                    enabled,
                    estimated_web_minutes,
                    _now(),
                    source_id,
                ),
            )
        self._fire_notify(
            "schedule_update",
            "ok",
            f"BCC: jadwal diubah — source {source_id}",
            (
                f"Source id={source_id} "
                f"web={web_hour:02d}:{web_minute:02d} "
                f"db={db_hour:02d}:{db_minute:02d} "
                f"enabled={enabled} est_web_min={estimated_web_minutes}"
            ),
            source_id=source_id,
        )

    def add_run_history(
        self, source_id: int, run_type: str, status: str, message: str
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO run_history(source_id,run_type,status,message,recorded_at)
                VALUES (?,?,?,?,?)""",
                (source_id, run_type, status, message, _now()),
            )
        label = ""
        try:
            src = self.get_source(source_id) if source_id else None
            if src:
                label = src.get("label") or ""
        except Exception:
            pass
        subj = f"BCC [{status}] {run_type}"
        if label:
            subj += f" — {label}"
        self._fire_notify(
            "run_history",
            status or "info",
            subj,
            f"run_type={run_type}\nstatus={status}\nsource_id={source_id}\n{message or ''}",
            source_id=source_id if source_id else None,
        )

    def recent_history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT h.*, s.label FROM run_history h
                LEFT JOIN sources s ON s.id=h.source_id
                ORDER BY h.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def history_for_date(
        self, day: str, backup_only: bool = True
    ) -> list[dict[str, Any]]:
        """Activity rows for calendar day YYYY-MM-DD (matches recorded_at prefix)."""
        day = (day or "").strip()[:10]
        if len(day) != 10:
            return []
        prefix = f"{day}%"
        with self.connect() as conn:
            if backup_only:
                rows = conn.execute(
                    """SELECT h.*, s.label FROM run_history h
                    LEFT JOIN sources s ON s.id=h.source_id
                    WHERE h.recorded_at LIKE ?
                      AND h.run_type LIKE 'backup%'
                    ORDER BY h.id ASC""",
                    (prefix,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT h.*, s.label FROM run_history h
                    LEFT JOIN sources s ON s.id=h.source_id
                    WHERE h.recorded_at LIKE ?
                    ORDER BY h.id ASC""",
                    (prefix,),
                ).fetchall()
            return [dict(r) for r in rows]

    def set_deploy_revision(self, source_id: int, version: str, remote_hash: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO deploy_revisions(source_id,template_version,remote_hash,deployed_at)
                VALUES (?,?,?,?)""",
                (source_id, version, remote_hash, _now()),
            )
