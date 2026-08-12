"""Daily backup activity reports (dashboard text + email)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from bcc.services.notify_service import NotifyService

if TYPE_CHECKING:
    from bcc.db.repository import Repository

log = logging.getLogger(__name__)

SETTING_DAILY_ENABLED = "daily_report_enabled"
SETTING_LAST_SENT = "report_email_last_day"
SETTING_DAILY_TO = "daily_report_to"
DEFAULT_REPORT_TO = "akenprodev@gmail.com"


class ReportService:
    def __init__(self, repo: "Repository") -> None:
        self.repo = repo
        self.notify = NotifyService(repo)

    def ensure_defaults(self) -> None:
        self.notify.ensure_defaults()
        if not self.repo.get_setting(SETTING_DAILY_ENABLED):
            self.repo.set_setting(SETTING_DAILY_ENABLED, "1")
        if not (self.repo.get_setting(SETTING_DAILY_TO) or "").strip():
            self.repo.set_setting(SETTING_DAILY_TO, DEFAULT_REPORT_TO)
        # Seed global notify_to if empty (event notifications)
        if not (self.repo.get_setting("notify_to") or "").strip():
            self.repo.set_setting("notify_to", DEFAULT_REPORT_TO)

    def report_recipient(self) -> str:
        return (
            (self.repo.get_setting(SETTING_DAILY_TO) or "").strip()
            or DEFAULT_REPORT_TO
        )

    @staticmethod
    def today_local() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def normalize_day(self, day: Optional[str] = None) -> str:
        raw = (day or self.today_local()).strip()
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            return self.today_local()

    def build_daily_report(self, day: Optional[str] = None) -> str:
        day = self.normalize_day(day)
        rows = self.repo.history_for_date(day, backup_only=True)
        all_rows = rows
        ok_all = sum(
            1
            for r in all_rows
            if (r.get("run_type") or "") == "backup_all"
            and (r.get("status") or "").lower() in ("ok", "success")
        )
        fail_all = sum(
            1
            for r in all_rows
            if (r.get("run_type") or "") == "backup_all"
            and (r.get("status") or "").lower() in ("fail", "error", "failed")
        )
        arrival_rows = [
            r
            for r in all_rows
            if (r.get("run_type") or "").startswith("backup_arrival")
        ]
        arrival_n = len(arrival_rows)
        lines = [
            "Backup Control Center — Laporan aktivitas backup",
            "===============================================",
            f"Tanggal: {day}",
            f"Total baris aktivitas: {len(all_rows)}",
            f"backup_all OK: {ok_all}  |  FAIL: {fail_all}",
            f"backup masuk (arrival): {arrival_n} entri deteksi",
            "",
        ]
        if not all_rows:
            lines.append(f"Tidak ada aktivitas backup pada tanggal {day}.")
        else:
            lines.append("Aktivitas:")
            lines.append("-" * 72)
            for h in all_rows:
                lines.append(
                    f"{h.get('recorded_at') or '-'}  "
                    f"[{h.get('status') or '?'}]  "
                    f"{h.get('label') or '(source #' + str(h.get('source_id')) + ')'}  "
                    f"{h.get('run_type') or '-'}: "
                    f"{(h.get('message') or '').replace(chr(10), ' ').strip()}"
                )
        lines.append("")
        lines.append(f"(dibuat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        return "\n".join(lines)

    def send_daily_report(
        self, day: Optional[str] = None, force: bool = False
    ) -> tuple[bool, str]:
        """Send daily report email. force=True for manual button."""
        self.ensure_defaults()
        day = self.normalize_day(day)
        body = self.build_daily_report(day)
        subject = f"BCC laporan backup {day}"
        to_addr = self.report_recipient()
        result = self.notify.send_email_to(to_addr, subject, body)
        if result == "ok":
            if not force:
                self.repo.set_setting(SETTING_LAST_SENT, day)
            log.info("Daily report email sent day=%s to=%s force=%s", day, to_addr, force)
            return True, f"Laporan {day} terkirim ke {to_addr}."
        return False, f"Gagal kirim laporan {day}: {result}"

    def maybe_auto_send_today(self) -> Optional[tuple[bool, str]]:
        """Once per local day when BCC opens/refreshes dashboard. Returns None if skipped."""
        self.ensure_defaults()
        if self.repo.get_setting(SETTING_DAILY_ENABLED, "1") != "1":
            return None
        if self.repo.get_setting("notify_email_enabled", "1") != "1":
            return None
        today = self.today_local()
        last = (self.repo.get_setting(SETTING_LAST_SENT) or "").strip()
        if last == today:
            return None
        # Mark early to avoid double-fire from parallel refreshes (on success or try)
        ok, msg = self.send_daily_report(today, force=False)
        if ok:
            return ok, msg
        # On failure do not set last day so it can retry later
        return ok, msg
