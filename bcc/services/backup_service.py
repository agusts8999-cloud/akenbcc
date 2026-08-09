"""Remote full backup (webs + dbs) with BCC run_history logging."""

from __future__ import annotations

from typing import Optional

from bcc.db.repository import Repository
from bcc.services.ssh_service import SSHResult, SSHService


class BackupService:
    def __init__(self, repo: Repository, ssh: Optional[SSHService] = None) -> None:
        self.repo = repo
        self.ssh = ssh or SSHService()

    def run_full_backup(self, source_id: int, timeout: int = 7200) -> SSHResult:
        """
        Run backup-webs then backup-dbs on a linux_vps source.
        Records backup_start, backup_webs, backup_dbs, backup_all in run_history.
        """
        source = self.repo.get_source(source_id)
        if not source:
            return SSHResult(False, "Source tidak ada")
        if source.get("role") != "linux_vps":
            return SSHResult(False, "Full backup Linux hanya untuk linux_vps")

        host = source.get("host") or ""
        user = source.get("username") or "root"
        port = int(source.get("port") or 22)
        deploy = (source.get("deploy_path") or "/www/backup-scripts").rstrip("/")
        label = source.get("source_label") or host
        pw = self.repo.source_password(source)
        sudo = pw if user != "root" else ""

        self.repo.add_run_history(
            source_id,
            "backup_start",
            "ok",
            f"manual full backup host={host} label={label} deploy={deploy}",
        )

        webs = self.ssh.run(
            host=host,
            username=user,
            command=f"bash {deploy}/backup-webs.sh 2>&1; echo EXIT:$?",
            port=port,
            password=pw,
            sudo_password=sudo,
            timeout=timeout,
        )
        out_w = webs.stdout or ""
        if "EXIT:0" in out_w:
            webs_ok = True
        elif "EXIT:" in out_w:
            webs_ok = False
        else:
            webs_ok = webs.ok

        webs_tail = (out_w or webs.message or "")[-1200:]
        self.repo.add_run_history(
            source_id,
            "backup_webs",
            "ok" if webs_ok else "fail",
            f"{host} | {webs.message} | {webs_tail}",
        )

        dbs = self.ssh.run(
            host=host,
            username=user,
            command=f"bash {deploy}/backup-dbs.sh 2>&1; echo EXIT:$?",
            port=port,
            password=pw,
            sudo_password=sudo,
            timeout=timeout,
        )
        out_d = dbs.stdout or ""
        if "EXIT:0" in out_d:
            dbs_ok = True
        elif "EXIT:" in out_d:
            dbs_ok = False
        else:
            dbs_ok = dbs.ok

        dbs_tail = (out_d or dbs.message or "")[-1200:]
        self.repo.add_run_history(
            source_id,
            "backup_dbs",
            "ok" if dbs_ok else "fail",
            f"{host} | {dbs.message} | {dbs_tail}",
        )

        all_ok = webs_ok and dbs_ok
        summary = (
            f"{host} label={label} webs={'ok' if webs_ok else 'fail'} "
            f"dbs={'ok' if dbs_ok else 'fail'}"
        )
        self.repo.add_run_history(
            source_id,
            "backup_all",
            "ok" if all_ok else "fail",
            summary,
        )

        out = (
            f"=== WEBS ===\n{(webs.stdout or '')[-2000:]}\n"
            f"=== DBS ===\n{(dbs.stdout or '')[-2000:]}\n"
            f"=== {summary} ===\n"
        )
        if all_ok:
            return SSHResult(True, summary, 0, out)
        return SSHResult(False, summary, 1, out)
