"""The DRAWING / ACTIVE / GRAB state machine. It turns a stream of hand landmarks
plus timestamps into mode changes, polygon edits and events. No camera or drawing
code here - feed it synthetic landmarks and fake times in tests.

    DRAWING --dwell on an earlier point (3+ points)--> ACTIVE
    DRAWING --open palm held (no points yet)---------> ACTIVE (quick rectangle zone)
    ACTIVE  --fist held clear_hold_s-----------------> DRAWING (polygon cleared)
    ACTIVE  --open palm held grab_hold_s-------------> GRAB (zone follows the palm)
    GRAB    --hand closes / hand lost----------------> ACTIVE (zone stays where dropped)

The cursor moves only in ACTIVE, while pointing inside the zone (see
should_move_cursor). Clicking (pinch) arrives in a later phase.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum

from poly.config import Config
from poly.filters import PointFilter
from poly.geometry import Point, PolygonDraft, distance, quick_zone, translate_within
from poly.gestures import (
    INDEX_TIP,
    Debouncer,
    DwellDetector,
    HoldTimer,
    Landmark,
    Pose,
    classify_pose,
    hand_size,
    palm_centre,
)

FrameSize = tuple[int, int]


class Mode(Enum):
    """What the hand is currently doing."""

    DRAWING = "DRAWING"
    ACTIVE = "ACTIVE"
    GRAB = "MOVING ZONE"


class Event(Enum):
    """Things that happened this frame - used for messages and sounds."""

    VERTEX_ADDED = "Point added"
    VERTEX_UNDONE = "Point undone"
    POLYGON_CLOSED = "Zone finished"
    QUICK_ZONE = "Quick zone created"
    POLYGON_CLEARED = "Zone cleared - draw a new one"
    ZONE_GRABBED = "Zone picked up"
    ZONE_DROPPED = "Zone placed"


class HoldAction(Enum):
    """Which long-hold action is currently filling up."""

    UNDO = "Undo"
    CLEAR = "Clear"
    QUICK_ZONE = "Quick zone"
    GRAB = "Grab"


@dataclass(frozen=True)
class FrameResult:
    """Everything the feedback layer needs to draw one frame."""

    mode: Mode
    pose: Pose
    tip: tuple[float, float] | None  # smoothed index fingertip (pixels)
    hand_visible: bool
    hand_size: float | None = None    # wrist -> middle knuckle (pixels)
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
        filter_args = (config.filter_min_cutoff_hz, config.filter_beta, config.filter_d_cutoff_hz)
        self._tip_filter = PointFilter(*filter_args)
        self._palm_filter = PointFilter(*filter_args)
        self._dwell = DwellDetector(config.dwell_time_s)
        self._undo_hold = HoldTimer(config.undo_hold_s)
        self._clear_hold = HoldTimer(config.clear_hold_s)
        self._quick_hold = HoldTimer(config.quick_zone_hold_s)
        self._grab_hold = HoldTimer(config.grab_hold_s)
        # Where the palm and the zone were when the grab started. The zone is always
        # placed relative to these (not nudged frame by frame), so rounding errors
        # can't accumulate and make the zone creep.
        self._grab_palm: tuple[float, float] = (0.0, 0.0)
        self._grab_vertices: list[Point] = []
        self._frame_size: FrameSize | None = None
        self._lost_frames = 0
        self._last = FrameResult(mode=self.mode, pose=Pose.NONE, tip=None, hand_visible=False)

    # ------------------------------------------------------------------ main entry
    def update(self, landmarks: Sequence[Landmark] | None, now_s: float,
               frame_size: FrameSize | None = None) -> FrameResult:
        """Process one frame. `landmarks` are 21 points in pixels (or None if no hand).
        `frame_size` (width, height) keeps generated and moved zones on screen."""
        if frame_size is not None:
            self._frame_size = frame_size
        if landmarks is None:
            return self._hand_missing()
        self._lost_frames = 0

        pose = self._pose.update(classify_pose(landmarks, self.config.finger_extended_ratio))
        raw_tip = (landmarks[INDEX_TIP][0], landmarks[INDEX_TIP][1])
        tip = self._tip_filter(raw_tip, now_s)
        palm = self._palm_filter(palm_centre(landmarks), now_s)
        size = hand_size(landmarks)

        if self.mode is Mode.DRAWING:
            result = self._update_drawing(pose, tip, palm, size, now_s)
        elif self.mode is Mode.ACTIVE:
            result = self._update_active(pose, tip, palm, now_s)
        else:
            result = self._update_grab(pose, tip, palm)
        result = replace(result, hand_size=size)
        self._last = result
        return result

    # ----------------------------------------------------------------- per mode
    def _update_drawing(self, pose: Pose, tip: tuple[float, float], palm: tuple[float, float],
                        size: float, now_s: float) -> FrameResult:
        cfg = self.config
        events: list[Event] = []
        vertices = self.polygon.vertices

        # Fist held -> undo the last vertex (only offered if there is one).
        can_undo = pose is Pose.FIST and bool(vertices)
        if self._undo_hold.update(can_undo, now_s):
            vertices.pop()
            events.append(Event.VERTEX_UNDONE)

        # Open palm held before any point is placed -> ready-made rectangle zone.
        # Only with no points, so it can never throw away points you've placed.
        can_quick = pose is Pose.OPEN_PALM and not vertices
        if self._quick_hold.update(can_quick, now_s):
            self.create_quick_zone(palm, size)
            events.append(Event.QUICK_ZONE)
            return FrameResult(self.mode, pose, tip, True,
                               inside=self.polygon.contains(tip), events=events)

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
        hold_action, hold_progress = _active_hold(
            (HoldAction.UNDO, self._undo_hold), (HoldAction.QUICK_ZONE, self._quick_hold))
        return FrameResult(
            mode=self.mode, pose=pose, tip=tip, hand_visible=True,
            dwell_progress=self._dwell.progress,
            hold_action=hold_action, hold_progress=hold_progress,
            close_target=close_target, events=events,
        )

    def _update_active(self, pose: Pose, tip: tuple[float, float], palm: tuple[float, float],
                       now_s: float) -> FrameResult:
        events: list[Event] = []
        if self._clear_hold.update(pose is Pose.FIST, now_s):
            self.clear()
            events.append(Event.POLYGON_CLEARED)
            return FrameResult(self.mode, pose, tip, True, events=events)

        if self._grab_hold.update(pose is Pose.OPEN_PALM, now_s):
            self.mode = Mode.GRAB
            self._grab_palm = palm
            self._grab_vertices = list(self.polygon.vertices)
            events.append(Event.ZONE_GRABBED)
            return FrameResult(self.mode, pose, tip, True, events=events)

        hold_action, hold_progress = _active_hold(
            (HoldAction.CLEAR, self._clear_hold), (HoldAction.GRAB, self._grab_hold))
        return FrameResult(
            mode=self.mode, pose=pose, tip=tip, hand_visible=True,
            hold_action=hold_action, hold_progress=hold_progress,
            inside=self.polygon.contains(tip), events=events,
        )

    def _update_grab(self, pose: Pose, tip: tuple[float, float],
                     palm: tuple[float, float]) -> FrameResult:
        if pose is not Pose.OPEN_PALM:
            self._drop_zone()
            return FrameResult(self.mode, pose, tip, True,
                               inside=self.polygon.contains(tip), events=[Event.ZONE_DROPPED])
        # The zone follows the palm: same offset as the palm has moved since the grab.
        dx, dy = palm[0] - self._grab_palm[0], palm[1] - self._grab_palm[1]
        self.polygon.vertices[:] = translate_within(
            self._grab_vertices, dx, dy, self._frame_size, self.config.edge_margin_px)
        return FrameResult(self.mode, pose, tip, True)

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
        advancing any timer); longer ones cancel everything in progress, and drop a
        zone that was being moved where it is."""
        self._lost_frames += 1
        if self._lost_frames <= self.config.hand_lost_grace_frames and self._last.hand_visible:
            return replace(self._last, events=[])
        events = []
        if self.mode is Mode.GRAB:
            self._drop_zone()
            events.append(Event.ZONE_DROPPED)
        self._reset_tracking()
        self._last = FrameResult(mode=self.mode, pose=Pose.NONE, tip=None, hand_visible=False)
        return replace(self._last, events=events)

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
        self._enter_active()
        return True

    def create_quick_zone(self, centre: tuple[float, float], size: float) -> None:
        """Replace the polygon with a rectangle around `centre`, sized in hand sizes
        and kept above the band where the palm would leave the camera's view."""
        cfg = self.config
        bottom_limit = None
        if self._frame_size is not None:
            bottom_limit = self._frame_size[1] - cfg.reach_margin_hands * size
        rect = quick_zone(centre, cfg.quick_zone_width_hands * size,
                          cfg.quick_zone_height_hands * size, self._frame_size,
                          bottom_limit, cfg.edge_margin_px)
        self.polygon.reset()
        self.polygon.vertices.extend(rect)
        self.polygon.close(3)
        self._enter_active()

    def clear(self) -> None:
        """Throw the polygon away and go back to DRAWING."""
        self.polygon.reset()
        self.mode = Mode.DRAWING
        self._reset_timers()

    # ------------------------------------------------------------------ helpers
    def _enter_active(self) -> None:
        self.mode = Mode.ACTIVE
        self._reset_timers()
        # The hand is probably still in the shape that got us here: make it relax
        # before the same shape can grab or clear.
        self._grab_hold.block_until_release()
        self._clear_hold.block_until_release()

    def _drop_zone(self) -> None:
        self._enter_active()

    def _reset_timers(self) -> None:
        for timer in (self._dwell, self._undo_hold, self._clear_hold,
                      self._quick_hold, self._grab_hold):
            timer.reset()

    def _reset_tracking(self) -> None:
        self._reset_timers()
        self._pose.reset(Pose.NONE)
        self._tip_filter.reset()
        self._palm_filter.reset()


def should_move_cursor(result: FrameResult) -> bool:
    """The cursor follows the fingertip only when pointing inside an ACTIVE zone.

    Everything else leaves it alone: outside the zone (so you can work normally),
    any other hand shape (so a fist or open palm never drags the pointer), and
    while moving the zone or when no hand is seen.
    """
    return (result.mode is Mode.ACTIVE and result.hand_visible and result.tip is not None
            and result.pose is Pose.POINT and result.inside)


def _active_hold(*holds: tuple[HoldAction, HoldTimer]) -> tuple[HoldAction | None, float]:
    """The hold that is currently filling up (at most one can be, since each needs
    a different pose)."""
    for action, timer in holds:
        if timer.progress > 0:
            return action, timer.progress
    return None, 0.0


def _round(point: tuple[float, float]) -> Point:
    return int(round(point[0])), int(round(point[1]))
