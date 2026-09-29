# CLAUDE.md — Poly (Polygonal Hand-Tracker / Virtual Trackpad)

## What this project is
A webcam hand-tracking tool. The user traces a polygon in the air with their index
fingertip; that polygon becomes a "virtual trackpad". Only fingertip movement
*inside* the polygon controls the cursor. Goal: precise, low-fatigue touchless input.

**Target users have dirty or sterile hands** — e.g. a mechanic with oily hands, a
surgeon who must stay sterile. They cannot touch a keyboard or mouse.

## Core design principle: 100% touchless
- **Every** user action (draw, close, redraw, click, move zone) must be a hand gesture.
- Keyboard shortcuts stay ONLY as a developer/debug fallback (behind `--debug-keys`),
  never as the way a real user operates it.
- Because there is no physical feedback, **every gesture must give clear visual
  feedback** (progress ring, colour change, on-screen label) and optionally a short
  sound (`--sound`). The user must always know what mode they're in and whether a
  gesture was recognised.
- Destructive actions (reset/redraw) need a longer hold than normal actions, so they
  can't happen by accident while working.

Stack: Python, OpenCV, MediaPipe Tasks `HandLandmarker` (model file
`hand_landmarker.task`, already in the repo root).

## Current state
`poly.py` (~150 lines) is a working proof of concept that:
- shows the webcam feed with an index-fingertip marker (landmark 8)
- adds vertices with key `d`, closes with `f`, resets with `r`, quits `q`/ESC
- tests inside/outside via `cv2.pointPolygonTest`

Not implemented yet (README claims them): cursor control, clicking, grab-and-move,
profiles. **Drawing currently depends on the keyboard — this is the main thing to replace.**

## Gesture design (the spec to implement)

### Modes (state machine)
```
            (no saved profile)                    (saved profile found)
   start ───────────────────► DRAWING      start ─────────────────────► ACTIVE
                                 │  close polygon (dwell on earlier pt)   ▲
                                 └────────────────────────────────────────┘
   ACTIVE ── fist held ~2 s ──► DRAWING (polygon cleared)
   ACTIVE ── open palm ───────► GRAB ── palm closes / hand leaves ──► ACTIVE
   any mode ── no hand for N frames ──► stays in mode, cursor does nothing
```

### Gesture map
| Mode | Gesture | Action | Why this gesture |
|---|---|---|---|
| DRAWING | Point (index only) + **hold still ~0.8 s** (dwell) | Add vertex | Dwell needs no second gesture and is a proven accessibility technique; a progress ring shows it filling |
| DRAWING | Dwell **on any earlier vertex** (3+ points placed; not the one just placed) | Close polygon → ACTIVE | Owner's choice after testing: points are placed freely in any order with no path drawn between them; on close they are ordered by angle around their centroid so the outline never self-intersects. The just-placed vertex is excluded so a small drift after placing can't close by accident |
| DRAWING | Fist held ~1 s | Undo last vertex | Quick correction without restarting |
| ACTIVE | Point, inside zone | Move cursor | Core feature |
| ACTIVE | Point, outside zone | Nothing | Lets the user work normally without moving the mouse |
| ACTIVE | Pinch (thumb tip 4 + index tip 8) | Click | Natural "press"; cursor freezes at pinch start |
| ACTIVE | Open palm (4–5 fingers) | Grab & move zone | Big, unmistakable gesture |
| ACTIVE | Fist held ~2 s | Clear & redraw | Long hold because it's destructive |

### Recognition rules (important for reliability)
- A gesture only "counts" after it has been stable for several consecutive frames
  (debounce). Why: MediaPipe sometimes misclassifies single frames, especially
  during fast movement.
- Dwell = filtered fingertip stays within a small radius for the dwell time.
  **Radius is normalised by hand size** (wrist 0 → middle MCP 9), so it works at any
  distance from the camera and tolerates small tremors.
- Finger "extended" is decided from fingertip-to-wrist vs knuckle-to-wrist distance
  ratios, not y-coordinates alone (y-only breaks when the hand is rotated).
- Pinch uses hysteresis (separate press and release thresholds) + debounce, so one
  pinch = one click.
- In DRAWING mode, pinch and palm are ignored — only point, dwell and fist matter.
  Why: fewer active gestures in a mode = fewer false triggers.
- After a vertex is added, the dwell must reset (finger must move away) before the
  next vertex can be added — prevents stacking points on the same spot.
- All timings and thresholds live in one `config.py` (dataclass) so they can be tuned
  after real-world testing. Nothing is hard-coded inline.

## Environment constraints — read first
- You (Claude Code) run in a cloud sandbox: **no webcam, no display, no real mouse.**
  You cannot run the live app. Do not try to test it by launching it.
- The real target machine is **Windows** with a webcam, run by the owner (Geraint).
- Keep all logic (geometry, mapping, smoothing, gesture classification, dwell timers,
  state machine, profiles) in **pure functions/classes that take plain numbers,
  landmark lists and timestamps**, and test those with pytest. Camera, window and
  mouse code stays in a thin I/O layer.
- Timers must take the current time as an argument (not call `time.time()`
  internally) so tests can simulate "held for 2 seconds" instantly.
- Real-world risk to flag in handoff notes: **gloves** (nitrile, latex, dark work
  gloves) can reduce MediaPipe's hand detection. This must be tested early on real hardware.

## Known bugs — fix in Phase 1
1. **Hard-coded Windows model path** (`C:\Users\Geraint\...`). Resolve relative to the
   script: `Path(__file__).parent / "hand_landmarker.task"`, with a `--model` override.
2. **Timestamps for `detect_for_video`** must strictly increase. `CAP_PROP_POS_MSEC`
   is unreliable for live webcams. Use `time.monotonic()`-based ms, guaranteed increasing.
3. **Frame not mirrored.** Flip horizontally (`cv2.flip(frame, 1)`) before detection.
4. `exit()` → `sys.exit(1)`; close the landmarker and release the camera in `finally`.

## Target structure
```
poly/
  __init__.py
  config.py       # all thresholds & timings (dataclass)
  geometry.py     # point-in-polygon, bounds, polygon→screen mapping
  filters.py      # One Euro filter
  gestures.py     # classify pose: point / pinch / fist / open palm; dwell detector
  modes.py        # state machine: DRAWING / ACTIVE / GRAB, consumes gesture events
  profiles.py     # save/load polygon profiles as JSON
  feedback.py     # on-screen overlays (progress ring, mode label), optional sound
  tracker.py      # MediaPipe wrapper (only file that imports mediapipe)
  cursor.py       # mouse backend (only file that moves the real mouse)
  app.py          # main loop, CLI args, debug keys
tests/
  test_geometry.py, test_filters.py, test_gestures.py, test_modes.py, test_profiles.py
poly.py           # thin entry point: `from poly.app import main; main()`
requirements.txt  # pinned versions
```
Why: separating pure logic from camera/mouse I/O makes it testable in a sandbox
and debuggable on the real machine.

## Phases
Do ONE phase per session unless told otherwise. Stop at the end of each phase,
summarise what changed and list the manual test steps.

### Phase 1 — Clean-up and structure
- Fix the 4 bugs. Create the package layout; move existing behaviour across.
- Move existing keys behind `--debug-keys`.
- `requirements.txt` (opencv-python, mediapipe, numpy, pytest). Check which Python
  versions the current mediapipe release supports; note it in README.
- `.gitignore` (venv, `__pycache__`, `profiles/*.json`).
- CLI args: `--camera INDEX`, `--model PATH`, `--source VIDEO_FILE` (replay a recorded
  clip for repeatable testing), `--debug-keys`.
- **Done when:** `pytest` passes and behaviour is unchanged on Windows (with `--debug-keys`).

### Phase 2 — Touchless drawing (highest priority)
- Implement `config.py`, `gestures.py` (point, fist, dwell), `modes.py`
  (DRAWING ↔ ACTIVE, undo, clear & redraw) and `feedback.py` (progress ring for
  dwell/holds, mode label, highlight first vertex when close enough to close).
- One Euro filter on the fingertip, used by dwell detection (Why: raw landmarks jitter,
  which would constantly break the dwell).
- **Done when:** a full draw → close → redraw cycle works with no keyboard, and
  the state machine is covered by tests using synthetic landmark sequences with
  simulated timestamps.

### Phase 3 — Cursor mapping
- 4-point polygon → perspective transform (`cv2.getPerspectiveTransform`) to the
  screen rectangle. Why: fills the whole screen even if the traced shape is skewed.
  Otherwise → normalise by bounding box, clamp to screen. Outside → no movement.
- Cursor backend in `cursor.py` (pyautogui or pynput — pick one, justify briefly).
  Real mouse control only with `--control-cursor`. Why: a buggy tracker hijacking the
  mouse makes the machine hard to recover without touching it.
- **Done when:** mapping tests pass (corners, centre, outside points).

### Phase 4 — Click and grab
- Pinch click (hysteresis, debounce, freeze cursor at pinch start).
- Open-palm grab: polygon follows hand translation; drops when palm closes or hand leaves.
- **Done when:** gesture tests pass with synthetic landmarks.

### Phase 5 — Profiles
- Store vertices **normalised (0–1)** plus camera resolution. Why: pixel coordinates
  break if resolution changes.
- **Auto-save** on polygon close; **auto-load** the last profile at startup (start in
  ACTIVE). Why: the user shouldn't have to redraw the zone every time — and there's no
  keyboard to pick a file. `--profile NAME` and `--fresh` CLI args for setup.
- **Done when:** round-trip tests pass.

### Phase 6 — Docs
- README only claims features that exist: install, run, gesture table, known
  limitations (lighting, gloves, camera placement).

## Conventions
- Python 3, type hints, small functions, docstrings on public functions.
- Only `tracker.py` imports mediapipe; only `cursor.py` moves the mouse.
- Don't modify or re-download `hand_landmarker.task`.
- Keep `python poly.py` runnable at every phase.
- The owner is learning from this code: comment the *why* for non-obvious maths
  and design choices (perspective transform, One Euro parameters, hysteresis).

## Handoff notes (end of every phase)
1. Files changed and why.
2. Exact Windows commands: create venv, `pip install -r requirements.txt`, run.
3. A short manual checklist (e.g. "point and hold → ring fills → vertex added").
4. Anything you could not verify (no camera in the sandbox), and which thresholds in
   `config.py` are most likely to need tuning.
