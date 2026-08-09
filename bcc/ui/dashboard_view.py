"""Dashboard tab with CTk-native status tables and disk pie chart."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, Sequence

import customtkinter as ctk

from bcc.services.monitor_service import MonitorService, human_bytes
from bcc.services.schedule_planner import detect_conflicts
from bcc.services.tailscale_service import TailscaleService
from bcc.ui.pie_chart import render_pie, slice_colors

if TYPE_CHECKING:
    from bcc.db.repository import Repository


def _ssh_label(ok: Optional[int]) -> str:
    if ok == 1:
        return "OK"
    if ok == 0:
        return "FAIL"
    return "?"


def _hhmm(hour, minute) -> str:
    if hour is None or minute is None:
        return "-"
    try:
        return f"{int(hour):02d}:{int(minute):02d}"
    except (TypeError, ValueError):
        return "-"


def _trunc(text: Optional[str], n: int = 36) -> str:
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.app = app
        self.monitor = MonitorService(repo)
        self.ts = TailscaleService()
        self._target_menu_map: dict[str, int] = {}
        self._pie_image = None  # keep ref for CTkImage
        self._disk_loading = False

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self.scroll, text="Dashboard", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w", pady=(0, 8))

        self.cards = ctk.CTkFrame(self.scroll)
        self.cards.pack(fill="x", pady=8)
        self.lbl_sources = ctk.CTkLabel(
            self.cards, text="Sumber: -", font=ctk.CTkFont(size=14)
        )
        self.lbl_sources.pack(side="left", padx=16, pady=12)
        self.lbl_ssh = ctk.CTkLabel(self.cards, text="SSH: -", font=ctk.CTkFont(size=14))
        self.lbl_ssh.pack(side="left", padx=16, pady=12)
        self.lbl_ts = ctk.CTkLabel(self.cards, text="Tailscale: -", font=ctk.CTkFont(size=14))
        self.lbl_ts.pack(side="left", padx=16, pady=12)

        bar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bar.pack(fill="x")
        ctk.CTkButton(bar, text="Refresh", width=100, command=self.refresh).pack(side="left")
        ctk.CTkButton(
            bar, text="Cek semua SSH", width=140, command=self._check_all_ssh
        ).pack(side="left", padx=8)

        # --- Disk pie ---
        ctk.CTkLabel(
            self.scroll,
            text="Disk server backup",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(14, 4))
        disk_bar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        disk_bar.pack(fill="x")
        self.target_menu = ctk.CTkOptionMenu(disk_bar, values=["(belum ada target)"], width=280)
        self.target_menu.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            disk_bar, text="Update disk chart", width=150, command=self._update_disk_chart
        ).pack(side="left")
        self.lbl_disk_status = ctk.CTkLabel(
            self.scroll, text="Belum dimuat — klik Update disk chart", text_color="gray", anchor="w"
        )
        self.lbl_disk_status.pack(anchor="w", pady=(4, 4))

        pie_row = ctk.CTkFrame(self.scroll, corner_radius=6)
        pie_row.pack(fill="x", pady=4)
        self.pie_label = ctk.CTkLabel(pie_row, text="")
        self.pie_label.pack(side="left", padx=12, pady=12)
        self.legend_frame = ctk.CTkFrame(pie_row, fg_color="transparent")
        self.legend_frame.pack(side="left", fill="both", expand=True, padx=12, pady=12)

        # --- Server Backup table ---
        ctk.CTkLabel(
            self.scroll, text="Server Backup", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", pady=(14, 4))
        self.tbl_targets = ctk.CTkFrame(self.scroll, corner_radius=6)
        self.tbl_targets.pack(fill="x", pady=2)
        self._target_headers = (
            "Label",
            "Host",
            "User",
            "Base path",
            "TS",
            "#Sumber",
            "SSH",
            "SSH dicek",
            "Catatan",
        )

        # --- Sources table ---
        ctk.CTkLabel(
            self.scroll, text="Sumber (VPS/PC)", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", pady=(14, 4))
        self.tbl_sources = ctk.CTkFrame(self.scroll, corner_radius=6)
        self.tbl_sources.pack(fill="x", pady=2)
        self._source_headers = (
            "Label",
            "Host",
            "Role",
            "aaPanel",
            "Remote folder",
            "Target",
            "TS",
            "SSH",
            "Deploy",
            "Web",
            "DB",
            "Aksi terakhir",
        )

        ctk.CTkLabel(
            self.scroll, text="Konflik jadwal", font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", pady=(16, 4))
        self.conflict_box = ctk.CTkTextbox(self.scroll, height=80)
        self.conflict_box.pack(fill="x")

        ctk.CTkLabel(
            self.scroll, text="Riwayat aksi", font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", pady=(12, 4))
        self.hist_box = ctk.CTkTextbox(self.scroll, height=180)
        self.hist_box.pack(fill="x", pady=(0, 12))

    def _clear_table(self, frame: ctk.CTkFrame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _fill_table(
        self,
        frame: ctk.CTkFrame,
        headers: Sequence[str],
        rows: list[Sequence[str]],
    ) -> None:
        self._clear_table(frame)
        bold = ctk.CTkFont(size=11, weight="bold")
        body = ctk.CTkFont(size=11)
        for col, h in enumerate(headers):
            ctk.CTkLabel(
                frame,
                text=h,
                font=bold,
                anchor="w",
                padx=6,
                pady=4,
            ).grid(row=0, column=col, sticky="ew", padx=1, pady=1)
            frame.grid_columnconfigure(col, weight=1, minsize=48)

        if not rows:
            ctk.CTkLabel(
                frame,
                text="(kosong)",
                text_color="gray",
                anchor="w",
                padx=6,
            ).grid(row=1, column=0, columnspan=max(len(headers), 1), sticky="w", pady=6)
            return

        for r_i, row in enumerate(rows, start=1):
            bg = ("gray90", "gray22") if r_i % 2 == 0 else ("gray95", "gray17")
            for c_i, cell in enumerate(row):
                ctk.CTkLabel(
                    frame,
                    text=str(cell),
                    font=body,
                    anchor="w",
                    padx=6,
                    pady=3,
                    fg_color=bg,
                    corner_radius=0,
                ).grid(row=r_i, column=c_i, sticky="nsew", padx=0, pady=0)

    def _refresh_target_menu(self) -> None:
        targets = self.repo.list_targets()
        if not targets:
            self._target_menu_map = {}
            self.target_menu.configure(values=["(belum ada target)"])
            self.target_menu.set("(belum ada target)")
            return
        labels = [f"{t['id']}: {t['label']} ({t['host']})" for t in targets]
        self._target_menu_map = {
            f"{t['id']}: {t['label']} ({t['host']})": int(t["id"]) for t in targets
        }
        cur = self.target_menu.get()
        self.target_menu.configure(values=labels)
        if cur in self._target_menu_map:
            self.target_menu.set(cur)
        else:
            self.target_menu.set(labels[0])

    def _apply_disk_result(self, data: dict[str, Any]) -> None:
        self._disk_loading = False
        if not data.get("ok"):
            self.lbl_disk_status.configure(
                text=f"Gagal: {data.get('message') or 'unknown'}",
                text_color="#c62828",
            )
            for w in self.legend_frame.winfo_children():
                w.destroy()
            return

        slices = data.get("slices") or []
        img = render_pie(slices, size=280)
        self._pie_image = ctk.CTkImage(light_image=img, dark_image=img, size=(280, 280))
        self.pie_label.configure(image=self._pie_image, text="")

        for w in self.legend_frame.winfo_children():
            w.destroy()
        colors = slice_colors(slices)
        ctk.CTkLabel(
            self.legend_frame,
            text=f"{data.get('target_label')} · {data.get('base_path')}",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))
        for i, s in enumerate(slices):
            rgb = colors[i] if i < len(colors) else (120, 120, 120)
            hex_c = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            line = (
                f"●  {s.get('label')} — {s.get('pct'):.2f}% "
                f"({human_bytes(int(s.get('bytes') or 0))})"
            )
            ctk.CTkLabel(
                self.legend_frame,
                text=line,
                text_color=hex_c,
                anchor="w",
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", pady=1)

        ts = datetime.now().strftime("%H:%M:%S")
        tot = human_bytes(int(data.get("total_bytes") or 0))
        free = human_bytes(int(data.get("free_bytes") or 0))
        self.lbl_disk_status.configure(
            text=f"Update {ts} · total {tot} · free {free} · {data.get('message')}",
            text_color="gray",
        )

    def _update_disk_chart(self) -> None:
        if self._disk_loading:
            return
        tid = self._target_menu_map.get(self.target_menu.get())
        if not tid:
            self.lbl_disk_status.configure(text="Tidak ada target", text_color="#c62828")
            return
        self._disk_loading = True
        self.lbl_disk_status.configure(text="Loading… (SSH ke server backup)", text_color="gray")

        def work() -> None:
            data = self.monitor.target_disk_slices(tid)
            self.after(0, lambda: self._apply_disk_result(data))

        threading.Thread(target=work, daemon=True).start()

    def refresh(self) -> None:
        snap = self.monitor.dashboard_snapshot()
        self.lbl_sources.configure(
            text=f"Sumber: {snap['sources_total']} | Target: {snap['targets_total']}"
        )
        self.lbl_ssh.configure(
            text=(
                f"SSH OK {snap['sources_ok']} / Fail {snap['sources_fail']} "
                f"/ ? {snap['sources_unknown']}"
            )
        )
        ts = self.ts.status()
        if not ts.installed:
            self.lbl_ts.configure(text="Tailscale: CLI tidak ada")
        else:
            self.lbl_ts.configure(
                text=f"Tailscale: {'ON' if ts.running else 'OFF'} {ts.ipv4 or ''}"
            )

        self._refresh_target_menu()

        target_rows: list[Sequence[str]] = []
        for t in self.repo.list_targets_overview():
            host = t.get("host") or ""
            target_rows.append(
                (
                    t.get("label") or "",
                    host,
                    t.get("username") or "",
                    t.get("base_path") or "",
                    "Ya" if TailscaleService.is_tailscale_ip(host) else "Tidak",
                    str(t.get("source_count") or 0),
                    _ssh_label(t.get("last_ssh_ok")),
                    t.get("last_ssh_at") or "-",
                    _trunc(t.get("notes"), 36),
                )
            )
        self._fill_table(self.tbl_targets, self._target_headers, target_rows)

        source_rows: list[Sequence[str]] = []
        for s in self.repo.list_sources_overview():
            host = s.get("host") or ""
            last = "-"
            if s.get("last_run_type"):
                last = f"{s.get('last_run_status') or '?'} {s.get('last_run_type')}"
                if s.get("last_run_at"):
                    last = f"{last} @ {s.get('last_run_at')}"
            source_rows.append(
                (
                    s.get("label") or "",
                    host,
                    s.get("role") or "",
                    "Ya" if s.get("aapanel") else "Tidak",
                    s.get("source_label") or "",
                    s.get("target_label") or "-",
                    "Ya" if TailscaleService.is_tailscale_ip(host) else "Tidak",
                    _ssh_label(s.get("last_ssh_ok")),
                    s.get("last_deploy_at") or "-",
                    _hhmm(s.get("web_hour"), s.get("web_minute")),
                    _hhmm(s.get("db_hour"), s.get("db_minute")),
                    _trunc(last, 48),
                )
            )
        self._fill_table(self.tbl_sources, self._source_headers, source_rows)

        confs = detect_conflicts(snap["schedules"])
        self.conflict_box.delete("1.0", "end")
        if not confs:
            self.conflict_box.insert("end", "Tidak ada konflik terdeteksi.\n")
        else:
            for c in confs:
                self.conflict_box.insert("end", f"- {c.detail}\n")

        self.hist_box.delete("1.0", "end")
        for h in snap["history"]:
            self.hist_box.insert(
                "end",
                f"{h.get('recorded_at')} [{h.get('status')}] {h.get('label') or ''} "
                f"{h.get('run_type')}: {h.get('message')}\n",
            )

    def _check_all_ssh(self) -> None:
        def work() -> None:
            for s in self.repo.list_sources():
                self.monitor.refresh_source_ssh(int(s["id"]))
            self.after(0, self.refresh)

        threading.Thread(target=work, daemon=True).start()
