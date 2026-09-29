"""Build fake 21-point hand landmarks (pixel units) for tests.

The canonical hand is described in "hand units" (wrist -> middle knuckle = 1),
wrist at the origin, fingers pointing up (negative y, like image coordinates).
It is then scaled, rotated and moved so the index fingertip lands where asked.
"""

from __future__ import annotations

import math

from poly.gestures import Pose

# Knuckle (MCP) positions for index, middle, ring, pinky.
_MCPS = {5: (-0.30, -0.95), 9: (0.0, -1.0), 13: (0.25, -0.95), 17: (0.48, -0.85)}
# Offsets from the knuckle for PIP, DIP, TIP.
_EXTENDED = [(0.0, -0.45), (0.0, -0.75), (0.0, -1.0)]
_CURLED = [(0.0, -0.30), (0.0, -0.10), (0.0, 0.10)]  # folds back towards the palm
_THUMB = [(-0.35, -0.15), (-0.60, -0.35), (-0.80, -0.55), (-0.95, -0.75)]

# Pinch: index finger bends towards the thumb, and the thumb tip meets its tip.
_PINCH_INDEX = [(-0.35, -1.35), (-0.50, -1.52), (-0.62, -1.47)]  # PIP, DIP, TIP
_PINCH_THUMB = [(-0.35, -0.15), (-0.60, -0.35), (-0.72, -0.85), (-0.66, -1.40)]

_EXTENDED_FINGERS = {
    Pose.POINT: {5},
    Pose.PINCH: {5},
    Pose.FIST: set(),
    Pose.OPEN_PALM: {5, 9, 13, 17},
    Pose.OTHER: {5, 9},  # "peace sign"
}


def canonical_hand(pose: Pose, thumb_gap: float | None = None) -> list[tuple[float, float]]:
    """21 (x, y) points in hand units for the given pose.

    `thumb_gap` (hand units) moves the thumb tip to that distance left of the index
    fingertip - for simulating a thumb closing in on a pinch.
    """
    points: list[tuple[float, float]] = [(0.0, 0.0)] + list(_THUMB)
    for mcp, (mx, my) in _MCPS.items():
        offsets = _EXTENDED if mcp in _EXTENDED_FINGERS[pose] else _CURLED
        points.append((mx, my))
        points.extend((mx + dx, my + dy) for dx, dy in offsets)
    if pose is Pose.PINCH:
        points[1:5] = _PINCH_THUMB
        points[6:9] = _PINCH_INDEX
    if thumb_gap is not None:
        points[4] = (points[8][0] - thumb_gap, points[8][1])
    return points


def make_hand(pose: Pose, tip_at: tuple[float, float] = (320, 240), size: float = 80,
              rotation_deg: float = 0.0,
              thumb_gap: float | None = None) -> list[tuple[float, float, float]]:
    """Landmarks in pixels with the index fingertip (landmark 8) at `tip_at`.

    `size` is the wrist -> middle knuckle distance in pixels; `rotation_deg` spins
    the whole hand in the image plane. z is 0 (a flat hand facing the camera).
    """
    a = math.radians(rotation_deg)
    cos_a, sin_a = math.cos(a), math.sin(a)
    pts = [((x * cos_a - y * sin_a) * size, (x * sin_a + y * cos_a) * size)
           for x, y in canonical_hand(pose, thumb_gap)]
    ox, oy = tip_at[0] - pts[8][0], tip_at[1] - pts[8][1]
    return [(x + ox, y + oy, 0.0) for x, y in pts]
