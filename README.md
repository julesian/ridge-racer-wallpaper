# R4 Spiral Grid Wallpaper

https://github.com/user-attachments/assets/cc8a2561-fa78-460a-9b8c-61d0a002c759

A Ridge Racer Type 4 inspired animated web wallpaper for Wallpaper Engine.

## Run locally

Open `index.html` in a browser, or serve the folder with any static server.

## Project structure

- `index.html`, `styles.css`, and `script.js` are the wallpaper runtime.
- `assets/r4-logo.svg`, `assets/spiral-ahead.mp3`, and `assets/track-vector/track-route-clean-trace.js` are loaded by the wallpaper.
- `assets/track-vector/track-route-clean-trace.json` and `.svg` mirror the runtime route for inspection.
- `tools/` contains one-off extraction scripts for rebuilding route assets from reference screenshots.

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

The generated `track-route-clean-trace.js` is the only route file required by the live wallpaper.
