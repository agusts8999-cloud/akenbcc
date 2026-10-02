"""Remote storage mounting, retention scanning, and safe lifecycle actions."""

from __future__ import annotations

import logging
import posixpath
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bcc.services.ssh_service import SSHService, target_route

log = logging.getLogger(__name__)


@dataclass
class StorageResult:
    ok: bool
    message: str
    found: int = 0
    acted: int = 0


class StorageService:
    def __init__(self, repo) -> None:
        self.repo = repo
        self.ssh = SSHService()

    def _connection(self, storage: dict[str, Any]) -> dict[str, Any]:
        target = self.repo.get_target(int(storage["target_id"]))
        if not target:
            raise ValueError("Target storage tidak ditemukan")
        route = target_route(target)
        return {"host": target["host"], "username": target["username"], "port": target["port"],
                "password": self.repo.target_password(target), "key_path": target.get("key_path") or "",
                **route}

    def test_storage(self, storage_id: int) -> StorageResult:
        storage = self.repo.get_storage(storage_id)
        if not storage:
            return StorageResult(False, "Storage tidak ditemukan")
        c = self._connection(storage)
        cmd = f"test -d {shlex.quote(storage['mount_path'])} && test -r {shlex.quote(storage['mount_path'])} && df -h {shlex.quote(storage['mount_path'])}"
        r = self.ssh.run(**c, command=cmd, timeout=30)
        return StorageResult(r.ok, r.message if r.ok else f"Storage gagal: {r.stderr or r.message}")

    def scan(self, storage_id: int, retention_days: int = 3) -> StorageResult:
        storage = self.repo.get_storage(storage_id)
        if not storage:
            return StorageResult(False, "Storage tidak ditemukan")
        days = max(1, int(retention_days))
        c = self._connection(storage)
        root = shlex.quote(storage["mount_path"])
        cmd = f"find {root} -type f -mmin +{days * 1440} -printf '%s\\t%T@\\t%p\\n' 2>/dev/null"
        r = self.ssh.run(**c, command=cmd, timeout=180)
        if not r.ok:
            return StorageResult(False, f"Scan gagal: {r.stderr or r.message}")
        count = 0
        now = datetime.now(timezone.utc).timestamp()
        for line in r.stdout.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            try:
                size, modified_epoch, path = int(parts[0]), float(parts[1]), parts[2]
                age = max(0.0, (now - modified_epoch) / 86400)
            except (ValueError, TypeError):
                continue
            self.repo.upsert_retention_item(storage_id, path, size, datetime.fromtimestamp(modified_epoch, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), age)
            count += 1
        return StorageResult(True, f"Scan selesai: {count} file melewati {days} hari", found=count)

    def act_on_items(self, item_ids: list[int], action: str, archive_storage_id: int | None = None, group_key: str = "arsip") -> StorageResult:
        if action not in {"archive", "delete"}:
            return StorageResult(False, "Aksi harus archive atau delete")
        items = [i for i in self.repo.list_retention_items(status="pending") if int(i["id"]) in set(item_ids)]
        acted = 0
        for item in items:
            source = self.repo.get_storage(int(item["storage_id"]))
            dest = self.repo.get_storage(int(archive_storage_id)) if archive_storage_id else None
            try:
                if action == "archive" and not dest:
                    raise ValueError("Storage arsip wajib dipilih")
                if action == "archive" and int(dest["target_id"]) != int(source["target_id"]):
                    raise ValueError("Arsip lintas server belum didukung; pilih storage pada server yang sama")
                c = self._connection(source)
                source_q = shlex.quote(item["path"])
                if action == "delete":
                    command = f"test -f {source_q} && rm -f -- {source_q}"
                else:
                    folder = f"{dest['mount_path'].rstrip('/')}/{group_key.strip() or 'arsip'}"
                    destination = f"{folder}/{posixpath.basename(item['path'])}"
                    command = (
                        f"mkdir -p {shlex.quote(folder)} && "
                        f"test ! -e {shlex.quote(destination)} && "
                        f"mv -- {source_q} {shlex.quote(destination)}"
                    )
                r = self.ssh.run(**c, command=command, timeout=120)
                if not r.ok:
                    raise RuntimeError(r.stderr or r.message)
                self.repo.update_retention_item(int(item["id"]), "archived" if action == "archive" else "deleted", archive_storage_id)
                acted += 1
            except Exception as exc:
                log.warning("retention action failed for item %s: %s", item["id"], exc)
                self.repo.update_retention_item(int(item["id"]), "error", archive_storage_id, str(exc)[:500])
        ok = bool(items) and acted == len(items)
        return StorageResult(ok, f"{action}: {acted}/{len(items)} file", acted=acted)

    def run_due_jobs(self) -> list[StorageResult]:
        results = []
        for job in self.repo.list_due_retention_jobs():
            result = self.scan(int(job["storage_id"]), int(job["retention_days"]))
            self.repo.set_retention_last_run(int(job["storage_id"]), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
            results.append(result)
            # Automatic destructive actions are deliberately not performed.
            if job["action"] in {"archive", "delete"}:
                log.warning("Retention job %s found files but requires explicit action; no automatic deletion/archive", job["id"])
        return results
