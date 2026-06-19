# R4 Spiral Grid Wallpaper

A Ridge Racer Type 4 inspired animated web wallpaper for Wallpaper Engine.

## Run locally

Open `index.html` in a browser, or serve the folder with any static server.

## Project structure

- `index.html`, `styles.css`, and `script.js` are the wallpaper runtime.
- `assets/r4-logo-tight.svg`, `assets/spiral-ahead.mp3`, track route files in `assets/track-vector/`, and `assets/tracks.js` are loaded by the wallpaper.
- `assets/tracks/wonderhill/` and `assets/tracks/shooting-hoops/` contain each track's layout, logo, and remastered image assets.
- `assets/track-vector/wonderhill-route.json` and `.svg` mirror the runtime route for inspection.
- `tools/` contains the Wonderhill and Shooting HooPs route builders.

## Tracks

Tracks are registered in `assets/tracks.js`. Each entry owns the display name, country, image/logo assets, route data, and starting-grid point:

```js
{
  id: "wonderhill-jpn",
  name: "Wonderhill",
  country: "JPN",
  imageAsset: "assets/tracks/wonderhill/wonderhill-remastered-borderless-orange-wave.png",
  logoAsset: "assets/tracks/wonderhill/wonderhill-logo-square.png",
  route: window.TRACK_ROUTE_WONDERHILL,
  startGrid: {
    point: [388.5, 493.5],
  },
}
```

When a track is loaded, the route is trimmed to begin at `startGrid.point` where possible and the animation timer resets so the marker starts from the grid. At runtime, `window.R4Wallpaper.setTrack(idOrIndex)` and `window.R4Wallpaper.nextTrack()` can be used to cycle registered tracks.

## Music

Place your own legally obtained loop of "Spiral Ahead" from the R4 OST at:

```text
assets/spiral-ahead.mp3
```

Browsers and Wallpaper Engine require a click or interaction before audio can start in many contexts, so the small circular control in the lower-right toggles playback.

## Wallpaper Engine

1. Open Wallpaper Engine.
2. Choose **Create Wallpaper**.
3. Choose **Web** and select this folder's `index.html`.
4. Keep `project.json` in the folder for metadata.
5. Add your audio file under `assets/spiral-ahead.mp3` before publishing.

The wallpaper is built with plain HTML, CSS, and Canvas, so it exports cleanly as a web wallpaper.

## Rebuilding route assets

The route tooling expects a source screenshot path instead of a machine-specific temp file:

```text
python tools/build_clean_trace_route.py path/to/reference.png
```

The generated `wonderhill-route.js` is the only route file required by the live wallpaper.

Shooting HooPs can be rebuilt from its layout image with:

```text
python tools/build_shooting_hoops_route.py assets/tracks/shooting-hoops/shooting-hoops-layout.png
```
