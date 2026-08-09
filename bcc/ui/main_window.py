"""Main window & navigation with logo, version branding, and data refresh."""

from __future__ import annotations

import logging
from datetime import datetime

import customtkinter as ctk
from PIL import Image

from bcc.db.repository import Repository
from bcc.paths import logo_ico, logo_png
from bcc.ui.dashboard_view import DashboardView
from bcc.ui.files_view import FilesView
from bcc.ui.monitor_view import MonitorView
from bcc.ui.schedules_view import SchedulesView
from bcc.ui.settings_view import SettingsView
from bcc.ui.sources_view import SourcesView
from bcc.ui.targets_view import TargetsView
from bcc.version import display_title, ui_version_line

log = logging.getLogger(__name__)


class MainWindow(ctk.CTk):
    def __init__(self, repo: Repository) -> None:
        super().__init__()
        self.repo = repo
        self._current_view = "Dashboard"
        self.title(display_title())
        self.geometry("1100x700")
        self.minsize(900, 560)
        self._apply_window_icon()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=12, pady=(16, 8), sticky="ew")

        self._logo_image = None
        png = logo_png()
        if png.is_file():
            try:
                pil = Image.open(png)
                self._logo_image = ctk.CTkImage(
                    light_image=pil, dark_image=pil, size=(56, 56)
                )
                ctk.CTkLabel(brand, image=self._logo_image, text="").pack(
                    side="left", padx=(0, 8)
                )
            except Exception as e:
                log.warning("Logo load failed: %s", e)

        text_col = ctk.CTkFrame(brand, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            text_col,
            text="Backup\nControl Center",
            font=ctk.CTkFont(size=14, weight="bold"),
            justify="left",
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col,
            text=ui_version_line(),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.views: dict[str, ctk.CTkFrame] = {}
        self._nav_buttons: list[ctk.CTkButton] = []

        items = [
            ("Dashboard", DashboardView),
            ("Server Backup", TargetsView),
            ("Sumber (VPS/PC)", SourcesView),
            ("File backup", FilesView),
            ("Jadwal", SchedulesView),
            ("Monitor", MonitorView),
            ("Pengaturan", SettingsView),
        ]
        for i, (label, cls) in enumerate(items, start=1):
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                command=lambda n=label: self.show(n),
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
            )
            btn.grid(row=i, column=0, padx=10, pady=4, sticky="ew")
            self._nav_buttons.append(btn)
            frame = cls(self.content, repo, self)
            frame.grid(row=0, column=0, sticky="nsew")
            self.views[label] = frame

        ctk.CTkButton(
            self.sidebar,
            text="Refresh data (F5)",
            command=self.refresh_all,
            height=32,
        ).grid(row=8, column=0, padx=10, pady=(12, 4), sticky="ew")

        self.lbl_refresh = ctk.CTkLabel(
            self.sidebar,
            text="Terakhir refresh: —",
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor="w",
            justify="left",
        )
        self.lbl_refresh.grid(row=9, column=0, padx=14, pady=(0, 4), sticky="sw")

        ctk.CTkLabel(
            self.sidebar,
            text="Support & monitoring\nBackup tetap mandiri",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
        ).grid(row=10, column=0, padx=16, pady=(4, 16), sticky="sw")

        # Keyboard shortcuts (bind on content frame — safer than CTk root bind)
        def _kb_refresh(event=None):
            self.refresh_all()
            return "break"

        self.bind_all("<F5>", _kb_refresh)
        self.bind_all("<Control-r>", _kb_refresh)
        self.bind_all("<Control-R>", _kb_refresh)

        self.show("Dashboard")
        self.refresh_all()

    def _apply_window_icon(self) -> None:
        ico = logo_ico()
        png = logo_png()
        try:
            if ico.is_file():
                self.iconbitmap(default=str(ico))
                try:
                    self.wm_iconbitmap(str(ico))
                except Exception:
                    pass
            if png.is_file():
                from tkinter import PhotoImage

                self._icon_photo = PhotoImage(file=str(png))
                self.iconphoto(True, self._icon_photo)
        except Exception as e:
            log.warning("Window icon failed: %s", e)

    def show(self, name: str) -> None:
        self._current_view = name
        for n, v in self.views.items():
            if n == name:
                v.tkraise()
                if hasattr(v, "refresh"):
                    try:
                        v.refresh()
                    except Exception as e:
                        log.warning("refresh %s: %s", name, e)
        for btn in self._nav_buttons:
            if btn.cget("text") == name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")
        self._stamp_refresh()

    def refresh_current(self) -> None:
        v = self.views.get(self._current_view)
        if v is not None and hasattr(v, "refresh"):
            try:
                v.refresh()
            except Exception as e:
                log.warning("refresh_current %s: %s", self._current_view, e)
        self._stamp_refresh()

    def refresh_all(self) -> None:
        """Reload all tabs from SQLite (manual F5 / sidebar button)."""
        for name, v in self.views.items():
            if hasattr(v, "refresh"):
                try:
                    v.refresh()
                except Exception as e:
                    log.warning("refresh_all %s: %s", name, e)
        self._stamp_refresh()
        # Keep current tab on top
        cur = self.views.get(self._current_view)
        if cur is not None:
            cur.tkraise()

    def _stamp_refresh(self) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.lbl_refresh.configure(text=f"Terakhir refresh: {ts}")
