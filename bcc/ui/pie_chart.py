"""Pillow pie chart for dashboard disk breakdown."""

from __future__ import annotations

from typing import Any, Sequence

from PIL import Image, ImageDraw

# Free green, then distinct non-purple slices, grey for Lainnya
_FREE = (76, 175, 80)
_OTHER = (158, 158, 158)
_SOURCE = [
    (33, 150, 243),
    (255, 152, 0),
    (0, 150, 136),
    (244, 67, 54),
    (121, 85, 72),
    (63, 81, 181),
    (0, 188, 212),
    (255, 193, 7),
]


def slice_colors(slices: Sequence[dict[str, Any]]) -> list[tuple[int, int, int]]:
    colors: list[tuple[int, int, int]] = []
    si = 0
    for s in slices:
        kind = (s.get("kind") or "").lower()
        label = (s.get("label") or "").lower()
        if kind == "free" or label == "free":
            colors.append(_FREE)
        elif kind == "other" or label == "lainnya":
            colors.append(_OTHER)
        else:
            colors.append(_SOURCE[si % len(_SOURCE)])
            si += 1
    return colors


def render_pie(
    slices: Sequence[dict[str, Any]],
    size: int = 280,
    bg: tuple[int, int, int] = (245, 245, 245),
) -> Image.Image:
    """Draw a pie chart. Each slice needs 'pct' (0-100) or 'bytes'."""
    img = Image.new("RGBA", (size, size), (*bg, 255))
    draw = ImageDraw.Draw(img)
    pad = 16
    bbox = (pad, pad, size - pad, size - pad)

    if not slices:
        draw.ellipse(bbox, outline=(160, 160, 160), width=2)
        return img.convert("RGB")

    values: list[float] = []
    for s in slices:
        if s.get("pct") is not None:
            values.append(max(0.0, float(s["pct"])))
        else:
            values.append(max(0.0, float(s.get("bytes") or 0)))
    total = sum(values)
    if total <= 0:
        draw.ellipse(bbox, outline=(160, 160, 160), width=2)
        return img.convert("RGB")

    colors = slice_colors(slices)
    start = -90.0
    for i, v in enumerate(values):
        extent = 360.0 * (v / total)
        if extent <= 0.01:
            continue
        end = start + extent
        color = colors[i] if i < len(colors) else _SOURCE[i % len(_SOURCE)]
        draw.pieslice(bbox, start=start, end=end, fill=color, outline=(255, 255, 255))
        start = end

    return img.convert("RGB")
