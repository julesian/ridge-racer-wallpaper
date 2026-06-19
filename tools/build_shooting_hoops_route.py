from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "track-vector"

TRACK_ID = "shooting-hoops"
TRACK_GLOBAL = "TRACK_ROUTE_SHOOTING_HOOPS"

# Hand-snapped centerline controls from the supplied layout. The route starts on
# the upper-left straight just past the start marker; the checker/marker overlay
# is deliberately excluded from the path.
CONTROLS = [
    (139.0, 79.0),
    (196.0, 79.0),
    (261.0, 80.0),
    (324.0, 79.0),
    (383.0, 79.0),
    (417.0, 91.0),
    (421.0, 128.0),
    (405.0, 176.0),
    (385.0, 222.0),
    (362.0, 269.0),
    (329.0, 305.0),
    (290.0, 310.0),
    (262.0, 289.0),
    (242.0, 247.0),
    (219.0, 201.0),
    (194.0, 163.0),
    (151.0, 159.0),
    (100.0, 160.0),
    (55.0, 156.0),
    (39.0, 130.0),
    (47.0, 98.0),
    (82.0, 80.0),
]


def catmull_rom(
    points: list[tuple[float, float]],
    samples_per_segment: int = 16,
) -> list[tuple[float, float]]:
    route: list[tuple[float, float]] = []
    count = len(points)
    for i in range(count):
        p0 = points[(i - 1) % count]
        p1 = points[i]
        p2 = points[(i + 1) % count]
        p3 = points[(i + 2) % count]
        for sample in range(samples_per_segment):
            t = sample / samples_per_segment
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                2 * p1[0]
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                2 * p1[1]
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            route.append((x, y))
    route.append(route[0])
    return route


def path_d(points: list[tuple[float, float]]) -> str:
    first = points[0]
    return " ".join([f"M {first[0]:.2f} {first[1]:.2f}"] + [f"L {x:.2f} {y:.2f}" for x, y in points[1:]])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Shooting HooPs route asset.")
    parser.add_argument("source", type=Path, help="Path to the Shooting HooPs layout image.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.open(args.source).convert("RGBA")
    route = catmull_rom(CONTROLS)
    rounded = [[round(x, 2), round(y, 2)] for x, y in route]

    data = {
        "id": TRACK_ID,
        "width": im.width,
        "height": im.height,
        "source": str(args.source),
        "coordinate_system": "pixel coordinates, origin top-left, 1 SVG unit = 1 source pixel",
        "note": "Centerline route for Shooting HooPs. Start/checker overlay is excluded; circuit is closed.",
        "smooth": False,
        "start_grid": {"point": [139.0, 79.0]},
        "controls": [[round(x, 2), round(y, 2)] for x, y in CONTROLS],
        "points": rounded,
    }

    (OUT / "shooting-hoops-route.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (OUT / "shooting-hoops-route.js").write_text(
        f"window.{TRACK_GLOBAL} = "
        + json.dumps(
            {"width": im.width, "height": im.height, "smooth": False, "points": rounded},
            separators=(",", ":"),
        )
        + ";\n",
        encoding="utf-8",
    )
    (OUT / "shooting-hoops-route.svg").write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{im.width}" height="{im.height}" viewBox="0 0 {im.width} {im.height}">
  <title>Shooting HooPs route</title>
  <path id="shooting-hoops-route" d="{path_d(route)}" fill="none" stroke="#00AEEF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
</svg>
''',
        encoding="utf-8",
    )

    overlay = im.copy()
    draw = ImageDraw.Draw(overlay)
    draw.line(route, fill=(0, 174, 239, 255), width=4, joint="curve")
    draw.rectangle((115, 49, 184, 102), outline=(255, 0, 80, 255), width=2)
    for x, y in CONTROLS:
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 0, 80, 230))
    overlay.save(OUT / "shooting-hoops-route-overlay.png")

    max_step = max(math.hypot(route[i + 1][0] - route[i][0], route[i + 1][1] - route[i][1]) for i in range(len(route) - 1))
    print(json.dumps({"points": len(route), "max_step": round(max_step, 3), "closed": route[0] == route[-1]}, indent=2))


if __name__ == "__main__":
    main()
