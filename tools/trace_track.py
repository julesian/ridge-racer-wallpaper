from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


OUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "track-vector"


def largest_component(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best: list[tuple[int, int]] = []
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    for y in range(h):
        xs = np.where(mask[y] & ~seen[y])[0]
        for x in xs:
            if seen[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(y, x)])
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


def skeleton_paths(skel: np.ndarray) -> list[list[tuple[float, float]]]:
    h, w = skel.shape
    pixels = {(int(y), int(x)) for y, x in zip(*np.where(skel))}
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def ns(p: tuple[int, int]) -> list[tuple[int, int]]:
        y, x = p
        return [(y + dy, x + dx) for dy, dx in offsets if (y + dy, x + dx) in pixels]

    degrees = {p: len(ns(p)) for p in pixels}
    nodes = {p for p, d in degrees.items() if d != 2}
    visited_edges: set[frozenset[tuple[int, int]]] = set()
    paths: list[list[tuple[float, float]]] = []

    for node in nodes:
        for nxt in ns(node):
            edge = frozenset((node, nxt))
            if edge in visited_edges:
                continue
            path = [node, nxt]
            visited_edges.add(edge)
            prev, cur = node, nxt
            while cur not in nodes:
                candidates = [p for p in ns(cur) if p != prev]
                if not candidates:
                    break
                nxt2 = candidates[0]
                visited_edges.add(frozenset((cur, nxt2)))
                path.append(nxt2)
                prev, cur = cur, nxt2
            if len(path) > 3:
                paths.append([(x + 0.5, y + 0.5) for y, x in path])

    # Closed loops can have no graph nodes, so trace any unvisited remaining cycle.
    for p in pixels:
        remaining = [n for n in ns(p) if frozenset((p, n)) not in visited_edges]
        if not remaining:
            continue
        path = [p, remaining[0]]
        visited_edges.add(frozenset((p, remaining[0])))
        prev, cur = p, remaining[0]
        while True:
            candidates = [q for q in ns(cur) if q != prev and frozenset((cur, q)) not in visited_edges]
            if not candidates:
                break
            nxt = candidates[0]
            visited_edges.add(frozenset((cur, nxt)))
            path.append(nxt)
            prev, cur = cur, nxt
            if cur == p:
                break
        if len(path) > 3:
            paths.append([(x + 0.5, y + 0.5) for y, x in path])

    return paths


def continuous_skeleton_walk(skel: np.ndarray) -> list[tuple[float, float]]:
    pixels = {(int(y), int(x)) for y, x in zip(*np.where(skel))}
    offsets = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, -1), (-1, 1), (1, 1), (1, -1)]

    def ns(p: tuple[int, int]) -> list[tuple[int, int]]:
        y, x = p
        return [(y + dy, x + dx) for dy, dx in offsets if (y + dy, x + dx) in pixels]

    adjacency = {p: ns(p) for p in pixels}
    endpoints = [p for p, neighbors in adjacency.items() if len(neighbors) == 1]
    if endpoints:
        start = min(endpoints, key=lambda p: (p[1], -p[0]))
    else:
        start = min(pixels, key=lambda p: (p[1], p[0]))

    visited: set[frozenset[tuple[int, int]]] = set()
    walk: list[tuple[int, int]] = [start]

    def edge_key(a: tuple[int, int], b: tuple[int, int]) -> frozenset[tuple[int, int]]:
        return frozenset((a, b))

    def dfs(current: tuple[int, int], previous: tuple[int, int] | None = None) -> None:
        candidates = [n for n in adjacency[current] if edge_key(current, n) not in visited]
        if previous is not None:
            py, px = previous
            cy, cx = current

            def turn_cost(n: tuple[int, int]) -> float:
                ny, nx = n
                vin = (cx - px, cy - py)
                vout = (nx - cx, ny - cy)
                dot = vin[0] * vout[0] + vin[1] * vout[1]
                denom = math.hypot(*vin) * math.hypot(*vout)
                return -(dot / denom) if denom else 0

            candidates.sort(key=turn_cost)
        else:
            candidates.sort()

        for nxt in candidates:
            key = edge_key(current, nxt)
            if key in visited:
                continue
            visited.add(key)
            walk.append(nxt)
            dfs(nxt, current)
            walk.append(current)

    dfs(start)
    return [(x + 0.5, y + 0.5) for y, x in walk]


def perpendicular_distance(pt: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    px, py = pt
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    return abs(dy * px - dx * py + bx * ay - by * ax) / math.hypot(dx, dy)


def simplify(points: list[tuple[float, float]], epsilon: float = 1.4) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    dmax = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        d = perpendicular_distance(points[i], points[0], points[-1])
        if d > dmax:
            index = i
            dmax = d
    if dmax > epsilon:
        return simplify(points[: index + 1], epsilon)[:-1] + simplify(points[index:], epsilon)
    return [points[0], points[-1]]


def path_d(points: list[tuple[float, float]]) -> str:
    start = points[0]
    chunks = [f"M {start[0]:.2f} {start[1]:.2f}"]
    chunks += [f"L {x:.2f} {y:.2f}" for x, y in points[1:]]
    return " ".join(chunks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace centerlines from the pale R4 track pixels in a source image.")
    parser.add_argument("source", type=Path, help="Path to the source track image.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sys.setrecursionlimit(100_000)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    im = Image.open(args.source).convert("RGB")
    arr = np.asarray(im)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # The route is the only high-blue, high-luminance yellow-white shape.
    mask = (r > 230) & (g > 195) & (b > 45)
    mask = close_mask(mask, iterations=2)
    mask = largest_component(mask)
    skel = zhang_suen_thin(mask)

    raw_paths = skeleton_paths(skel)
    paths = sorted((simplify(p) for p in raw_paths), key=len, reverse=True)
    paths = [p for p in paths if len(p) >= 2]
    continuous = continuous_skeleton_walk(skel)

    w, h = im.size
    svg_paths = "\n  ".join(
        f'<path id="track-{i + 1}" d="{path_d(p)}" fill="none" stroke="#00AEEF" '
        f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />'
        for i, p in enumerate(paths)
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <title>Extracted track centerline, 1:1 source coordinates</title>
  <metadata>Source: {args.source}</metadata>
  {svg_paths}
</svg>
'''
    (OUT_DIR / "track-centerline.svg").write_text(svg, encoding="utf-8")

    continuous_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <title>Extracted track continuous centerline walk, 1:1 source coordinates</title>
  <metadata>Source: {args.source}</metadata>
  <path id="track-continuous" d="{path_d(continuous)}" fill="none" stroke="#00AEEF"
    stroke-width="4" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
</svg>
'''
    (OUT_DIR / "track-centerline-continuous.svg").write_text(continuous_svg, encoding="utf-8")

    data = {
        "source": str(args.source),
        "width": w,
        "height": h,
        "coordinate_system": "pixel coordinates, origin top-left, 1 SVG unit = 1 source pixel",
        "paths": [
            {"id": f"track-{i + 1}", "points": [[round(x, 2), round(y, 2)] for x, y in p]}
            for i, p in enumerate(paths)
        ],
    }
    (OUT_DIR / "track-centerline.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    continuous_data = {
        "source": str(args.source),
        "width": w,
        "height": h,
        "coordinate_system": "pixel coordinates, origin top-left, 1 SVG unit = 1 source pixel",
        "path": {"id": "track-continuous", "points": [[round(x, 2), round(y, 2)] for x, y in continuous]},
    }
    (OUT_DIR / "track-centerline-continuous.json").write_text(json.dumps(continuous_data, indent=2), encoding="utf-8")
    js = (
        "window.TRACK_CENTERLINE = "
        + json.dumps(
            {
                "width": w,
                "height": h,
                "points": continuous_data["path"]["points"],
            },
            separators=(",", ":"),
        )
        + ";\n"
    )
    (OUT_DIR / "track-centerline-continuous.js").write_text(js, encoding="utf-8")

    overlay = im.convert("RGBA")
    draw = ImageDraw.Draw(overlay)
    for p in paths:
        draw.line(p, fill=(0, 174, 239, 255), width=4, joint="curve")
        for x, y in p:
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 0, 80, 220))
    overlay.save(OUT_DIR / "track-centerline-overlay.png")

    Image.fromarray((mask * 255).astype(np.uint8), "L").save(OUT_DIR / "track-mask.png")
    Image.fromarray((skel * 255).astype(np.uint8), "L").save(OUT_DIR / "track-skeleton.png")
    print(f"wrote {len(paths)} vector path(s) to {OUT_DIR}")
    print("points per path:", [len(p) for p in paths])
    print("continuous walk points:", len(continuous))


if __name__ == "__main__":
    main()
