"""Gesture recognition from hand landmarks: pose classification, debouncing, and
the dwell/hold timers. Pure logic - every function takes plain numbers and the
current time, so tests can simulate "held for 2 seconds" instantly."""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum
from typing import Generic, TypeVar

from poly.geometry import distance

# One landmark in pixel units: (x, y) or (x, y, z).
Landmark = Sequence[float]

# MediaPipe landmark numbers.
WRIST = 0
MIDDLE_MCP = 9
INDEX_TIP = 8
# (knuckle, tip) for the four fingers. The thumb is left out: people point with
# the thumb either tucked or sticking out, and it's needed only for pinch later.
INDEX = (5, 8)
MIDDLE = (9, 12)
RING = (13, 16)
PINKY = (17, 20)


class Pose(Enum):
    """The hand shapes the app reacts to."""

    NONE = "none"          # no hand
    POINT = "point"        # index extended, other fingers curled
    FIST = "fist"          # all four fingers curled
    OPEN_PALM = "palm"     # all four fingers extended
    OTHER = "other"        # anything else (ignored)


def _dist3(a: Landmark, b: Landmark) -> float:
    """Distance using z too when it is present.

    Why 3-D: when you point *towards* the camera the finger looks short in the 2-D
    image, and a 2-D-only test would call it curled. MediaPipe's z is roughly on
    the same scale as x, so including it undoes most of that foreshortening.
    """
    return math.dist(a[:3], b[:3]) if len(a) >= 3 and len(b) >= 3 else distance(a, b)


def hand_size(landmarks: Sequence[Landmark]) -> float:
    """Wrist -> middle-finger knuckle distance: our ruler for "how big is the hand
    in the image", so thresholds work at any distance from the camera."""
    return _dist3(landmarks[WRIST], landmarks[MIDDLE_MCP])


def finger_extended(landmarks: Sequence[Landmark], finger: tuple[int, int], ratio: float) -> bool:
    """True if the finger's tip is much further from the wrist than its knuckle.

    Why ratios instead of "tip is above knuckle": y-coordinates only work while the
    hand is upright. Distances from the wrist don't care how the hand is rotated.
    """
    knuckle, tip = finger
    wrist = landmarks[WRIST]
    knuckle_dist = _dist3(landmarks[knuckle], wrist)
    if knuckle_dist <= 0:
        return False
    return _dist3(landmarks[tip], wrist) >= ratio * knuckle_dist


def classify_pose(landmarks: Sequence[Landmark] | None, extended_ratio: float) -> Pose:
    """Classify one frame's landmarks into a Pose (no debouncing)."""
    if landmarks is None:
        return Pose.NONE
    index, middle, ring, pinky = (
        finger_extended(landmarks, f, extended_ratio) for f in (INDEX, MIDDLE, RING, PINKY)
    )
    others = (middle, ring, pinky)
    if index and not any(others):
        return Pose.POINT
    if not index and not any(others):
        return Pose.FIST
    if index and all(others):
        return Pose.OPEN_PALM
    return Pose.OTHER


T = TypeVar("T")


class Debouncer(Generic[T]):
    """Only accept a new value after it has been seen `frames` times in a row.

    Why: MediaPipe occasionally gets a single frame wrong (especially during fast
    movement). Requiring a few identical frames filters out those one-off blips.
    """

    def __init__(self, initial: T, frames: int) -> None:
        self.frames = frames
        self.reset(initial)

    def reset(self, value: T) -> None:
        """Force the current value and forget any pending change."""
        self.value = value
        self._candidate = value
        self._count = 0

    def update(self, raw: T) -> T:
        """Feed this frame's raw value; return the debounced value."""
        if raw == self.value:
            self._candidate, self._count = raw, 0
        elif raw == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = raw, 1
        if self._count >= self.frames:
            self.value, self._count = raw, 0
        return self.value


class DwellDetector:
    """Fires once when a point stays within a radius for `dwell_time_s`.

    The dwell starts where the finger first settles (the anchor). Moving beyond
    the radius restarts it from the new position. After firing it won't fire again
    until the finger has left the radius - so holding still drops one vertex, not a
    pile of them.
    """

    def __init__(self, dwell_time_s: float) -> None:
        self.dwell_time_s = dwell_time_s
        self.reset()

    def reset(self) -> None:
        """Cancel any dwell in progress."""
        self._anchor: tuple[float, float] | None = None
        self._start = 0.0
        self._fired = False
        self.progress = 0.0  # 0..1, for the on-screen ring

    def update(self, point: tuple[float, float], now_s: float, radius: float) -> bool:
        """Feed the current (filtered) point. Returns True on the frame the dwell completes."""
        if self._anchor is None or distance(point, self._anchor) > radius:
            self._anchor, self._start, self._fired = point, now_s, False
        if self._fired:
            self.progress = 0.0
            return False
        self.progress = min(1.0, (now_s - self._start) / self.dwell_time_s)
        if self.progress >= 1.0:
            self._fired = True
            self.progress = 0.0
            return True
        return False


class HoldTimer:
    """Fires once when a condition has been true continuously for `duration_s`.

    Must be released (condition false) before it can fire again, so one long hold
    means one action.
    """

    def __init__(self, duration_s: float) -> None:
        self.duration_s = duration_s
        self.reset()

    def reset(self) -> None:
        """Cancel any hold in progress."""
        self._start: float | None = None
        self._fired = False
        self.progress = 0.0  # 0..1, for the on-screen ring

    def update(self, active: bool, now_s: float) -> bool:
        """Feed whether the condition holds this frame. Returns True on the frame it fires."""
        if not active:
            self.reset()
            return False
        if self._start is None:
            self._start = now_s
        if self._fired:
            self.progress = 0.0
            return False
        self.progress = min(1.0, (now_s - self._start) / self.duration_s)
        if self.progress >= 1.0:
            self._fired = True
            self.progress = 0.0
            return True
        return False
