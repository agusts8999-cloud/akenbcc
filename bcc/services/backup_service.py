"""Remote full backup (webs + dbs) with BCC run_history logging."""

from __future__ import annotations

import time
from typing import Any, Optional

from bcc.db.repository import Repository
from bcc.services.ssh_service import SSHResult, SSHService, ordered_hosts


class BackupService:
    def __init__(self, repo: Repository, ssh: Optional[SSHService] = None) -> None:
        self.repo = repo
        self.ssh = ssh or SSHService()

    def _hosts(self, source: dict[str, Any]) -> list[str]:
        return ordered_hosts(
            source.get("host") or "",
            source.get("alt_host") or "",
            source.get("last_ssh_host") or "",
        )

    def _run(self, source: dict[str, Any], command: str, timeout: int) -> SSHResult:
        user = source.get("username") or "root"
        pw = self.repo.source_password(source)
        result = self.ssh.run(
            host=source.get("host") or "",
            username=user,
            command=command,
            port=int(source.get("port") or 22),
            password=pw,
            key_path=source.get("key_path") or "",
            timeout=timeout,
            sudo_password=pw if user != "root" else "",
            hosts=self._hosts(source),
        )
        if result.host_used:
            self.repo.remember_ssh_host(int(source["id"]), result.host_used)
            source["last_ssh_host"] = result.host_used
        return result

    def run_full_backup(self, source_id: int, timeout: int = 7200) -> SSHResult:
        """
        Start backup-all.sh on the VPS and poll its log.
        The remote job keeps running if the PC SSH session drops.
        """
        source = self.repo.get_source(source_id)
        if not source:
            return SSHResult(False, "Source tidak ada")
        if source.get("role") != "linux_vps":
            return SSHResult(False, "Full backup Linux hanya untuk linux_vps")

        host = source.get("host") or ""
        deploy = (source.get("deploy_path") or "/www/backup-scripts").rstrip("/")
        label = source.get("source_label") or host
        self.repo.add_run_history(
            source_id,
            "backup_start",
            "ok",
            f"manual full backup host={host} label={label} deploy={deploy}",
        )

        start = (
            f"d='{deploy}'; "
            "if ! flock -n \"$d/.lock-webs\" true; then echo BUSY_WEBS; exit 0; fi; "
            "if ! flock -n \"$d/.lock-dbs\" true; then echo BUSY_DBS; exit 0; fi; "
            "mkdir -p \"$d/logs\"; "
            "log=\"$d/logs/backup-all_$(date +%Y%m%d).log\"; "
            "offset=$(wc -c < \"$log\" 2>/dev/null || echo 0); "
            "echo OFFSET:$offset; echo LOG:$log; "
            "if command -v setsid >/dev/null 2>&1; then "
            "setsid nohup bash \"$d/backup-all.sh\" >/dev/null 2>&1 </dev/null & "
            "else nohup bash \"$d/backup-all.sh\" >/dev/null 2>&1 </dev/null & fi; "
            "echo PID:$!"
        )
        started = self._run(source, start, 45)
        out = started.stdout or ""
        if "BUSY_WEBS" in out or "BUSY_DBS" in out:
            msg = "Backup sudah berjalan di server. Tidak dimulai ulang."
            self.repo.add_run_history(source_id, "backup_all", "fail", f"{host} {msg}")
            return SSHResult(False, msg, 1, out)
        if "OFFSET:" not in out:
            msg = started.message or "SSH gagal saat memulai backup"
            self._record(source_id, host, label, False, False, False, msg, out)
            return SSHResult(False, msg, 1, out)

        offset, log_path, pid = 0, "", ""
        for line in out.splitlines():
            if line.startswith("OFFSET:"):
                offset = _int(line.split(":", 1)[1])
            elif line.startswith("LOG:"):
                log_path = line.split(":", 1)[1].strip()
            elif line.startswith("PID:"):
                pid = line.split(":", 1)[1].strip()
        if not log_path:
            msg = "Server tidak mengembalikan path log backup"
            self._record(source_id, host, label, False, False, False, msg, out)
            return SSHResult(False, msg, 1, out)

        deadline = time.monotonic() + timeout
        chunk = ""
        while time.monotonic() < deadline:
            time.sleep(8 if not chunk else 15)
            source = self.repo.get_source(source_id) or source
            proc = ""
            if pid.isdigit():
                proc = f"if ps -p {pid} >/dev/null 2>&1; then echo BCC_PROC:RUNNING; else echo BCC_PROC:DEAD; fi"
            poll = (
                f"if [ ! -f '{log_path}' ]; then echo WAIT; exit 0; fi; "
                f"tail -c +{offset + 1} '{log_path}'; echo; {proc}"
            )
            result = self._run(source, poll, 40)
            chunk = result.stdout or ""
            if "BACKUP ALL SELESAI" in chunk or "BCC_PROC:DEAD" in chunk:
                break
        else:
            chunk += "\nTIMEOUT"

        webs_ok = "backup-webs.sh: OK" in chunk
        dbs_ok = "backup-dbs.sh: OK" in chunk
        all_ok = "BACKUP ALL SELESAI SUKSES" in chunk
        summary = (
            f"{host} label={label} webs={'ok' if webs_ok else 'fail'} "
            f"dbs={'ok' if dbs_ok else 'fail'}"
        )
        self._record(source_id, host, label, webs_ok, dbs_ok, all_ok, summary, chunk)
        return SSHResult(all_ok, summary, 0 if all_ok else 1, chunk[-4000:])

    def _record(
        self,
        source_id: int,
        host: str,
        label: str,
        webs_ok: bool,
        dbs_ok: bool,
        all_ok: bool,
        summary: str,
        chunk: str,
    ) -> None:
        tail = (chunk or "")[-1200:]
        self.repo.add_run_history(
            source_id, "backup_webs", "ok" if webs_ok else "fail", f"{host} | {tail}"
        )
        self.repo.add_run_history(
            source_id, "backup_dbs", "ok" if dbs_ok else "fail", f"{host} | {tail}"
        )
        self.repo.add_run_history(
            source_id,
            "backup_all",
            "ok" if all_ok else "fail",
            summary or f"{host} label={label}",
        )


def _int(value: str) -> int:
    try:
        return int((value or "").strip() or "0")
    except ValueError:
        return 0
