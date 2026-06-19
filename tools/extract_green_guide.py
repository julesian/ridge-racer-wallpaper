from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


OUT = Path(__file__).resolve().parents[1] / "assets" / "track-vector"
TRACK_WIDTH = 888
TRACK_HEIGHT = 597


def largest_components(mask: np.ndarray, min_size: int = 20) -> list[list[tuple[int, int]]]:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    comps: list[list[tuple[int, int]]] = []
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for y in range(h):
        for x in np.where(mask[y] & ~seen[y])[0]:
            if seen[y, x]:
                continue
            q = deque([(y, int(x))])
            seen[y, x] = True
            pts: list[tuple[int, int]] = []
            while q:
                cy, cx = q.popleft()
                pts.append((cy, cx))
                for dy, dx in neighbors:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if len(pts) >= min_size:
                comps.append(pts)
    return sorted(comps, key=len, reverse=True)


def component_centerline(points: list[tuple[int, int]]) -> list[tuple[float, float]]:
    # A light nearest-neighbor ordering works well for the user's rough green guide strokes.
    remaining = {(x, y) for y, x in points}
    start = min(remaining, key=lambda p: (p[0], p[1]))
    ordered = [start]
    remaining.remove(start)
    current = start
    while remaining:
        cx, cy = current
        nxt = min(remaining, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        if math.hypot(nxt[0] - cx, nxt[1] - cy) > 24:
            break
        ordered.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return [(float(x), float(y)) for x, y in ordered]


def screen_to_track(pt: tuple[float, float], screenshot_size: tuple[int, int]) -> tuple[float, float]:
    sx, sy = pt
    sw, sh = screenshot_size
    scale = min(sw / TRACK_WIDTH, sh / TRACK_HEIGHT)
    return (
        (sx - sw * 0.5) / scale + TRACK_WIDTH * 0.5,
        (sy - sh * 0.5) / scale + TRACK_HEIGHT * 0.5,
    )


def simplify(points: list[tuple[float, float]], spacing: int = 10) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points
    out = [points[0]]
    last = points[0]
    for p in points[1:-1]:
        if math.hypot(p[0] - last[0], p[1] - last[1]) >= spacing:
            out.append(p)
            last = p
    out.append(points[-1])
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract green guide strokes from an annotated R4 screenshot.")
    parser.add_argument("source", type=Path, help="Path to the annotated source screenshot.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.open(args.source).convert("RGB")
    arr = np.asarray(im)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mask = (g > 130) & (r < 110) & (b < 120)
    comps = largest_components(mask)
    guides = []
    overlay = im.convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    colors = [(0, 255, 255, 255), (255, 0, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255)]
    for i, comp in enumerate(comps[:12]):
        center = component_centerline(comp)
        track_pts = [screen_to_track(p, im.size) for p in center]
        reduced = simplify(track_pts, spacing=8)
        guides.append(
            {
                "id": f"green-guide-{i + 1}",
                "screen_points": [[round(x, 1), round(y, 1)] for x, y in simplify(center, spacing=12)],
                "track_points": [[round(x, 1), round(y, 1)] for x, y in reduced],
                "pixel_count": len(comp),
            }
        )
        if len(center) > 1:
            draw.line(center, fill=colors[i % len(colors)], width=3)
    data = {
        "source": str(args.source),
        "screenshot_width": im.width,
        "screenshot_height": im.height,
        "track_width": TRACK_WIDTH,
        "track_height": TRACK_HEIGHT,
        "guides": guides,
    }
    (OUT / "green-guide.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    overlay.save(OUT / "green-guide-overlay.png")
    print(json.dumps({"components": len(comps), "sizes": [len(c) for c in comps[:12]]}, indent=2))


if __name__ == "__main__":
    main()
