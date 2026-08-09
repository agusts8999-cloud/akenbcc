"""Template rendering and deploy to remote sources."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Optional

from bcc.db.repository import Repository
from bcc.paths import templates_dir
from bcc.services.ssh_service import SSHResult, SSHService

log = logging.getLogger(__name__)

TEMPLATE_VERSION = "0.1.0"

LINUX_FILES = [
    "config.sh",
    "lib.sh",
    "backup-webs.sh",
    "backup-dbs.sh",
    "backup-all.sh",
    "setup-ssh.sh",
    "exclude-web.list",
    "VERSION",
]

# Placeholders: __WEB_H__ __WEB_M__ __DB_H__ __DB_M__ __DEPLOY__ __WEB_NAME__ __DB_NAME__
AAPANEL_REGISTER_PY = r'''
import os, sys
os.chdir("/www/server/panel")
sys.path.insert(0, "/www/server/panel/class")
sys.path.insert(0, "/www/server/panel")
import public
from crontab import crontab

def make_get(**kwargs):
    g = public.dict_obj()
    for k, v in kwargs.items():
        setattr(g, k, v)
    return g

cron = crontab()
existing = public.M("crontab").field("id,name,echo").select()

web_h, web_m = __WEB_H__, __WEB_M__
db_h, db_m = __DB_H__, __DB_M__
deploy = "__DEPLOY__"
web_name = "__WEB_NAME__"
db_name = "__DB_NAME__"

# Remove old BCC / legacy remote backup jobs (avoid duplicates)
legacy_exact = [
    web_name, db_name,
    "Backup Web Remote to Webmin",
    "Backup DB Remote to Webmin",
]
to_delete = []
for row in list(existing):
    n = row.get("name") or ""
    if n in legacy_exact or n.startswith("BCC Web Remote") or n.startswith("BCC DB Remote"):
        to_delete.append(row)

for row in to_delete:
    try:
        g = make_get(id=str(row["id"]))
        if hasattr(cron, "DelCrontab"):
            cron.DelCrontab(g)
        else:
            public.M("crontab").where("id=?", (row["id"],)).delete()
        print("DEL", row.get("name"))
    except Exception as e:
        print("DEL_WARN", row.get("name"), e)

jobs = [
    {
        "name": web_name,
        "type": "day", "where1": "", "hour": str(web_h), "minute": str(web_m),
        "save": "", "backupTo": "localhost", "sType": "toShell", "sName": "",
        "sBody": "bash %s/backup-webs.sh" % deploy, "urladdress": "",
        "save_local": "0", "notice": "0", "notice_channel": "",
    },
    {
        "name": db_name,
        "type": "day", "where1": "", "hour": str(db_h), "minute": str(db_m),
        "save": "", "backupTo": "localhost", "sType": "toShell", "sName": "",
        "sBody": "bash %s/backup-dbs.sh" % deploy, "urladdress": "",
        "save_local": "0", "notice": "0", "notice_channel": "",
    },
]

for job in jobs:
    get = make_get(**job)
    print("ADD", job["name"], cron.AddCrontab(get))
print("DONE")
'''


class DeployService:
    def __init__(self, repo: Repository, ssh: Optional[SSHService] = None) -> None:
        self.repo = repo
        self.ssh = ssh or SSHService()

    def render_linux_config(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        mysql_password: str = "",
        remote_password: str = "",
    ) -> str:
        tpl = (templates_dir() / "linux" / "config.sh").read_text(encoding="utf-8")
        source_ip = source["host"]
        source_label = source.get("source_label") or f"aapanel-{source_ip}"
        deploy = source.get("deploy_path") or "/www/backup-scripts"
        base = (target.get("base_path") or "/home/backupuser/backups").rstrip("/")
        replacements = {
            "SOURCE_IP": source_ip,
            "SOURCE_LABEL": source_label,
            "WEB_ROOT": source.get("web_root") or "/www/wwwroot",
            "MYSQL_USER": source.get("mysql_user") or "root",
            "MYSQL_PASSWORD": mysql_password or "",
            "REMOTE_HOST": target["host"],
            "REMOTE_USER": target["username"],
            "REMOTE_PASSWORD": remote_password or "",
            "REMOTE_BASE": f"{base}/{source_label}",
            "REMOTE_PORT": str(target.get("port") or 22),
            "SSH_KEY_DIR": f"{deploy}/.ssh",
            "SSH_KEY": f"{deploy}/.ssh/id_ed25519_backup",
            "LOCAL_STAGING": f"{deploy}/staging",
            "LOCAL_LOG_DIR": f"{deploy}/logs",
        }
        # Replace simple KEY="..." lines
        out = tpl
        for key, val in replacements.items():
            out = re.sub(
                rf'^{key}=".*"$',
                f'{key}="{val}"',
                out,
                flags=re.M,
            )
        # SSH_OPTS depends on variables — leave template if it uses ${}
        return out

    def collect_linux_files(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        mysql_password: str,
        remote_password: str,
    ) -> dict[str, str]:
        base = templates_dir() / "linux"
        files: dict[str, str] = {}
        for name in LINUX_FILES:
            path = base / name
            if name == "config.sh":
                files[name] = self.render_linux_config(
                    source, target, mysql_password, remote_password
                )
            elif path.exists():
                files[name] = path.read_text(encoding="utf-8")
            else:
                log.warning("template missing: %s", path)
        files["VERSION"] = TEMPLATE_VERSION + "\n"
        return files

    def deploy_linux(self, source_id: int) -> SSHResult:
        source = self.repo.get_source(source_id)
        if not source:
            return SSHResult(False, "Source tidak ditemukan")
        if source["role"] != "linux_vps":
            return SSHResult(False, "Deploy Linux hanya untuk linux_vps")
        tid = source.get("target_id")
        if not tid:
            return SSHResult(False, "Source belum di-link ke backup target")
        target = self.repo.get_target(int(tid))
        if not target:
            return SSHResult(False, "Backup target tidak ditemukan")

        src_pw = self.repo.source_password(source)
        mysql_pw = self.repo.source_mysql_password(source)
        tgt_pw = self.repo.target_password(target)
        deploy_path = source.get("deploy_path") or "/www/backup-scripts"

        files = self.collect_linux_files(source, target, mysql_pw, tgt_pw)
        # content as strings
        upload_map = {k: v for k, v in files.items()}
        res = self.ssh.upload_dir_files(
            host=source["host"],
            username=source["username"],
            local_files=upload_map,
            remote_dir=deploy_path,
            port=int(source.get("port") or 22),
            password=src_pw,
            key_path=source.get("key_path") or "",
            sudo_password=src_pw if source["username"] != "root" else "",
        )
        if not res.ok:
            self.repo.add_run_history(source_id, "deploy", "fail", res.message)
            return res

        # setup ssh trust on remote
        setup = self.ssh.run(
            host=source["host"],
            username=source["username"],
            command=f"bash {deploy_path}/setup-ssh.sh",
            port=int(source.get("port") or 22),
            password=src_pw,
            sudo_password=src_pw if source["username"] != "root" else "",
            timeout=180,
        )
        if not setup.ok:
            self.repo.add_run_history(
                source_id, "setup_ssh", "fail", setup.message + "\n" + setup.stdout[-500:]
            )
            # still continue to cron if key may already exist
            log.warning("setup-ssh: %s", setup.message)

        cron_res = self.push_aapanel_schedule(source_id)
        h = hashlib.sha256("".join(files.values()).encode()).hexdigest()[:16]
        self.repo.set_deploy_revision(source_id, TEMPLATE_VERSION, h)
        self.repo.update_source(source_id, last_deploy_at=__import__("datetime").datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        msg = f"Deploy OK. setup-ssh={setup.ok}; cron={cron_res.ok}: {cron_res.message}"
        self.repo.add_run_history(source_id, "deploy", "ok" if res.ok else "fail", msg)
        return SSHResult(True, msg, 0, setup.stdout + "\n" + (cron_res.stdout or ""))

    @staticmethod
    def _job_names(source: dict[str, Any]) -> tuple[str, str]:
        slug = (source.get("source_label") or source.get("host") or "host").strip()
        # aaPanel name length / special chars soft sanitize
        slug = re.sub(r"[^\w.\- ]+", "_", slug)[:48]
        return (f"BCC Web Remote · {slug}", f"BCC DB Remote · {slug}")

    def _register_cron(
        self, source: dict[str, Any], src_pw: str, sch: dict[str, Any]
    ) -> SSHResult:
        web_h = int(sch.get("web_hour", 2))
        web_m = int(sch.get("web_minute", 0))
        db_h = int(sch.get("db_hour", 3))
        db_m = int(sch.get("db_minute", 0))
        deploy = source.get("deploy_path") or "/www/backup-scripts"
        web_name, db_name = self._job_names(source)

        if source.get("aapanel"):
            # Escape names for embedding in remote Python string literals
            def esc(s: str) -> str:
                return s.replace("\\", "\\\\").replace('"', '\\"')

            script = (
                AAPANEL_REGISTER_PY.replace("__WEB_H__", str(web_h))
                .replace("__WEB_M__", str(web_m))
                .replace("__DB_H__", str(db_h))
                .replace("__DB_M__", str(db_m))
                .replace("__DEPLOY__", deploy)
                .replace("__WEB_NAME__", esc(web_name))
                .replace("__DB_NAME__", esc(db_name))
            )
            # Preflight + register
            cmd = (
                f"test -x /www/server/panel/pyenv/bin/python3 || "
                f"{{ echo PRECHECK_FAIL panel_python; exit 2; }}; "
                f"test -f {deploy}/backup-webs.sh || "
                f"{{ echo PRECHECK_FAIL missing_backup-webs; exit 3; }}; "
                f"test -f {deploy}/backup-dbs.sh || "
                f"{{ echo PRECHECK_FAIL missing_backup-dbs; exit 4; }}; "
                f"cat > /tmp/bcc_reg_cron.py << 'BCCEOF'\n{script}\nBCCEOF\n"
                f"/www/server/panel/pyenv/bin/python3 /tmp/bcc_reg_cron.py; "
                f"echo '---CRONTAB---'; crontab -l 2>/dev/null | grep -E 'BCC|backup-webs|backup-dbs' || true"
            )
            return self.ssh.run(
                host=source["host"],
                username=source["username"],
                command=cmd,
                port=int(source.get("port") or 22),
                password=src_pw,
                sudo_password=src_pw if source["username"] != "root" else "",
                timeout=120,
            )

        # plain crontab
        marker = "# bcc-backup-remote"
        block = (
            f"{marker}\n"
            f"{web_m} {web_h} * * * /bin/bash {deploy}/backup-webs.sh >> {deploy}/logs/cron-webs.log 2>&1\n"
            f"{db_m} {db_h} * * * /bin/bash {deploy}/backup-dbs.sh >> {deploy}/logs/cron-dbs.log 2>&1\n"
        )
        cmd = (
            f"(crontab -l 2>/dev/null | sed '/{marker}/,/backup-dbs/d'; echo '{block}') | crontab -"
        )
        return self.ssh.run(
            host=source["host"],
            username=source["username"],
            command=cmd,
            port=int(source.get("port") or 22),
            password=src_pw,
            sudo_password=src_pw if source["username"] != "root" else "",
        )

    def push_aapanel_schedule(self, source_id: int) -> SSHResult:
        """
        Create/update aaPanel Plan Tasks (or plain crontab) for web+DB backup
        from the schedule stored in BCC inventory.
        """
        source = self.repo.get_source(source_id)
        if not source:
            return SSHResult(False, "Source tidak ada")
        if source.get("role") != "linux_vps":
            return SSHResult(False, "Push cron aaPanel hanya untuk linux_vps")

        src_pw = self.repo.source_password(source)
        sch = self.repo.get_schedule(source_id) or {}
        web_h = int(sch.get("web_hour", 2))
        web_m = int(sch.get("web_minute", 0))
        db_h = int(sch.get("db_hour", 3))
        db_m = int(sch.get("db_minute", 0))
        host = source.get("host") or ""

        res = self._register_cron(source, src_pw, sch)
        out = res.stdout or ""
        if source.get("aapanel"):
            ok = res.ok and "PRECHECK_FAIL" not in out and "DONE" in out
        else:
            ok = res.ok

        detail = (
            f"{host} web={web_h:02d}:{web_m:02d} db={db_h:02d}:{db_m:02d} "
            f"aapanel={bool(source.get('aapanel'))} | {res.message}"
        )
        self.repo.add_run_history(
            source_id,
            "cron_push",
            "ok" if ok else "fail",
            detail + ((" | " + (res.stdout or "")[-300:]) if res.stdout else ""),
        )
        if not ok:
            return SSHResult(False, detail, res.exit_code, res.stdout, res.stderr)
        return SSHResult(True, detail, 0, res.stdout, res.stderr)

    def apply_schedule(self, source_id: int) -> SSHResult:
        """Alias for push_aapanel_schedule (back-compat)."""
        return self.push_aapanel_schedule(source_id)

    def export_windows_package(self, source_id: int, dest_dir: Path) -> Path:
        """Copy Windows templates to a folder for manual install."""
        source = self.repo.get_source(source_id)
        if not source:
            raise ValueError("source not found")
        tid = source.get("target_id")
        target = self.repo.get_target(int(tid)) if tid else None
        win = templates_dir() / "windows"
        dest_dir.mkdir(parents=True, exist_ok=True)
        for p in win.glob("*"):
            if p.is_file():
                text = p.read_text(encoding="utf-8")
                if target and p.name.endswith((".ps1", ".psd1", ".config.ps1")):
                    text = text.replace("{{REMOTE_HOST}}", target["host"])
                    text = text.replace("{{REMOTE_USER}}", target["username"])
                    text = text.replace(
                        "{{REMOTE_BASE}}",
                        f"{(target.get('base_path') or '/home/backupuser/backups').rstrip('/')}/{source.get('source_label') or ('windows-' + source['host'])}",
                    )
                    text = text.replace("{{SOURCE_HOST}}", source["host"])
                (dest_dir / p.name).write_text(text, encoding="utf-8")
        return dest_dir
