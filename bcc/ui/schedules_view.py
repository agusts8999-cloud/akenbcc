"""Jadwal tab — simpan lokal + push cron ke aaPanel (CustomTkinter)."""

from __future__ import annotations

import tkinter.messagebox as mb
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from bcc.services.deploy_service import DeployService

if TYPE_CHECKING:
    from bcc.db.repository import Repository


class SchedulesView(ctk.CTkFrame):
    """Simpan jadwal lokal + push cron ke aaPanel (per baris / massal)."""

    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.app = app
        self.deploy = DeployService(repo)
        self._rows: list[dict[str, Any]] = []

        ctk.CTkLabel(
            self, text="Jadwal", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            self,
            text=(
                "Jadwal harian (jam server sumber). "
                "Simpan lokal = SQLite; push = cron di aaPanel / root crontab."
            ),
            text_color="gray",
            wraplength=800,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x")
        ctk.CTkButton(bar, text="Refresh", width=90, command=self.refresh).pack(
            side="left", padx=3
        )
        ctk.CTkButton(
            bar, text="Auto-stagger + push", width=140, command=self._auto_stagger
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            bar, text="Push semua ke aaPanel", width=150, command=self._push_all
        ).pack(side="left", padx=3)
        self._auto_push = ctk.CTkCheckBox(
            bar, text="Auto-push ke aaPanel setelah simpan (sumber aaPanel)"
        )
        self._auto_push.select()
        self._auto_push.pack(side="left", padx=12)

        # header
        head = ctk.CTkFrame(self)
        head.pack(fill="x", pady=(10, 2))
        for i, label in enumerate(
            ["ID", "Host", "Label", "Web H", "Web M", "DB H", "DB M", "Aksi"]
        ):
            ctk.CTkLabel(head, text=label, font=ctk.CTkFont(weight="bold"), width=70 if i < 7 else 280).grid(
                row=0, column=i, padx=2, sticky="w"
            )

        self.listbox = ctk.CTkScrollableFrame(self, height=280)
        self.listbox.pack(fill="both", expand=True, pady=4)

        ctk.CTkLabel(self, text="Log push:").pack(anchor="w")
        self.log = ctk.CTkTextbox(self, height=140)
        self.log.pack(fill="x", pady=(0, 8))

        self.refresh()

    def _append_log(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def refresh(self) -> None:
        for w in self.listbox.winfo_children():
            w.destroy()
        self._rows.clear()

        sources = [s for s in self.repo.list_sources() if s.get("role") == "linux_vps"]
        for s in sources:
            sch = self.repo.get_schedule(int(s["id"])) or {}
            row_f = ctk.CTkFrame(self.listbox, fg_color="transparent")
            row_f.pack(fill="x", pady=2)
            sid = int(s["id"])
            ctk.CTkLabel(row_f, text=str(sid), width=40).grid(row=0, column=0, padx=2)
            ctk.CTkLabel(row_f, text=s["host"], width=110, anchor="w").grid(
                row=0, column=1, padx=2
            )
            ctk.CTkLabel(
                row_f, text=(s.get("source_label") or "")[:22], width=130, anchor="w"
            ).grid(row=0, column=2, padx=2)

            entries: dict[str, ctk.CTkEntry] = {}
            for col, key, default, hi in [
                (3, "web_hour", 2, 23),
                (4, "web_minute", 0, 59),
                (5, "db_hour", 3, 23),
                (6, "db_minute", 0, 59),
            ]:
                e = ctk.CTkEntry(row_f, width=48)
                val = int(sch.get(key, default))
                e.insert(0, str(val))
                e.grid(row=0, column=col, padx=2)
                entries[key] = e

            acts = ctk.CTkFrame(row_f, fg_color="transparent")
            acts.grid(row=0, column=7, padx=2)
            ctk.CTkButton(
                acts,
                text="Simpan lokal",
                width=90,
                command=lambda i=sid, en=entries: self._save_row(i, en, push=False),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                acts,
                text="Push",
                width=55,
                command=lambda i=sid: self._push_one(i),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                acts,
                text="Simpan+push",
                width=100,
                command=lambda i=sid, en=entries: self._save_row(i, en, push=True),
            ).pack(side="left", padx=2)

            self._rows.append({"id": sid, "entries": entries})

    def _read_entries(self, entries: dict[str, ctk.CTkEntry]) -> dict[str, int]:
        def _n(key: str, default: int, hi: int) -> int:
            try:
                v = int((entries[key].get() or str(default)).strip())
            except ValueError:
                v = default
            return max(0, min(hi, v))

        return {
            "web_hour": _n("web_hour", 2, 23),
            "web_minute": _n("web_minute", 0, 59),
            "db_hour": _n("db_hour", 3, 23),
            "db_minute": _n("db_minute", 0, 59),
        }

    def _save_row(
        self, source_id: int, entries: dict[str, ctk.CTkEntry], push: bool = False
    ) -> None:
        times = self._read_entries(entries)
        self.repo.update_schedule(source_id, **times)
        src = self.repo.get_source(source_id) or {}
        self._append_log(
            f"Lokal OK #{source_id} {src.get('host')}: "
            f"web={times['web_hour']:02d}:{times['web_minute']:02d} "
            f"db={times['db_hour']:02d}:{times['db_minute']:02d}"
        )
        do_push = push or (
            bool(self._auto_push.get()) and bool(src.get("aapanel"))
        )
        if do_push:
            self._push_one(source_id)
        else:
            mb.showinfo("Jadwal", f"Jadwal lokal disimpan untuk #{source_id}")

    def _push_one(self, source_id: int) -> None:
        self._append_log(f"Push cron → source #{source_id} …")

        def work() -> None:
            r = self.deploy.push_aapanel_schedule(source_id)
            src = self.repo.get_source(source_id) or {}
            host = src.get("host") or str(source_id)
            msg = ("OK: " if r.ok else "GAGAL: ") + r.message
            self.app.post_ui(lambda: self._append_log(msg))
            if r.stdout:
                self.app.post_ui(lambda: self._append_log(r.stdout[-500:]))
            self.app.post_ui(
                lambda: mb.showinfo("Push aaPanel", f"Cron OK: {host}\n{r.message}")
                if r.ok
                else mb.showerror("Push aaPanel", f"Gagal: {host}\n{r.message}"),
            )

        self.app.run_async(work, "Push jadwal aaPanel")

    def _push_all(self) -> None:
        self._append_log("=== Push semua ke aaPanel ===")

        def work() -> None:
            ok_n = fail_n = 0
            for s in self.repo.list_sources():
                if s.get("role") != "linux_vps":
                    continue
                sid = int(s["id"])
                r = self.deploy.push_aapanel_schedule(sid)
                line = f"{'OK' if r.ok else 'FAIL'} {s['host']}: {r.message}"
                self.app.post_ui(lambda m=line: self._append_log(m))
                if r.ok:
                    ok_n += 1
                else:
                    fail_n += 1
            self.app.post_ui(
                lambda: mb.showinfo(
                    "Push semua",
                    f"Selesai. Sukses={ok_n}, Gagal={fail_n}. Lihat Log push.",
                ),
            )

        self.app.run_async(work, "Push semua jadwal")

    def _auto_stagger(self) -> None:
        sources = [s for s in self.repo.list_sources() if s.get("role") == "linux_vps"]
        base_web = 2 * 60
        for i, s in enumerate(sources):
            web = base_web + i * 90
            db = web + 60
            wh, wm = divmod(web % (24 * 60), 60)
            dh, dm = divmod(db % (24 * 60), 60)
            self.repo.update_schedule(int(s["id"]), wh, wm, dh, dm)
            self._append_log(
                f"Stagger #{s['id']} {s['host']}: web={wh:02d}:{wm:02d} db={dh:02d}:{dm:02d}"
            )
        self.refresh()
        self._push_all()
