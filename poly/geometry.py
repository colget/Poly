"""Pure geometry helpers: coordinate conversion, point-in-polygon, and the polygon
being drawn. No camera, window or mouse code here, so it is all unit-testable."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

Point = tuple[int, int]


def landmarks_to_pixels(landmarks: list[tuple[float, float, float]], width: int,
                        height: int) -> list[tuple[float, float, float]]:
    """Convert normalised MediaPipe landmarks to pixel units, keeping sub-pixel
    precision (the smoothing filter needs it).

    z is scaled by the width because MediaPipe documents z as using "roughly the
    same scale as x". That keeps 3-D distances meaningful in pixels.
    """
    return [(x * width, y * height, z * width) for x, y, z in landmarks]


def distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Euclidean distance between two 2-D points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_in_polygon(point: tuple[float, float], polygon: list[Point]) -> bool:
    """Return True if `point` is inside `polygon` or exactly on its edge.

    A polygon with fewer than 3 vertices has no area, so nothing is inside it.
    """
    if len(polygon) < 3:
        return False
    contour = np.asarray(polygon, dtype=np.float32)
    # measureDist=False makes OpenCV return +1 (inside), 0 (on edge) or -1 (outside).
    return cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False) >= 0


def order_around_centroid(points: list[Point]) -> list[Point]:
    """Order points by angle around their centre, so they form a shape whose
    edges never cross - whatever order the user placed them in.

    Why this works: seen from the centre, each edge joins two neighbouring
    directions, so every edge sits in its own "slice" of the circle and can't
    cross another. The centroid is always inside the points' outline, so no gap
    between neighbouring directions exceeds 180 degrees.

    Points on the outside make the shape convex; a point placed further in makes a
    notch (a concave corner), which is how irregular zones are still possible.
    """
    if len(points) < 3:
        return list(points)
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


@dataclass
class PolygonDraft:
    """The zone being drawn: pixel vertices plus a closed flag.

    While drawing, vertices are kept in the order they were placed (so undo removes
    the latest one). Closing reorders them into a non-crossing outline.
    """

    vertices: list[Point] = field(default_factory=list)
    closed: bool = False

    def add_vertex(self, point: Point, min_distance: float) -> bool:
        """Append `point` unless the polygon is closed or `point` is within
        `min_distance` of any existing vertex. Returns True if it was added."""
        if self.closed:
            return False
        if any(distance(point, v) <= min_distance for v in self.vertices):
            return False
        self.vertices.append(point)
        return True

    def close(self, min_vertices: int) -> bool:
        """Close the polygon if it has enough vertices, ordering them into a
        non-crossing outline. Returns True on success."""
        if self.closed or len(self.vertices) < min_vertices:
            return False
        self.vertices[:] = order_around_centroid(self.vertices)
        self.closed = True
        return True

    def reset(self) -> None:
        """Throw away all vertices and start drawing again."""
        self.vertices.clear()
        self.closed = False

    def contains(self, point: tuple[float, float]) -> bool:
        """True if the polygon is closed and `point` is inside it (or on its edge)."""
        return self.closed and point_in_polygon(point, self.vertices)
