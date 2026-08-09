"""Settings tab."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from bcc import APP_ID, APP_NAME
from bcc.paths import app_data_dir, db_path, logo_png, templates_dir
from bcc.services.tailscale_service import TailscaleService
from bcc.version import build_string, full_version, version_string

if TYPE_CHECKING:
    from bcc.db.repository import Repository


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo

        ctk.CTkLabel(
            self, text="Pengaturan", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")

        info = ctk.CTkTextbox(self, height=300)
        info.pack(fill="x", pady=8)
        ts = TailscaleService().status()
        info.insert(
            "end",
            f"{APP_NAME}\n"
            f"App ID: {APP_ID}\n"
            f"Version: {version_string()}\n"
            f"Build: {build_string()}\n"
            f"Full: {full_version()}\n"
            f"EXE name pattern: {APP_ID}-{full_version()}.exe\n\n"
            f"Logo: {logo_png()}\n"
            f"Data dir: {app_data_dir()}\n"
            f"Database: {db_path()}\n"
            f"Templates: {templates_dir()}\n"
            f"Log: {app_data_dir() / 'bcc.log'}\n\n"
            f"Tailscale installed: {ts.installed}\n"
            f"Tailscale running: {ts.running}\n"
            f"IPv4: {ts.ipv4 or '-'}\n\n"
            "Prinsip: BCC adalah support & monitoring.\n"
            "Cron / Task Scheduler di sumber menjalankan backup secara mandiri.\n\n"
            "Retensi default script: 7 hari (template config).\n"
            "Dev: python -m bcc\n"
            "Build: python build_exe.py\n",
        )
        info.configure(state="disabled")

        ctk.CTkLabel(self, text="Ambang alert disk (GB)", anchor="w").pack(anchor="w")
        self.thresh = ctk.CTkEntry(self, width=120)
        self.thresh.insert(0, self.repo.get_setting("disk_alert_gb", "20"))
        self.thresh.pack(anchor="w", pady=4)
        ctk.CTkButton(self, text="Simpan setting", command=self._save).pack(anchor="w", pady=8)
        self.msg = ctk.CTkLabel(self, text="")
        self.msg.pack(anchor="w")

    def refresh(self) -> None:
        self.thresh.delete(0, "end")
        self.thresh.insert(0, self.repo.get_setting("disk_alert_gb", "20"))

    def _save(self) -> None:
        self.repo.set_setting("disk_alert_gb", self.thresh.get().strip() or "20")
        self.msg.configure(text="Tersimpan.")
