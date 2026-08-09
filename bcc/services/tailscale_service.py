"""Tailscale CLI helpers."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class TailscaleStatus:
    installed: bool
    running: bool
    ipv4: str
    summary: str
    peers: list[str]


class TailscaleService:
    def _bin(self) -> Optional[str]:
        return shutil.which("tailscale")

    def status(self) -> TailscaleStatus:
        path = self._bin()
        if not path:
            return TailscaleStatus(False, False, "", "Tailscale CLI tidak ditemukan di PATH", [])
        try:
            ip = subprocess.run(
                [path, "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            ipv4 = (ip.stdout or "").strip().splitlines()[0] if ip.stdout else ""
            st = subprocess.run(
                [path, "status"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            summary = (st.stdout or st.stderr or "")[:2000]
            peers = re.findall(r"(100\.\d+\.\d+\.\d+)", summary)
            running = bool(ipv4) or "100." in summary
            return TailscaleStatus(True, running, ipv4, summary, peers)
        except (subprocess.TimeoutExpired, OSError) as e:
            return TailscaleStatus(True, False, "", f"Error: {e}", [])

    @staticmethod
    def is_tailscale_ip(host: str) -> bool:
        return bool(re.match(r"^100\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host.strip()))
