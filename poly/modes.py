"""The DRAWING <-> ACTIVE state machine. It turns a stream of hand landmarks plus
timestamps into mode changes, polygon edits and events. No camera or drawing code
here - feed it synthetic landmarks and fake times in tests.

    DRAWING --dwell on an earlier point (3+ points)--> ACTIVE
    ACTIVE  --fist held clear_hold_s-------------------> DRAWING (polygon cleared)

GRAB (open palm) and clicking (pinch) arrive in a later phase.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

from poly.config import Config
from poly.filters import PointFilter
from poly.geometry import Point, PolygonDraft, distance
from poly.gestures import (
    INDEX_TIP,
    Debouncer,
    DwellDetector,
    HoldTimer,
    Landmark,
    Pose,
    classify_pose,
    hand_size,
)


class Mode(Enum):
    """What the hand is currently doing."""

    DRAWING = "DRAWING"
    ACTIVE = "ACTIVE"


class Event(Enum):
    """Things that happened this frame - used for messages and sounds."""

    VERTEX_ADDED = "Point added"
    VERTEX_UNDONE = "Point undone"
    POLYGON_CLOSED = "Zone finished"
    POLYGON_CLEARED = "Zone cleared - draw a new one"


class HoldAction(Enum):
    """Which long-hold action is currently filling up."""

    UNDO = "Undo"
    CLEAR = "Clear"


@dataclass(frozen=True)
class FrameResult:
    """Everything the feedback layer needs to draw one frame."""

    mode: Mode
    pose: Pose
    tip: tuple[float, float] | None  # smoothed index fingertip (pixels)
    hand_visible: bool
    dwell_progress: float = 0.0       # 0..1
    hold_action: HoldAction | None = None
    hold_progress: float = 0.0        # 0..1
    close_target: Point | None = None  # vertex under the finger; dwelling finishes the zone
    inside: bool = False              # fingertip inside the closed polygon
    events: list[Event] = field(default_factory=list)


class ModeMachine:
    """Consumes landmarks + timestamps; owns the polygon and the current mode."""

    def __init__(self, config: Config, polygon: PolygonDraft | None = None) -> None:
        self.config = config
        self.polygon = polygon if polygon is not None else PolygonDraft()
        # A ready-made closed polygon (e.g. a saved profile) means we start ACTIVE.
        self.mode = Mode.ACTIVE if self.polygon.closed else Mode.DRAWING

        self._pose = Debouncer(Pose.NONE, config.pose_debounce_frames)
        self._tip_filter = PointFilter(
            config.filter_min_cutoff_hz, config.filter_beta, config.filter_d_cutoff_hz
        )
        self._dwell = DwellDetector(config.dwell_time_s)
        self._undo_hold = HoldTimer(config.undo_hold_s)
        self._clear_hold = HoldTimer(config.clear_hold_s)
        self._lost_frames = 0
        self._last = FrameResult(mode=self.mode, pose=Pose.NONE, tip=None, hand_visible=False)

    # ------------------------------------------------------------------ main entry
    def update(self, landmarks: Sequence[Landmark] | None, now_s: float) -> FrameResult:
        """Process one frame. `landmarks` are 21 points in pixels (or None if no hand)."""
        if landmarks is None:
            return self._hand_missing()
        self._lost_frames = 0

        pose = self._pose.update(classify_pose(landmarks, self.config.finger_extended_ratio))
        raw_tip = (landmarks[INDEX_TIP][0], landmarks[INDEX_TIP][1])
        tip = self._tip_filter(raw_tip, now_s)
        size = hand_size(landmarks)

        if self.mode is Mode.DRAWING:
            result = self._update_drawing(pose, tip, size, now_s)
        else:
            result = self._update_active(pose, tip, now_s)
        self._last = result
        return result

    # ----------------------------------------------------------------- per mode
    def _update_drawing(self, pose: Pose, tip: tuple[float, float], size: float,
                        now_s: float) -> FrameResult:
        cfg = self.config
        events: list[Event] = []
        vertices = self.polygon.vertices

        # Fist held -> undo the last vertex (only offered if there is one).
        can_undo = pose is Pose.FIST and bool(vertices)
        if self._undo_hold.update(can_undo, now_s):
            vertices.pop()
            events.append(Event.VERTEX_UNDONE)

        close_target = self._close_target(tip, size)
        # Don't even start a dwell on top of an existing vertex: it would fill the
        # ring and then stack a duplicate point, which feels broken.
        too_close = any(distance(tip, v) <= cfg.min_vertex_distance_px for v in vertices)

        if pose is Pose.POINT and (close_target is not None or not too_close):
            if self._dwell.update(tip, now_s, cfg.dwell_radius_hands * size):
                if close_target is not None:
                    self.close_polygon()
                    events.append(Event.POLYGON_CLOSED)
                elif self.polygon.add_vertex(_round(tip), cfg.min_vertex_distance_px):
                    events.append(Event.VERTEX_ADDED)
        else:
            self._dwell.reset()

        if self.mode is Mode.ACTIVE:  # just closed
            return FrameResult(self.mode, pose, tip, True,
                               inside=self.polygon.contains(tip), events=events)
        return FrameResult(
            mode=self.mode, pose=pose, tip=tip, hand_visible=True,
            dwell_progress=self._dwell.progress,
            hold_action=HoldAction.UNDO if self._undo_hold.progress > 0 else None,
            hold_progress=self._undo_hold.progress,
            close_target=close_target, events=events,
        )

    def _update_active(self, pose: Pose, tip: tuple[float, float], now_s: float) -> FrameResult:
        events: list[Event] = []
        if self._clear_hold.update(pose is Pose.FIST, now_s):
            self.clear()
            events.append(Event.POLYGON_CLEARED)
            return FrameResult(self.mode, pose, tip, True, events=events)
        return FrameResult(
            mode=self.mode, pose=pose, tip=tip, hand_visible=True,
            hold_action=HoldAction.CLEAR if self._clear_hold.progress > 0 else None,
            hold_progress=self._clear_hold.progress,
            inside=self.polygon.contains(tip), events=events,
        )

    def _close_target(self, tip: tuple[float, float], size: float) -> Point | None:
        """The placed point the finger is resting on, if dwelling there should
        finish the zone.

        Any point counts except the most recent one. Why: right after placing a
        point the finger is still next to it, and a small drift followed by a
        pause would otherwise finish the zone by accident.
        """
        vertices = self.polygon.vertices
        if len(vertices) < self.config.min_polygon_vertices:
            return None
        radius = self.config.close_radius_hands * size
        candidates = [v for v in vertices[:-1] if distance(tip, v) <= radius]
        return min(candidates, key=lambda v: distance(tip, v), default=None)

    def _hand_missing(self) -> FrameResult:
        """No hand this frame. Brief dropouts keep the previous state (without
        advancing any timer); longer ones cancel everything in progress."""
        self._lost_frames += 1
        if self._lost_frames <= self.config.hand_lost_grace_frames and self._last.hand_visible:
            return replace(self._last, events=[])
        self._reset_tracking()
        self._last = FrameResult(mode=self.mode, pose=Pose.NONE, tip=None, hand_visible=False)
        return self._last

    # ------------------------------------------------------ actions (also debug keys)
    def add_vertex(self, point: Point) -> bool:
        """Add a vertex directly (debug key 'd'). Only works while drawing."""
        if self.mode is not Mode.DRAWING:
            return False
        return self.polygon.add_vertex(point, self.config.min_vertex_distance_px)

    def close_polygon(self) -> bool:
        """Close the polygon and switch to ACTIVE if it has enough vertices."""
        if not self.polygon.close(self.config.min_polygon_vertices):
            return False
        self.mode = Mode.ACTIVE
        self._reset_timers()
        return True

    def clear(self) -> None:
        """Throw the polygon away and go back to DRAWING."""
        self.polygon.reset()
        self.mode = Mode.DRAWING
        self._reset_timers()

    # ------------------------------------------------------------------ helpers
    def _reset_timers(self) -> None:
        self._dwell.reset()
        self._undo_hold.reset()
        self._clear_hold.reset()

    def _reset_tracking(self) -> None:
        self._reset_timers()
        self._pose.reset(Pose.NONE)
        self._tip_filter.reset()


def _round(point: tuple[float, float]) -> Point:
    return int(round(point[0])), int(round(point[1]))
