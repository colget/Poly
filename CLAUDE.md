# CLAUDE.md — Poly (Polygonal Hand-Tracker / Virtual Trackpad)

## What this project is
A webcam hand-tracking tool. The user traces a polygon in the air with their index
fingertip; that polygon becomes a "virtual trackpad". Only fingertip movement
*inside* the polygon controls the cursor. Goal: precise, low-fatigue touchless input
(accessibility, hygiene-sensitive settings, microgravity use cases).

Stack: Python, OpenCV, MediaPipe Tasks `HandLandmarker` (model file
`hand_landmarker.task`, already in the repo root).

## Current state (be honest about the gap)
`poly.py` (~150 lines) is a working proof of concept that ONLY does:
- live webcam feed with index-fingertip marker (landmark 8)
- add polygon vertices with `d`, close with `f` (3+ points), reset `r`, quit `q`/ESC
- inside/outside test via `cv2.pointPolygonTest`, shown as on-screen text

The README describes features that are NOT implemented yet:
cursor control, clicking, grab-and-move gesture, save/load profiles.
The work below builds those.

## Environment constraints — read first
- You (Claude Code) are running in a cloud sandbox: **no webcam, no display, no real
  mouse.** You cannot run the live app. Do not try to "test" it by launching it.
- The real target machine is **Windows** with a webcam, run by the owner (Geraint).
- Therefore: keep all logic (geometry, mapping, smoothing, gestures, profiles) in
  **pure functions that take plain numbers/landmark lists**, and test those with
  pytest. Camera, window and mouse code stays in a thin I/O layer.
- When you finish a phase, write clear manual test steps for Geraint to run on
  Windows (see "Handoff notes" below).

## Known bugs — fix in Phase 1
1. **Hard-coded Windows model path** (`C:\Users\Geraint\...`). The model is in the
   repo, so resolve it relative to the script: `Path(__file__).parent / "hand_landmarker.task"`,
   with an optional `--model` CLI override.
2. **Timestamps for `detect_for_video`.** It needs strictly increasing timestamps.
   `cap.get(cv2.CAP_PROP_POS_MSEC)` is unreliable for live webcams (often 0 or
   non-increasing). Use `time.monotonic()`-based milliseconds and guarantee each
   value is greater than the last.
3. **Frame is not mirrored.** Moving the hand left moves the marker right. Flip the
   frame horizontally (`cv2.flip(frame, 1)`) before detection so movement feels natural.
4. `exit()` → `sys.exit(1)` with an error code; close the landmarker and release
   the camera in a `finally`/context manager.

## Target structure
```
poly/
  __init__.py
  geometry.py     # point-in-polygon, polygon bounds, polygon→screen mapping
  filters.py      # One Euro filter (cursor smoothing)
  gestures.py     # pinch detection w/ hysteresis, open-hand "grab" detection
  profiles.py     # save/load polygon profiles as JSON
  tracker.py      # MediaPipe wrapper (only file that imports mediapipe)
  cursor.py       # mouse control backend (only file that moves the real mouse)
  app.py          # main loop, keys, drawing, CLI args
tests/
  test_geometry.py, test_filters.py, test_gestures.py, test_profiles.py
poly.py           # keep as a thin entry point: `from poly.app import main; main()`
requirements.txt  # pinned versions
```
Why: separating pure logic from camera/mouse I/O is what makes this testable in a
sandbox and debuggable on the real machine.

## Phases
Do ONE phase per session unless told otherwise. Stop at the end of each phase,
summarise what changed, and list the manual test steps.

### Phase 1 — Clean-up and structure
- Fix the 4 bugs above.
- Create the package layout above; move existing behaviour across unchanged.
- Add `requirements.txt` (opencv-python, mediapipe, numpy, pytest + cursor lib later).
  Check which Python versions the current mediapipe release supports and note it in README.
- Add `.gitignore` (venv, `__pycache__`, `profiles/*.json` if user-specific).
- Add CLI args: `--camera INDEX`, `--model PATH`, `--source VIDEO_FILE` (lets us replay
  a recorded clip instead of a live camera — useful for repeatable testing).
- **Done when:** `pytest` passes, and the app behaves exactly as before on Windows.

### Phase 2 — Cursor mapping + smoothing
- Map fingertip position inside the polygon to screen coordinates:
  - If the polygon has exactly 4 points: use a perspective transform
    (`cv2.getPerspectiveTransform`) from the quad to the screen rectangle. Why: it
    fills the whole screen even if the traced shape is skewed.
  - Otherwise: normalise by the polygon's bounding box, then clamp to screen.
  - Outside the polygon: cursor does not move (this is the core feature).
- Smoothing: implement a **One Euro filter** on x/y. Why: it removes jitter when the
  finger is still but adds little lag during fast movement — better than a plain
  moving average for pointing.
- Cursor backend in `cursor.py` (pyautogui or pynput — pick one, justify briefly).
  **Cursor control must be OFF by default**, enabled with `--control-cursor`, with
  `c` key to toggle at runtime. Why: a buggy tracker hijacking the real mouse makes
  the machine hard to use.
- **Done when:** unit tests cover mapping (corners, centre, outside points) and the filter.

### Phase 3 — Gestures
- **Click:** pinch = distance between thumb tip (4) and index tip (8), **normalised by
  hand size** (e.g. wrist 0 → middle-finger MCP 9). Why: raw pixel distance changes as
  the hand moves closer/further from the camera.
  Use hysteresis (separate press/release thresholds) + a short debounce so one pinch
  = one click.
  Note: pinching moves the index tip — freeze cursor position at pinch start.
- **Grab & move zone:** 4–5 fingers extended → the polygon follows the hand
  (translate all vertices by hand movement); releasing the open hand drops it.
  Detect "extended" using fingertip-to-wrist vs knuckle-to-wrist distance ratios,
  not y-coordinates alone (y-only breaks when the hand is rotated).
- Optional: touchless vertex placement (e.g. hold still for ~1 s = add point) so the
  `d` key isn't needed.
- **Done when:** gesture functions are tested with synthetic landmark lists.

### Phase 4 — Profiles
- Save/load polygons as JSON in `profiles/`. Store vertices **normalised (0–1)**
  plus the camera resolution they were made at. Why: pixel coordinates break if the
  camera resolution changes.
- Keys: `s` save (named or timestamped), `l` load most recent; `--profile NAME` CLI arg.
- **Done when:** round-trip save/load tests pass.

### Phase 5 — Docs
- Update README so it only claims features that exist; add install, run, key list,
  gesture list, known limitations. Add a LICENSE only if the owner asks.

## Conventions
- Python 3, type hints, small functions, docstrings on public functions.
- Only `tracker.py` imports mediapipe; only `cursor.py` moves the mouse.
- Don't modify or re-download `hand_landmarker.task`.
- Keep `poly.py` runnable as `python poly.py` at every phase.
- Prefer clarity over cleverness — the owner is learning from this code, so comment
  the *why* for any non-obvious maths (perspective transform, One Euro parameters).

## Handoff notes (end of every phase)
Write in your final message:
1. Files changed and why.
2. Exact commands for Windows: create venv, `pip install -r requirements.txt`, run.
3. A short manual checklist (e.g. "trace a square, enable cursor, move inside → cursor
   moves; move outside → cursor stays").
4. Anything you could not verify because there is no camera in the sandbox.
