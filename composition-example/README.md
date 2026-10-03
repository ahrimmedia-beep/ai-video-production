# Composition example

One HyperFrames composition from the pipeline, reduced to six scenes and 17 seconds. The layout, helpers and motion code come from a production video. The text is neutral placeholder text.

## Files

| File | What it holds |
|---|---|
| `index.html` | The frame (1080 x 1920), the styles, the six scenes, the presenter box and the caption band. |
| `timeline.js` | One paused GSAP timeline: scene changes, layout changes, themes, captions and a clock and a counter driven by timeline time. |
| `package.json` | The pinned HyperFrames CLI commands. |

## How HyperFrames renders it

1. The root `#root` element declares the size and the length: `data-width`, `data-height`, `data-duration`.
2. `timeline.js` builds one timeline with `{ paused: true }`. A short inline script registers it as `window.__timelines["main"]`. The key matches `data-composition-id`.
3. The renderer opens the page in a headless browser, seeks the timeline to each frame and captures it. Every animation and every text change is a function of timeline time, so any frame can be rendered on its own and comes out the same each time.
4. Frames and audio tracks are encoded into an MP4.

```bash
npm run check    # lint, runtime, layout, motion and contrast checks
npm run dev      # preview in the browser
npm run render   # writes renders/example.mp4
```

## What is replaced in this example

- **Presenter.** In production the presenter box holds the avatar video, cut into clips on the same segments as the voice track so the lips stay in sync after pauses are removed. Here it is a CSS silhouette with a "placeholder" tag.
- **Audio.** Production compositions have a voice track, a sound effects track and a music bed with volume automation. The example has no audio.
- **Caption timing.** Production captions start on the word timings of the voice. Here the times are set by hand.
- **Fonts and GSAP.** Production projects ship local font files and a local copy of GSAP. The example uses system fonts and loads GSAP 3.14.2 from the jsDelivr CDN.

The page references no local media files. `npm run check` reports 0 errors and 0 warnings. The remaining info notes come from scenes overlapping during crossfades and the slow camera push-in.
