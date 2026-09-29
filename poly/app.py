"""Main loop: camera/video in, hand tracking, overlays out. Command-line args live
here too. Keep this layer thin - decisions belong in the pure modules."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from poly import feedback
from poly.config import DEFAULT_CONFIG, Config
from poly.geometry import Point, PolygonDraft, landmark_to_pixel
from poly.tracker import HandTracker

# hand_landmarker.task sits in the repo root, one level above this package.
# Resolving it from this file (not the current directory) means the app works no
# matter which folder you launch it from.
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
WINDOW_NAME = "Poly - Finger Tracking (ESC/q to quit)"
INDEX_FINGER_TIP = 8  # MediaPipe landmark number
QUIT_KEYS = (27, ord("q"))  # ESC, q
FALLBACK_FPS = 30.0  # used when a video file doesn't report its frame rate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Poly: touchless polygon trackpad.")
    parser.add_argument("--camera", type=int, default=0, metavar="INDEX",
                        help="webcam index (default 0; try 1 or 2 if you get no image)")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH, metavar="PATH",
                        help="path to hand_landmarker.task (default: next to poly.py)")
    parser.add_argument("--source", type=Path, default=None, metavar="VIDEO_FILE",
                        help="replay a recorded video instead of the webcam")
    parser.add_argument("--debug-keys", action="store_true",
                        help="developer fallback: d = add vertex, f = close, r = reset")
    return parser.parse_args(argv)


def handle_debug_key(key: int, draft: PolygonDraft, fingertip: Point | None,
                     config: Config) -> str | None:
    """Apply a developer debug key to the polygon. Returns a log message, or None
    if the key did nothing."""
    if key == ord("d") and fingertip is not None:
        if draft.add_vertex(fingertip, config.min_vertex_distance_px):
            return f"Added point {len(draft.vertices)}: {fingertip}"
    elif key == ord("f"):
        if draft.close(config.min_polygon_vertices):
            return "Polygon finished!"
    elif key == ord("r"):
        draft.reset()
        return "Reset."
    return None


def _open_capture(args: argparse.Namespace) -> cv2.VideoCapture:
    """Open the video file given by --source, or the webcam given by --camera."""
    if args.source is not None:
        if not args.source.exists():
            print(f"ERROR: video file not found: {args.source}")
            sys.exit(1)
        return cv2.VideoCapture(str(args.source))
    return cv2.VideoCapture(args.camera)


def main(argv: list[str] | None = None) -> None:
    """Run the app until the user quits or the video/camera ends."""
    args = parse_args(argv)
    config = DEFAULT_CONFIG

    if not args.model.exists():
        print(f"\nERROR: model file not found at:\n  {args.model}")
        print(f"Download it from:\n  {MODEL_URL}")
        print("and save it next to poly.py, or pass --model PATH.\n")
        sys.exit(1)

    cap = _open_capture(args)
    if not cap.isOpened():
        if args.source is not None:
            print(f"ERROR: cannot open video file {args.source}")
        else:
            print(f"ERROR: cannot open webcam {args.camera}. Try --camera 1 or --camera 2.")
        cap.release()
        sys.exit(1)

    replaying = args.source is not None
    fps = cap.get(cv2.CAP_PROP_FPS) or FALLBACK_FPS
    # Webcam: wait 1 ms for a key and run as fast as frames arrive.
    # Video file: wait one frame period so playback runs at roughly real speed.
    key_wait_ms = max(1, int(1000 / fps)) if replaying else 1

    draft = PolygonDraft()
    tracker = None
    try:
        tracker = HandTracker(args.model, config)
        print("\n=== Poly - Polygon Tracer ===")
        if args.debug_keys:
            print("Debug keys: 'd' add vertex, 'f' close polygon (3+ points), 'r' reset")
        else:
            print("Touchless drawing is not implemented yet; run with --debug-keys to draw.")
        print("ESC or 'q' (or close the window) to quit.\n")

        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                print("End of video." if replaying else "Failed to grab frame.")
                break

            # Mirror the image so moving your hand right moves the dot right,
            # like looking in a mirror. Done *before* detection so landmark
            # coordinates match what is drawn on screen.
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            # Time for this frame. A video file uses its own timeline so a replay
            # behaves the same every run; a webcam uses time.monotonic(), which
            # (unlike the wall clock) never jumps backwards.
            now_s = frame_index / fps if replaying else time.monotonic()
            frame_index += 1

            landmarks = tracker.detect(frame, now_s)
            fingertip = None
            if landmarks is not None:
                tip = landmarks[INDEX_FINGER_TIP]
                fingertip = landmark_to_pixel(tip[0], tip[1], w, h)
            inside = fingertip is not None and draft.contains(fingertip)

            overlay = frame.copy()
            if fingertip is not None:
                feedback.draw_fingertip(overlay, fingertip)
            feedback.draw_polygon(overlay, draft.vertices, draft.closed)
            text, colour = feedback.status_line(draft.closed, inside, args.debug_keys)
            feedback.draw_status(overlay, text, colour, len(draft.vertices))
            cv2.imshow(WINDOW_NAME, overlay)

            key = cv2.waitKey(key_wait_ms) & 0xFF
            if key in QUIT_KEYS:
                break
            # Closing the window with its X button should also quit.
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            if args.debug_keys:
                message = handle_debug_key(key, draft, fingertip, config)
                if message:
                    print(message)
    finally:
        if tracker is not None:
            tracker.close()
        cap.release()
        cv2.destroyAllWindows()
        print("Exited.")
