Polygonal Hand-Tracker: Custom Virtual Input Zone

A lightweight, webcam-based hand-tracking tool that lets you define a movable polygonal "virtual trackpad" in air using your fingertip.
Cursor control is restricted to movements inside your custom-drawn shape — perfect for precise, low-fatigue input (e.g., zero-gravity environments like ISS/Artemis, accessibility, or touchless setups).

Unlike most virtual mice (fixed bounding boxes or full-screen tracking), this lets you:
Draw any polygon (square, rectangle, irregular) by tracing with your index finger.
Save/load profiles for reuse.
Grab & relocate the zone with a 4–5 finger gesture (ideal for drifting in microgravity).
Ignore input outside the zone to reduce jitter/false positives.

Built with MediaPipe Hand Landmarker and OpenCV.

Current state (work in progress): the app tracks your index fingertip and checks whether it is
inside a polygon. Touchless (gesture) drawing is being built; for now drawing uses developer
keys behind `--debug-keys`:
'd' add vertex, 'f' close polygon (3+ points), 'r' reset. Quit with ESC/q or by closing the window.
Planned: gesture drawing, cursor mapping, pinch-clicks, multi-finger grab, JSON profile save.

## Install & run (Windows)

Requires **Python 3.11 or 3.12**. The pinned numpy (2.4) needs 3.11+, and mediapipe 1.0.1
officially supports up to 3.12.

```
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python poly.py --debug-keys
```

Options: `--camera INDEX` (try 1 or 2 if you get no image), `--model PATH` (defaults to
`hand_landmarker.task` next to `poly.py`), `--source VIDEO_FILE` (replay a recorded clip
instead of the webcam), `--debug-keys`.

Run the tests with `pytest`.


Standard air-gesture mice tire users with full-arm waving.  
This bounded, user-defined zone minimizes motion for prolonged use, especially in space where physical mice or trackballs float away and arm strain is amplified.

Potential uses: Space ops (NASA/ESA touchless tools), hygiene-sensitive environments, VR/AR prototyping, accessibility.
