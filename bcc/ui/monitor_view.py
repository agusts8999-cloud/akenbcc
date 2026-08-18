"""Monitor capacity & remote logs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from bcc.services.monitor_service import MonitorService

if TYPE_CHECKING:
    from bcc.db.repository import Repository


class MonitorView(ctk.CTkFrame):
    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.app = app
        self.monitor = MonitorService(repo)

        ctk.CTkLabel(
            self, text="Monitor kapasitas & log", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=8)
        self.target_menu = ctk.CTkOptionMenu(bar, values=["(pilih target)"])
        self.target_menu.pack(side="left", padx=4)
        self.source_menu = ctk.CTkOptionMenu(bar, values=["(pilih sumber)"])
        self.source_menu.pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Disk target", command=self._disk).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Log sumber", command=self._logs).pack(side="left", padx=4)

        self.out = ctk.CTkTextbox(self)
        self.out.pack(fill="both", expand=True)

        self._tmap: dict[str, Optional[int]] = {}
        self._smap: dict[str, Optional[int]] = {}

    def refresh(self) -> None:
        targets = self.repo.list_targets()
        sources = self.repo.list_sources()
        tlabels = [f"{t['id']}: {t['label']}" for t in targets] or ["(pilih target)"]
        slabels = [f"{s['id']}: {s['label']}" for s in sources] or ["(pilih sumber)"]
        self._tmap = {f"{t['id']}: {t['label']}": t["id"] for t in targets}
        self._smap = {f"{s['id']}: {s['label']}": s["id"] for s in sources}
        self.target_menu.configure(values=tlabels)
        self.source_menu.configure(values=slabels)
        if tlabels:
            self.target_menu.set(tlabels[0])
        if slabels:
            self.source_menu.set(slabels[0])

    def _disk(self) -> None:
        tid = self._tmap.get(self.target_menu.get())
        if not tid:
            return
        self.out.insert("end", "Checking disk...\n")

        def work() -> None:
            r = self.monitor.check_target_disk(tid)
            text = r.stdout or r.message
            self.app.post_ui(lambda: self.out.insert("end", text + "\n\n"))

        self.app.run_async(work, "Cek disk target")

    def _logs(self) -> None:
        sid = self._smap.get(self.source_menu.get())
        if not sid:
            return
        self.out.insert("end", "Fetching logs...\n")

        def work() -> None:
            r = self.monitor.check_source_logs(sid)
            text = r.stdout or r.message
            self.app.post_ui(lambda: self.out.insert("end", text + "\n\n"))

        self.app.run_async(work, "Ambil log sumber")
