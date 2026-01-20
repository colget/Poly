Polygonal Hand-Tracker: Custom Virtual Input Zone

A lightweight, webcam-based hand-tracking tool that lets you define a movable polygonal "virtual trackpad" in air using your fingertip.
Cursor control is restricted to movements inside your custom-drawn shape — perfect for precise, low-fatigue input (e.g., zero-gravity environments like ISS/Artemis, accessibility, or touchless setups).

Unlike most virtual mice (fixed bounding boxes or full-screen tracking), this lets you:
Draw any polygon (square, rectangle, irregular) by tracing with your index finger.
Save/load profiles for reuse.
Grab & relocate the zone with a 4–5 finger gesture (ideal for drifting in microgravity).
Ignore input outside the zone to reduce jitter/false positives.

Built with MediaPipe Hand Landmarker and OpenCV.

Its Features
Trace polygon vertices in real-time ('d' to add point).
Close/finish polygon ('f').
Check fingertip "inside" status (green highlight).
Reset ('r') or quit (ESC/q).
Extensible: Add cursor mapping, pinch-clicks, multi-finger grab, JSON profile save.


Standard air-gesture mice tire users with full-arm waving.  
This bounded, user-defined zone minimizes motion for prolonged use, especially in space where physical mice or trackballs float away and arm strain is amplified.

Potential uses: Space ops (NASA/ESA touchless tools), hygiene-sensitive environments, VR/AR prototyping, accessibility.
