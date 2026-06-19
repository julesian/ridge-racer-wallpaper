(function () {
  "use strict";

  const canvas = document.getElementById("wallpaper");
  const ctx = canvas.getContext("2d", { alpha: false });
  const pixelCanvas = document.createElement("canvas");
  const pixelCtx = pixelCanvas.getContext("2d");
  const trackMaskCanvas = document.createElement("canvas");
  const trackMaskCtx = trackMaskCanvas.getContext("2d", { willReadFrequently: true });
  const routeLayerCanvas = document.createElement("canvas");
  const routeLayerCtx = routeLayerCanvas.getContext("2d");
  const music = document.getElementById("music");
  const muteToggle = document.getElementById("muteToggle");
  const muteIndicator = document.getElementById("muteIndicator");
  const courseName = document.getElementById("courseName");
  const scaleValue = document.getElementById("scaleValue");
  const scaleSteps = Array.from(document.querySelectorAll(".scale-step"));
  const logoToggle = document.getElementById("logoToggle");
  const trackSelectToggle = document.getElementById("trackSelectToggle");
  const trackSelectors = document.getElementById("trackSelectors");
  const trackArrowButtons = Array.from(document.querySelectorAll(".track-arrow"));
  const bottomLogo = document.getElementById("bottomLogo");
  const trackLogo = bottomLogo ? bottomLogo.querySelector(".wonderhill-logo") : null;

  const TAU = Math.PI * 2;
  const DESIGN_VIEWPORT = {
    width: 1366,
    height: 768,
  };
  const SCALE_REFERENCE_TRACK = {
    width: 888,
    height: 597,
  };
  const CONTENT_ZOOM = 1.08;
  const PROJECTION_BAND_ROWS = 0;
  const GREY_FIELD_OFFSET_ROWS = 3;
  const COLUMNS_PER_GRID_ROW = 2;
  const LOWER_RHOMBUS_LIFT_ROWS = 3;
  const SCENE_OFFSET = {
    x: 39,
    y: 0,
  };
  const palette = {
    gold: "#febb00",
    grey: "#383b36",
    greyDim: "#2f322e",
    orange: "#f47f00",
  };

  let width = 1;
  let height = 1;
  let dpr = 1;
  let baseScale = 1;
  let hexCenters = [];
  let trackGridCenters = [];
  let route = [];
  let routeLengths = [];
  let totalRouteLength = 1;
  let planeHalfWidth = 1;
  let projectionGeometry = null;
  let lastRenderTime = -Infinity;
  let routeLayerDirty = true;
  let animationStartTime = null;

  const FRAME_INTERVAL = 1000 / 24;
  const PIXEL_SCALE = 3;
  const settings = {
    scale: readStoredScale(),
    logo: readStoredLogo(),
    trackSelect: readStoredTrackSelect(),
    muted: readStoredMuted(),
  };
  const fallbackRoute = {
    width: 888,
    height: 597,
    smooth: true,
    points: [
      [360, 531],
      [292, 525],
      [210, 506],
      [136, 506],
      [101, 498],
      [94, 476],
      [103, 444],
      [138, 418],
      [211, 389],
      [244, 374],
      [253, 342],
      [252, 292],
      [238, 257],
      [196, 235],
      [108, 231],
      [70, 217],
      [74, 185],
      [91, 143],
      [118, 112],
      [160, 111],
      [204, 137],
      [260, 141],
      [333, 138],
      [407, 122],
      [463, 104],
      [492, 80],
      [540, 65],
      [607, 70],
      [653, 94],
      [674, 132],
      [667, 168],
      [640, 191],
      [596, 188],
      [568, 165],
      [585, 139],
      [630, 145],
      [656, 174],
      [635, 207],
      [610, 230],
      [596, 285],
      [612, 355],
      [638, 426],
      [656, 491],
      [624, 519],
      [537, 519],
      [445, 513],
    ],
  };
  const fallbackTrack = {
    id: "fallback",
    name: "Wonderhill",
    country: "JPN",
    imageAsset: "assets/tracks/wonderhill/wonderhill-remastered-borderless-orange-wave.png",
    logoAsset: "assets/tracks/wonderhill/wonderhill-logo-square.png",
    route: fallbackRoute,
    startGrid: {
      point: [388.5, 493.5],
    },
  };
  const trackCatalog = buildTrackCatalog(window.R4_TRACKS);
  let activeTrackIndex = 0;
  let activeTrack = trackCatalog[activeTrackIndex];
  let trackData = activeTrack.route;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = Math.max(1, window.innerWidth);
    height = Math.max(1, window.innerHeight);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    resizePixelCanvas();
    rebuildScene();
  }

  function rebuildScene() {
    const viewportFit = Math.min(
      width / SCALE_REFERENCE_TRACK.width,
      height / SCALE_REFERENCE_TRACK.height
    );
    const designFit = Math.min(
      DESIGN_VIEWPORT.width / SCALE_REFERENCE_TRACK.width,
      DESIGN_VIEWPORT.height / SCALE_REFERENCE_TRACK.height
    );
    baseScale = Math.min(viewportFit, designFit) * CONTENT_ZOOM * settings.scale;
    buildRoute();
    buildHexField();
    syncTrackSelectorGeometry();
  }

  function resizePixelCanvas() {
    pixelCanvas.width = Math.max(1, Math.ceil(width / PIXEL_SCALE));
    pixelCanvas.height = Math.max(1, Math.ceil(height / PIXEL_SCALE));
    trackMaskCanvas.width = pixelCanvas.width;
    trackMaskCanvas.height = pixelCanvas.height;
    routeLayerCanvas.width = pixelCanvas.width;
    routeLayerCanvas.height = pixelCanvas.height;
    pixelCtx.setTransform(1 / PIXEL_SCALE, 0, 0, 1 / PIXEL_SCALE, 0, 0);
    pixelCtx.imageSmoothingEnabled = false;
    routeLayerCtx.setTransform(1, 0, 0, 1, 0, 0);
    routeLayerDirty = true;
  }

  function mapPoint(x, y) {
    const routeScale = activeTrack.routeScale || 1;
    return {
      x: width * 0.5 + ((x - trackData.width * 0.5) * routeScale + SCENE_OFFSET.x) * baseScale,
      y: height * 0.5 + ((y - trackData.height * 0.5) * routeScale + SCENE_OFFSET.y) * baseScale,
    };
  }

  function buildRoute() {
    let mapped = trackData.points.map(([x, y]) => mapPoint(x, y));
    if (mapped.length > 2 && distance(mapped[0], mapped[mapped.length - 1]) < 2 * baseScale) {
      mapped = mapped.slice(0, -1);
    }
    route = trackData.smooth ? smoothClosedPath(mapped, 10) : mapped.concat([mapped[0]]);
    routeLengths = [0];
    totalRouteLength = 0;
    for (let i = 1; i < route.length; i += 1) {
      totalRouteLength += distance(route[i - 1], route[i]);
      routeLengths.push(totalRouteLength);
    }
    routeLayerDirty = true;
  }

  function buildTrackCatalog(tracks) {
    const sourceTracks = Array.isArray(tracks) && tracks.length ? tracks : [fallbackTrack];
    const sanitizedTracks = sourceTracks
      .map((track) => {
        const routeData = sanitizeTrackData(track.route || track.data || track, track);
        if (!routeData) return null;

        return {
          id: track.id || slugifyTrackName(track.name || "track"),
          name: track.name || "Unnamed Track",
          country: track.country || "",
          imageAsset: track.imageAsset || "",
          logoAsset: track.logoAsset || "",
          routeScale: Number.isFinite(track.routeScale) ? track.routeScale : 1,
          startGrid: track.startGrid || null,
          route: routeData,
        };
      })
      .filter(Boolean);

    return sanitizedTracks.length ? sanitizedTracks : [{ ...fallbackTrack, route: sanitizeTrackData(fallbackRoute, fallbackTrack) }];
  }

  function slugifyTrackName(name) {
    return String(name)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function sanitizeTrackData(data, track) {
    if (!data || !Array.isArray(data.points) || data.points.length < 2) return null;

    let points = data.points;
    if (points.length > 500) {
      const startPoint = track && track.startGrid && track.startGrid.point;
      const isStartGridPoint = startPoint
        ? ([x, y]) => Math.hypot(x - startPoint[0], y - startPoint[1]) <= 3
        : ([x, y]) => x >= 386 && x <= 390 && y >= 492 && y <= 495;
      const startIndex = points.findIndex(isStartGridPoint);
      const endIndex = findLastIndex(points, isStartGridPoint);

      if (startIndex >= 0 && endIndex > startIndex + 300) {
        points = points.slice(startIndex, endIndex + 1);
      }
    }

    const first = points[0];
    const last = points[points.length - 1];
    if (Math.hypot(first[0] - last[0], first[1] - last[1]) > 2) {
      points = points.concat([first]);
    }

    return {
      width: data.width || fallbackRoute.width,
      height: data.height || fallbackRoute.height,
      smooth: data.smooth !== false,
      points,
    };
  }

  function setActiveTrack(index) {
    if (!trackCatalog.length) return;
    activeTrackIndex = ((index % trackCatalog.length) + trackCatalog.length) % trackCatalog.length;
    activeTrack = trackCatalog[activeTrackIndex];
    trackData = activeTrack.route;
    animationStartTime = null;
    lastRenderTime = -Infinity;
    syncTrackInfo();
    rebuildScene();
  }

  function syncTrackInfo() {
    if (courseName) courseName.textContent = formatTrackName(activeTrack);
    if (trackLogo && activeTrack.logoAsset) {
      trackLogo.src = activeTrack.logoAsset;
      trackLogo.alt = formatTrackName(activeTrack);
    }
  }

  function formatTrackName(track) {
    return track.country ? `${track.name} [${track.country}]` : track.name;
  }

  function syncTrackSelectorGeometry() {
    if (!trackSelectors) return;
    const center = lowerPlaneCenter();
    const distance = Math.min(
      width * 0.47,
      Math.max(130, 310 + 240 * settings.scale)
    );
    document.documentElement.style.setProperty("--track-selector-center-x", `${Math.round(center.x)}px`);
    document.documentElement.style.setProperty("--track-selector-distance", `${Math.round(distance)}px`);
  }

  function nextTrack() {
    setActiveTrack(activeTrackIndex + 1);
  }

  function previousTrack() {
    setActiveTrack(activeTrackIndex - 1);
  }

  window.R4Wallpaper = {
    get tracks() {
      return trackCatalog.map(({ id, name, country, imageAsset, logoAsset, routeScale, startGrid }) => ({
        id,
        name,
        country,
        displayName: formatTrackName({ name, country }),
        imageAsset,
        logoAsset,
        routeScale,
        startGrid,
      }));
    },
    get activeTrack() {
      return {
        id: activeTrack.id,
        name: activeTrack.name,
        country: activeTrack.country,
        displayName: formatTrackName(activeTrack),
        imageAsset: activeTrack.imageAsset,
        logoAsset: activeTrack.logoAsset,
        routeScale: activeTrack.routeScale,
        startGrid: activeTrack.startGrid,
      };
    },
    setTrack(idOrIndex) {
      const index =
        typeof idOrIndex === "number"
          ? idOrIndex
          : trackCatalog.findIndex((track) => track.id === idOrIndex);
      if (index >= 0) setActiveTrack(index);
    },
    previousTrack,
    nextTrack,
  };

  function findLastIndex(items, predicate) {
    for (let i = items.length - 1; i >= 0; i -= 1) {
      if (predicate(items[i], i)) return i;
    }
    return -1;
  }

  function smoothClosedPath(points, steps) {
    const out = [];
    for (let i = 0; i < points.length; i += 1) {
      const p0 = points[(i - 1 + points.length) % points.length];
      const p1 = points[i];
      const p2 = points[(i + 1) % points.length];
      const p3 = points[(i + 2) % points.length];
      for (let s = 0; s < steps; s += 1) {
        const t = s / steps;
        const t2 = t * t;
        const t3 = t2 * t;
        out.push({
          x:
            0.5 *
            (2 * p1.x +
              (-p0.x + p2.x) * t +
              (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 +
              (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
          y:
            0.5 *
            (2 * p1.y +
              (-p0.y + p2.y) * t +
              (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 +
              (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3),
        });
      }
    }
    out.push(out[0]);
    return out;
  }

  function buildHexField() {
    const outerGridMetrics = projectionRhombusMetrics();
    const fieldMetrics = lowerPlaneMetrics(greyFieldCenter());
    planeHalfWidth = fieldMetrics.dx * fieldMetrics.halfCols;

    trackGridCenters = buildRhombusCells(outerGridMetrics, true);
    hexCenters = buildRhombusCells(fieldMetrics);

    const fieldBounds = rhombusPolygon(fieldMetrics);
    projectionGeometry = {
      bounds: rhombusPolygon(outerGridMetrics),
      fieldLeft: fieldBounds[0],
      fieldRight: fieldBounds[2],
      bottom: fieldBounds[3],
    };
  }

  function lowerPlaneMetrics(center) {
    const cell = 7.95 * baseScale;
    return {
      cell,
      center: center || lowerPlaneCenter(),
      dx: cell * 1.78,
      dy: cell * 1.78,
      halfCols: 22,
      rows: 11,
    };
  }

  function projectionRhombusMetrics() {
    const metrics = lowerPlaneMetrics();
    return {
      ...metrics,
      halfCols: metrics.halfCols + PROJECTION_BAND_ROWS * COLUMNS_PER_GRID_ROW,
      rows: metrics.rows + PROJECTION_BAND_ROWS,
    };
  }

  function buildRhombusCells(metrics, includeGridCoordinates) {
    const cells = [];
    for (let col = -metrics.halfCols; col <= metrics.halfCols; col += 1) {
      const rowRange = columnRowRange(col, metrics);
      for (let row = rowRange.min; row <= rowRange.max; row += 1) {
        const point = axialToScreen(col, row, metrics);
        cells.push(includeGridCoordinates ? { ...point, col, row } : point);
      }
    }
    return cells;
  }

  function columnRowRange(col, metrics) {
    const middleCount = metrics.rows * 2 + 1;
    const count = Math.max(1, middleCount - Math.abs(col));
    const min = -Math.floor(count / 2);
    return {
      min,
      max: min + count - 1,
    };
  }

  function axialToScreen(col, row, metrics) {
    const stagger = Math.abs(col) % 2 === 0 ? 0 : 0.5;
    return {
      x: metrics.center.x + col * metrics.dx,
      y: metrics.center.y + (row + stagger) * metrics.dy,
    };
  }

  function lowerPlaneCenter() {
    const rowHeight = 7.95 * baseScale * 1.78;
    return {
      x: width * 0.5,
      y: height * 0.5 - rowHeight * LOWER_RHOMBUS_LIFT_ROWS,
    };
  }

  function greyFieldCenter() {
    const metrics = lowerPlaneMetrics();
    return {
      x: metrics.center.x,
      y: metrics.center.y + metrics.dy * GREY_FIELD_OFFSET_ROWS,
    };
  }

  function rhombusPolygon(metrics) {
    return [
      { x: metrics.center.x - metrics.dx * metrics.halfCols, y: metrics.center.y },
      { x: metrics.center.x, y: metrics.center.y - metrics.dy * metrics.rows },
      { x: metrics.center.x + metrics.dx * metrics.halfCols, y: metrics.center.y },
      { x: metrics.center.x, y: metrics.center.y + metrics.dy * metrics.rows },
    ];
  }

  function routePoint(progress) {
    const target = ((progress % 1) + 1) % 1 * totalRouteLength;
    let lo = 0;
    let hi = routeLengths.length - 1;
    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2);
      if (routeLengths[mid] < target) lo = mid + 1;
      else hi = mid;
    }
    const i = Math.max(1, lo);
    const prev = route[i - 1];
    const next = route[i];
    const span = Math.max(0.0001, routeLengths[i] - routeLengths[i - 1]);
    const t = (target - routeLengths[i - 1]) / span;
    return {
      x: prev.x + (next.x - prev.x) * t,
      y: prev.y + (next.y - prev.y) * t,
      angle: Math.atan2(next.y - prev.y, next.x - prev.x),
    };
  }

  function drawCircleCell(cx, cy, size, fill, alpha) {
    ctx.globalAlpha = alpha;
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.arc(cx, cy, size, 0, TAU);
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  function drawHexField(marker, projection, time) {
    const cell = 6.95 * baseScale;
    for (const p of hexCenters) {
      const distToMarker = distance(p, marker);
      const cut = isNearPath(p, projection.cutSegments, 22 * baseScale);
      const coveredByProjection = isProjectedTrackCell(p, projection);
      const spotlight = Math.max(0, 1 - distToMarker / (105 * baseScale));
      const drift = 0.04 * Math.sin(time * 0.002 + p.x * 0.02 + p.y * 0.014);

      if (cut || coveredByProjection) continue;
      drawCircleCell(
        p.x,
        p.y,
        cell,
        spotlight > 0.05 ? palette.greyDim : palette.grey,
        0.86 + spotlight * 0.08 + drift
      );
    }
  }

  function drawMidTrack(marker, projection, time) {
    drawProjectionGuide(projection);
    drawHexField(marker, projection, time);
    drawProjectedTrackLayer(projection);
  }

  function drawProjectionGuide(projection) {
    const cell = 6.95 * baseScale;
    for (const p of trackGridCenters) {
      if (!pointInConvexPolygon(p, projection.bounds)) continue;
      drawCircleCell(p.x, p.y, cell, palette.gold, 1);
    }
  }

  function drawProjectedTrackLayer(projection) {
    const cell = 6.95 * baseScale;
    for (const p of trackGridCenters) {
      if (!isProjectedTrackCell(p, projection)) continue;
      drawCircleCell(p.x, p.y, cell, palette.orange, 1);
    }
  }

  function isProjectedTrackCell(point, projection) {
    if (!isInsideProjectionArea(point, projection)) return false;
    return isNearPath(point, projection.activeSegments, projection.trackWidth);
  }

  function isInsideProjectionArea(point, projection) {
    if (!pointInConvexPolygon(point, projection.bounds)) return false;
    const lowerBoundary =
      point.x <= projection.bottom.x
        ? lineYAtX(projection.fieldLeft, projection.bottom, point.x)
        : lineYAtX(projection.bottom, projection.fieldRight, point.x);
    return point.y <= lowerBoundary - 30 * baseScale;
  }

  function lineYAtX(a, b, x) {
    const t = (x - a.x) / Math.max(0.0001, b.x - a.x);
    return a.y + (b.y - a.y) * t;
  }

  function pointInConvexPolygon(point, vertices) {
    let direction = 0;
    for (let i = 0; i < vertices.length; i += 1) {
      const a = vertices[i];
      const b = vertices[(i + 1) % vertices.length];
      const cross = (b.x - a.x) * (point.y - a.y) -
        (b.y - a.y) * (point.x - a.x);
      if (Math.abs(cross) < 0.001) continue;
      const nextDirection = Math.sign(cross);
      if (direction && direction !== nextDirection) return false;
      direction = nextDirection;
    }
    return true;
  }

  function projectedRoutePoint(localProgress, anchorProgress, scale) {
    const anchor = routePoint(anchorProgress);
    const p = routePoint(localProgress);
    const focus = lowerPlaneCenter();
    const dx = p.x - anchor.x;
    const dy = p.y - anchor.y;
    const localScale = scale || projectionScale(anchorProgress);
    const rotation = -0.44;
    const cos = Math.cos(rotation);
    const sin = Math.sin(rotation);
    const sx = dx * localScale;
    const sy = dy * localScale;

    return {
      x: focus.x + sx * cos - sy * sin,
      y: focus.y + sx * sin + sy * cos,
    };
  }

  function projectionScale(progress) {
    const anchor = routePoint(progress);
    let maxX = 1;
    const windowSize = 0.16;
    for (let i = 0; i <= 36; i += 1) {
      const p = routePoint(progress - windowSize + (windowSize * 2 * i) / 36);
      const dx = p.x - anchor.x;
      maxX = Math.max(maxX, Math.abs(dx));
    }
    const fit = (planeHalfWidth * 2.58) / maxX;
    return Math.max(2.48, Math.min(4.43, fit));
  }

  function projectedRoutePath(progress, windowSize) {
    const points = [];
    const steps = 84;
    const scale = projectionScale(progress);
    for (let i = 0; i <= steps; i += 1) {
      points.push(
        projectedRoutePoint(
          progress - windowSize + (windowSize * 2 * i) / steps,
          progress,
          scale
        )
      );
    }
    return points;
  }

  function offsetPath(points, dx, dy) {
    return points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
  }

  function createProjection(activePath, cutPath) {
    return {
      ...projectionGeometry,
      activeSegments: pathSegments(activePath),
      cutSegments: pathSegments(cutPath),
      trackWidth: 19 * baseScale,
    };
  }

  function pathSegments(points) {
    const segments = [];
    for (let i = 1; i < points.length; i += 1) {
      const a = points[i - 1];
      const b = points[i];
      segments.push({
        a,
        b,
        minX: Math.min(a.x, b.x),
        maxX: Math.max(a.x, b.x),
        minY: Math.min(a.y, b.y),
        maxY: Math.max(a.y, b.y),
      });
    }
    return segments;
  }

  function drawTopTrack() {
    if (routeLayerDirty) {
      rebuildTopTrackLayer("#fed98d", 0.76, 12.4 * baseScale);
    }

    pixelCtx.save();
    pixelCtx.setTransform(1, 0, 0, 1, 0, 0);
    pixelCtx.drawImage(routeLayerCanvas, 0, 0);
    pixelCtx.restore();
  }

  function rebuildTopTrackLayer(color, alpha, lineWidth) {
    const layerWidth = routeLayerCanvas.width;
    const layerHeight = routeLayerCanvas.height;
    routeLayerCtx.clearRect(0, 0, layerWidth, layerHeight);

    if (route.length < 2) {
      routeLayerDirty = false;
      return;
    }

    const maskWidth = trackMaskCanvas.width;
    const maskHeight = trackMaskCanvas.height;
    trackMaskCtx.setTransform(1, 0, 0, 1, 0, 0);
    trackMaskCtx.clearRect(0, 0, maskWidth, maskHeight);
    trackMaskCtx.strokeStyle = "#fff";
    trackMaskCtx.globalAlpha = 1;
    trackMaskCtx.lineWidth = Math.max(2, Math.round(lineWidth / PIXEL_SCALE));
    trackMaskCtx.lineCap = "round";
    trackMaskCtx.lineJoin = "round";
    trackMaskCtx.beginPath();
    trackMaskCtx.moveTo(
      Math.round(route[0].x / PIXEL_SCALE),
      Math.round(route[0].y / PIXEL_SCALE)
    );
    for (let i = 1; i < route.length; i += 1) {
      trackMaskCtx.lineTo(
        Math.round(route[i].x / PIXEL_SCALE),
        Math.round(route[i].y / PIXEL_SCALE)
      );
    }
    trackMaskCtx.stroke();

    const rgba = parseHexColor(color);
    const mask = trackMaskCtx.getImageData(0, 0, maskWidth, maskHeight);
    const out = routeLayerCtx.createImageData(maskWidth, maskHeight);
    const targetAlpha = Math.round(alpha * 255);

    for (let i = 0; i < mask.data.length; i += 4) {
      if (mask.data[i + 3] < 96) continue;
      out.data[i] = rgba.r;
      out.data[i + 1] = rgba.g;
      out.data[i + 2] = rgba.b;
      out.data[i + 3] = targetAlpha;
    }

    routeLayerCtx.putImageData(out, 0, 0);
    routeLayerDirty = false;
  }

  function parseHexColor(color) {
    const value = color.replace("#", "");
    return {
      r: parseInt(value.slice(0, 2), 16),
      g: parseInt(value.slice(2, 4), 16),
      b: parseInt(value.slice(4, 6), 16),
    };
  }

  function drawMarker(marker, time) {
    const blinkOpacity = 0.65 + 0.35 * Math.sin((time / 1000) * TAU);
    const radius = 15 * baseScale;

    pixelCtx.strokeStyle = `rgba(255, 224, 78, ${blinkOpacity})`;
    pixelCtx.lineWidth = 7.2 * baseScale;
    pixelCtx.beginPath();
    pixelCtx.arc(marker.x, marker.y, radius, 0, TAU);
    pixelCtx.stroke();

    pixelCtx.strokeStyle = `rgba(255, 248, 170, ${blinkOpacity})`;
    pixelCtx.lineWidth = 3.2 * baseScale;
    pixelCtx.beginPath();
    pixelCtx.arc(marker.x, marker.y, radius, 0, TAU);
    pixelCtx.stroke();
  }

  function draw(time) {
    if (time - lastRenderTime < FRAME_INTERVAL) {
      requestAnimationFrame(draw);
      return;
    }
    lastRenderTime = time;

    if (animationStartTime === null) animationStartTime = time;
    const elapsed = Math.max(0, time - animationStartTime);
    const progress = (1 - (elapsed * 0.000024) % 1) % 1;
    const marker = routePoint(progress);
    const activePath = projectedRoutePath(progress, 0.16);
    const cutPath = offsetPath(activePath, 0, 54 * baseScale);
    const projection = createProjection(activePath, cutPath);

    ctx.fillStyle = palette.gold;
    ctx.fillRect(0, 0, width, height);

    const bgGradient = ctx.createRadialGradient(
      width * 0.55,
      height * 0.47,
      80 * baseScale,
      width * 0.55,
      height * 0.47,
      650 * baseScale
    );
    bgGradient.addColorStop(0, "rgba(255, 199, 24, 0.24)");
    bgGradient.addColorStop(1, "rgba(244, 173, 0, 0.08)");
    ctx.fillStyle = bgGradient;
    ctx.fillRect(0, 0, width, height);

    drawMidTrack(marker, projection, time);
    pixelCtx.clearRect(0, 0, width, height);
    drawTopTrack();
    drawMarker(marker, time);
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(pixelCanvas, 0, 0, canvas.width, canvas.height);
    ctx.restore();

    requestAnimationFrame(draw);
  }

  function distance(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function isNearPath(point, segments, maxDistance) {
    const maxDistanceSq = maxDistance * maxDistance;
    for (const segment of segments) {
      if (
        point.x < segment.minX - maxDistance ||
        point.x > segment.maxX + maxDistance ||
        point.y < segment.minY - maxDistance ||
        point.y > segment.maxY + maxDistance
      ) {
        continue;
      }
      if (distanceToSegmentSq(point, segment.a, segment.b) <= maxDistanceSq) {
        return true;
      }
    }
    return false;
  }

  function distanceToSegmentSq(p, a, b) {
    const vx = b.x - a.x;
    const vy = b.y - a.y;
    const wx = p.x - a.x;
    const wy = p.y - a.y;
    const c1 = vx * wx + vy * wy;
    const c2 = vx * vx + vy * vy;
    const t = Math.max(0, Math.min(1, c1 / c2));
    const dx = p.x - (a.x + vx * t);
    const dy = p.y - (a.y + vy * t);
    return dx * dx + dy * dy;
  }

  function readStoredScale() {
    try {
      const storedValue = window.localStorage.getItem("r4-wallpaper-scale");
      if (storedValue !== null) {
        const value = Number(storedValue);
        if (Number.isFinite(value)) return Math.max(0.25, Math.min(2, value));
      }
    } catch (error) {
      console.warn("Scale preference unavailable.", error);
    }
    return 1;
  }

  function syncScaleControl() {
    if (scaleValue) scaleValue.textContent = `${Math.round(settings.scale * 100)}%`;
    for (const step of scaleSteps) {
      const value = Number(step.dataset.scale);
      const isFilled = value <= settings.scale + 0.001;
      const isCurrent = Math.abs(value - settings.scale) < 0.001;
      step.classList.toggle("is-filled", isFilled);
      step.classList.toggle("is-current", isCurrent);
      step.setAttribute("aria-pressed", isCurrent ? "true" : "false");
    }
  }

  function syncLogoControl() {
    if (logoToggle) logoToggle.checked = settings.logo;
    if (bottomLogo) bottomLogo.hidden = !settings.logo;
  }

  function syncTrackSelectControl() {
    if (trackSelectToggle) trackSelectToggle.checked = settings.trackSelect;
    if (trackSelectors) trackSelectors.hidden = !settings.trackSelect || trackCatalog.length < 2;
  }

  function syncMuteControl() {
    if (music) music.muted = settings.muted;
    if (muteToggle) muteToggle.setAttribute("aria-pressed", settings.muted ? "true" : "false");
    if (muteIndicator) muteIndicator.classList.toggle("is-checked", settings.muted);
  }

  function setContentScale(value) {
    settings.scale = Math.max(0.25, Math.min(2, Number(value) || 1));
    try {
      window.localStorage.setItem("r4-wallpaper-scale", String(settings.scale));
    } catch (error) {
      console.warn("Could not store scale preference.", error);
    }
    syncScaleControl();
    rebuildScene();
  }

  function readStoredLogo() {
    try {
      const value = window.localStorage.getItem("r4-wallpaper-logo");
      if (value === "0") return false;
      if (value === "1") return true;
    } catch (error) {
      console.warn("Logo preference unavailable.", error);
    }
    return true;
  }

  function setLogoVisible(value) {
    settings.logo = Boolean(value);
    try {
      window.localStorage.setItem("r4-wallpaper-logo", settings.logo ? "1" : "0");
    } catch (error) {
      console.warn("Could not store logo preference.", error);
    }
    syncLogoControl();
  }

  function readStoredTrackSelect() {
    try {
      const value = window.localStorage.getItem("r4-wallpaper-track-select");
      if (value === "0") return false;
      if (value === "1") return true;
    } catch (error) {
      console.warn("Track selector preference unavailable.", error);
    }
    return false;
  }

  function setTrackSelectVisible(value) {
    settings.trackSelect = Boolean(value);
    try {
      window.localStorage.setItem("r4-wallpaper-track-select", settings.trackSelect ? "1" : "0");
    } catch (error) {
      console.warn("Could not store track selector preference.", error);
    }
    syncTrackSelectControl();
  }

  function readStoredMuted() {
    try {
      const value = window.localStorage.getItem("r4-wallpaper-muted");
      if (value === "0") return false;
      if (value === "1") return true;
    } catch (error) {
      console.warn("Mute preference unavailable.", error);
    }
    return false;
  }

  function setMuted(value) {
    settings.muted = Boolean(value);
    try {
      window.localStorage.setItem("r4-wallpaper-muted", settings.muted ? "1" : "0");
    } catch (error) {
      console.warn("Could not store mute preference.", error);
    }
    syncMuteControl();
    startMusic();
  }

  async function startMusic() {
    if (!music) return;
    music.volume = 1;
    music.muted = settings.muted;
    try {
      await music.play();
    } catch (error) {
      window.addEventListener("pointerdown", unlockMusicOnce, { once: true });
      window.addEventListener("keydown", unlockMusicOnce, { once: true });
      console.warn("Browser blocked autoplay until the first interaction.", error);
    }
  }

  function unlockMusicOnce() {
    startMusic();
  }

  for (const step of scaleSteps) {
    step.addEventListener("click", () => {
      setContentScale(step.dataset.scale);
    });
  }

  logoToggle.addEventListener("change", () => {
    setLogoVisible(logoToggle.checked);
  });

  trackSelectToggle.addEventListener("change", () => {
    setTrackSelectVisible(trackSelectToggle.checked);
  });

  for (const button of trackArrowButtons) {
    button.addEventListener("click", () => {
      const step = Number(button.dataset.trackStep) || 1;
      setActiveTrack(activeTrackIndex + step);
    });
  }

  muteToggle.addEventListener("click", () => {
    setMuted(!settings.muted);
  });

  window.addEventListener("resize", resize);
  syncScaleControl();
  syncLogoControl();
  syncTrackSelectControl();
  syncMuteControl();
  syncTrackInfo();
  startMusic();
  resize();
  draw(0);
})();
