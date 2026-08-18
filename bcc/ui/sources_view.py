"""Sources (VPS / PC) tab."""

from __future__ import annotations

import tkinter.filedialog as fd
import tkinter.messagebox as mb
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from bcc.services.deploy_service import DeployService
from bcc.services.monitor_service import MonitorService
from bcc.services.backup_service import BackupService
from bcc.services.ssh_service import SSHService
from bcc.services.tailscale_service import TailscaleService

if TYPE_CHECKING:
    from bcc.db.repository import Repository


class SourcesView(ctk.CTkFrame):
    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.app = app
        self.ssh = SSHService()
        self.deploy = DeployService(repo)
        self.monitor = MonitorService(repo)
        self.backup = BackupService(repo)
        self.selected_id: Optional[int] = None

        ctk.CTkLabel(
            self, text="Sumber VPS / PC", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=8)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.listbox = ctk.CTkScrollableFrame(left, width=280)
        self.listbox.pack(fill="both", expand=True, padx=4, pady=4)

        form = ctk.CTkScrollableFrame(body)
        form.grid(row=0, column=1, sticky="nsew")
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.role = ctk.CTkOptionMenu(form, values=["linux_vps", "windows_pc"])
        self.aapanel = ctk.CTkCheckBox(form, text="aaPanel (daftar cron via panel)")
        self.aapanel.select()
        self.target_menu = ctk.CTkOptionMenu(form, values=["(none)"])
        self._target_ids: dict[str, Optional[int]] = {"(none)": None}

        row = 0
        ctk.CTkLabel(form, text="Role").grid(row=row, column=0, sticky="w", padx=6, pady=3)
        self.role.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        row += 1
        ctk.CTkLabel(form, text="Backup target").grid(row=row, column=0, sticky="w", padx=6)
        self.target_menu.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        row += 1
        self.aapanel.grid(row=row, column=1, sticky="w", padx=6, pady=3)
        row += 1

        fields = [
            ("label", "Label"),
            ("host", "Host"),
            ("port", "Port"),
            ("username", "User SSH"),
            ("password", "Password SSH"),
            ("deploy_path", "Deploy path (Linux)"),
            ("web_root", "Web root"),
            ("source_label", "Remote folder label"),
            ("mysql_user", "MySQL user"),
            ("mysql_password", "MySQL password"),
            ("notes", "Catatan"),
        ]
        for key, label in fields:
            ctk.CTkLabel(form, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=3)
            show = "*" if "password" in key else None
            e = ctk.CTkEntry(form, width=300, show=show)
            e.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
            self.entries[key] = e
            row += 1
        form.grid_columnconfigure(1, weight=1)
        self.entries["port"].insert(0, "22")
        self.entries["deploy_path"].insert(0, "/www/backup-scripts")
        self.entries["web_root"].insert(0, "/www/wwwroot")
        self.entries["username"].insert(0, "ubuntu")
        self.entries["mysql_user"].insert(0, "root")

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=row, column=0, columnspan=2, pady=10)
        for text, cmd in [
            ("Refresh", self.refresh),
            ("Baru", self._new),
            ("Simpan", self._save),
            ("Hapus", self._delete),
            ("Test SSH", self._test),
            ("Deploy Linux", self._deploy),
            ("Jalankan backup penuh", self._run_backup),
            ("Export Windows", self._export_win),
        ]:
            ctk.CTkButton(btns, text=text, width=130, command=cmd).pack(side="left", padx=3)

        self.status = ctk.CTkTextbox(form, height=120)
        self.status.grid(row=row + 1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)

    def refresh(self) -> None:
        targets = self.repo.list_targets()
        labels = ["(none)"] + [f"{t['id']}: {t['label']}" for t in targets]
        self._target_ids = {"(none)": None}
        for t in targets:
            self._target_ids[f"{t['id']}: {t['label']}"] = t["id"]
        self.target_menu.configure(values=labels)

        for w in self.listbox.winfo_children():
            w.destroy()
        for s in self.repo.list_sources():
            ts = "TS" if TailscaleService.is_tailscale_ip(s["host"]) else "noTS"
            ssh = {1: "OK", 0: "FAIL"}.get(s.get("last_ssh_ok"), "?")
            b = ctk.CTkButton(
                self.listbox,
                text=f"[{s['role']}] {s['label']} | SSH {ssh} | {ts}",
                anchor="w",
                command=lambda i=s["id"]: self._select(i),
            )
            b.pack(fill="x", pady=2)

    def _log(self, msg: str) -> None:
        self.status.insert("end", msg + "\n")
        self.status.see("end")

    def _new(self) -> None:
        self.selected_id = None
        for e in self.entries.values():
            e.delete(0, "end")
        self.entries["port"].insert(0, "22")
        self.entries["deploy_path"].insert(0, "/www/backup-scripts")
        self.entries["web_root"].insert(0, "/www/wwwroot")
        self.entries["username"].insert(0, "ubuntu")
        self.entries["mysql_user"].insert(0, "root")
        self.role.set("linux_vps")
        self.aapanel.select()

    def _select(self, sid: int) -> None:
        s = self.repo.get_source(sid)
        if not s:
            return
        self.selected_id = sid
        self.role.set(s["role"])
        if s.get("aapanel"):
            self.aapanel.select()
        else:
            self.aapanel.deselect()
        tid = s.get("target_id")
        choice = "(none)"
        for k, v in self._target_ids.items():
            if v == tid:
                choice = k
                break
        self.target_menu.set(choice)
        vals = {
            "label": s["label"],
            "host": s["host"],
            "port": str(s["port"]),
            "username": s["username"],
            "password": "",
            "deploy_path": s.get("deploy_path") or "",
            "web_root": s.get("web_root") or "",
            "source_label": s.get("source_label") or "",
            "mysql_user": s.get("mysql_user") or "root",
            "mysql_password": "",
            "notes": s.get("notes") or "",
        }
        for k, v in vals.items():
            self.entries[k].delete(0, "end")
            self.entries[k].insert(0, v)

    def _save(self) -> None:
        d = {k: e.get().strip() for k, e in self.entries.items()}
        if not d["label"] or not d["host"]:
            mb.showwarning("Validasi", "Label & host wajib")
            return
        tid = self._target_ids.get(self.target_menu.get())
        port = int(d["port"] or 22)
        if self.selected_id:
            kwargs = dict(
                label=d["label"],
                role=self.role.get(),
                host=d["host"],
                port=port,
                username=d["username"],
                target_id=tid,
                deploy_path=d["deploy_path"],
                web_root=d["web_root"],
                source_label=d["source_label"],
                mysql_user=d["mysql_user"],
                aapanel=bool(self.aapanel.get()),
                notes=d["notes"],
            )
            if d["password"]:
                kwargs["password"] = d["password"]
            if d["mysql_password"]:
                kwargs["mysql_password"] = d["mysql_password"]
            self.repo.update_source(self.selected_id, **kwargs)
        else:
            self.selected_id = self.repo.add_source(
                label=d["label"],
                role=self.role.get(),
                host=d["host"],
                username=d["username"],
                target_id=tid,
                port=port,
                password=d["password"],
                deploy_path=d["deploy_path"] or "/www/backup-scripts",
                web_root=d["web_root"] or "/www/wwwroot",
                source_label=d["source_label"],
                mysql_user=d["mysql_user"],
                mysql_password=d["mysql_password"],
                aapanel=bool(self.aapanel.get()),
                notes=d["notes"],
            )
        self._log("Disimpan.")
        self.refresh()

    def _delete(self) -> None:
        if self.selected_id and mb.askyesno("Hapus", "Hapus sumber ini?"):
            self.repo.soft_delete_source(self.selected_id)
            self._new()
            self.refresh()

    def _test(self) -> None:
        if not self.selected_id:
            mb.showinfo("Info", "Simpan & pilih sumber dulu")
            return

        def work() -> None:
            r = self.monitor.refresh_source_ssh(self.selected_id)
            self.app.post_ui(lambda: self._log(r.message))
            self.app.post_ui(self.refresh)

        self.app.run_async(work, "Test SSH sumber")

    def _deploy(self) -> None:
        if not self.selected_id:
            return
        self._log("Deploy Linux dimulai (bisa lama)...")

        def work() -> None:
            r = self.deploy.deploy_linux(self.selected_id)
            self.app.post_ui(lambda: self._log(r.message))
            if r.stdout:
                self.app.post_ui(lambda: self._log(r.stdout[-1500:]))
            self.app.post_ui(self.refresh)

        self.app.run_async(work, "Deploy Linux")

    def _run_backup(self) -> None:
        if not self.selected_id:
            mb.showinfo("Info", "Pilih sumber Linux dulu")
            return
        s = self.repo.get_source(self.selected_id)
        if not s or s.get("role") != "linux_vps":
            mb.showwarning("Backup", "Hanya untuk linux_vps.")
            return
        if not mb.askyesno(
            "Backup penuh",
            f"Jalankan backup webs+dbs di {s.get('host')}?\nBisa memakan waktu lama.",
        ):
            return
        self._log(f"Backup penuh dimulai di {s.get('host')}...")

        def work() -> None:
            r = self.backup.run_full_backup(self.selected_id)
            self.app.post_ui(lambda: self._log(r.message))
            if r.stdout:
                self.app.post_ui(lambda: self._log(r.stdout[-2000:]))
            self.app.post_ui(
                lambda: mb.showinfo("Backup", r.message)
                if r.ok
                else mb.showerror("Backup", r.message),
            )
            self.app.post_ui(self.refresh)

        self.app.run_async(work, "Backup penuh")

    def _export_win(self) -> None:
        if not self.selected_id:
            return
        dest = fd.askdirectory(title="Folder export paket Windows")
        if not dest:
            return
        try:
            p = self.deploy.export_windows_package(self.selected_id, Path(dest) / "bcc-windows-backup")
            self._log(f"Paket Windows diexport ke: {p}")
            mb.showinfo("Export", f"Selesai:\n{p}\nJalankan Register-BackupTask.ps1 sebagai Admin.")
        except Exception as e:
            mb.showerror("Export", str(e))
