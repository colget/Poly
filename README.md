Polygonal Hand-Tracker: Custom Virtual Input Zone

A lightweight, webcam-based hand-tracking tool that lets you define a movable polygonal "virtual trackpad" in air using your fingertip.
Cursor control is restricted to movements inside your custom-drawn shape — perfect for precise, low-fatigue input (e.g., zero-gravity environments like ISS/Artemis, accessibility, or touchless setups).

Unlike most virtual mice (fixed bounding boxes or full-screen tracking), this lets you:
Draw any polygon (square, rectangle, irregular) by tracing with your index finger.
Save/load profiles for reuse.
Grab & relocate the zone with a 4–5 finger gesture (ideal for drifting in microgravity).
Ignore input outside the zone to reduce jitter/false positives.

Built with MediaPipe Hand Landmarker and OpenCV.

Current state (work in progress): drawing the zone is fully touchless. Cursor control, clicking,
grabbing the zone and saved profiles are still to come.

| Mode | Gesture | Action |
|---|---|---|
| DRAWING | Point (index finger only) and hold still ~0.8 s | Add a point anywhere, in any order (a ring fills while you hold) |
| DRAWING | Hold still on an earlier point (3+ points placed) | Finish: the points are joined into a zone -> ACTIVE |
| DRAWING | Fist held ~1 s | Undo the last point |
| ACTIVE | Point | Shows whether your fingertip is inside the zone |
| ACTIVE | Fist held ~2 s | Clear the zone and draw a new one |

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
instead of the webcam), `--sound`, and `--debug-keys` (developer fallback: 'd' add point,
'f' close, 'r' clear).

Run the tests with `pytest`.


Standard air-gesture mice tire users with full-arm waving.  
This bounded, user-defined zone minimizes motion for prolonged use, especially in space where physical mice or trackballs float away and arm strain is amplified.

Potential uses: Space ops (NASA/ESA touchless tools), hygiene-sensitive environments, VR/AR prototyping, accessibility.
