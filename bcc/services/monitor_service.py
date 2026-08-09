"""Remote health / capacity monitoring."""

from __future__ import annotations

import re
from typing import Any, Optional

from bcc.db.repository import Repository
from bcc.services.ssh_service import SSHResult, SSHService


def human_bytes(n: int) -> str:
    x = float(max(0, n))
    for unit in ("B", "K", "M", "G", "T"):
        if x < 1024.0 or unit == "T":
            if unit == "B":
                return f"{int(x)} B"
            return f"{x:.1f} {unit}"
        x /= 1024.0
    return f"{x:.1f} T"


class MonitorService:
    def __init__(self, repo: Repository, ssh: Optional[SSHService] = None) -> None:
        self.repo = repo
        self.ssh = ssh or SSHService()

    def check_target_disk(self, target_id: int) -> SSHResult:
        t = self.repo.get_target(target_id)
        if not t:
            return SSHResult(False, "Target tidak ada")
        path = t.get("base_path") or "/home/backupuser/backups"
        cmd = (
            f"df -h '{path}' 2>/dev/null; echo '---'; "
            f"du -sh '{path}'/* 2>/dev/null | head -40; echo '---'; "
            f"df -B1 '{path}' | tail -1"
        )
        return self.ssh.run(
            host=t["host"],
            username=t["username"],
            command=cmd,
            port=int(t.get("port") or 22),
            password=self.repo.target_password(t),
            key_path=t.get("key_path") or "",
            timeout=60,
        )

    def target_disk_slices(self, target_id: int) -> dict[str, Any]:
        """
        Pie breakdown of filesystem holding target base_path:
        Free + per source_label folder + residual Lainnya.
        """
        t = self.repo.get_target(target_id)
        if not t:
            return {
                "ok": False,
                "message": "Target tidak ada",
                "total_bytes": 0,
                "free_bytes": 0,
                "slices": [],
            }
        path = (t.get("base_path") or "/home/backupuser/backups").rstrip("/")
        cmd = (
            f"echo '===DF==='; df -B1 '{path}' 2>/dev/null | tail -1; "
            f"echo '===DU==='; du -sb '{path}'/*/ 2>/dev/null; "
            f"echo '===END==='"
        )
        r = self.ssh.run(
            host=t["host"],
            username=t["username"],
            command=cmd,
            port=int(t.get("port") or 22),
            password=self.repo.target_password(t),
            key_path=t.get("key_path") or "",
            timeout=90,
        )
        if not r.ok and not (r.stdout or "").strip():
            return {
                "ok": False,
                "message": r.message or "SSH gagal",
                "total_bytes": 0,
                "free_bytes": 0,
                "slices": [],
                "target_label": t.get("label") or t.get("host"),
                "base_path": path,
            }

        out = r.stdout or ""
        total = used = free = 0
        m_df = re.search(
            r"===DF===\s*\n(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)",
            out,
        )
        if m_df:
            total = int(m_df.group(2))
            used = int(m_df.group(3))
            free = int(m_df.group(4))
        else:
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[1].isdigit() and parts[2].isdigit():
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])

        folder_bytes: dict[str, int] = {}
        in_du = False
        for line in out.splitlines():
            if line.strip() == "===DU===":
                in_du = True
                continue
            if line.strip() == "===END===":
                in_du = False
                continue
            if not in_du:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            size = int(parts[0])
            folder = parts[1].rstrip("/")
            name = folder.split("/")[-1] if folder else parts[1]
            if name:
                folder_bytes[name] = folder_bytes.get(name, 0) + size

        known_labels: set[str] = set()
        ordered_known: list[tuple[str, int]] = []
        seen: set[str] = set()
        for s in self.repo.list_sources():
            if int(s.get("target_id") or 0) != int(target_id):
                continue
            lab = (s.get("source_label") or "").strip()
            if not lab or lab in seen:
                continue
            seen.add(lab)
            known_labels.add(lab)
            ordered_known.append((lab, folder_bytes.get(lab, 0)))

        known_sum = sum(sz for _, sz in ordered_known)
        residual = max(0, used - known_sum)

        if total <= 0:
            return {
                "ok": False,
                "message": "Gagal parse df (total=0). " + (r.message or ""),
                "total_bytes": 0,
                "free_bytes": free,
                "slices": [],
                "target_label": t.get("label") or t.get("host"),
                "base_path": path,
                "raw": out[-500:],
            }

        def pct(b: int) -> float:
            return round(100.0 * b / total, 2)

        slices: list[dict[str, Any]] = [
            {"label": "Free", "bytes": free, "pct": pct(free), "kind": "free"}
        ]
        for lab, sz in ordered_known:
            if sz <= 0:
                continue
            slices.append(
                {"label": lab, "bytes": sz, "pct": pct(sz), "kind": "source"}
            )
        if residual > 0:
            slices.append(
                {
                    "label": "Lainnya",
                    "bytes": residual,
                    "pct": pct(residual),
                    "kind": "other",
                }
            )

        psum = sum(s["pct"] for s in slices)
        if slices and abs(psum - 100.0) > 0.05 and psum > 0:
            scale = 100.0 / psum
            for s in slices:
                s["pct"] = round(s["pct"] * scale, 2)

        return {
            "ok": True,
            "message": (
                f"OK {t.get('host')} total={human_bytes(total)} "
                f"free={human_bytes(free)}"
            ),
            "total_bytes": total,
            "free_bytes": free,
            "used_bytes": used,
            "slices": slices,
            "target_label": t.get("label") or t.get("host"),
            "base_path": path,
        }

    def check_source_logs(self, source_id: int) -> SSHResult:
        s = self.repo.get_source(source_id)
        if not s:
            return SSHResult(False, "Source tidak ada")
        deploy = s.get("deploy_path") or "/www/backup-scripts"
        cmd = (
            f"ls -lt {deploy}/logs 2>/dev/null | head -10; echo '==='; "
            f"tail -30 {deploy}/logs/backup-all_$(date +%Y%m%d).log 2>/dev/null || "
            f"tail -30 $(ls -t {deploy}/logs/*.log 2>/dev/null | head -1) 2>/dev/null; "
            f"echo '===DISK==='; df -h {deploy} 2>/dev/null | tail -1"
        )
        pw = self.repo.source_password(s)
        return self.ssh.run(
            host=s["host"],
            username=s["username"],
            command=cmd,
            port=int(s.get("port") or 22),
            password=pw,
            key_path=s.get("key_path") or "",
            sudo_password=pw if s["username"] != "root" else "",
            timeout=60,
        )

    def refresh_source_ssh(self, source_id: int) -> SSHResult:
        s = self.repo.get_source(source_id)
        if not s:
            return SSHResult(False, "Source tidak ada")
        r = self.ssh.test(
            host=s["host"],
            username=s["username"],
            port=int(s.get("port") or 22),
            password=self.repo.source_password(s),
            key_path=s.get("key_path") or "",
        )
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.repo.update_source(
            source_id, last_ssh_ok=1 if r.ok else 0, last_ssh_at=now
        )
        self.repo.add_run_history(
            source_id, "ssh_test", "ok" if r.ok else "fail", r.message
        )
        return r

    def dashboard_snapshot(self) -> dict[str, Any]:
        sources = self.repo.list_sources()
        targets = self.repo.list_targets()
        ok = sum(1 for s in sources if s.get("last_ssh_ok") == 1)
        fail = sum(1 for s in sources if s.get("last_ssh_ok") == 0)
        unk = len(sources) - ok - fail
        return {
            "sources_total": len(sources),
            "sources_ok": ok,
            "sources_fail": fail,
            "sources_unknown": unk,
            "targets_total": len(targets),
            "history": self.repo.recent_history(12),
            "schedules": self.repo.list_schedules_joined(),
        }
