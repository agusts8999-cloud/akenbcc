"""Browse backup or source files for a selected server/PC."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Optional

import customtkinter as ctk

from bcc.services.browse_service import BrowseService, human_size

if TYPE_CHECKING:
    from bcc.db.repository import Repository


class FilesView(ctk.CTkFrame):
    MODE_LABELS = {
        "Server backup": BrowseService.MODE_BACKUP,
        "Mesin sumber": BrowseService.MODE_SOURCE,
    }

    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.app = app
        self.browse = BrowseService(repo)
        self._smap: dict[str, int] = {}
        self._current_path: str = ""
        self._browse_root: str = ""
        self._entries: list[dict[str, Any]] = []
        self._selected_name: Optional[str] = None
        self._loading = False
        self._row_widgets: list[ctk.CTkButton] = []

        ctk.CTkLabel(
            self, text="File backup", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            self,
            text=(
                "Pilih server/PC sumber, lalu lihat file di folder remote backup "
                "atau di mesin sumber (web root)."
            ),
            text_color="gray",
            wraplength=800,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=4)
        ctk.CTkLabel(bar, text="Sumber:").pack(side="left", padx=(0, 4))
        self.source_menu = ctk.CTkOptionMenu(
            bar, values=["(pilih sumber)"], width=280, command=self._on_source_change
        )
        self.source_menu.pack(side="left", padx=4)
        ctk.CTkLabel(bar, text="Mode:").pack(side="left", padx=(12, 4))
        self.mode_menu = ctk.CTkOptionMenu(
            bar,
            values=list(self.MODE_LABELS.keys()),
            width=140,
            command=self._on_mode_change,
        )
        self.mode_menu.set("Server backup")
        self.mode_menu.pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Refresh", width=80, command=self._reload).pack(
            side="left", padx=4
        )
        ctk.CTkButton(bar, text="Atas", width=70, command=self._go_up).pack(
            side="left", padx=4
        )
        ctk.CTkButton(bar, text="Buka", width=70, command=self._open_selected).pack(
            side="left", padx=4
        )

        self.lbl_path = ctk.CTkLabel(
            self, text="Path: —", anchor="w", font=ctk.CTkFont(size=12)
        )
        self.lbl_path.pack(fill="x", pady=(8, 2))
        self.lbl_status = ctk.CTkLabel(
            self, text="Pilih sumber lalu Refresh.", text_color="gray", anchor="w"
        )
        self.lbl_status.pack(fill="x", pady=(0, 6))

        # header
        head = ctk.CTkFrame(self)
        head.pack(fill="x")
        for col, (txt, w) in enumerate(
            [("Nama", 360), ("Tipe", 70), ("Ukuran", 90), ("Modified", 140)]
        ):
            ctk.CTkLabel(
                head, text=txt, font=ctk.CTkFont(weight="bold"), width=w, anchor="w"
            ).grid(row=0, column=col, sticky="w", padx=6, pady=4)
            head.grid_columnconfigure(col, weight=1 if col == 0 else 0)

        self.listbox = ctk.CTkScrollableFrame(self)
        self.listbox.pack(fill="both", expand=True, pady=4)

    def refresh(self) -> None:
        sources = self.repo.list_sources()
        if not sources:
            self._smap = {}
            self.source_menu.configure(values=["(pilih sumber)"])
            self.source_menu.set("(pilih sumber)")
            return
        labels = [f"{s['id']}: {s['label']} ({s['host']})" for s in sources]
        self._smap = {
            f"{s['id']}: {s['label']} ({s['host']})": int(s["id"]) for s in sources
        }
        cur = self.source_menu.get()
        self.source_menu.configure(values=labels)
        if cur in self._smap:
            self.source_menu.set(cur)
        else:
            self.source_menu.set(labels[0])
            self._current_path = ""
            self._browse_root = ""
        # Initial load if list empty
        if not self._entries and not self._loading:
            self._reload()

    def _mode_key(self) -> str:
        return self.MODE_LABELS.get(self.mode_menu.get(), BrowseService.MODE_BACKUP)

    def _source_id(self) -> Optional[int]:
        return self._smap.get(self.source_menu.get())

    def _on_source_change(self, _val: str = "") -> None:
        self._current_path = ""
        self._browse_root = ""
        self._reload()

    def _on_mode_change(self, _val: str = "") -> None:
        self._current_path = ""
        self._browse_root = ""
        self._reload()

    def _reload(self) -> None:
        sid = self._source_id()
        if not sid:
            self.lbl_status.configure(text="Tidak ada sumber.", text_color="#c62828")
            return
        if self._loading:
            return
        path = self._current_path or None
        self._loading = True
        self.lbl_status.configure(text="Loading…", text_color="gray")

        def work() -> None:
            data = self.browse.list_dir(sid, self._mode_key(), path)
            self.after(0, lambda: self._apply_list(data))

        threading.Thread(target=work, daemon=True).start()

    def _apply_list(self, data: dict[str, Any]) -> None:
        self._loading = False
        for w in self.listbox.winfo_children():
            w.destroy()
        self._row_widgets.clear()
        self._selected_name = None
        self._entries = data.get("entries") or []
        self._current_path = data.get("path") or ""
        self._browse_root = data.get("root") or ""

        ep = data.get("endpoint_label") or ""
        self.lbl_path.configure(
            text=f"Path: {self._current_path or '—'}  ·  {ep}"
        )

        if not data.get("ok"):
            self.lbl_status.configure(
                text=data.get("message") or "Gagal",
                text_color="#c62828",
            )
            return

        self.lbl_status.configure(
            text=data.get("message") or f"{len(self._entries)} item",
            text_color="gray",
        )
        for i, e in enumerate(self._entries):
            self._add_row(i, e)

    def _add_row(self, index: int, e: dict[str, Any]) -> None:
        fname = e.get("name") or ""
        is_dir = bool(e.get("is_dir"))
        tip = "folder" if is_dir else "file"
        size = "—" if is_dir else human_size(int(e.get("size") or 0))
        mtime = e.get("mtime") or "—"
        # Single CTkButton row — avoid .bind() on CTk widgets (tkinter nametowidget crash)
        label = f"{fname}   |  {tip}  |  {size}  |  {mtime}"
        btn = ctk.CTkButton(
            self.listbox,
            text=label,
            anchor="w",
            height=28,
            fg_color=("gray90", "gray22"),
            text_color=("gray10", "gray90"),
            hover_color=("gray80", "gray30"),
            command=lambda n=fname, d=is_dir: self._on_row_click(n, d),
        )
        btn.pack(fill="x", pady=1)
        self._row_widgets.append(btn)

    def _on_row_click(self, fname: str, is_dir: bool) -> None:
        self._selected_name = fname
        full = f"{(self._current_path or '').rstrip('/')}/{fname}"
        if is_dir:
            self.lbl_status.configure(
                text=f"Masuk folder: {full}", text_color="gray"
            )
            self._enter(fname)
        else:
            self.lbl_status.configure(text=f"File: {full}", text_color="gray")
            for j, w in enumerate(self._row_widgets):
                sel = self._entries[j].get("name") == fname if j < len(self._entries) else False
                try:
                    w.configure(
                        fg_color=("gray75", "gray35") if sel else ("gray90", "gray22")
                    )
                except Exception:
                    pass

    def _enter(self, name: str) -> None:
        if not self._current_path:
            return
        nxt = f"{self._current_path.rstrip('/')}/{name}"
        self._current_path = nxt
        self._reload()

    def _go_up(self) -> None:
        if not self._browse_root:
            self._reload()
            return
        sid = self._source_id()
        if not sid:
            return
        ctx = self.browse.root_for(sid, self._mode_key())
        if not ctx.get("ok"):
            self.lbl_status.configure(text=ctx.get("message") or "Gagal", text_color="#c62828")
            return
        parent = self.browse.parent_path(
            ctx["root"], self._current_path or ctx["root"], ctx.get("max_depth")
        )
        self._current_path = parent
        self._reload()

    def _open_selected(self) -> None:
        if not self._selected_name:
            self.lbl_status.configure(text="Pilih baris dulu.", text_color="gray")
            return
        for e in self._entries:
            if e.get("name") == self._selected_name:
                if e.get("is_dir"):
                    self._enter(self._selected_name)
                else:
                    full = f"{self._current_path.rstrip('/')}/{self._selected_name}"
                    self.lbl_status.configure(text=f"File: {full}", text_color="gray")
                return
