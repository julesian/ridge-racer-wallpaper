from __future__ import annotations

import heapq
import argparse
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


OUT = Path(__file__).resolve().parents[1] / "assets" / "track-vector"

# Waypoints are only used to choose the flow around intersections/loop order.
# The exported route follows the skeletonized pale track pixels between them.
WAYPOINTS = [
    (430, 494),
    (493, 497),
    (560, 500),
    (623, 500),
    (638, 487),
    (634, 451),
    (611, 367),
    (594, 307),
    (587, 261),
    (600, 216),
    (606, 187),
    (596, 166),
    (579, 151),
    (560, 146),
    (548, 154),
    (550, 169),
    (566, 183),
    (590, 188),
    (609, 177),
    (618, 153),
    (614, 125),
    (591, 106),
    (557, 100),
    (522, 101),
    (492, 113),
    (469, 136),
    (469, 160),
    (462, 188),
    (430, 199),
    (387, 207),
    (342, 202),
    (300, 208),
    (259, 200),
    (219, 187),
    (197, 194),
    (183, 225),
    (178, 262),
    (222, 257),
    (282, 263),
    (309, 286),
    (311, 322),
    (303, 374),
    (265, 403),
    (205, 432),
    (196, 458),
    (211, 475),
    (275, 475),
    (350, 476),
    (430, 494),
]


def close_mask(mask: np.ndarray, iterations: int = 2) -> np.ndarray:
    def dilate(src: np.ndarray) -> np.ndarray:
        padded = np.pad(src, 1)
        out = np.zeros_like(src)
        for dy in range(3):
            for dx in range(3):
                out |= padded[dy : dy + src.shape[0], dx : dx + src.shape[1]]
        return out

    def erode(src: np.ndarray) -> np.ndarray:
        padded = np.pad(src, 1, constant_values=True)
        out = np.ones_like(src)
        for dy in range(3):
            for dx in range(3):
                out &= padded[dy : dy + src.shape[0], dx : dx + src.shape[1]]
        return out

    out = mask
    for _ in range(iterations):
        out = dilate(out)
    for _ in range(iterations):
        out = erode(out)
    return out


def zhang_suen_thin(image: np.ndarray) -> np.ndarray:
    img = image.copy().astype(np.uint8)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            padded = np.pad(img, 1)
            p2 = padded[:-2, 1:-1]
            p3 = padded[:-2, 2:]
            p4 = padded[1:-1, 2:]
            p5 = padded[2:, 2:]
            p6 = padded[2:, 1:-1]
            p7 = padded[2:, :-2]
            p8 = padded[1:-1, :-2]
            p9 = padded[:-2, :-2]
            neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]
            count = sum(neighbors)
            transitions = sum((neighbors[i] == 0) & (neighbors[(i + 1) % 8] == 1) for i in range(8))
            if step == 0:
                removable = (
                    (img == 1)
                    & (count >= 2)
                    & (count <= 6)
                    & (transitions == 1)
                    & ((p2 * p4 * p6) == 0)
                    & ((p4 * p6 * p8) == 0)
                )
            else:
                removable = (
                    (img == 1)
                    & (count >= 2)
                    & (count <= 6)
                    & (transitions == 1)
                    & ((p2 * p4 * p8) == 0)
                    & ((p2 * p6 * p8) == 0)
                )
            if removable.any():
                img[removable] = 0
                changed = True
    return img.astype(bool)


def largest_component(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best: list[tuple[int, int]] = []
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for y in range(h):
        for x in np.where(mask[y] & ~seen[y])[0]:
            q: deque[tuple[int, int]] = deque([(y, int(x))])
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
            if len(pts) > len(best):
                best = pts
    out = np.zeros_like(mask, dtype=bool)
    for y, x in best:
        out[y, x] = True
    return out


def remove_overlays(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    yy, xx = np.indices(mask.shape)

    # Small start ring at bottom-left: remove only the circular decoration,
    # not the nearby main horizontal route.
    ring = (xx - 269) ** 2 + (yy - 477) ** 2 <= 18**2
    out[ring] = False

    # Checker/start grid plus arrow under the bottom straight.
    out[466:519, 374:430] = False
    out[500:518, 368:412] = False

    # Repaint the intended bottom straight through the removed grid area so the
    # route remains continuous after deleting the overlay.
    out[490:503, 430:575] = mask[490:503, 430:575]
    out[472:486, 205:374] = mask[472:486, 205:374]
    return out


def build_graph(skel: np.ndarray) -> tuple[set[tuple[int, int]], dict[tuple[int, int], list[tuple[tuple[int, int], float]]]]:
    pixels = {(int(x), int(y)) for y, x in zip(*np.where(skel))}
    offsets = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    graph: dict[tuple[int, int], list[tuple[tuple[int, int], float]]] = {}
    for x, y in pixels:
        graph[(x, y)] = [
            ((x + dx, y + dy), math.hypot(dx, dy))
            for dx, dy in offsets
            if (x + dx, y + dy) in pixels
        ]
    return pixels, graph


def snap(point: tuple[int, int], pixels: set[tuple[int, int]], radius: int = 24) -> tuple[int, int]:
    x, y = point
    candidates = [p for p in pixels if abs(p[0] - x) <= radius and abs(p[1] - y) <= radius]
    if not candidates:
        candidates = list(pixels)
    return min(candidates, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)


def shortest_path(
    graph: dict[tuple[int, int], list[tuple[tuple[int, int], float]]],
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    queue: list[tuple[float, tuple[int, int]]] = [(0.0, start)]
    dist = {start: 0.0}
    prev: dict[tuple[int, int], tuple[int, int]] = {}
    while queue:
        cost, node = heapq.heappop(queue)
        if node == goal:
            break
        if cost != dist[node]:
            continue
        for nxt, weight in graph[node]:
            next_cost = cost + weight
            if next_cost < dist.get(nxt, math.inf):
                dist[nxt] = next_cost
                prev[nxt] = node
                heapq.heappush(queue, (next_cost, nxt))
    if goal not in dist:
        raise RuntimeError(f"No path from {start} to {goal}")
    out = [goal]
    while out[-1] != start:
        out.append(prev[out[-1]])
    out.reverse()
    return out


def dedupe_collinear(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    out = [points[0]]
    for i in range(1, len(points) - 1):
        ax, ay = out[-1]
        bx, by = points[i]
        cx, cy = points[i + 1]
        if (round(bx - ax), round(by - ay)) == (round(cx - bx), round(cy - by)):
            continue
        out.append(points[i])
    out.append(points[-1])
    return out


def interpolate_bridge(points: list[tuple[float, float]], steps: int = 70) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for a, b in zip(points, points[1:]):
        for i in range(steps):
            t = i / steps
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(points[-1])
    return out


def path_d(points: list[tuple[float, float]]) -> str:
    first = points[0]
    return " ".join([f"M {first[0]:.2f} {first[1]:.2f}"] + [f"L {x:.2f} {y:.2f}" for x, y in points[1:]])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the clean R4 track route from a source screenshot.")
    parser.add_argument("source", type=Path, help="Path to the 888 x 597 reference screenshot.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    im = Image.open(args.source).convert("RGB")
    arr = np.asarray(im)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mask = (r > 230) & (g > 195) & (b > 45)
    mask = remove_overlays(mask)
    mask = close_mask(mask, iterations=2)
    mask = largest_component(mask)
    skel = zhang_suen_thin(mask)
    pixels, graph = build_graph(skel)
    snapped = [snap(p, pixels) for p in WAYPOINTS]

    route_px: list[tuple[int, int]] = []
    bridge_start = WAYPOINTS[-2]
    bridge_end = WAYPOINTS[-1]
    for waypoint_a, waypoint_b, a, b in zip(WAYPOINTS, WAYPOINTS[1:], snapped, snapped[1:]):
        if waypoint_a == bridge_start and waypoint_b == bridge_end:
            segment_float = interpolate_bridge([(350.5, 476.5), (389.5, 486.5), (430.5, 494.5)])
            route_px.extend([(round(x - 0.5), round(y - 0.5)) for x, y in segment_float][1:] if route_px else [])
            continue
        segment = shortest_path(graph, a, b)
        route_px.extend(segment[1:] if route_px else segment)

    route = dedupe_collinear([(x + 0.5, y + 0.5) for x, y in route_px])
    rounded = [[round(x, 2), round(y, 2)] for x, y in route]

    data = {
        "width": im.width,
        "height": im.height,
        "source": str(args.source),
        "coordinate_system": "pixel coordinates, origin top-left, 1 SVG unit = 1 source pixel",
        "note": "Bitmap-traced route with start ring/checker/arrow overlays removed from the mask.",
        "points": rounded,
        "waypoints": WAYPOINTS,
        "snapped_points": [[x + 0.5, y + 0.5] for x, y in snapped],
    }
    (OUT / "track-route-clean-trace.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (OUT / "track-route-clean-trace.js").write_text(
        "window.TRACK_ROUTE_CLEAN_TRACE = "
        + json.dumps({"width": im.width, "height": im.height, "points": rounded}, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    (OUT / "track-route-clean-trace.svg").write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="{im.width}" height="{im.height}" viewBox="0 0 {im.width} {im.height}">
  <title>Clean bitmap trace route</title>
  <path id="track-route-clean-trace" d="{path_d(route)}" fill="none" stroke="#00AEEF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
</svg>
''',
        encoding="utf-8",
    )

    overlay = im.convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    draw.line(route, fill=(0, 174, 239, 255), width=4, joint="curve")
    for x, y in WAYPOINTS:
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 0, 80, 230))
    overlay.save(OUT / "track-route-clean-trace-overlay.png")
    Image.fromarray((mask * 255).astype(np.uint8), "L").save(OUT / "track-route-clean-mask.png")

    max_step = max(math.hypot(route[i + 1][0] - route[i][0], route[i + 1][1] - route[i][1]) for i in range(len(route) - 1))
    print(json.dumps({"points": len(route), "max_step": round(max_step, 3)}, indent=2))


if __name__ == "__main__":
    main()
