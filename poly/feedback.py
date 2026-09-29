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

from poly.config import Config
from poly.geometry import Point
from poly.gestures import Pose
from poly.modes import Event, FrameResult, HoldAction, Mode

# OpenCV colours are BGR, not RGB.
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREY = (160, 160, 160)
AMBER = (0, 190, 255)
GREEN = (0, 220, 0)
ORANGE = (0, 130, 255)
RED = (40, 40, 230)
CYAN = (255, 220, 0)
MAGENTA = (220, 60, 220)

MODE_COLOURS = {Mode.DRAWING: AMBER, Mode.ACTIVE: GREEN, Mode.GRAB: CYAN}
HOLD_COLOURS = {
    HoldAction.UNDO: ORANGE,
    HoldAction.CLEAR: RED,
    HoldAction.QUICK_ZONE: GREEN,
    HoldAction.GRAB: CYAN,
}

FONT = cv2.FONT_HERSHEY_SIMPLEX
RING_RADIUS = 26


def _pt(p: tuple[float, float]) -> Point:
    return int(round(p[0])), int(round(p[1]))


def draw_polygon(image: np.ndarray, vertices: list[Point], closed: bool,
                 colour: tuple[int, int, int] = GREEN) -> None:
    """Closed: outline with a light fill. Drawing: loose amber dots only - the
    order points are placed in doesn't matter, so no path is drawn."""
    if not vertices:
        return
    pts = np.array(vertices, np.int32).reshape((-1, 1, 2))
    if closed:
        fill = image.copy()
        cv2.fillPoly(fill, [pts], colour)
        cv2.addWeighted(fill, 0.15, image, 0.85, 0, dst=image)
        cv2.polylines(image, [pts], isClosed=True, color=colour, thickness=3)
        return
    for v in vertices:
        cv2.circle(image, v, 7, AMBER, cv2.FILLED)
        cv2.circle(image, v, 9, BLACK, 1)  # thin outline so dots show on any background


def draw_reach_band(image: np.ndarray, limit_y: float) -> None:
    """Shade the bottom strip where a pointing fingertip puts the palm below the
    camera's view (so MediaPipe loses the hand)."""
    h, w = image.shape[:2]
    y = int(limit_y)
    if y >= h or y < 70:  # nothing to show, or it would cover the banner
        return
    band = image[y:h]
    band[:] = (band * 0.55).astype(image.dtype)
    cv2.line(image, (0, y), (w, y), GREY, 1, cv2.LINE_AA)
    cv2.putText(image, "Too low - your palm leaves the camera view", (12, y + 20),
                FONT, 0.5, GREY, 1)


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


def draw_pinch(image: np.ndarray, tip: tuple[float, float], thumb: tuple[float, float],
               pressed: bool) -> None:
    """Line from thumb tip to index tip while a pinch is near: thin while closing
    in (pointer frozen), thick and green once it clicks."""
    colour, thickness = (GREEN, 4) if pressed else (MAGENTA, 2)
    cv2.line(image, _pt(thumb), _pt(tip), colour, thickness, cv2.LINE_AA)
    cv2.circle(image, _pt(thumb), 6, colour, cv2.FILLED)


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
    # See-through, so a zone or fingertip near the top edge stays visible.
    strip = image[0:64]
    strip[:] = (strip * 0.35).astype(image.dtype)
    cv2.rectangle(image, (0, 0), (w, 64), colour, 2)
    cv2.putText(image, title, (12, 28), FONT, 0.8, colour, 2)
    cv2.putText(image, hint, (12, 54), FONT, 0.5, WHITE, 1)


def mode_hint(result: FrameResult, vertex_count: int, min_vertices: int) -> str:
    """One-line instructions for the current mode."""
    if not result.hand_visible:
        return "No hand seen - keep your whole hand, including the palm, in view"
    if result.mode is Mode.DRAWING:
        if vertex_count == 0:
            return "Point & hold still = add point   |   Open palm 1.5s = quick zone"
        if vertex_count >= min_vertices:
            return "Hold on an earlier point to finish   |   Fist 1s = undo"
        return "Point & hold still = add point   |   Fist 1s = undo"
    if result.mode is Mode.GRAB:
        return "Move your open hand to drag the zone   |   Close your hand to drop it"
    return "Point = move   |   Pinch = click   |   Open palm = move zone   |   Fist 2s = clear"


def render(image: np.ndarray, result: FrameResult, vertices: list[Point], closed: bool,
           config: Config, debug_keys: bool, fps: float | None = None) -> None:
    """Draw every overlay for one frame onto `image` (in place)."""
    # The reach band matters while placing a zone; in ACTIVE it would just clutter.
    if result.mode is not Mode.ACTIVE and result.hand_size is not None:
        draw_reach_band(image, image.shape[0] - config.reach_margin_hands * result.hand_size)

    draw_polygon(image, vertices, closed, MODE_COLOURS[result.mode])

    if result.mode is Mode.DRAWING and result.close_target is not None:
        draw_close_hint(image, result.close_target)

    if result.tip is not None:
        if result.mode is Mode.ACTIVE:
            colour = GREEN if result.inside else ORANGE
        else:
            colour = CYAN if result.pose in (Pose.POINT, Pose.OPEN_PALM) else GREY
        if result.thumb_tip is not None and (result.cursor_frozen or result.pose is Pose.PINCH):
            draw_pinch(image, result.tip, result.thumb_tip, result.pose is Pose.PINCH)
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
    _banner(image, title, mode_hint(result, len(vertices), config.min_polygon_vertices),
            MODE_COLOURS[result.mode])

    h = image.shape[0]
    status = f"Pose: {result.pose.value}   Points: {len(vertices)}"
    if fps is not None:
        status += f"   {fps:.0f} fps"
    if debug_keys:
        status += "   [debug keys: d/f/r]"
    cv2.putText(image, status, (12, h - 12), FONT, 0.5, WHITE, 1)


def draw_screen_preview(image: np.ndarray, screen_size: tuple[int, int],
                        position: tuple[int, int] | None, moving: bool,
                        controls_mouse: bool, width: int = 150) -> None:
    """Mini map of the computer screen (bottom-right) with a dot where the pointer is.

    Why: without --control-cursor this is the only way to see where the pointer
    would go - handy for checking the mapping before handing over the real mouse.
    """
    img_h, img_w = image.shape[:2]
    sw, sh = screen_size
    height = max(1, int(width * sh / sw))
    x0, y0 = img_w - width - 12, img_h - height - 30
    x1, y1 = x0 + width, y0 + height
    area = image[y0:y1, x0:x1]
    area[:] = (area * 0.35).astype(image.dtype)
    cv2.rectangle(image, (x0, y0), (x1, y1), WHITE, 1)
    label, colour = ("Mouse: ON", GREEN) if controls_mouse else ("Mouse: preview", GREY)
    cv2.putText(image, label, (x0, y0 - 6), FONT, 0.45, colour, 1)
    if position is not None:
        px = x0 + int(position[0] / max(sw - 1, 1) * (width - 1))
        py = y0 + int(position[1] / max(sh - 1, 1) * (height - 1))
        cv2.circle(image, (px, py), 4, GREEN if moving else GREY, cv2.FILLED)


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
    Event.QUICK_ZONE: (1320, 180),
    Event.ZONE_GRABBED: (660, 80),
    Event.ZONE_DROPPED: (990, 80),
    Event.CLICK: (1500, 40),
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
