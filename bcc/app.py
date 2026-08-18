"""Application entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def _setup_logging() -> Path:
    from bcc.paths import app_data_dir

    log_dir = app_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "bcc.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    return log_file


def main() -> None:
    _setup_logging()
    log = logging.getLogger("bcc")
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        log.error("customtkinter belum terpasang. Jalankan: pip install -r requirements.txt")
        print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    from bcc.db.repository import Repository
    from bcc.ui.main_window import MainWindow
    from bcc.services.storage_service import StorageService

    repo = Repository()
    repo.initialize()
    app = MainWindow(repo)

    # Policy scheduler: scan-only by default.  Archive/delete always needs
    # explicit item selection from the Storage tab.
    storage_service = StorageService(repo)
    def run_storage_jobs() -> None:
        # Avoid showing a loader every minute when no policy is due.
        if repo.list_due_retention_jobs():
            app.run_async(
                storage_service.run_due_jobs,
                "Jadwal scan storage",
                job_key="scheduled-storage-scan",
            )
        app.after(60_000, run_storage_jobs)
    app.after(60_000, run_storage_jobs)
    app.mainloop()


if __name__ == "__main__":
    main()
