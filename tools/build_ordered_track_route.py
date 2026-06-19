from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


OUT = Path(__file__).resolve().parents[1] / "assets" / "track-vector"
TRACK_WIDTH = 888
TRACK_HEIGHT = 597

# Direct control points traced from the clean 888 x 597 reference image.
# Ordered according to the intended flow; no green annotation geometry is used.
TRACK_CONTROLS = [
    (414, 476),
    (350, 476),
    (275, 475),
    (211, 475),
    (195, 462),
    (196, 437),
    (232, 416),
    (285, 394),
    (305, 374),
    (310, 329),
    (310, 289),
    (288, 263),
    (248, 257),
    (205, 257),
    (177, 263),
    (178, 230),
    (194, 195),
    (218, 187),
    (258, 200),
    (297, 208),
    (340, 202),
    (385, 207),
    (429, 200),
    (462, 188),
    (469, 162),
    (467, 136),
    (488, 115),
    (517, 101),
    (556, 100),
    (591, 105),
    (614, 124),
    (619, 151),
    (611, 176),
    (590, 188),
    (566, 183),
    (549, 168),
    (548, 153),
    (560, 146),
    (579, 151),
    (597, 166),
    (607, 186),
    (601, 215),
    (587, 261),
    (593, 306),
    (610, 365),
    (634, 452),
    (638, 488),
    (622, 500),
    (560, 500),
    (493, 497),
    (430, 494),
    (414, 476),
]


def track_to_screen(pt: tuple[float, float], screenshot_size: tuple[int, int]) -> tuple[float, float]:
    tx, ty = pt
    sw, sh = screenshot_size
    scale = min(sw / TRACK_WIDTH, sh / TRACK_HEIGHT)
    return (
        sw * 0.5 + (tx - TRACK_WIDTH * 0.5) * scale,
        sh * 0.5 + (ty - TRACK_HEIGHT * 0.5) * scale,
    )


def catmull_rom(points: list[tuple[float, float]], steps: int = 12) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    work = points[:-1] if points[0] == points[-1] else points
    for i, p1 in enumerate(work):
        p0 = work[(i - 1) % len(work)]
        p2 = work[(i + 1) % len(work)]
        p3 = work[(i + 2) % len(work)]
        for s in range(steps):
            t = s / steps
            t2 = t * t
            t3 = t2 * t
            out.append(
                (
                    0.5
                    * (
                        2 * p1[0]
                        + (-p0[0] + p2[0]) * t
                        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                    ),
                    0.5
                    * (
                        2 * p1[1]
                        + (-p0[1] + p2[1]) * t
                        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                    ),
                )
            )
    out.append(out[0])
    return out


def path_d(points: list[tuple[float, float]]) -> str:
    first = points[0]
    return " ".join([f"M {first[0]:.2f} {first[1]:.2f}"] + [f"L {x:.2f} {y:.2f}" for x, y in points[1:]])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the hand-ordered R4 track route from a source screenshot.")
    parser.add_argument("source", type=Path, help="Path to the reference screenshot used for the overlay.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    screenshot = Image.open(args.source).convert("RGBA")
    controls = TRACK_CONTROLS
    route = catmull_rom(controls, steps=20)
    rounded = [[round(x, 2), round(y, 2)] for x, y in route]
    data = {
        "width": TRACK_WIDTH,
        "height": TRACK_HEIGHT,
        "source": str(args.source),
        "coordinate_system": "pixel coordinates, origin top-left, 1 SVG unit = 1 source pixel",
        "note": "Ordered route retraced from the clean reference image. Start-grid overlay is intentionally not part of this route.",
        "points": rounded,
        "control_points": [[round(x, 2), round(y, 2)] for x, y in controls],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "track-route-ordered.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (OUT / "track-route-ordered.js").write_text(
        "window.TRACK_ROUTE_ORDERED = "
        + json.dumps({"width": TRACK_WIDTH, "height": TRACK_HEIGHT, "points": rounded}, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    (OUT / "track-route-ordered.svg").write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{TRACK_WIDTH}" height="{TRACK_HEIGHT}" viewBox="0 0 {TRACK_WIDTH} {TRACK_HEIGHT}">
  <title>Ordered track route following visible centerline</title>
  <path id="track-route-ordered" d="{path_d(route)}" fill="none" stroke="#00AEEF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
</svg>
''',
        encoding="utf-8",
    )

    overlay = screenshot.copy()
    draw = ImageDraw.Draw(overlay)
    draw.line([track_to_screen(p, screenshot.size) for p in route], fill=(0, 174, 239, 255), width=4, joint="curve")
    for x, y in TRACK_CONTROLS:
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 0, 80, 230))
    overlay.save(OUT / "track-route-ordered-overlay.png")

    max_step = max(math.hypot(route[i + 1][0] - route[i][0], route[i + 1][1] - route[i][1]) for i in range(len(route) - 1))
    print(json.dumps({"points": len(route), "max_step": round(max_step, 3)}, indent=2))


if __name__ == "__main__":
    main()
