"""Main window & navigation with logo, version branding, and data refresh."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable, Optional

import customtkinter as ctk
from PIL import Image

from bcc.db.repository import Repository
from bcc.paths import logo_ico, logo_png
from bcc.ui.dashboard_view import DashboardView
from bcc.ui.files_view import FilesView
from bcc.ui.monitor_view import MonitorView
from bcc.ui.schedules_view import SchedulesView
from bcc.ui.settings_view import SettingsView
from bcc.ui.storage_view import StorageView
from bcc.ui.sources_view import SourcesView
from bcc.ui.targets_view import TargetsView
from bcc.version import display_title, ui_version_line

log = logging.getLogger(__name__)


class MainWindow(ctk.CTk):
    def __init__(self, repo: Repository) -> None:
        super().__init__()
        self.repo = repo
        self._current_view = "Dashboard"
        self._ui_queue: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._job_queue: deque[tuple[str, str, Callable[[], Any]]] = deque()
        self._active_job_key: Optional[str] = None
        self._active_job_started = 0.0
        self._busy_cycle = 0
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
        self.lbl_busy = ctk.CTkLabel(
            text_col, text="", font=ctk.CTkFont(size=10), text_color="#4da3ff", anchor="w"
        )
        self.busy_bar = ctk.CTkProgressBar(text_col, width=145, height=8, mode="indeterminate")
        self._busy_count = 0
        self._busy_label = "Memproses"
        self._busy_lock = threading.Lock()

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
            ("Storage", StorageView),
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

        self.refresh_button = ctk.CTkButton(
            self.sidebar,
            text="Refresh data (F5)",
            command=self.refresh_all,
            height=32,
        )
        self.refresh_button.grid(row=8, column=0, padx=10, pady=(12, 4), sticky="ew")

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
            if self._active_job_key is None:
                self.refresh_all()
            return "break"

        self.bind_all("<F5>", _kb_refresh)
        self.bind_all("<Control-r>", _kb_refresh)
        self.bind_all("<Control-R>", _kb_refresh)

        self.busy_overlay = ctk.CTkFrame(self, corner_radius=0, fg_color=("#eef2f7", "#111827"))
        busy_card = ctk.CTkFrame(self.busy_overlay, width=390, height=170, corner_radius=12)
        busy_card.place(relx=0.5, rely=0.5, anchor="center")
        busy_card.pack_propagate(False)
        self.overlay_title = ctk.CTkLabel(
            busy_card, text="Sedang memproses", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.overlay_title.pack(pady=(28, 8))
        self.overlay_detail = ctk.CTkLabel(busy_card, text="Mohon tunggu…", text_color="gray")
        self.overlay_detail.pack(pady=(0, 10))
        self.overlay_bar = ctk.CTkProgressBar(busy_card, width=300, mode="indeterminate")
        self.overlay_bar.pack(pady=4)

        # Tk APIs are only touched by this poller on the main thread. Workers
        # communicate through post_ui(), never through widget.after().
        self.after(50, self._poll_ui_queue)
        self.show("Dashboard")

    def begin_busy(self, label: str = "Memproses") -> None:
        """Show the global indeterminate progress indicator."""
        with self._busy_lock:
            self._busy_count += 1
            self._busy_label = label
            self._busy_cycle += 1
        self._render_busy()

    def end_busy(self) -> None:
        """Hide the indicator when the last background operation finishes."""
        with self._busy_lock:
            self._busy_count = max(0, self._busy_count - 1)
        self._render_busy()

    def _render_busy(self) -> None:
        with self._busy_lock:
            active = self._busy_count > 0
            label = self._busy_label
        if active:
            self.lbl_busy.configure(text=f"⟳ {label}…")
            if not self.busy_bar.winfo_ismapped():
                self.busy_bar.pack(anchor="w", pady=(2, 0))
            self.busy_bar.start()
            self.overlay_title.configure(text=label)
            self.overlay_detail.configure(text="Mohon tunggu… · 0 detik")
            self.busy_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.busy_overlay.lift()
            self.overlay_bar.start()
            for btn in self._nav_buttons:
                btn.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            self._update_busy_elapsed(self._busy_cycle)
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()
            self.lbl_busy.configure(text="")
            self.overlay_bar.stop()
            self.busy_overlay.place_forget()
            for btn in self._nav_buttons:
                btn.configure(state="normal")
            self.refresh_button.configure(state="normal")

    def post_ui(self, callback: Callable[[], None]) -> None:
        """Queue a callback for execution by Tk's main thread."""
        self._ui_queue.put(callback)

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                callback = self._ui_queue.get_nowait()
                try:
                    callback()
                except Exception:
                    log.exception("UI callback failed")
        except queue.Empty:
            pass
        try:
            self.after(50, self._poll_ui_queue)
        except Exception:
            pass

    def run_async(
        self,
        work: Callable[[], Any],
        label: str = "Memproses",
        job_key: Optional[str] = None,
    ) -> Optional[threading.Thread]:
        """Queue background work; only one long operation runs at a time."""
        if threading.current_thread() is not threading.main_thread():
            self.post_ui(lambda: self.run_async(work, label, job_key))
            return None

        key = job_key or label
        queued_keys = {item[0] for item in self._job_queue}
        if key == self._active_job_key or key in queued_keys:
            log.info("Background operation already active/queued: %s", key)
            return None
        self._job_queue.append((key, label, work))
        if self._active_job_key is None:
            return self._start_next_job()
        return None

    def _start_next_job(self) -> Optional[threading.Thread]:
        if self._active_job_key is not None or not self._job_queue:
            return None
        key, label, work = self._job_queue.popleft()
        self._active_job_key = key
        self._active_job_started = time.monotonic()
        self.begin_busy(label)

        def wrapped() -> None:
            try:
                work()
            except Exception:
                log.exception("Background operation failed: %s", label)
            finally:
                self.post_ui(self._complete_active_job)

        thread = threading.Thread(target=wrapped, daemon=True)
        thread.start()
        return thread

    def _complete_active_job(self) -> None:
        self.end_busy()
        self._active_job_key = None
        self._active_job_started = 0.0
        self._start_next_job()

    def _update_busy_elapsed(self, cycle: int) -> None:
        if self._active_job_key is None or cycle != self._busy_cycle:
            return
        elapsed = max(0, int(time.monotonic() - self._active_job_started))
        waiting = len(self._job_queue)
        suffix = f" · {waiting} proses menunggu" if waiting else ""
        self.overlay_detail.configure(text=f"Mohon tunggu… · {elapsed} detik{suffix}")
        self.after(500, lambda: self._update_busy_elapsed(cycle))

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
        if self._active_job_key is not None:
            return
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
        """Reload only the visible tab to avoid hidden network/render work."""
        if self._active_job_key is not None:
            return
        self.refresh_current()

    def _stamp_refresh(self) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.lbl_refresh.configure(text=f"Terakhir refresh: {ts}")
