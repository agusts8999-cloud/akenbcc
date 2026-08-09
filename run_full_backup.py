#!/usr/bin/env python3
"""One-shot: full backup one source by host, write BCC run_history."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bcc.db.repository import Repository
from bcc.services.backup_service import BackupService


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "100.70.225.48"
    repo = Repository()
    repo.initialize()
    src = None
    for s in repo.list_sources():
        if s.get("host") == host:
            src = s
            break
    if not src:
        print(f"Source not found: {host}")
        return 1
    sid = int(src["id"])
    print(f"=== Full backup source_id={sid} {host} ===")
    r = BackupService(repo).run_full_backup(sid)
    print(r.message)
    print((r.stdout or "")[-2500:])
    print("--- recent history for source ---")
    for h in repo.recent_history(20):
        if int(h.get("source_id") or 0) == sid:
            print(
                f"{h.get('recorded_at')} [{h.get('status')}] {h.get('run_type')}: "
                f"{(h.get('message') or '')[:160]}"
            )
    return 0 if r.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
