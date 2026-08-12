"""Backup servers (targets) tab."""

from __future__ import annotations

import threading
import tkinter.messagebox as mb
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from bcc.services.ssh_service import SSHService
from bcc.services.tailscale_service import TailscaleService

if TYPE_CHECKING:
    from bcc.db.repository import Repository


class TargetsView(ctk.CTkFrame):
    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.ssh = SSHService()
        self.selected_id: Optional[int] = None

        ctk.CTkLabel(
            self, text="Server Backup", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            self,
            text="Tujuan remote untuk rsync/scp (contoh Webmin + backupuser).",
            text_color="gray",
        ).pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=8)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.listbox = ctk.CTkScrollableFrame(left, width=260)
        self.listbox.pack(fill="both", expand=True, padx=4, pady=4)

        form = ctk.CTkFrame(body)
        form.grid(row=0, column=1, sticky="nsew")
        self.entries: dict[str, ctk.CTkEntry] = {}
        fields = [
            ("label", "Label"),
            ("host", "Host (Tailscale IP)"),
            ("port", "Port"),
            ("username", "User SSH"),
            ("password", "Password (opsional)"),
            ("base_path", "Base path backup"),
            ("webmin_url", "Webmin URL (kosong = https://host:10000)"),
            ("notes", "Catatan"),
        ]
        for i, (key, label) in enumerate(fields):
            ctk.CTkLabel(form, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            show = "*" if key == "password" else None
            e = ctk.CTkEntry(form, width=320, show=show)
            e.grid(row=i, column=1, sticky="ew", padx=8, pady=4)
            self.entries[key] = e
        form.grid_columnconfigure(1, weight=1)

        self.entries["port"].insert(0, "22")
        self.entries["base_path"].insert(0, "/home/backupuser/backups")
        self.entries["username"].insert(0, "backupuser")

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=len(fields), column=0, columnspan=2, pady=12)
        ctk.CTkButton(btns, text="Refresh", width=80, command=self.refresh).pack(
            side="left", padx=4
        )
        ctk.CTkButton(btns, text="Baru", width=80, command=self._new).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Simpan", width=80, command=self._save).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Hapus", width=80, command=self._delete).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Test SSH", width=100, command=self._test).pack(
            side="left", padx=4
        )

        self.status = ctk.CTkLabel(form, text="", text_color="gray")
        self.status.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", padx=8)

    def refresh(self) -> None:
        for w in self.listbox.winfo_children():
            w.destroy()
        for t in self.repo.list_targets():
            badge = ""
            if TailscaleService.is_tailscale_ip(t["host"]):
                badge = " [TS]"
            b = ctk.CTkButton(
                self.listbox,
                text=f"{t['label']} ({t['host']}){badge}",
                anchor="w",
                command=lambda i=t["id"]: self._select(i),
            )
            b.pack(fill="x", pady=2)

    def _new(self) -> None:
        self.selected_id = None
        for k, e in self.entries.items():
            e.delete(0, "end")
        self.entries["port"].insert(0, "22")
        self.entries["base_path"].insert(0, "/home/backupuser/backups")
        self.entries["username"].insert(0, "backupuser")

    def _select(self, tid: int) -> None:
        t = self.repo.get_target(tid)
        if not t:
            return
        self.selected_id = tid
        mapping = {
            "label": t["label"],
            "host": t["host"],
            "port": str(t["port"]),
            "username": t["username"],
            "password": "",
            "base_path": t["base_path"],
            "webmin_url": t.get("webmin_url") or "",
            "notes": t.get("notes") or "",
        }
        for k, v in mapping.items():
            self.entries[k].delete(0, "end")
            self.entries[k].insert(0, v)

    def _save(self) -> None:
        data = {k: e.get().strip() for k, e in self.entries.items()}
        if not data["label"] or not data["host"] or not data["username"]:
            mb.showwarning("Validasi", "Label, host, username wajib.")
            return
        port = int(data["port"] or "22")
        if self.selected_id:
            kwargs = {
                "label": data["label"],
                "host": data["host"],
                "port": port,
                "username": data["username"],
                "base_path": data["base_path"],
                "webmin_url": data.get("webmin_url") or "",
                "notes": data["notes"],
            }
            if data["password"]:
                kwargs["password"] = data["password"]
            self.repo.update_target(self.selected_id, **kwargs)
        else:
            self.selected_id = self.repo.add_target(
                label=data["label"],
                host=data["host"],
                username=data["username"],
                base_path=data["base_path"] or "/home/backupuser/backups",
                port=port,
                password=data["password"],
                notes=data["notes"],
                webmin_url=data.get("webmin_url") or "",
            )
        self.status.configure(text="Tersimpan.")
        self.refresh()

    def _delete(self) -> None:
        if not self.selected_id:
            return
        if mb.askyesno("Hapus", "Hapus server backup ini?"):
            self.repo.soft_delete_target(self.selected_id)
            self._new()
            self.refresh()

    def _test(self) -> None:
        data = {k: e.get().strip() for k, e in self.entries.items()}
        pw = data["password"]
        tid = self.selected_id
        if tid:
            t = self.repo.get_target(tid)
            if t and not pw:
                pw = self.repo.target_password(t)

        def work() -> None:
            from datetime import datetime, timezone

            r = self.ssh.test(
                data["host"], data["username"], int(data["port"] or 22), password=pw
            )
            if tid:
                now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                self.repo.update_target(
                    tid, last_ssh_ok=1 if r.ok else 0, last_ssh_at=now
                )
            self.after(0, lambda: self.status.configure(text=r.message))
            self.after(
                0,
                lambda: mb.showinfo("Test SSH", r.message)
                if r.ok
                else mb.showerror("Test SSH", r.message),
            )
            self.after(0, self.refresh)

        self.status.configure(text="Testing...")
        threading.Thread(target=work, daemon=True).start()
