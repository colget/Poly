"""On-screen overlays and optional sounds. Drawing only - no decisions are made
here; everything shown comes from the state machine's FrameResult.

Why so much feedback: the user can't feel a touchless trackpad, so the screen has
to tell them what mode they're in and whether a gesture is being recognised.
"""

from __future__ import annotations

import sys
import threading

import cv2
import numpy as np

from poly.geometry import Point
from poly.modes import Event, FrameResult, HoldAction, Mode
from poly.gestures import Pose

# OpenCV colours are BGR, not RGB.
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (160, 160, 160)
AMBER = (0, 190, 255)
GREEN = (0, 220, 0)
ORANGE = (0, 130, 255)
RED = (40, 40, 230)
CYAN = (255, 220, 0)

MODE_COLOURS = {Mode.DRAWING: AMBER, Mode.ACTIVE: GREEN}
HOLD_COLOURS = {HoldAction.UNDO: ORANGE, HoldAction.CLEAR: RED}

FONT = cv2.FONT_HERSHEY_SIMPLEX
RING_RADIUS = 26


def _pt(p: tuple[float, float]) -> Point:
    return int(round(p[0])), int(round(p[1]))


def draw_polygon(image: np.ndarray, vertices: list[Point], closed: bool) -> None:
    """Closed: green outline with a light fill. Drawing: loose amber dots only -
    the order points are placed in doesn't matter, so no path is drawn."""
    if not vertices:
        return
    pts = np.array(vertices, np.int32).reshape((-1, 1, 2))
    if closed:
        fill = image.copy()
        cv2.fillPoly(fill, [pts], GREEN)
        cv2.addWeighted(fill, 0.15, image, 0.85, 0, dst=image)
        cv2.polylines(image, [pts], isClosed=True, color=GREEN, thickness=3)
        return
    for v in vertices:
        cv2.circle(image, v, 7, AMBER, cv2.FILLED)
        cv2.circle(image, v, 9, BLACK, 1)  # thin outline so dots show on any background


def draw_close_hint(image: np.ndarray, target: Point) -> None:
    """Highlight the point under the finger: holding still here finishes the zone."""
    cv2.circle(image, target, 18, GREEN, 3)
    cv2.putText(image, "Hold to finish", (target[0] + RING_RADIUS + 12, target[1] - 14),
                FONT, 0.6, GREEN, 2)


def draw_fingertip(image: np.ndarray, tip: tuple[float, float], colour: tuple[int, int, int]) -> None:
    """Mark the (smoothed) index fingertip."""
    c = _pt(tip)
    cv2.circle(image, c, 7, colour, cv2.FILLED)
    cv2.circle(image, c, 10, WHITE, 2)


def draw_progress_ring(image: np.ndarray, centre: tuple[float, float], progress: float,
                       colour: tuple[int, int, int], label: str | None = None) -> None:
    """Arc around the fingertip filling clockwise from 12 o'clock as progress goes 0 -> 1."""
    if progress <= 0:
        return
    c = _pt(centre)
    cv2.circle(image, c, RING_RADIUS, (60, 60, 60), 2)  # faint track
    cv2.ellipse(image, c, (RING_RADIUS, RING_RADIUS), -90, 0, 360 * progress, colour, 5, cv2.LINE_AA)
    if label:
        cv2.putText(image, label, (c[0] + RING_RADIUS + 6, c[1] + 6), FONT, 0.6, colour, 2)


def _banner(image: np.ndarray, title: str, hint: str, colour: tuple[int, int, int]) -> None:
    w = image.shape[1]
    cv2.rectangle(image, (0, 0), (w, 64), BLACK, cv2.FILLED)
    cv2.rectangle(image, (0, 0), (w, 64), colour, 2)
    cv2.putText(image, title, (12, 28), FONT, 0.8, colour, 2)
    cv2.putText(image, hint, (12, 54), FONT, 0.5, WHITE, 1)


def mode_hint(result: FrameResult, vertex_count: int, min_vertices: int) -> str:
    """One-line instructions for the current mode."""
    if result.mode is Mode.DRAWING:
        hint = "Point & hold still = add point   |   Fist 1s = undo"
        if vertex_count >= min_vertices:
            hint = "Hold on an earlier point to finish   |   Fist 1s = undo"
        return hint
    return "Point inside the zone   |   Fist 2s = clear & redraw"


def render(image: np.ndarray, result: FrameResult, vertices: list[Point], closed: bool,
           min_vertices: int, debug_keys: bool) -> None:
    """Draw every overlay for one frame onto `image` (in place)."""
    draw_polygon(image, vertices, closed)

    if result.mode is Mode.DRAWING and result.close_target is not None:
        draw_close_hint(image, result.close_target)

    if result.tip is not None:
        if result.mode is Mode.ACTIVE:
            colour = GREEN if result.inside else ORANGE
        else:
            colour = CYAN if result.pose is Pose.POINT else GREY
        draw_fingertip(image, result.tip, colour)
        draw_progress_ring(image, result.tip, result.dwell_progress, CYAN)
        if result.hold_action is not None:
            draw_progress_ring(image, result.tip, result.hold_progress,
                               HOLD_COLOURS[result.hold_action], result.hold_action.value)

    title = result.mode.value
    if result.mode is Mode.ACTIVE and result.tip is not None:
        title += "  -  inside" if result.inside else "  -  outside"
    if not result.hand_visible:
        title += "  -  no hand"
    _banner(image, title, mode_hint(result, len(vertices), min_vertices),
            MODE_COLOURS[result.mode])

    h = image.shape[0]
    status = f"Pose: {result.pose.value}   Points: {len(vertices)}"
    if debug_keys:
        status += "   [debug keys: d/f/r]"
    cv2.putText(image, status, (12, h - 12), FONT, 0.5, WHITE, 1)


class Flash:
    """A short confirmation message ("Point added") shown for a fixed time."""

    def __init__(self, duration_s: float) -> None:
        self.duration_s = duration_s
        self._text = ""
        self._until = 0.0

    def show(self, text: str, now_s: float) -> None:
        """Start showing `text` from `now_s`."""
        self._text, self._until = text, now_s + self.duration_s

    def draw(self, image: np.ndarray, now_s: float) -> None:
        """Draw the message centred near the bottom, if it hasn't expired."""
        if now_s >= self._until:
            return
        h, w = image.shape[:2]
        (tw, th), _ = cv2.getTextSize(self._text, FONT, 1.0, 2)
        x, y = (w - tw) // 2, h - 50
        cv2.rectangle(image, (x - 12, y - th - 12), (x + tw + 12, y + 12), BLACK, cv2.FILLED)
        cv2.putText(image, self._text, (x, y), FONT, 1.0, WHITE, 2)


# (frequency Hz, duration ms) per event: rising tones for progress, falling for undo.
TONES = {
    Event.VERTEX_ADDED: (880, 80),
    Event.POLYGON_CLOSED: (1320, 180),
    Event.VERTEX_UNDONE: (440, 120),
    Event.POLYGON_CLEARED: (330, 300),
}


class Sounds:
    """Optional short beeps (--sound). Windows uses winsound; elsewhere the
    terminal bell. Beeps play on a background thread so the video never stalls."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def play(self, event: Event) -> None:
        """Play the tone for `event` (no-op when disabled)."""
        if not self.enabled:
            return
        freq, ms = TONES[event]
        if sys.platform == "win32":
            import winsound  # Windows-only standard library module

            threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()
        else:
            print("\a", end="", flush=True)
