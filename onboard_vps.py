#!/usr/bin/env python3
"""Seed + deploy + verify one VPS source by host, record BCC history."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ensure seed catalog up to date
import seed_existing_servers as seed  # noqa: E402
from bcc.db.repository import Repository
from bcc.services.deploy_service import DeployService
from bcc.services.ssh_service import SSHService

HOST = "100.96.165.22"
BACKUP = "100.110.117.36"


def main(host: str | None = None, run_backup: bool = False) -> int:
    host = host or HOST
    # 1) seed all known (idempotent) including this host
    seed.main()
    repo = Repository()
    ssh = SSHService()
    deploy = DeployService(repo)

    src = None
    for s in repo.list_sources():
        if s.get("host") == host:
            src = s
            break
    if not src:
        print("Source missing after seed")
        return 1

    sid = int(src["id"])
    pw = repo.source_password(src)
    label = src.get("source_label") or f"aapanel-{host}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n=== Onboard source id={sid} {host} ===")

    print("--- SSH test ---")
    t = ssh.test(host, src["username"], int(src.get("port") or 22), password=pw)
    print(t.message)
    if not t.ok:
        repo.add_run_history(sid, "ssh_test", "fail", t.message)
        repo.update_source(sid, last_ssh_ok=0, last_ssh_at=now, password=pw)
        return 2
    repo.update_source(sid, last_ssh_ok=1, last_ssh_at=now, password=pw)

    print("--- reach backup ---")
    probe = ssh.run(
        host,
        src["username"],
        (
            f"tailscale ip -4 2>/dev/null; "
            f"timeout 8 bash -c 'echo >/dev/tcp/{BACKUP}/22' && echo REACHABLE || echo NOT_REACHABLE"
        ),
        port=int(src.get("port") or 22),
        password=pw,
        timeout=40,
    )
    print(probe.stdout or probe.message)
    if "REACHABLE" not in (probe.stdout or "") or (
        "NOT_REACHABLE" in (probe.stdout or "")
        and not any(ln.strip() == "REACHABLE" for ln in (probe.stdout or "").splitlines())
    ):
        repo.add_run_history(sid, "mesh_setup", "fail", f"unreachable {BACKUP}: {(probe.stdout or '')[:300]}")
        return 3

    print("--- deploy (scripts + setup-ssh + cron) ---")
    res = deploy.deploy_linux(sid)
    print(res.message)
    print((res.stdout or "")[-2000:])

    print("--- BatchMode ---")
    key = "/www/backup-scripts/.ssh/id_ed25519_backup"
    batch = ssh.run(
        host,
        src["username"],
        (
            f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes "
            f"-o StrictHostKeyChecking=accept-new -o ConnectTimeout=25 "
            f"backupuser@{BACKUP} "
            f"'echo SSH_OK; mkdir -p ~/backups/{label}/{{webs,dbs,logs}}; ls -la ~/backups/{label}'"
        ),
        port=int(src.get("port") or 22),
        password=pw,
        timeout=60,
    )
    print(batch.stdout or batch.message)
    if "SSH_OK" not in (batch.stdout or ""):
        repo.add_run_history(
            sid,
            "setup_ssh",
            "fail",
            f"BatchMode fail after deploy: {(batch.stdout or batch.message)[:400]}",
        )
        return 4

    print("--- rsync marker ---")
    xfer = ssh.run(
        host,
        src["username"],
        (
            f"echo bcc-onboard-$(date +%Y%m%d%H%M%S) > /tmp/bcc-onboard.txt && "
            f"rsync -az -e 'ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes "
            f"-o StrictHostKeyChecking=accept-new' "
            f"/tmp/bcc-onboard.txt "
            f"backupuser@{BACKUP}:/home/backupuser/backups/{label}/logs/ && echo RSYNC_OK"
        ),
        port=int(src.get("port") or 22),
        password=pw,
        timeout=90,
    )
    print(xfer.stdout or xfer.message)
    ok = "RSYNC_OK" in (xfer.stdout or "")
    status = "ok" if ok else "partial"
    msg = (
        f"host={host}; backup={BACKUP}; setup_ok; batch=yes; rsync={ok}; "
        f"remote=/home/backupuser/backups/{label}"
    )
    repo.add_run_history(sid, "onboard", status, msg)
    sch = repo.get_schedule(sid) or {}
    wh = int(sch.get("web_hour", 2))
    wm = int(sch.get("web_minute", 0))
    dh = int(sch.get("db_hour", 3))
    dm = int(sch.get("db_minute", 0))
    repo.update_source(
        sid,
        last_deploy_at=now,
        last_ssh_ok=1,
        notes=f"Tailscale {host}; deploy+ssh trust {status}; web {wh:02d}:{wm:02d} / DB {dh:02d}:{dm:02d}",
        password=pw,
    )
    print(f"BCC recorded status={status} source_id={sid}")

    if not ok:
        return 5

    if run_backup:
        print("--- backup-all (live) ---")
        bur = ssh.run(
            host,
            src["username"],
            "bash /www/backup-scripts/backup-all.sh 2>&1 | tee /tmp/bcc-backup-all.log; "
            "echo EXIT:$?; tail -n 40 /tmp/bcc-backup-all.log",
            port=int(src.get("port") or 22),
            password=pw,
            timeout=7200,
        )
        print((bur.stdout or bur.message)[-3000:])
        b_ok = bur.ok and "EXIT:0" in (bur.stdout or "")
        repo.add_run_history(
            sid,
            "backup_manual",
            "ok" if b_ok else "fail",
            (bur.stdout or bur.message)[-1500:],
        )
        return 0 if b_ok else 6

    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Onboard one VPS source into BCC")
    p.add_argument("host", nargs="?", default=HOST, help="Source host IP")
    p.add_argument(
        "--backup",
        action="store_true",
        help="After onboard, run backup-all.sh once (can take long)",
    )
    args = p.parse_args()
    raise SystemExit(main(host=args.host, run_backup=args.backup))
