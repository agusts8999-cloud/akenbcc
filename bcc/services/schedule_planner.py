"""Schedule anti-overlap planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Conflict:
    source_a: str
    source_b: str
    detail: str


def _minutes(h: int, m: int) -> int:
    return h * 60 + m


def detect_conflicts(rows: list[dict[str, Any]], stagger_default: int = 60) -> list[Conflict]:
    """Detect overlapping web backup windows on different sources."""
    conflicts: list[Conflict] = []
    items = []
    for r in rows:
        if not r.get("enabled", 1):
            continue
        start = _minutes(int(r["web_hour"]), int(r["web_minute"]))
        dur = int(r.get("estimated_web_minutes") or 60)
        items.append((r["label"], r.get("host", ""), start, start + dur, r))

    for i, (la, ha, sa, ea, ra) in enumerate(items):
        for lb, hb, sb, eb, rb in items[i + 1 :]:
            # overlap
            if sa < eb and sb < ea:
                gap = abs(sa - sb)
                if gap < stagger_default:
                    conflicts.append(
                        Conflict(
                            la,
                            lb,
                            f"Overlap web ~{la} [{sa//60:02d}:{sa%60:02d}+{ea-sa}m] vs "
                            f"{lb} [{sb//60:02d}:{sb%60:02d}]; gap {gap}m < {stagger_default}m",
                        )
                    )
        # same host: db before web ends
        web_end = ea
        db_start = _minutes(int(ra["db_hour"]), int(ra["db_minute"]))
        if db_start < web_end and db_start >= sa:
            # ok if sequential same host partially
            pass
        if db_start < web_end:
            conflicts.append(
                Conflict(
                    la,
                    la,
                    f"DB {ra['db_hour']:02d}:{ra['db_minute']:02d} berpeluang bentrok "
                    f"dengan web yang diperkirakan selesai ~{web_end//60:02d}:{web_end%60:02d}",
                )
            )
    return conflicts


def auto_stagger(
    rows: list[dict[str, Any]], start_hour: int = 2, stagger_minutes: int = 90
) -> list[dict[str, int]]:
    """Return new web/db times staggered across sources."""
    out = []
    for i, r in enumerate(sorted(rows, key=lambda x: x.get("label", ""))):
        total = start_hour * 60 + i * stagger_minutes
        wh, wm = divmod(total % (24 * 60), 60)
        db_total = (total + 60) % (24 * 60)
        dh, dm = divmod(db_total, 60)
        out.append(
            {
                "source_id": r["source_id"],
                "web_hour": wh,
                "web_minute": wm,
                "db_hour": dh,
                "db_minute": dm,
            }
        )
    return out
