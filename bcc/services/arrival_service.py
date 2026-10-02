"""Detect new backup archives arriving on the backup server (SSH scan)."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from bcc.db.repository import Repository
from bcc.services.monitor_service import human_bytes
from bcc.services.ssh_service import SSHService, target_route

log = logging.getLogger(__name__)

SETTING_STATE = "arrival_scan_state"
SETTING_ON_REFRESH = "arrival_scan_on_refresh"
SETTING_INTERVAL_MIN = "arrival_scan_interval_min"
SETTING_LAST_AT = "arrival_last_scan_at"

DEFAULT_INTERVAL_MIN = 15
MAX_FINGERPRINTS = 800
MSG_TRUNCATE = 1800


@dataclass
class ArrivalFile:
    path: str
    size: int
    mtime: float
    kind: str  # webs | dbs

    @property
    def name(self) -> str:
        return self.path.rstrip("/").split("/")[-1]

    def fingerprint(self) -> str:
        return f"{self.path}|{self.size}|{int(self.mtime)}"


@dataclass
class ScanResult:
    ok: bool
    message: str
    new_files: int = 0
    sources_updated: int = 0
    errors: list[str] = field(default_factory=list)
    skipped_throttle: bool = False


class BackupArrivalService:
    def __init__(self, repo: Repository, ssh: Optional[SSHService] = None) -> None:
        self.repo = repo
        self.ssh = ssh or SSHService()

    def ensure_defaults(self) -> None:
        if not self.repo.get_setting(SETTING_ON_REFRESH):
            self.repo.set_setting(SETTING_ON_REFRESH, "1")
        if not self.repo.get_setting(SETTING_INTERVAL_MIN):
            self.repo.set_setting(SETTING_INTERVAL_MIN, str(DEFAULT_INTERVAL_MIN))

    def _load_state(self) -> dict[str, Any]:
        raw = self.repo.get_setting(SETTING_STATE, "")
        if not raw:
            return {"sources": {}}
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                return {"sources": {}}
            data.setdefault("sources", {})
            return data
        except json.JSONDecodeError:
            return {"sources": {}}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.repo.set_setting(SETTING_STATE, json.dumps(state, separators=(",", ":")))

    def should_scan_on_refresh(self) -> bool:
        self.ensure_defaults()
        if self.repo.get_setting(SETTING_ON_REFRESH, "1") != "1":
            return False
        try:
            interval = int(self.repo.get_setting(SETTING_INTERVAL_MIN) or DEFAULT_INTERVAL_MIN)
        except ValueError:
            interval = DEFAULT_INTERVAL_MIN
        interval = max(1, interval)
        last = (self.repo.get_setting(SETTING_LAST_AT) or "").strip()
        if not last:
            return True
        try:
            # accept epoch or ISO
            if last.replace(".", "", 1).isdigit():
                last_ts = float(last)
            else:
                last_ts = datetime.fromisoformat(last).timestamp()
        except ValueError:
            return True
        return (time.time() - last_ts) >= interval * 60

    def mark_scan_time(self) -> None:
        self.repo.set_setting(SETTING_LAST_AT, str(time.time()))

    def scan_all(self, force: bool = False) -> ScanResult:
        """Scan all targets/sources for new archives. force bypasses throttle."""
        self.ensure_defaults()
        if not force and not self.should_scan_on_refresh():
            return ScanResult(
                True,
                "Scan dilewati (throttle interval belum lewat).",
                skipped_throttle=True,
            )

        state = self._load_state()
        sources_map: dict[str, Any] = state.setdefault("sources", {})
        errors: list[str] = []
        total_new = 0
        sources_updated = 0

        targets = self.repo.list_targets()
        if not targets:
            self.mark_scan_time()
            return ScanResult(True, "Tidak ada server backup (target).", 0, 0)

        all_sources = self.repo.list_sources()
        for t in targets:
            tid = int(t["id"])
            linked = [s for s in all_sources if int(s.get("target_id") or 0) == tid]
            if not linked:
                continue
            try:
                listed = self._list_files_for_target(t, linked)
            except Exception as e:
                msg = f"Target {t.get('label') or tid}: {e}"
                log.warning("arrival scan SSH failed: %s", msg)
                errors.append(msg)
                continue

            for source in linked:
                sid = int(source["id"])
                sid_key = str(sid)
                src_state = sources_map.setdefault(sid_key, {})
                webs_new = self._diff_kind(src_state, "webs", listed.get(sid, {}).get("webs", []))
                dbs_new = self._diff_kind(src_state, "dbs", listed.get(sid, {}).get("dbs", []))

                # Persist fingerprints always after processing
                self._commit_kind_state(src_state, "webs", listed.get(sid, {}).get("webs", []))
                self._commit_kind_state(src_state, "dbs", listed.get(sid, {}).get("dbs", []))

                if not webs_new and not dbs_new:
                    continue

                total_new += len(webs_new) + len(dbs_new)
                sources_updated += 1
                self._record_arrival(source, webs_new, dbs_new)

        state["sources"] = sources_map
        state["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self._save_state(state)
        self.mark_scan_time()

        if errors and total_new == 0 and sources_updated == 0:
            return ScanResult(
                False,
                "Scan gagal: " + "; ".join(errors[:3]),
                0,
                0,
                errors,
            )
        parts = [f"Scan selesai: {total_new} file baru dari {sources_updated} sumber."]
        if errors:
            parts.append(f"Peringatan: {'; '.join(errors[:2])}")
        return ScanResult(True, " ".join(parts), total_new, sources_updated, errors)

    def _diff_kind(
        self,
        src_state: dict[str, Any],
        kind: str,
        files: list[ArrivalFile],
    ) -> list[ArrivalFile]:
        kind_state = src_state.get(kind) or {}
        initialized = bool(kind_state.get("initialized"))
        prev = set(kind_state.get("fingerprints") or [])
        if not initialized:
            # Baseline: no history flood
            return []
        return [f for f in files if f.fingerprint() not in prev]

    def _commit_kind_state(
        self,
        src_state: dict[str, Any],
        kind: str,
        files: list[ArrivalFile],
    ) -> None:
        fps = [f.fingerprint() for f in files]
        # Keep previous fingerprints that may still matter + current (cap)
        old = list((src_state.get(kind) or {}).get("fingerprints") or [])
        merged = list(dict.fromkeys(fps + old))[:MAX_FINGERPRINTS]
        max_mtime = max((f.mtime for f in files), default=0.0)
        src_state[kind] = {
            "initialized": True,
            "fingerprints": merged,
            "max_mtime": max_mtime,
        }

    def _record_arrival(
        self,
        source: dict[str, Any],
        webs_new: list[ArrivalFile],
        dbs_new: list[ArrivalFile],
    ) -> None:
        sid = int(source["id"])
        parts: list[str] = []
        if webs_new:
            parts.append(
                f"webs ({len(webs_new)}): "
                + ", ".join(
                    f"{f.name} ({human_bytes(f.size)})" for f in webs_new[:12]
                )
                + ("…" if len(webs_new) > 12 else "")
            )
        if dbs_new:
            parts.append(
                f"dbs ({len(dbs_new)}): "
                + ", ".join(
                    f"{f.name} ({human_bytes(f.size)})" for f in dbs_new[:12]
                )
                + ("…" if len(dbs_new) > 12 else "")
            )
        msg = "; ".join(parts)
        if len(msg) > MSG_TRUNCATE:
            msg = msg[: MSG_TRUNCATE - 1] + "…"

        # Prefer specific run_types when only one kind; else combined
        if webs_new and not dbs_new:
            run_type = "backup_arrival_web"
        elif dbs_new and not webs_new:
            run_type = "backup_arrival_db"
        else:
            run_type = "backup_arrival"

        self.repo.add_run_history(sid, run_type, "ok", msg)

    def _list_files_for_target(
        self,
        target: dict[str, Any],
        sources: list[dict[str, Any]],
    ) -> dict[int, dict[str, list[ArrivalFile]]]:
        base = (target.get("base_path") or "/home/backupuser/backups").rstrip("/")
        # One SSH: find under base for *.tar.gz / *.sql.gz
        cmd = (
            "find "
            + self._shell_quote(base)
            + " -type f \\( -name '*.tar.gz' -o -name '*.sql.gz' \\) "
            "-printf '%T@ %s %p\\n' 2>/dev/null || "
            "find "
            + self._shell_quote(base)
            + " -type f \\( -name '*.tar.gz' -o -name '*.sql.gz' \\) "
            "-exec stat -c '%Y %s %n' {} \\; 2>/dev/null"
        )
        r = self.ssh.run(
            host=target["host"],
            username=target["username"],
            command=cmd,
            port=int(target.get("port") or 22),
            password=self.repo.target_password(target),
            key_path=target.get("key_path") or "",
            timeout=120,
            **target_route(target),
        )
        if not r.ok and not (r.stdout or "").strip():
            raise RuntimeError(r.message or "SSH gagal")

        by_label: dict[str, dict[str, list[ArrivalFile]]] = {}
        for line in (r.stdout or "").splitlines():
            parsed = self._parse_find_line(line)
            if not parsed:
                continue
            mtime, size, path = parsed
            rel = path
            if path.startswith(base + "/"):
                rel = path[len(base) + 1 :]
            elif path.startswith(base):
                rel = path[len(base) :].lstrip("/")
            parts = rel.split("/")
            if len(parts) < 2:
                continue
            label = parts[0]
            kind = parts[1] if parts[1] in ("webs", "dbs") else ""
            if kind not in ("webs", "dbs"):
                # maybe base_path already includes label nesting differently
                continue
            entry = ArrivalFile(path=path, size=size, mtime=mtime, kind=kind)
            by_label.setdefault(label, {"webs": [], "dbs": []})[kind].append(entry)

        out: dict[int, dict[str, list[ArrivalFile]]] = {}
        for s in sources:
            sid = int(s["id"])
            lab = (s.get("source_label") or "").strip()
            if not lab:
                continue
            out[sid] = by_label.get(lab, {"webs": [], "dbs": []})
        return out

    @staticmethod
    def _shell_quote(path: str) -> str:
        return "'" + path.replace("'", "'\"'\"'") + "'"

    @staticmethod
    def _parse_find_line(line: str) -> Optional[tuple[float, int, str]]:
        line = line.strip()
        if not line:
            return None
        # "%T@ %s %p" or "%Y %s %n"
        m = re.match(r"^([0-9]+(?:\.[0-9]*)?)\s+(\d+)\s+(.+)$", line)
        if not m:
            return None
        try:
            return float(m.group(1)), int(m.group(2)), m.group(3).strip()
        except ValueError:
            return None
