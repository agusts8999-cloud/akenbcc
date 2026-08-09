"""Settings tab: disk alert + email / WA laporan."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from bcc import APP_ID, APP_NAME
from bcc.paths import app_data_dir, db_path, logo_png, templates_dir
from bcc.services.notify_service import NotifyService, SMTP_DEFAULTS
from bcc.services.tailscale_service import TailscaleService
from bcc.version import build_string, full_version, version_string

if TYPE_CHECKING:
    from bcc.db.repository import Repository


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, repo: Repository, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.repo = repo
        self.notify = NotifyService(repo)
        self.notify.ensure_defaults()

        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True)

        ctk.CTkLabel(
            outer, text="Pengaturan", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")

        info = ctk.CTkTextbox(outer, height=180)
        info.pack(fill="x", pady=8)
        ts = TailscaleService().status()
        info.insert(
            "end",
            f"{APP_NAME}\n"
            f"App ID: {APP_ID}\n"
            f"Version: {version_string()}  Build: {build_string()}  Full: {full_version()}\n"
            f"Data: {app_data_dir()}\n"
            f"DB: {db_path()}\n"
            f"Templates: {templates_dir()}\n"
            f"Logo: {logo_png()}\n"
            f"Tailscale: installed={ts.installed} running={ts.running} IPv4={ts.ipv4 or '-'}\n",
        )
        info.configure(state="disabled")

        # --- disk ---
        ctk.CTkLabel(
            outer, text="Alert disk", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(12, 4))
        ctk.CTkLabel(outer, text="Ambang alert disk (GB)", anchor="w").pack(anchor="w")
        self.thresh = ctk.CTkEntry(outer, width=120)
        self.thresh.insert(0, self.repo.get_setting("disk_alert_gb", "20"))
        self.thresh.pack(anchor="w", pady=4)

        # --- email ---
        ctk.CTkLabel(
            outer, text="Laporan Email (SMTP)", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(16, 4))
        self.email_en = ctk.CTkCheckBox(outer, text="Aktifkan email laporan")
        self.email_en.pack(anchor="w")
        if self.repo.get_setting("notify_email_enabled", "1") == "1":
            self.email_en.select()

        row1 = ctk.CTkFrame(outer, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        self._lbl_entry(row1, "To (penerima)", "notify_to", width=320)
        self._lbl_entry(row1, "From", "smtp_from", default=SMTP_DEFAULTS["smtp_from"])

        row2 = ctk.CTkFrame(outer, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        self._lbl_entry(row2, "SMTP host", "smtp_host", default=SMTP_DEFAULTS["smtp_host"])
        self._lbl_entry(row2, "Port", "smtp_port", default=SMTP_DEFAULTS["smtp_port"], width=80)

        row3 = ctk.CTkFrame(outer, fg_color="transparent")
        row3.pack(fill="x", pady=2)
        self._lbl_entry(row3, "User", "smtp_user", default=SMTP_DEFAULTS["smtp_user"])
        fr_pw = ctk.CTkFrame(row3, fg_color="transparent")
        fr_pw.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(fr_pw, text="Password SMTP", anchor="w").pack(anchor="w")
        self.smtp_password = ctk.CTkEntry(fr_pw, width=200, show="*")
        # leave blank if already stored; placeholder hint
        if self.notify.smtp_password():
            self.smtp_password.insert(0, "")
            self.smtp_password.configure(placeholder_text="(tersimpan — isi untuk ganti)")
        self.smtp_password.pack(anchor="w")

        em_btns = ctk.CTkFrame(outer, fg_color="transparent")
        em_btns.pack(anchor="w", pady=6)
        ctk.CTkButton(em_btns, text="Simpan email", command=self._save_email, width=120).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(em_btns, text="Tes kirim email", command=self._test_email, width=140).pack(
            side="left"
        )

        # --- WA ---
        ctk.CTkLabel(
            outer, text="WhatsApp (placeholder)", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(16, 4))
        ctk.CTkLabel(
            outer,
            text="Belum dikirim jika token API kosong. Default nomor: +6281219752227",
            text_color="gray",
        ).pack(anchor="w")
        self.wa_en = ctk.CTkCheckBox(outer, text="Aktifkan WA (butuh token)")
        self.wa_en.pack(anchor="w", pady=4)
        if self.repo.get_setting("notify_wa_enabled", "0") == "1":
            self.wa_en.select()

        row_wa = ctk.CTkFrame(outer, fg_color="transparent")
        row_wa.pack(fill="x", pady=2)
        self._lbl_entry(
            row_wa,
            "Nomor WA",
            "notify_wa_phone",
            default=SMTP_DEFAULTS["notify_wa_phone"],
            width=180,
        )
        fr_tok = ctk.CTkFrame(row_wa, fg_color="transparent")
        fr_tok.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(fr_tok, text="Token API (isi nanti)", anchor="w").pack(anchor="w")
        self.wa_token = ctk.CTkEntry(fr_tok, width=240, show="*")
        if self.notify.wa_token():
            self.wa_token.configure(placeholder_text="(tersimpan — isi untuk ganti)")
        else:
            self.wa_token.configure(placeholder_text="kosong = belum aktif")
        self.wa_token.pack(anchor="w")

        wa_btns = ctk.CTkFrame(outer, fg_color="transparent")
        wa_btns.pack(anchor="w", pady=6)
        ctk.CTkButton(wa_btns, text="Simpan WA", command=self._save_wa, width=120).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(wa_btns, text="Tes WA", command=self._test_wa, width=100).pack(side="left")

        # --- disk save ---
        ctk.CTkButton(
            outer, text="Simpan ambang disk", command=self._save_disk, width=160
        ).pack(anchor="w", pady=(16, 4))

        self.msg = ctk.CTkLabel(outer, text="", wraplength=640, justify="left")
        self.msg.pack(anchor="w", pady=8)

    def _lbl_entry(
        self,
        parent,
        label: str,
        key: str,
        default: str = "",
        width: int = 200,
    ) -> ctk.CTkEntry:
        fr = ctk.CTkFrame(parent, fg_color="transparent")
        fr.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(fr, text=label, anchor="w").pack(anchor="w")
        e = ctk.CTkEntry(fr, width=width)
        val = self.repo.get_setting(key, default) or default
        e.insert(0, val)
        e.pack(anchor="w")
        setattr(self, f"e_{key}", e)
        return e

    def refresh(self) -> None:
        self.thresh.delete(0, "end")
        self.thresh.insert(0, self.repo.get_setting("disk_alert_gb", "20"))
        for key, default in (
            ("notify_to", ""),
            ("smtp_from", SMTP_DEFAULTS["smtp_from"]),
            ("smtp_host", SMTP_DEFAULTS["smtp_host"]),
            ("smtp_port", SMTP_DEFAULTS["smtp_port"]),
            ("smtp_user", SMTP_DEFAULTS["smtp_user"]),
            ("notify_wa_phone", SMTP_DEFAULTS["notify_wa_phone"]),
        ):
            e = getattr(self, f"e_{key}", None)
            if e is None:
                continue
            e.delete(0, "end")
            e.insert(0, self.repo.get_setting(key, default) or default)

    def _save_disk(self) -> None:
        self.repo.set_setting("disk_alert_gb", self.thresh.get().strip() or "20")
        self.msg.configure(text="Ambang disk tersimpan.")

    def _save_email(self) -> None:
        self.repo.set_setting(
            "notify_email_enabled", "1" if self.email_en.get() else "0"
        )
        self.repo.set_setting("notify_to", self.e_notify_to.get().strip())
        self.repo.set_setting("smtp_from", self.e_smtp_from.get().strip())
        self.repo.set_setting("smtp_host", self.e_smtp_host.get().strip())
        self.repo.set_setting("smtp_port", self.e_smtp_port.get().strip() or "465")
        self.repo.set_setting("smtp_user", self.e_smtp_user.get().strip())
        pw = self.smtp_password.get()
        if pw:
            self.notify.set_smtp_password(pw)
            self.smtp_password.delete(0, "end")
            self.smtp_password.configure(placeholder_text="(tersimpan — isi untuk ganti)")
        self.msg.configure(text="Pengaturan email tersimpan (password terenkripsi di AppData).")

    def _save_wa(self) -> None:
        self.repo.set_setting("notify_wa_enabled", "1" if self.wa_en.get() else "0")
        self.repo.set_setting("notify_wa_phone", self.e_notify_wa_phone.get().strip())
        tok = self.wa_token.get()
        if tok:
            self.notify.set_wa_token(tok)
            self.wa_token.delete(0, "end")
            self.wa_token.configure(placeholder_text="(tersimpan — isi untuk ganti)")
        self.msg.configure(text="Pengaturan WhatsApp tersimpan.")

    def _test_email(self) -> None:
        self._save_email()
        self.msg.configure(text="Mengirim email tes…")

        def work() -> None:
            ok, text = self.notify.test_email()
            self.after(0, lambda: self.msg.configure(text=text))

        threading.Thread(target=work, daemon=True).start()

    def _test_wa(self) -> None:
        self._save_wa()
        self.msg.configure(text="Menguji WA…")

        def work() -> None:
            ok, text = self.notify.test_wa()
            self.after(0, lambda: self.msg.configure(text=text))

        threading.Thread(target=work, daemon=True).start()
