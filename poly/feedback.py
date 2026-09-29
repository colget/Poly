"""On-screen overlays. Drawing only - no decisions are made here."""

from __future__ import annotations

import cv2
import numpy as np

from poly.geometry import Point

# OpenCV colours are BGR, not RGB.
FINGERTIP_FILL = (0, 0, 255)
FINGERTIP_RING = (255, 255, 255)
POLYGON_OPEN = (0, 200, 255)
POLYGON_CLOSED = (0, 255, 0)
STATUS_TRACING = (255, 255, 100)
STATUS_INSIDE = (0, 255, 100)
STATUS_OUTSIDE = (0, 100, 255)
POINT_COUNT = (200, 200, 50)

FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_fingertip(image: np.ndarray, tip: Point) -> None:
    """Mark the index fingertip with a filled dot and a white ring."""
    cv2.circle(image, tip, 8, FINGERTIP_FILL, cv2.FILLED)
    cv2.circle(image, tip, 12, FINGERTIP_RING, 2)


def draw_polygon(image: np.ndarray, vertices: list[Point], closed: bool) -> None:
    """Draw the polygon: an open orange path while tracing, green once closed."""
    if len(vertices) < 2:
        return
    pts = np.array(vertices, np.int32).reshape((-1, 1, 2))
    if closed:
        cv2.polylines(image, [pts], isClosed=True, color=POLYGON_CLOSED, thickness=3)
    else:
        cv2.polylines(image, [pts], isClosed=False, color=POLYGON_OPEN, thickness=2)


def status_line(closed: bool, inside: bool, debug_keys: bool) -> tuple[str, tuple[int, int, int]]:
    """Choose the status text and colour for the current state."""
    if closed:
        colour = STATUS_INSIDE if inside else STATUS_OUTSIDE
        return f"Polygon ready - Tip inside? {'YES' if inside else 'NO'}", colour
    if debug_keys:
        return "Tracing - Press 'd' to add point", STATUS_TRACING
    return "Tracing - drawing needs --debug-keys for now", STATUS_TRACING


def draw_status(image: np.ndarray, text: str, colour: tuple[int, int, int], vertex_count: int) -> None:
    """Draw the status line and, once drawing has started, the vertex count."""
    cv2.putText(image, text, (20, 40), FONT, 0.9, colour, 2)
    if vertex_count:
        cv2.putText(image, f"Points: {vertex_count}", (20, 80), FONT, 0.7, POINT_COUNT, 2)
