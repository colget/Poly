"""Pure geometry helpers: coordinate conversion, point-in-polygon, and the polygon
being drawn. No camera, window or mouse code here, so it is all unit-testable."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

Point = tuple[int, int]


def landmark_to_pixel(x_norm: float, y_norm: float, width: int, height: int) -> Point:
    """Convert a MediaPipe normalised (0-1) landmark position into pixel coordinates."""
    return int(x_norm * width), int(y_norm * height)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
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


@dataclass
class PolygonDraft:
    """The polygon the user is tracing: a list of pixel vertices plus a closed flag."""

    vertices: list[Point] = field(default_factory=list)
    closed: bool = False

    def add_vertex(self, point: Point, min_distance: float) -> bool:
        """Append `point` unless the polygon is closed or `point` is within
        `min_distance` of the previous vertex. Returns True if it was added."""
        if self.closed:
            return False
        if self.vertices and distance(point, self.vertices[-1]) <= min_distance:
            return False
        self.vertices.append(point)
        return True

    def close(self, min_vertices: int) -> bool:
        """Close the polygon if it has enough vertices. Returns True on success."""
        if self.closed or len(self.vertices) < min_vertices:
            return False
        self.closed = True
        return True

    def reset(self) -> None:
        """Throw away all vertices and start drawing again."""
        self.vertices.clear()
        self.closed = False

    def contains(self, point: tuple[float, float]) -> bool:
        """True if the polygon is closed and `point` is inside it (or on its edge)."""
        return self.closed and point_in_polygon(point, self.vertices)
