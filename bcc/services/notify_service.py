"""Email (SMTP SSL) + WhatsApp stub notifications for BCC events."""

from __future__ import annotations

import logging
import smtplib
import threading
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from bcc.db.repository import Repository

log = logging.getLogger(__name__)

# Defaults for first-time UI / ensure_defaults (password left empty unless set by user)
SMTP_DEFAULTS = {
    "notify_email_enabled": "1",
    "smtp_host": "mail.akenvi.com",
    "smtp_port": "465",
    "smtp_user": "admin@akenpro.com",
    "smtp_from": "admin@akenpro.com",
    "notify_to": "",
    "notify_wa_phone": "+6281219752227",
    "notify_wa_enabled": "0",
    "notify_wa_provider": "fonnte",
    "notify_wa_api_url": "https://api.fonnte.com/send",
}

SETTING_SMTP_PASSWORD = "smtp_password_enc"
SETTING_WA_TOKEN = "notify_wa_token_enc"


class NotifyService:
    def __init__(self, repo: "Repository") -> None:
        self.repo = repo

    def ensure_defaults(self) -> None:
        """Seed non-secret notify keys if missing (no password overwrite)."""
        for k, v in SMTP_DEFAULTS.items():
            if not self.repo.get_setting(k):
                self.repo.set_setting(k, v)

    def smtp_password(self) -> str:
        return self.repo.secrets.decrypt(self.repo.get_setting(SETTING_SMTP_PASSWORD, ""))

    def set_smtp_password(self, plain: str) -> None:
        if plain:
            self.repo.set_setting(SETTING_SMTP_PASSWORD, self.repo.secrets.encrypt(plain))

    def wa_token(self) -> str:
        return self.repo.secrets.decrypt(self.repo.get_setting(SETTING_WA_TOKEN, ""))

    def set_wa_token(self, plain: str) -> None:
        if plain:
            self.repo.set_setting(SETTING_WA_TOKEN, self.repo.secrets.encrypt(plain))
        else:
            self.repo.set_setting(SETTING_WA_TOKEN, "")

    def notify(
        self,
        event: str,
        status: str,
        subject: str,
        body: str,
        source_id: Optional[int] = None,
        async_send: bool = True,
    ) -> None:
        """Fire-and-forget notify; never raises to caller."""
        try:
            self.ensure_defaults()
            payload = {
                "event": event,
                "status": status,
                "subject": subject,
                "body": body,
                "source_id": source_id,
            }
            if async_send:
                threading.Thread(
                    target=self._dispatch, args=(payload,), daemon=True
                ).start()
            else:
                self._dispatch(payload)
        except Exception as e:
            log.warning("notify schedule failed: %s", e)

    def _dispatch(self, payload: dict[str, Any]) -> None:
        email_ok = self._send_email(
            payload["subject"],
            self._format_body(payload),
        )
        wa_ok = self._send_wa(self._format_wa(payload))
        log.info(
            "notify event=%s status=%s email=%s wa=%s",
            payload.get("event"),
            payload.get("status"),
            email_ok,
            wa_ok,
        )

    def _format_body(self, payload: dict[str, Any]) -> str:
        return (
            f"Backup Control Center — laporan otomatis\n"
            f"========================================\n"
            f"Event : {payload.get('event')}\n"
            f"Status: {payload.get('status')}\n"
            f"Source id: {payload.get('source_id') if payload.get('source_id') is not None else '-'}\n"
            f"\n{payload.get('body') or ''}\n"
        )

    def _format_wa(self, payload: dict[str, Any]) -> str:
        subj = payload.get("subject") or payload.get("event")
        return f"BCC [{payload.get('status')}] {subj}\n{(payload.get('body') or '')[:800]}"

    def _send_email(self, subject: str, body: str) -> str:
        if self.repo.get_setting("notify_email_enabled", "1") != "1":
            return "disabled"
        to_addr = (self.repo.get_setting("notify_to") or "").strip()
        if not to_addr:
            return "no_to"
        host = (self.repo.get_setting("smtp_host") or SMTP_DEFAULTS["smtp_host"]).strip()
        port = int(self.repo.get_setting("smtp_port") or "465")
        user = (self.repo.get_setting("smtp_user") or "").strip()
        from_addr = (self.repo.get_setting("smtp_from") or user or "noreply@localhost").strip()
        password = self.smtp_password()
        if not password:
            return "no_password"
        msg = EmailMessage()
        msg["Subject"] = subject[:200] if subject else "BCC report"
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(body)
        try:
            with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
            return "ok"
        except Exception as e:
            log.warning("SMTP send failed: %s", e)
            return f"fail:{e}"

    def _send_wa(self, text: str) -> str:
        if self.repo.get_setting("notify_wa_enabled", "0") != "1":
            return "disabled"
        token = self.wa_token()
        if not token:
            return "no_token"
        phone = (self.repo.get_setting("notify_wa_phone") or "").strip()
        if not phone:
            return "no_phone"
        target = "".join(c for c in phone if c.isdigit())
        url = (
            self.repo.get_setting("notify_wa_api_url")
            or SMTP_DEFAULTS["notify_wa_api_url"]
        )
        data = urllib.parse.urlencode(
            {"target": target, "message": text}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": token,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            log.info("WA response: %s", raw[:300])
            return "ok"
        except urllib.error.HTTPError as e:
            log.warning("WA HTTP error: %s", e)
            return f"fail:{e}"
        except Exception as e:
            log.warning("WA send failed: %s", e)
            return f"fail:{e}"

    def test_email(self) -> tuple[bool, str]:
        self.ensure_defaults()
        r = self._send_email(
            "BCC — tes laporan email",
            "Ini pesan tes dari Backup Control Center.\n"
            "Jika Anda menerima email ini, SMTP sudah benar.",
        )
        if r == "ok":
            return True, "Email tes terkirim."
        return False, f"Gagal email tes: {r}"

    def test_wa(self) -> tuple[bool, str]:
        self.ensure_defaults()
        if self.repo.get_setting("notify_wa_enabled", "0") != "1":
            return False, "WA belum diaktifkan (centang enable di Pengaturan)."
        if not self.wa_token():
            return False, "Token API WA kosong — isi nanti untuk mengaktifkan kirim."
        r = self._send_wa("BCC — tes WhatsApp laporan otomatis.")
        if r == "ok":
            return True, "WA tes terkirim."
        return False, f"Gagal WA tes: {r}"
