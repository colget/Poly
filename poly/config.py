"""All tunable thresholds and timings live here, so real-world tuning never means
hunting through the code for magic numbers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Tunable settings. Frozen so nothing changes a threshold behind your back."""

    # --- MediaPipe HandLandmarker -------------------------------------------------
    # Only one hand drives the trackpad; tracking a second one would only add noise.
    max_hands: int = 1
    # Confidence needed to *find* a hand from scratch (higher = fewer ghost hands).
    min_hand_detection_confidence: float = 0.7
    # Confidence needed to keep believing a hand is still there between frames.
    min_hand_presence_confidence: float = 0.6
    # Confidence needed to keep tracking landmarks instead of re-detecting.
    min_tracking_confidence: float = 0.6

    # --- Polygon drawing ------------------------------------------------------------
    # A new vertex closer than this (pixels) to the previous one is ignored, so a
    # double press doesn't stack two points on the same spot.
    min_vertex_distance_px: float = 15.0
    # A polygon needs at least a triangle to enclose any area.
    min_polygon_vertices: int = 3


DEFAULT_CONFIG = Config()
