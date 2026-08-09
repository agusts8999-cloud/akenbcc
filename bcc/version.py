"""Version helpers (single source: bcc.__init__)."""

from __future__ import annotations

from bcc import APP_ID, APP_NAME, __build__, __version__


def version_string() -> str:
    return __version__


def build_string() -> str:
    return str(__build__)


def full_version() -> str:
    return f"{__version__}-{__build__}"


def executable_basename() -> str:
    return f"{APP_ID}-{full_version()}"


def display_title() -> str:
    return f"{APP_NAME} {full_version()}"


def file_version_tuple() -> tuple[int, int, int, int]:
    """Windows VERSIONINFO (major, minor, patch, build)."""
    parts = (__version__ + ".0.0.0").split(".")
    major = int(parts[0]) if parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return (major, minor, patch, int(__build__))


def ui_version_line() -> str:
    return f"v{__version__} · build {__build__}"
