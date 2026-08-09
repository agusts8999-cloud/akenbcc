"""List remote directories for File backup browser (path-clamped)."""

from __future__ import annotations

import re
from typing import Any, Optional

from bcc.db.repository import Repository
from bcc.services.ssh_service import SSHService


def _shell_quote(path: str) -> str:
    return "'" + path.replace("'", "'\"'\"'") + "'"


def _norm_abs(path: str) -> str:
    """POSIX-style abs path without resolving symlinks locally."""
    p = (path or "").replace("\\", "/").strip()
    if not p:
        return "/"
    if not p.startswith("/"):
        p = "/" + p
    parts: list[str] = []
    for seg in p.split("/"):
        if not seg or seg == ".":
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return "/" + "/".join(parts) if parts else "/"


def _under_root(root: str, path: str) -> bool:
    r = _norm_abs(root).rstrip("/") or "/"
    p = _norm_abs(path)
    if r == "/":
        return p.startswith("/")
    return p == r or p.startswith(r + "/")


def human_size(n: int) -> str:
    x = float(max(0, n))
    for unit in ("B", "K", "M", "G", "T"):
        if x < 1024.0 or unit == "T":
            if unit == "B":
                return f"{int(x)} B"
            return f"{x:.1f} {unit}"
        x /= 1024.0
    return f"{x:.1f} T"


class BrowseService:
    MODE_BACKUP = "backup"
    MODE_SOURCE = "source"
    # Max folder depth below source root for mode source (safety)
    SOURCE_MAX_DEPTH = 3

    def __init__(self, repo: Repository, ssh: Optional[SSHService] = None) -> None:
        self.repo = repo
        self.ssh = ssh or SSHService()

    def root_for(self, source_id: int, mode: str) -> dict[str, Any]:
        """
        Resolve SSH endpoint + root path for a source and mode.
        Returns ok, message, host, username, password, port, key_path, root, max_depth.
        """
        source = self.repo.get_source(source_id)
        if not source:
            return {"ok": False, "message": "Sumber tidak ada"}

        if mode == self.MODE_BACKUP:
            tid = source.get("target_id")
            if not tid:
                return {"ok": False, "message": "Sumber belum di-link ke server backup"}
            target = self.repo.get_target(int(tid))
            if not target:
                return {"ok": False, "message": "Server backup tidak ditemukan"}
            base = (target.get("base_path") or "/home/backupuser/backups").rstrip("/")
            label = (source.get("source_label") or source.get("host") or "unknown").strip()
            root = f"{base}/{label}"
            return {
                "ok": True,
                "message": "OK",
                "mode": mode,
                "host": target["host"],
                "username": target["username"],
                "password": self.repo.target_password(target),
                "port": int(target.get("port") or 22),
                "key_path": target.get("key_path") or "",
                "root": _norm_abs(root),
                "max_depth": None,
                "source_label": label,
                "endpoint_label": f"{target.get('label')} ({target['host']})",
            }

        # mode source
        if source.get("role") != "linux_vps":
            return {
                "ok": False,
                "message": (
                    "Mode mesin sumber hanya untuk linux_vps. "
                    "Untuk Windows, lihat folder di server backup."
                ),
            }
        root = (source.get("web_root") or "/www/wwwroot").rstrip("/") or "/www/wwwroot"
        return {
            "ok": True,
            "message": "OK",
            "mode": mode,
            "host": source["host"],
            "username": source["username"],
            "password": self.repo.source_password(source),
            "port": int(source.get("port") or 22),
            "key_path": source.get("key_path") or "",
            "root": _norm_abs(root),
            "max_depth": self.SOURCE_MAX_DEPTH,
            "source_label": source.get("source_label") or "",
            "endpoint_label": f"{source.get('label')} ({source['host']})",
            "sudo_password": self.repo.source_password(source)
            if source["username"] != "root"
            else "",
        }

    def clamp_path(self, root: str, path: str, max_depth: Optional[int] = None) -> str:
        r = _norm_abs(root)
        p = _norm_abs(path or root)
        if not _under_root(r, p):
            return r
        if max_depth is not None:
            # depth of path relative to root
            if r == "/":
                rel_parts = [x for x in p.split("/") if x]
            else:
                rel = p[len(r) :].lstrip("/")
                rel_parts = [x for x in rel.split("/") if x] if rel else []
            if len(rel_parts) > max_depth:
                # clamp to max_depth
                if r == "/":
                    p = "/" + "/".join(rel_parts[:max_depth])
                else:
                    p = r + "/" + "/".join(rel_parts[:max_depth])
                p = _norm_abs(p)
        return p

    def parent_path(self, root: str, path: str, max_depth: Optional[int] = None) -> str:
        p = self.clamp_path(root, path, max_depth)
        r = _norm_abs(root)
        if p == r or p == "/":
            return r
        parent = _norm_abs(p.rsplit("/", 1)[0] or "/")
        return self.clamp_path(root, parent, max_depth)

    def list_dir(
        self,
        source_id: int,
        mode: str,
        path: Optional[str] = None,
    ) -> dict[str, Any]:
        ctx = self.root_for(source_id, mode)
        if not ctx.get("ok"):
            return {
                "ok": False,
                "message": ctx.get("message") or "Gagal",
                "path": "",
                "root": "",
                "entries": [],
            }

        root = ctx["root"]
        max_depth = ctx.get("max_depth")
        cur = self.clamp_path(root, path or root, max_depth)

        # Ensure dir exists; list
        q = _shell_quote(cur)
        cmd = (
            f"if [ ! -d {q} ]; then "
            f"  echo '===ERR==='; echo 'NOT_DIR'; exit 2; "
            f"fi; "
            f"echo '===LIST==='; "
            f"find {q} -maxdepth 1 -mindepth 1 "
            f"-printf '%y|%s|%TY-%Tm-%Td %TH:%TM|%f\\n' 2>/dev/null | sort; "
            f"echo '===END==='"
        )
        sudo = ctx.get("sudo_password") or ""
        r = self.ssh.run(
            host=ctx["host"],
            username=ctx["username"],
            command=cmd,
            port=int(ctx["port"]),
            password=ctx.get("password") or "",
            key_path=ctx.get("key_path") or "",
            sudo_password=sudo,
            timeout=60,
        )

        out = r.stdout or ""
        if "NOT_DIR" in out or (not r.ok and "===LIST===" not in out):
            # try fallback / mkdir empty
            if "NOT_DIR" in out:
                return {
                    "ok": False,
                    "message": f"Path tidak ada atau bukan folder: {cur}",
                    "path": cur,
                    "root": root,
                    "entries": [],
                    "endpoint_label": ctx.get("endpoint_label"),
                }
            # fallback ls
            return self._list_fallback(ctx, cur, root)

        entries = self._parse_find(out)
        if not entries and "===LIST===" in out and "===END===" in out:
            # empty dir is ok
            pass
        elif not entries and r.ok is False:
            fb = self._list_fallback(ctx, cur, root)
            if fb.get("entries") or not fb.get("ok"):
                return fb

        return {
            "ok": True,
            "message": f"{len(entries)} item",
            "path": cur,
            "root": root,
            "entries": entries,
            "endpoint_label": ctx.get("endpoint_label"),
            "mode": mode,
        }

    def _list_fallback(self, ctx: dict[str, Any], cur: str, root: str) -> dict[str, Any]:
        q = _shell_quote(cur)
        cmd = f"ls -la {q} 2>&1"
        r = self.ssh.run(
            host=ctx["host"],
            username=ctx["username"],
            command=cmd,
            port=int(ctx["port"]),
            password=ctx.get("password") or "",
            key_path=ctx.get("key_path") or "",
            sudo_password=ctx.get("sudo_password") or "",
            timeout=60,
        )
        if not r.ok and not r.stdout:
            return {
                "ok": False,
                "message": r.message or "SSH gagal",
                "path": cur,
                "root": root,
                "entries": [],
                "endpoint_label": ctx.get("endpoint_label"),
            }
        entries = self._parse_ls_la(r.stdout or "")
        return {
            "ok": True,
            "message": f"{len(entries)} item (ls fallback)",
            "path": cur,
            "root": root,
            "entries": entries,
            "endpoint_label": ctx.get("endpoint_label"),
        }

    @staticmethod
    def _parse_find(out: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        in_list = False
        for line in out.splitlines():
            if line.strip() == "===LIST===":
                in_list = True
                continue
            if line.strip() == "===END===":
                in_list = False
                continue
            if not in_list:
                continue
            # type|size|mtime|name  — name may contain |
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue
            y, size_s, mtime, name = parts[0], parts[1], parts[2], parts[3]
            if not name or name in (".", ".."):
                continue
            is_dir = y.strip().lower() in ("d", "directory")
            try:
                size = int(size_s)
            except ValueError:
                size = 0
            entries.append(
                {
                    "name": name,
                    "is_dir": is_dir,
                    "size": size,
                    "mtime": mtime.strip(),
                }
            )
        # dirs first then name
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries

    @staticmethod
    def _parse_ls_la(out: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        # -rw-r--r-- 1 user group 123 Jan 1 12:00 name
        pat = re.compile(
            r"^([dl\-])[rwxstST\-]{9}\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\S+\s+\S+\s+\S+)\s+(.+)$"
        )
        for line in out.splitlines():
            m = pat.match(line.strip())
            if not m:
                continue
            kind, size_s, mtime, name = m.group(1), m.group(2), m.group(3), m.group(4)
            if name in (".", ".."):
                continue
            # strip symlink " -> "
            if " -> " in name:
                name = name.split(" -> ", 1)[0]
            entries.append(
                {
                    "name": name,
                    "is_dir": kind == "d",
                    "size": int(size_s),
                    "mtime": mtime,
                }
            )
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries
