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


def quick_zone(centre: tuple[float, float], width: float, height: float,
               frame_size: tuple[int, int] | None, bottom_limit: float | None,
               margin: float) -> list[Point]:
    """A width x height rectangle centred on `centre`, pushed back inside the frame.

    `bottom_limit` is the lowest y the zone may reach (the top of the "palm leaves
    the camera" band). If the rectangle doesn't fit between the top margin and that
    limit, it is shortened rather than placed where it can't be used.
    Corners are returned clockwise on screen from the top-left.
    """
    left, top = centre[0] - width / 2, centre[1] - height / 2
    if frame_size is not None:
        w, h = frame_size
        left = min(max(left, margin), w - margin - width)
        left = max(left, margin)  # wider than the frame: pin to the left edge
        right = min(left + width, w - margin)
        lowest = h - margin if bottom_limit is None else min(bottom_limit, h - margin)
        top = min(max(top, margin), lowest - height)
        top = max(top, margin)
        bottom = max(min(top + height, lowest), top + 1)
    else:
        right, bottom = left + width, top + height
    corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
    return [(int(round(x)), int(round(y))) for x, y in corners]


def translate_within(vertices: list[Point], dx: float, dy: float,
                     frame_size: tuple[int, int] | None, margin: float) -> list[Point]:
    """Move every vertex by (dx, dy), limiting the move so the whole shape stays
    inside the frame. Why: a zone dragged off-screen could never be grabbed back."""
    if frame_size is not None and vertices:
        w, h = frame_size
        xs, ys = [v[0] for v in vertices], [v[1] for v in vertices]
        dx = min(max(dx, margin - min(xs)), w - margin - max(xs))
        dy = min(max(dy, margin - min(ys)), h - margin - max(ys))
    return [(int(round(x + dx)), int(round(y + dy))) for x, y in vertices]


def order_corners(quad: list[Point]) -> list[Point]:
    """Order 4 corners as top-left, top-right, bottom-right, bottom-left.

    Angle order around the centre already goes clockwise on screen (image y points
    down); we just rotate the list so it starts at the corner nearest the top-left,
    i.e. the one with the smallest x + y.
    """
    ordered = order_around_centroid(quad)
    start = min(range(len(ordered)), key=lambda i: ordered[i][0] + ordered[i][1])
    return ordered[start:] + ordered[:start]


class ZoneMapper:
    """Maps a fingertip position inside the zone to a pixel on the screen.

    * 4-corner convex zone -> perspective transform. Why: a zone traced in the air
      is never a perfect rectangle (and the camera sees it at an angle). A
      perspective transform (homography) stretches any 4-sided shape onto the
      screen rectangle, so each corner of the zone lands exactly on a corner of the
      screen and every edge lands on a screen edge. Plain scaling would leave
      parts of the screen unreachable for a skewed shape.
    * Anything else -> the zone's bounding box is scaled to the screen.
    * Fingertip outside the zone -> None (the cursor doesn't move).

    `edge_padding` makes the outer strip of the zone (that fraction of its width or
    height on each side) map onto the screen edge. Why: reaching a screen edge
    otherwise needs the finger exactly on the zone boundary, where one wobble
    takes it outside and the cursor stops short.
    """

    def __init__(self, vertices: list[Point], screen_size: tuple[int, int],
                 edge_padding: float) -> None:
        self.vertices = list(vertices)
        self.screen_size = screen_size
        self.edge_padding = edge_padding
        self._homography: np.ndarray | None = None
        if len(vertices) == 4:
            corners = np.asarray(order_corners(self.vertices), dtype=np.float32)
            # A concave or flattened 4-gon folds the mapping over itself, so only
            # use the perspective transform for a proper convex quadrilateral.
            if cv2.isContourConvex(corners) and cv2.contourArea(corners) > 1:
                unit_square = np.float32([(0, 0), (1, 0), (1, 1), (0, 1)])
                self._homography = cv2.getPerspectiveTransform(corners, unit_square)
        xs, ys = [v[0] for v in self.vertices], [v[1] for v in self.vertices]
        self._bbox = (min(xs), min(ys), max(xs), max(ys))

    @property
    def uses_perspective(self) -> bool:
        """True if the 4-corner perspective transform is in use."""
        return self._homography is not None

    def normalised(self, point: tuple[float, float]) -> tuple[float, float]:
        """Position within the zone as (u, v), where (0, 0) is the top-left corner
        and (1, 1) the bottom-right. Not clamped."""
        if self._homography is not None:
            # Homogeneous coordinates: multiply [x, y, 1] by the 3x3 matrix, then
            # divide by the third component. That division is what lets straight
            # lines stay straight while the shape's far side is squeezed/stretched.
            u, v, w = self._homography @ np.array([point[0], point[1], 1.0])
            return float(u / w), float(v / w)
        x0, y0, x1, y1 = self._bbox
        return ((point[0] - x0) / max(x1 - x0, 1e-9),
                (point[1] - y0) / max(y1 - y0, 1e-9))

    def map(self, point: tuple[float, float]) -> tuple[int, int] | None:
        """Screen pixel for `point`, or None if `point` is outside the zone."""
        if not point_in_polygon(point, self.vertices):
            return None
        u, v = self.normalised(point)
        p = self.edge_padding
        # Stretch the inner (1 - 2p) of the zone to cover 0..1, then clamp.
        u = min(max((u - p) / (1 - 2 * p), 0.0), 1.0)
        v = min(max((v - p) / (1 - 2 * p), 0.0), 1.0)
        w, h = self.screen_size
        return int(round(u * (w - 1))), int(round(v * (h - 1)))


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
