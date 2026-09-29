"""Pointer modes: how fingertip movement inside the zone becomes pointer movement.

TABLET (absolute): each spot in the zone *is* a spot on the screen, like a drawing
tablet. Fast and direct, but every wobble of the finger shows up on screen, and
precision depends on how big the zone looks to the camera. See geometry.ZoneMapper.

TRACKPAD (relative): moving the finger *nudges* the pointer from wherever it is,
like a laptop trackpad. Taking the finger out of the zone (or relaxing it) is
"lifting" it: the pointer stays put, and coming back doesn't make it jump.
Two choices make it work at any distance and on any screen:

* Finger movement is measured in hand sizes, not camera pixels. A hand far from
  the camera looks small, so the same real movement covers fewer pixels; dividing
  by the hand's size cancels that out.
* Pointer movement is a fraction of the screen width, so a TV and a laptop feel
  the same.

Pure logic: positions and timestamps in, a pointer position out.
"""

from __future__ import annotations

import math
from enum import Enum

from poly.config import Config


class PointerMode(Enum):
    """How the zone drives the pointer (chosen with --pointer)."""

    TABLET = "tablet"
    TRACKPAD = "trackpad"


def acceleration_gain(speed_hands_per_s: float, config: Config) -> float:
    """How far the pointer moves per hand size of finger movement, in screen widths.

    Pointer acceleration, as on every real trackpad: below the "slow" speed you get
    the low gain (fine, precise movement), above the "fast" speed the high gain (a
    flick crosses the screen), with a smooth S-curve in between so speeding up
    never makes the pointer lurch.
    """
    slow, fast = config.trackpad_slow_speed_hands, config.trackpad_fast_speed_hands
    t = min(max((speed_hands_per_s - slow) / (fast - slow), 0.0), 1.0)
    t = t * t * (3 - 2 * t)  # smoothstep: gentle at both ends
    return config.trackpad_min_gain + (config.trackpad_max_gain - config.trackpad_min_gain) * t


class TrackpadPointer:
    """Relative pointer movement with acceleration."""

    def __init__(self, screen_size: tuple[int, int], config: Config) -> None:
        self.screen_size = screen_size
        self.config = config
        self._pos: tuple[float, float] | None = None  # sub-pixel pointer position
        self._output: tuple[int, int] | None = None
        self.lift()

    def lift(self) -> None:
        """Finger lifted (left the zone, changed shape, hand lost): stop tracking
        movement, so touching down again elsewhere doesn't jump the pointer."""
        self._last_tip: tuple[float, float] | None = None
        self._last_time = 0.0

    def move(self, tip: tuple[float, float], hand_size: float, now_s: float,
             current: tuple[int, int] | None) -> tuple[int, int]:
        """Feed the (smoothed) fingertip while "touching"; returns the new pointer
        position. `current` is where the pointer really is now (None if unknown)."""
        w, h = self.screen_size
        if current is None:
            current = (w // 2, h // 2)
        if self._output is None or current != self._output:
            # First use, or something else moved the pointer (e.g. the real mouse):
            # carry on from where it actually is, like a real trackpad.
            self._pos = (float(current[0]), float(current[1]))
            self._output = current

        if self._last_tip is None or hand_size <= 0:  # touching down: no movement yet
            self._last_tip, self._last_time = tip, now_s
            return self._output
        dt = now_s - self._last_time
        if dt <= 0:
            return self._output

        dx = (tip[0] - self._last_tip[0]) / hand_size
        dy = (tip[1] - self._last_tip[1]) / hand_size
        self._last_tip, self._last_time = tip, now_s
        gain = acceleration_gain(math.hypot(dx, dy) / dt, self.config) * w

        assert self._pos is not None
        # Keep the sub-pixel position so slow movements that are less than a pixel
        # per frame still add up instead of being rounded away.
        x = min(max(self._pos[0] + dx * gain, 0.0), w - 1.0)
        y = min(max(self._pos[1] + dy * gain, 0.0), h - 1.0)
        self._pos = (x, y)
        self._output = (int(round(x)), int(round(y)))
        return self._output
