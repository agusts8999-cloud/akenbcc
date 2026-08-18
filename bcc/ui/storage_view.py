"""Storage and retention management tab."""

from __future__ import annotations

import tkinter.messagebox as mb
from typing import Any, Optional

import customtkinter as ctk

from bcc.services.storage_service import StorageService


class StorageView(ctk.CTkFrame):
    def __init__(self, master, repo, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.app = app
        self.storage = StorageService(repo)
        self.selected_id: Optional[int] = None
        self.items: dict[int, tuple[ctk.BooleanVar, ctk.CTkEntry]] = {}
        self.target_map: dict[str, int] = {}
        self.archive_map: dict[str, int] = {}
        self.show_all_items = False
        self.items_page = 0
        self.items_page_size = 50
        self._filtered_items: list[dict[str, Any]] = []
        self.age_filter_values = [
            "> 1 hari",
            "> 2 hari",
            "> 3 hari",
            "> 7 hari",
            "> 14 hari",
            "> 30 hari",
        ]

        ctk.CTkLabel(self, text="Storage & Retention", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="Daftarkan mount/path backup, scan file lama, lalu arsipkan atau hapus secara eksplisit.", text_color="gray").pack(anchor="w")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=8)
        body.grid_columnconfigure(1, weight=1); body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body); left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.storage_list = ctk.CTkScrollableFrame(left, width=250); self.storage_list.pack(fill="both", expand=True, padx=4, pady=4)
        form = ctk.CTkScrollableFrame(body); form.grid(row=0, column=1, sticky="nsew")
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.target_menu = ctk.CTkOptionMenu(form, values=["(belum ada target)"]); self.target_menu.pack(anchor="w", padx=8, pady=4)
        for key, label, default in (("label", "Label storage", ""), ("mount_path", "Mount/path remote", "/home/backupuser/backups"), ("notes", "Catatan", ""), ("interval_hours", "Interval scan (jam)", "24")):
            ctk.CTkLabel(form, text=label).pack(anchor="w", padx=8, pady=(6, 0))
            e = ctk.CTkEntry(form, width=360); e.insert(0, default); e.pack(anchor="w", padx=8, pady=2); self.entries[key] = e
        ctk.CTkLabel(form, text="Filter scan berdasarkan umur file").pack(
            anchor="w", padx=8, pady=(6, 0)
        )
        self.age_filter_menu = ctk.CTkOptionMenu(
            form,
            values=self.age_filter_values,
            command=lambda _value: self._reset_items_page(),
        )
        self.age_filter_menu.set("> 3 hari")
        self.age_filter_menu.pack(anchor="w", padx=8, pady=2)
        self.schedule_enabled = ctk.CTkCheckBox(form, text="Scan otomatis sesuai interval (selama BCC berjalan)"); self.schedule_enabled.pack(anchor="w", padx=8, pady=6)
        ctk.CTkLabel(form, text="Rencana tindakan setelah review").pack(anchor="w", padx=8, pady=(6, 0))
        self.action_menu = ctk.CTkOptionMenu(form, values=["review", "archive", "delete"]); self.action_menu.set("review"); self.action_menu.pack(anchor="w", padx=8, pady=2)
        ctk.CTkLabel(form, text="Storage tujuan arsip").pack(anchor="w", padx=8, pady=(6, 0))
        self.archive_menu = ctk.CTkOptionMenu(form, values=["(tidak ada)"]); self.archive_menu.pack(anchor="w", padx=8, pady=2)
        buttons = ctk.CTkFrame(form, fg_color="transparent"); buttons.pack(anchor="w", pady=10)
        for text, cmd in (("Baru", self._new), ("Simpan", self._save), ("Hapus", self._delete), ("Test mount", self._test), ("Scan file lama", self._scan)):
            ctk.CTkButton(buttons, text=text, width=105, command=cmd).pack(side="left", padx=3)
        self.status = ctk.CTkLabel(form, text="", text_color="gray", wraplength=700, justify="left"); self.status.pack(anchor="w", padx=8, pady=4)
        ctk.CTkLabel(form, text="Kandidat file (pilih lalu gunakan aksi)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=8, pady=(14, 4))
        bulk_bar = ctk.CTkFrame(form, fg_color="transparent")
        bulk_bar.pack(anchor="w", padx=8, pady=(0, 4))
        self.show_all_button = ctk.CTkButton(
            bulk_bar, text="Tampilkan semua", width=120, command=self._toggle_show_all
        )
        self.show_all_button.pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            bulk_bar, text="Pilih semua", width=100, command=self._select_all
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            bulk_bar, text="Kosongkan pilihan", width=130, command=self._clear_selection
        ).pack(side="left", padx=4)
        self.items_summary = ctk.CTkLabel(bulk_bar, text="", text_color="gray")
        self.items_summary.pack(side="left", padx=8)
        self.items_frame = ctk.CTkScrollableFrame(form, height=260); self.items_frame.pack(fill="both", expand=True, padx=8, pady=4)
        pager = ctk.CTkFrame(form, fg_color="transparent")
        pager.pack(anchor="w", padx=8, pady=(0, 4))
        self.prev_page_button = ctk.CTkButton(
            pager, text="← Sebelumnya", width=110, command=self._previous_items_page
        )
        self.prev_page_button.pack(side="left")
        self.items_page_label = ctk.CTkLabel(pager, text="Halaman 0/0", text_color="gray")
        self.items_page_label.pack(side="left", padx=10)
        self.next_page_button = ctk.CTkButton(
            pager, text="Berikutnya →", width=110, command=self._next_items_page
        )
        self.next_page_button.pack(side="left")
        action_bar = ctk.CTkFrame(form, fg_color="transparent"); action_bar.pack(anchor="w", padx=8, pady=6)
        ctk.CTkLabel(action_bar, text="Folder arsip (opsional):").pack(side="left")
        self.group_entry = ctk.CTkEntry(
            action_bar, width=130, placeholder_text="arsip"
        )
        self.group_entry.pack(side="left", padx=5)
        ctk.CTkButton(action_bar, text="Pindahkan pilihan", command=lambda: self._act("archive")).pack(side="left", padx=4)
        ctk.CTkButton(action_bar, text="Hapus pilihan", fg_color="#a33", hover_color="#822", command=lambda: self._act("delete")).pack(side="left", padx=4)
        ctk.CTkButton(action_bar, text="Pindahkan semua", command=lambda: self._act_all("archive")).pack(side="left", padx=4)
        ctk.CTkButton(action_bar, text="Hapus semua", fg_color="#8b1a1a", hover_color="#681414", command=lambda: self._act_all("delete")).pack(side="left", padx=4)

    def _selected_target(self) -> Optional[int]:
        return self.target_map.get(self.target_menu.get())

    def refresh(self) -> None:
        targets = self.repo.list_targets(); self.target_map = {f"{t['id']}: {t['label']} ({t['host']})": int(t['id']) for t in targets}
        self.target_menu.configure(values=list(self.target_map) or ["(belum ada target)"])
        if self.selected_id:
            for s in self.repo.list_storages():
                if int(s["id"]) == self.selected_id: self._select(self.selected_id); break
        storages = self.repo.list_storages(); self.archive_map = {f"{s['id']}: {s['label']}": int(s['id']) for s in storages}
        self.archive_menu.configure(values=list(self.archive_map) or ["(tidak ada)"])
        for w in self.storage_list.winfo_children(): w.destroy()
        for s in storages:
            ctk.CTkButton(self.storage_list, text=f"{s['label']} · {s['mount_path']}", anchor="w", command=lambda i=s['id']: self._select(int(i))).pack(fill="x", pady=2)
        self._render_items()

    def _new(self) -> None:
        self.selected_id = None
        for e in self.entries.values(): e.delete(0, "end")
        self.entries["mount_path"].insert(0, "/home/backupuser/backups"); self.entries["interval_hours"].insert(0, "24"); self.age_filter_menu.set("> 3 hari"); self.action_menu.set("review"); self.schedule_enabled.deselect()

    def _select(self, sid: int) -> None:
        s = self.repo.get_storage(sid)
        if not s: return
        self.selected_id = sid
        for k in ("label", "mount_path", "notes"):
            self.entries[k].delete(0, "end"); self.entries[k].insert(0, s.get(k) or "")
        target_label = next((x for x, i in self.target_map.items() if i == int(s["target_id"])), None)
        if target_label: self.target_menu.set(target_label)
        job = self.repo.get_retention_job(sid) or {}
        for k, default in (("interval_hours", "24"),):
            self.entries[k].delete(0, "end"); self.entries[k].insert(0, str(job.get(k) or default))
        self._set_age_filter(int(job.get("retention_days") or 3))
        self.action_menu.set(job.get("action") or "review"); (self.schedule_enabled.select() if job.get("schedule_enabled") else self.schedule_enabled.deselect())
        self._render_items()

    def _save(self) -> None:
        tid = self._selected_target(); data = {k: e.get().strip() for k, e in self.entries.items()}
        if not tid or not data["label"] or not data["mount_path"]: mb.showwarning("Validasi", "Target, label, dan mount/path wajib."); return
        if self.selected_id: self.repo.update_storage(self.selected_id, target_id=tid, label=data["label"], mount_path=data["mount_path"], notes=data["notes"])
        else: self.selected_id = self.repo.add_storage(tid, data["label"], data["mount_path"], notes=data["notes"])
        archive_id = self.archive_map.get(self.archive_menu.get())
        self.repo.save_retention_job(self.selected_id, self._selected_age_days(), self.action_menu.get(), archive_id, bool(self.schedule_enabled.get()), int(data["interval_hours"] or 24))
        self.status.configure(text="Storage dan kebijakan retention tersimpan."); self.refresh()

    def _delete(self) -> None:
        if self.selected_id and mb.askyesno("Hapus konfigurasi", "Hapus konfigurasi storage? File remote tidak disentuh."):
            self.repo.soft_delete_storage(self.selected_id); self._new(); self.refresh()

    def _test(self) -> None:
        if not self.selected_id: return
        self.status.configure(text="Testing mount via SSH…")
        self.app.run_async(
            lambda: self._finish(self.storage.test_storage(self.selected_id)),
            "Test storage",
        )

    def _scan(self) -> None:
        if not self.selected_id: return
        sid, days = self.selected_id, self._selected_age_days(); self.status.configure(text=f"Scanning file > {days} hari via SSH…")
        self.app.run_async(
            lambda: self._finish(self.storage.scan(sid, days)),
            "Scan file backup",
        )

    def _finish(self, result) -> None:
        self.app.post_ui(lambda: (self.status.configure(text=result.message), self._reset_items_page()))

    def _render_items(self) -> None:
        for w in self.items_frame.winfo_children(): w.destroy()
        self.items = {}
        if not self.selected_id:
            self._filtered_items = []
            self.items_summary.configure(text="Pilih storage terlebih dahulu")
            self.items_page_label.configure(text="Halaman 0/0")
            self.prev_page_button.configure(state="disabled")
            self.next_page_button.configure(state="disabled")
            return
        status_filter = "all" if self.show_all_items else "pending"
        minimum_age = self._selected_age_days()
        rows = [
            item
            for item in self.repo.list_retention_items(self.selected_id, status_filter)
            if float(item.get("age_days") or 0) > minimum_age
        ]
        self._filtered_items = rows
        pending_count = sum(1 for item in rows if item.get("status") == "pending")
        pages = max(1, (len(rows) + self.items_page_size - 1) // self.items_page_size)
        self.items_page = min(max(0, self.items_page), pages - 1)
        start = self.items_page * self.items_page_size
        page_rows = rows[start : start + self.items_page_size]
        self.items_summary.configure(
            text=f"{len(rows)} hasil filter · {pending_count} pending"
        )
        self.items_page_label.configure(text=f"Halaman {self.items_page + 1}/{pages}")
        self.prev_page_button.configure(state="normal" if self.items_page > 0 else "disabled")
        self.next_page_button.configure(
            state="normal" if self.items_page + 1 < pages else "disabled"
        )
        if not rows:
            ctk.CTkLabel(
                self.items_frame,
                text="Tidak ada file untuk ditampilkan.",
                text_color="gray",
            ).pack(anchor="w", pady=8)
            return
        for item in page_rows:
            row = ctk.CTkFrame(self.items_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            status = item.get("status") or "pending"
            text = (
                f"[{status}] {item['age_days']:.1f} hari · "
                f"{item['size_bytes']} B · {item['path']}"
            )
            if status == "pending":
                var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(row, text=text, variable=var).pack(
                    side="left", fill="x", expand=True
                )
                group = ctk.CTkEntry(row, width=110)
                saved_group = item.get("group_key") or ""
                if saved_group != "arsip":
                    group.insert(0, saved_group)
                else:
                    group.configure(placeholder_text="arsip")
                group.pack(side="right")
                self.items[int(item["id"])] = (var, group)
            else:
                ctk.CTkLabel(row, text=text, text_color="gray", anchor="w").pack(
                    side="left", fill="x", expand=True
                )

    def _toggle_show_all(self) -> None:
        self.show_all_items = not self.show_all_items
        self.show_all_button.configure(
            text="Tampilkan pending" if self.show_all_items else "Tampilkan semua"
        )
        self._reset_items_page()

    def _reset_items_page(self) -> None:
        self.items_page = 0
        self._render_items()

    def _previous_items_page(self) -> None:
        if self.items_page > 0:
            self.items_page -= 1
            self._render_items()

    def _next_items_page(self) -> None:
        if (self.items_page + 1) * self.items_page_size < len(self._filtered_items):
            self.items_page += 1
            self._render_items()

    def _selected_age_days(self) -> int:
        value = self.age_filter_menu.get().replace(">", "").replace("hari", "").strip()
        try:
            return max(1, int(value))
        except ValueError:
            return 3

    def _set_age_filter(self, days: int) -> None:
        label = f"> {max(1, int(days))} hari"
        if label not in self.age_filter_values:
            self.age_filter_values.append(label)
            self.age_filter_menu.configure(values=self.age_filter_values)
        self.age_filter_menu.set(label)

    def _select_all(self) -> None:
        for var, _ in self.items.values():
            var.set(True)

    def _clear_selection(self) -> None:
        for var, _ in self.items.values():
            var.set(False)

    def _validate_action(self, action: str) -> Optional[int]:
        if action != "archive":
            return None
        archive_id = self.archive_map.get(self.archive_menu.get())
        if not archive_id:
            mb.showwarning("Storage tujuan", "Pilih storage tujuan pemindahan.")
            return -1
        if archive_id == self.selected_id:
            mb.showwarning(
                "Storage tujuan", "Storage tujuan harus berbeda dari storage sumber."
            )
            return -1
        return archive_id

    def _act_all(self, action: str) -> None:
        ids = [
            int(item["id"])
            for item in self._filtered_items
            if item.get("status") == "pending"
        ]
        if not ids:
            mb.showinfo("Tindakan massal", "Tidak ada kandidat pending dalam hasil filter.")
            return
        self._run_action(ids, action, all_visible=True)

    def _act(self, action: str) -> None:
        ids = [i for i, (var, _) in self.items.items() if var.get()]
        if not ids:
            mb.showinfo("Pilih file", "Pilih minimal satu kandidat pending.")
            return
        self._run_action(ids, action, all_visible=False)

    def _run_action(self, ids: list[int], action: str, all_visible: bool) -> None:
        archive_id = self._validate_action(action)
        if archive_id == -1:
            return
        scope = "semua file pending dalam hasil filter" if all_visible else "file terpilih"
        if action == "delete" and not mb.askyesno(
            "Hapus permanen",
            f"{len(ids)} {scope} akan dihapus permanen dari server remote. Lanjutkan?",
        ):
            return
        if action == "archive" and not mb.askyesno(
            "Pindahkan file",
            f"Pindahkan {len(ids)} {scope} ke storage tujuan?",
        ):
            return
        group_name = self.group_entry.get().strip() or "arsip"
        self.status.configure(text=f"Menjalankan {action}…")
        self.app.run_async(
            lambda: self._finish(
                self.storage.act_on_items(
                    ids,
                    action,
                    archive_id,
                    group_name,
                )
            ),
            "Tindakan file backup",
        )
