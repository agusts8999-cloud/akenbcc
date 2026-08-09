"""Paths for app data, templates, and frozen resources."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def package_root() -> Path:
    """Directory `bcc/` (or `_MEIPASS/bcc` when frozen)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidate = meipass / "bcc"
        if candidate.is_dir():
            return candidate
        return meipass
    return Path(__file__).resolve().parent


def workspace_root() -> Path:
    """d:\\development\\backup (parent of bcc/) — not used when frozen."""
    return package_root().parent


def resource_path(*parts: str) -> Path:
    """
    Resolve a path under package root, supporting PyInstaller one-file (_MEIPASS).
    Example: resource_path("assets", "logo.png")
    """
    root = package_root()
    path = root.joinpath(*parts)
    if path.exists():
        return path
    # fallback: MEIPASS flat layout
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        alt = Path(sys._MEIPASS).joinpath(*parts)
        if alt.exists():
            return alt
    return path


def templates_dir() -> Path:
    return resource_path("templates")


def assets_dir() -> Path:
    return resource_path("assets")


def logo_png() -> Path:
    return assets_dir() / "logo.png"


def logo_ico() -> Path:
    return assets_dir() / "logo.ico"


def app_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "BackupControlCenter"
    return Path.home() / ".config" / "bcc"


def db_path() -> Path:
    return app_data_dir() / "bcc.db"
