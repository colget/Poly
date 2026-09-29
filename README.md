Polygonal Hand-Tracker: Custom Virtual Input Zone

A lightweight, webcam-based hand-tracking tool that lets you define a movable polygonal "virtual trackpad" in air using your fingertip.
Cursor control is restricted to movements inside your custom-drawn shape — perfect for precise, low-fatigue input (e.g., zero-gravity environments like ISS/Artemis, accessibility, or touchless setups).

Unlike most virtual mice (fixed bounding boxes or full-screen tracking), this lets you:
Draw any polygon (square, rectangle, irregular) by tracing with your index finger.
Save/load profiles for reuse.
Grab & relocate the zone with a 4–5 finger gesture (ideal for drifting in microgravity).
Ignore input outside the zone to reduce jitter/false positives.

Built with MediaPipe Hand Landmarker and OpenCV.

Current state (work in progress): creating, moving and clearing the zone and moving the mouse
pointer and clicking are fully touchless. Saved profiles are still to come.

| Mode | Gesture | Action |
|---|---|---|
| DRAWING | Point (index finger only) and hold still ~0.8 s | Add a point anywhere, in any order (a ring fills while you hold) |
| DRAWING | Hold still on an earlier point (3+ points placed) | Finish: the points are joined into a zone -> ACTIVE |
| DRAWING | Fist held ~1 s | Undo the last point |
| DRAWING | Open palm held ~1.5 s (no points yet) | Quick zone: a ready-made rectangle around your hand -> ACTIVE |
| ACTIVE | Point inside the zone | Moves the mouse pointer (see pointer modes below) |
| ACTIVE | Point outside the zone | Nothing - the pointer stays put, so you can let go of the mouse |
| ACTIVE | Pinch thumb tip to index tip (inside the zone) | Left click. The pointer freezes as your thumb closes in, so the click lands where you aimed. Two quick pinches = double-click |
| ACTIVE | Open palm held ~0.5 s | Pick the zone up; it follows your hand. Close your hand to drop it |
| ACTIVE | Fist held ~2 s | Clear the zone and draw a new one |

**Tracking tip:** MediaPipe has to see your *palm* to find your hand. When you point at the
bottom part of the picture, your palm is below the camera's view and tracking drops out. The
shaded band at the bottom of the screen shows where this happens. Keep zones above it (quick
zones do this automatically), sit a little further back, or tilt the camera down.

**Two pointer modes** (`--pointer`):

- `tablet` (default): each spot in the zone *is* a spot on the screen, like a drawing tablet. A
  4-cornered zone uses a perspective transform, so even a skewed zone reaches every screen corner.
- `trackpad`: moving your finger *nudges* the pointer, like a laptop trackpad, with acceleration
  (slow = precise, quick flick = far). Leaving the zone or relaxing your finger is "lifting" it.
  Movement is measured in hand sizes and scaled to the screen width, so it feels the same close
  to or far from the camera, and on a laptop or a big TV.

**Mouse control is off unless you ask for it.** By default a small screen map (bottom-right)
only *previews* where the pointer would go. Run with `--control-cursor` to move the real mouse.

The banner at the top always shows the current mode and what you can do. `--sound` adds a short
beep when a gesture is recognised. Quit with ESC/q or by closing the window.

## Install & run (Windows)

Requires **Python 3.11 or 3.12**. The pinned numpy (2.4) needs 3.11+, and mediapipe 1.0.1
officially supports up to 3.12.

```
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python poly.py
```

Options: `--camera INDEX` (try 1 or 2 if you get no image), `--model PATH` (defaults to
`hand_landmarker.task` next to `poly.py`), `--source VIDEO_FILE` (replay a recorded clip
instead of the webcam), `--sound`, `--control-cursor` (move the real mouse),
`--pointer tablet|trackpad`, `--camera-backend`, `--resolution WxH`, `--fps N`, `--screen WxH`
(override the detected screen size, e.g. `--screen 2560x1440`), and `--debug-keys` (developer fallback: 'd' add point,
'f' close, 'r' clear).

**If tracking feels laggy or jumpy**, try the camera options. The app prints what the camera
actually delivers at startup, and the live frame rate is shown at the bottom of the window:

```
python poly.py --camera-backend dshow
python poly.py --camera-backend dshow --resolution 1280x720 --fps 60
```

`dshow` (DirectShow) is often smoother than Windows' default camera driver. A higher resolution
helps when you're far from the camera. More frames per second makes the pointer feel less
laggy. Cameras ignore settings they can't do, so check the printed line.

Run the tests with `pytest`.


Standard air-gesture mice tire users with full-arm waving.  
This bounded, user-defined zone minimizes motion for prolonged use, especially in space where physical mice or trackballs float away and arm strain is amplified.

Potential uses: Space ops (NASA/ESA touchless tools), hygiene-sensitive environments, VR/AR prototyping, accessibility.
