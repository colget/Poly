"""State machine tests driven by synthetic hands and a simulated 30 fps clock."""

import random

import pytest

from poly.config import DEFAULT_CONFIG
from poly.geometry import PolygonDraft, distance
from poly.gestures import Pose, palm_centre
from poly.modes import Event, FrameResult, HoldAction, Mode, ModeMachine
from synthetic_hands import make_hand

FPS = 30
FRAME = (640, 480)
SQUARE = [(150, 120), (450, 120), (450, 380), (150, 380)]


def shoelace_area(pts):
    """Area of a polygon; a self-crossing outline would come out much smaller."""
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


class Sim:
    """Feeds frames into a ModeMachine and records everything that happened."""

    def __init__(self, machine: ModeMachine | None = None) -> None:
        self.m = machine or ModeMachine(DEFAULT_CONFIG)
        self.t = 0.0
        self.events: list[Event] = []
        self.results: list[FrameResult] = []

    def _step(self, landmarks) -> FrameResult:
        r = self.m.update(landmarks, self.t, FRAME)
        self.t += 1 / FPS
        self.events += r.events
        self.results.append(r)
        return r

    def hold(self, pose, at, seconds, size=80, jitter=0.0, seed=0) -> FrameResult:
        rng = random.Random(seed)
        r = None
        for _ in range(round(seconds * FPS)):
            p = (at[0] + rng.uniform(-jitter, jitter), at[1] + rng.uniform(-jitter, jitter))
            r = self._step(make_hand(pose, p, size))
        return r

    def move(self, pose, start, end, seconds, size=80) -> FrameResult:
        n = round(seconds * FPS)
        r = None
        for i in range(1, n + 1):
            f = i / n
            p = (start[0] + (end[0] - start[0]) * f, start[1] + (end[1] - start[1]) * f)
            r = self._step(make_hand(pose, p, size))
        return r

    def no_hand(self, frames) -> FrameResult:
        r = None
        for _ in range(frames):
            r = self._step(None)
        return r

    def draw(self, corners, dwell_s=1.5):
        """Point-and-hold at each corner, moving between them."""
        prev = corners[0]
        for c in corners:
            if c != prev:
                self.move(Pose.POINT, prev, c, 0.4)
            self.hold(Pose.POINT, c, dwell_s)
            prev = c


def test_starts_in_drawing_without_a_polygon():
    assert ModeMachine(DEFAULT_CONFIG).mode is Mode.DRAWING


def test_starts_active_with_a_closed_polygon():
    poly = PolygonDraft(vertices=list(SQUARE), closed=True)
    assert ModeMachine(DEFAULT_CONFIG, poly).mode is Mode.ACTIVE


def test_full_draw_close_redraw_cycle():
    sim = Sim()
    sim.draw(SQUARE)
    assert sim.events == [Event.VERTEX_ADDED] * 4
    assert sim.m.mode is Mode.DRAWING
    for got, want in zip(sim.m.polygon.vertices, SQUARE):
        assert distance(got, want) < 3  # the filter settles on the corner

    # Go back to the first corner and hold: closes instead of adding a 5th point.
    sim.move(Pose.POINT, SQUARE[-1], SQUARE[0], 0.4)
    sim.hold(Pose.POINT, SQUARE[0], 1.5)
    assert sim.events[-1] is Event.POLYGON_CLOSED
    assert sim.m.mode is Mode.ACTIVE
    assert len(sim.m.polygon.vertices) == 4

    # ACTIVE: inside/outside follows the fingertip.
    assert sim.move(Pose.POINT, SQUARE[0], (300, 250), 0.5).inside
    assert not sim.move(Pose.POINT, (300, 250), (580, 250), 0.5).inside

    # Fist held 2 s clears and returns to DRAWING.
    sim.hold(Pose.FIST, (300, 250), 2.5)
    assert sim.events[-1] is Event.POLYGON_CLEARED
    assert sim.m.mode is Mode.DRAWING
    assert sim.m.polygon.vertices == [] and not sim.m.polygon.closed

    # ...and a second polygon can be drawn straight away.
    sim.draw(SQUARE[:3])
    assert len(sim.m.polygon.vertices) == 3


def test_holding_still_for_long_adds_one_vertex():
    sim = Sim()
    sim.hold(Pose.POINT, (200, 200), 5.0)
    assert sim.events == [Event.VERTEX_ADDED]


def test_dwell_shows_progress_before_firing():
    sim = Sim()
    r = sim.hold(Pose.POINT, (200, 200), 0.5)
    assert 0 < r.dwell_progress < 1
    assert sim.m.polygon.vertices == []


def test_moving_finger_never_adds_vertices():
    sim = Sim()
    sim.move(Pose.POINT, (100, 100), (500, 400), 3.0)
    assert sim.events == []


def test_tremor_is_tolerated():
    sim = Sim()
    sim.hold(Pose.POINT, (200, 200), 1.5, jitter=6, seed=3)
    assert sim.events == [Event.VERTEX_ADDED]


def test_small_far_away_hand_with_proportional_tremor():
    # Hand 30 px big (far from camera): the dwell radius shrinks with it.
    sim = Sim()
    sim.hold(Pose.POINT, (200, 200), 1.5, size=30, jitter=2, seed=4)
    assert sim.events == [Event.VERTEX_ADDED]


def test_only_pointing_drops_vertices():
    for pose in (Pose.OPEN_PALM, Pose.OTHER, Pose.FIST):
        sim = Sim()
        sim.hold(pose, (200, 200), 3.0)
        assert Event.VERTEX_ADDED not in sim.events, pose


def test_cannot_close_with_fewer_than_three_points():
    sim = Sim()
    sim.draw(SQUARE[:2])
    sim.move(Pose.POINT, SQUARE[1], SQUARE[0], 0.4)
    r = sim.hold(Pose.POINT, SQUARE[0], 2.0)
    assert r.close_target is None
    assert sim.m.mode is Mode.DRAWING


def test_no_vertex_stacked_on_an_earlier_vertex():
    sim = Sim()
    sim.draw(SQUARE[:2])
    sim.move(Pose.POINT, SQUARE[1], SQUARE[0], 0.4)
    sim.hold(Pose.POINT, SQUARE[0], 2.0)
    assert len(sim.m.polygon.vertices) == 2


def test_close_target_is_reported_for_the_highlight():
    sim = Sim()
    sim.draw(SQUARE[:3])
    r = sim.move(Pose.POINT, SQUARE[2], (SQUARE[1][0] + 10, SQUARE[1][1]), 0.6)
    assert r.close_target == sim.m.polygon.vertices[1]


def test_points_in_any_order_make_a_non_crossing_zone():
    # "Bow-tie" order: joining these in placement order would cross itself.
    sim = Sim()
    sim.draw([SQUARE[0], SQUARE[2], SQUARE[1], SQUARE[3]])
    assert sim.m.mode is Mode.DRAWING
    # Finish on a point that was neither first nor last.
    sim.move(Pose.POINT, SQUARE[3], SQUARE[2], 0.4)
    sim.hold(Pose.POINT, SQUARE[2], 1.5)
    assert sim.events[-1] is Event.POLYGON_CLOSED
    assert abs(shoelace_area(sim.m.polygon.vertices) - 300 * 260) < 2000
    assert sim.move(Pose.POINT, SQUARE[2], (300, 250), 0.5).inside


def test_resting_near_the_latest_point_does_not_finish():
    # Right after placing a point the finger is still beside it: a small drift
    # and a pause must not finish the zone by accident.
    sim = Sim()
    sim.draw(SQUARE[:3])
    drift = (SQUARE[2][0] + 25, SQUARE[2][1])
    sim.move(Pose.POINT, SQUARE[2], drift, 0.2)
    r = sim.hold(Pose.POINT, drift, 0.5)
    assert r.close_target is None
    sim.hold(Pose.POINT, drift, 1.5)
    assert Event.POLYGON_CLOSED not in sim.events


def test_fist_undoes_one_vertex_per_hold():
    sim = Sim()
    sim.draw(SQUARE[:3])
    r = sim.hold(Pose.FIST, SQUARE[2], 0.5)
    assert r.hold_action is HoldAction.UNDO and 0 < r.hold_progress < 1
    sim.hold(Pose.FIST, SQUARE[2], 2.5)  # keep holding: still just one undo
    assert sim.events.count(Event.VERTEX_UNDONE) == 1
    assert len(sim.m.polygon.vertices) == 2

    sim.hold(Pose.OTHER, SQUARE[2], 0.3)  # release...
    sim.hold(Pose.FIST, SQUARE[2], 1.3)  # ...and fist again: second undo
    assert len(sim.m.polygon.vertices) == 1


def test_no_undo_ring_when_nothing_to_undo():
    sim = Sim()
    r = sim.hold(Pose.FIST, (200, 200), 1.5)
    assert r.hold_action is None and sim.events == []


def test_short_fist_in_active_does_not_clear():
    poly = PolygonDraft(vertices=list(SQUARE), closed=True)
    sim = Sim(ModeMachine(DEFAULT_CONFIG, poly))
    r = sim.hold(Pose.FIST, (300, 250), 1.5)  # longer than undo, shorter than clear
    assert r.hold_action is HoldAction.CLEAR and r.hold_progress > 0.5
    sim.hold(Pose.POINT, (300, 250), 0.5)
    assert sim.m.mode is Mode.ACTIVE and sim.events == []


def test_pointing_in_active_does_not_add_vertices():
    poly = PolygonDraft(vertices=list(SQUARE), closed=True)
    sim = Sim(ModeMachine(DEFAULT_CONFIG, poly))
    sim.hold(Pose.POINT, (300, 250), 3.0)
    assert sim.events == [] and len(sim.m.polygon.vertices) == 4


def test_single_frame_misclassification_does_not_break_dwell():
    sim = Sim()
    sim.hold(Pose.POINT, (200, 200), 0.5)
    sim.hold(Pose.FIST, (200, 200), 1 / FPS)  # one bad frame
    sim.hold(Pose.POINT, (200, 200), 0.4)
    assert sim.events == [Event.VERTEX_ADDED]
    assert sim.t < 1.0  # finished on the original schedule, not restarted


def test_brief_hand_dropout_keeps_the_dwell():
    sim = Sim()
    sim.hold(Pose.POINT, (200, 200), 0.5)
    r = sim.no_hand(3)
    assert r.hand_visible and r.tip is not None and r.dwell_progress > 0
    sim.hold(Pose.POINT, (200, 200), 0.4)
    assert sim.events == [Event.VERTEX_ADDED]


def test_long_hand_loss_cancels_the_dwell():
    sim = Sim()
    sim.hold(Pose.POINT, (200, 200), 0.6)
    r = sim.no_hand(20)
    assert not r.hand_visible and r.tip is None and r.dwell_progress == 0
    sim.hold(Pose.POINT, (200, 200), 0.4)
    assert sim.events == []  # had to start again


def test_hand_loss_keeps_mode_and_polygon():
    poly = PolygonDraft(vertices=list(SQUARE), closed=True)
    sim = Sim(ModeMachine(DEFAULT_CONFIG, poly))
    sim.no_hand(100)
    assert sim.m.mode is Mode.ACTIVE and len(sim.m.polygon.vertices) == 4


def test_filter_restarts_after_hand_loss():
    # Reappearing elsewhere must not drag the dot across from the old position.
    sim = Sim()
    sim.hold(Pose.POINT, (100, 100), 0.5)
    sim.no_hand(20)
    r = sim.hold(Pose.POINT, (500, 400), 1 / FPS)
    assert r.tip == (500, 400)


def test_debug_actions():
    m = ModeMachine(DEFAULT_CONFIG)
    for v in SQUARE:
        assert m.add_vertex(v)
    assert m.close_polygon() and m.mode is Mode.ACTIVE
    assert not m.add_vertex((1, 1))  # not while ACTIVE
    m.clear()
    assert m.mode is Mode.DRAWING and m.polygon.vertices == []


# ---------------------------------------------------------------- quick zone


def test_open_palm_creates_a_quick_zone_around_the_hand():
    sim = Sim()
    r = sim.hold(Pose.OPEN_PALM, (320, 200), 0.8)
    assert r.hold_action is HoldAction.QUICK_ZONE and 0 < r.hold_progress < 1
    sim.hold(Pose.OPEN_PALM, (320, 200), 1.0)
    assert sim.events == [Event.QUICK_ZONE]
    assert sim.m.mode is Mode.ACTIVE
    verts = sim.m.polygon.vertices
    assert len(verts) == 4
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    assert max(xs) - min(xs) == pytest.approx(4 * 80, abs=2)  # 4 hand sizes wide
    # Centred horizontally on the palm, not the fingertip.
    palm_x, _ = palm_centre(make_hand(Pose.OPEN_PALM, (320, 200)))
    assert abs((max(xs) + min(xs)) / 2 - palm_x) < 2


def test_quick_zone_stays_above_the_reach_band():
    # Palm low in the frame: the zone is lifted so its bottom stays where the
    # palm is still visible while pointing.
    sim = Sim()
    sim.hold(Pose.OPEN_PALM, (320, 330), 2.0)
    bottom = max(v[1] for v in sim.m.polygon.vertices)
    assert bottom <= FRAME[1] - DEFAULT_CONFIG.reach_margin_hands * 80 + 1
    assert min(v[1] for v in sim.m.polygon.vertices) >= DEFAULT_CONFIG.edge_margin_px


def test_quick_zone_only_when_no_points_placed():
    sim = Sim()
    sim.draw(SQUARE[:1])
    sim.hold(Pose.OPEN_PALM, (320, 200), 3.0)
    assert sim.events == [Event.VERTEX_ADDED]
    assert sim.m.mode is Mode.DRAWING


def test_palm_still_open_after_quick_zone_does_not_grab():
    sim = Sim()
    sim.hold(Pose.OPEN_PALM, (320, 200), 4.0)
    assert sim.events == [Event.QUICK_ZONE]
    assert sim.m.mode is Mode.ACTIVE


# ---------------------------------------------------------------- grab & move


def active_sim() -> Sim:
    return Sim(ModeMachine(DEFAULT_CONFIG, PolygonDraft(vertices=list(SQUARE), closed=True)))


def test_short_open_palm_does_not_grab():
    sim = active_sim()
    r = sim.hold(Pose.OPEN_PALM, (300, 250), 0.3)
    assert r.hold_action is HoldAction.GRAB
    sim.hold(Pose.OTHER, (300, 250), 0.3)
    assert sim.m.mode is Mode.ACTIVE and sim.events == []


def test_grab_moves_the_zone_with_the_palm_and_drops_it():
    sim = active_sim()
    sim.hold(Pose.OPEN_PALM, (300, 250), 0.8)
    assert sim.events == [Event.ZONE_GRABBED] and sim.m.mode is Mode.GRAB
    sim.move(Pose.OPEN_PALM, (300, 250), (340, 200), 0.6)
    sim.hold(Pose.OPEN_PALM, (340, 200), 1.0)  # let the smoothing settle
    moved = sim.m.polygon.vertices
    for got, want in zip(moved, SQUARE):
        assert abs(got[0] - (want[0] + 40)) <= 2 and abs(got[1] - (want[1] - 50)) <= 2
    sim.hold(Pose.FIST, (340, 200), 0.3)  # close the hand
    assert sim.events[-1] is Event.ZONE_DROPPED and sim.m.mode is Mode.ACTIVE
    assert sim.m.polygon.vertices == moved  # stays where it was dropped


def test_grabbed_zone_cannot_leave_the_frame():
    sim = active_sim()
    sim.hold(Pose.OPEN_PALM, (300, 250), 0.8)
    sim.move(Pose.OPEN_PALM, (300, 250), (600, 250), 0.5)
    sim.hold(Pose.OPEN_PALM, (600, 250), 1.0)
    xs = [v[0] for v in sim.m.polygon.vertices]
    assert max(xs) == FRAME[0] - DEFAULT_CONFIG.edge_margin_px
    assert max(xs) - min(xs) == 300  # shape unchanged


def test_losing_the_hand_drops_the_zone():
    sim = active_sim()
    sim.hold(Pose.OPEN_PALM, (300, 250), 0.8)
    sim.no_hand(3)  # brief flicker: still holding it
    assert sim.m.mode is Mode.GRAB
    sim.no_hand(20)
    assert sim.m.mode is Mode.ACTIVE and sim.events[-1] is Event.ZONE_DROPPED


def test_fist_used_to_drop_does_not_start_a_clear():
    sim = active_sim()
    sim.hold(Pose.OPEN_PALM, (300, 250), 0.8)
    r = sim.hold(Pose.FIST, (300, 250), 3.0)  # drop with a fist and keep holding
    assert Event.POLYGON_CLEARED not in sim.events and r.hold_action is None
    sim.hold(Pose.OTHER, (300, 250), 0.3)  # relax...
    sim.hold(Pose.FIST, (300, 250), 2.5)  # ...then a deliberate fist still clears
    assert sim.events[-1] is Event.POLYGON_CLEARED


def test_palm_in_drawing_with_points_is_ignored():
    sim = Sim()
    sim.draw(SQUARE[:2])
    r = sim.hold(Pose.OPEN_PALM, SQUARE[1], 2.0)
    assert r.hold_action is None and sim.m.mode is Mode.DRAWING
