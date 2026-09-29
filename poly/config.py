"""All tunable thresholds and timings live here, so real-world tuning never means
hunting through the code for magic numbers.

Distances marked "hand sizes" are multiples of the distance from the wrist to the
middle-finger knuckle (landmarks 0 -> 9). Using the hand as the ruler means the
same setting works whether the hand is 30 cm or 1 m from the camera.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Tunable settings. Frozen so nothing changes a threshold behind your back."""

    # --- MediaPipe HandLandmarker -------------------------------------------------
    # Only one hand drives the trackpad; tracking a second one would only add noise.
    max_hands: int = 1
    # Confidence needed to *find* a hand from scratch. Lower = the hand is picked up
    # more easily (first real test lost the hand a lot at 0.7), at the cost of the
    # occasional false detection.
    min_hand_detection_confidence: float = 0.5
    # Confidence needed to keep believing a hand is still there between frames.
    min_hand_presence_confidence: float = 0.5
    # Confidence needed to keep tracking landmarks instead of re-detecting.
    min_tracking_confidence: float = 0.5

    # --- Hand dropouts ----------------------------------------------------------------
    # MediaPipe sometimes misses a hand for a frame or two. For up to this many
    # frames we pretend the hand is still where it was, so a flicker doesn't
    # restart a dwell or a hold. After that the hand counts as gone.
    hand_lost_grace_frames: int = 6

    # --- Fingertip smoothing (One Euro filter, pixel units) ----------------------------
    # The One Euro filter is a low-pass filter whose cutoff rises with speed:
    #   cutoff = min_cutoff + beta * speed
    # Slow/still finger -> low cutoff -> heavy smoothing (kills jitter).
    # Fast finger       -> high cutoff -> little smoothing (little lag).
    # min_cutoff: lower = steadier when still, but more lag. The paper suggests 1 Hz;
    # 0.5 Hz cut simulated tremor ~3.8x (vs ~3.1x) for under 1 px extra lag, and the
    # first real test showed a jittery dot.
    filter_min_cutoff_hz: float = 0.5
    # beta: how quickly smoothing backs off as speed rises. Speed is in pixels/s, so
    # at 600 px/s (a quick sweep) the cutoff becomes 1 + 0.01*600 = 7 Hz.
    filter_beta: float = 0.01
    # Cutoff used to smooth the speed estimate itself (paper default).
    filter_d_cutoff_hz: float = 1.0

    # --- Pose classification -----------------------------------------------------------
    # A finger counts as extended when (tip -> wrist) is at least this many times
    # (knuckle -> wrist). Straight fingers score ~1.8-2.0, curled ones ~0.6-1.1.
    finger_extended_ratio: float = 1.3
    # A new pose only "counts" after this many identical frames in a row (debounce).
    pose_debounce_frames: int = 3

    # --- Drawing ----------------------------------------------------------------------
    # Hold the pointing finger still this long to drop a vertex.
    dwell_time_s: float = 0.8
    # "Still" = the fingertip stays within this radius (hand sizes) of where the
    # dwell started. Big enough to forgive tremor, small enough to feel deliberate.
    dwell_radius_hands: float = 0.25
    # Dwelling within this distance (hand sizes) of an earlier point finishes the
    # zone (once there are enough points).
    close_radius_hands: float = 0.5
    # A new vertex closer than this (pixels) to the previous one is ignored, so two
    # points never stack on the same spot.
    min_vertex_distance_px: float = 15.0
    # A polygon needs at least a triangle to enclose any area.
    min_polygon_vertices: int = 3
    # Hold a fist this long in DRAWING mode to undo the last vertex.
    undo_hold_s: float = 1.0
    # Hold a fist this long in ACTIVE mode to clear the zone and redraw. Longer than
    # undo because it's destructive and must not happen by accident.
    clear_hold_s: float = 2.0

    # --- Feedback -----------------------------------------------------------------------
    # How long an on-screen confirmation ("Point added") stays visible.
    flash_message_s: float = 1.2


DEFAULT_CONFIG = Config()
