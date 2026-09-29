import pytest

from poly.config import DEFAULT_CONFIG
from poly.gestures import (
    Debouncer, DwellDetector, HoldTimer, Pose, classify_pose, hand_size, palm_centre,
)
from synthetic_hands import make_hand

RATIO = DEFAULT_CONFIG.finger_extended_ratio


@pytest.mark.parametrize("pose", [Pose.POINT, Pose.FIST, Pose.OPEN_PALM, Pose.OTHER])
@pytest.mark.parametrize("rotation", [0, 45, 90, 180, -60])
@pytest.mark.parametrize("size", [30, 80, 200])
def test_classify_pose_any_rotation_and_size(pose, rotation, size):
    # Ratios, not y-coordinates, so rotation and distance from camera don't matter.
    assert classify_pose(make_hand(pose, size=size, rotation_deg=rotation), RATIO) is pose


def test_no_hand_is_none():
    assert classify_pose(None, RATIO) is Pose.NONE


def test_hand_size_is_wrist_to_middle_knuckle():
    assert hand_size(make_hand(Pose.POINT, size=80)) == pytest.approx(80)


def test_pointing_at_camera_uses_depth():
    # Foreshortened index finger: short in 2-D, but z shows it reaching forward.
    hand = [list(p) for p in make_hand(Pose.FIST, size=80)]
    wrist, knuckle = hand[0], hand[5]
    for joint, reach in ((6, 0.5), (7, 0.8), (8, 1.0)):
        hand[joint] = [knuckle[0], knuckle[1], -reach * 80]  # straight towards camera
    assert classify_pose(hand, RATIO) is Pose.POINT
    flat = [p[:2] for p in hand]  # without z it would look like a fist
    assert classify_pose(flat, RATIO) is Pose.FIST


def test_debouncer_ignores_single_frame_blips():
    d = Debouncer(Pose.POINT, frames=3)
    assert [d.update(p) for p in [Pose.FIST, Pose.POINT, Pose.FIST, Pose.FIST]] == [Pose.POINT] * 4
    assert d.update(Pose.FIST) is Pose.FIST  # third FIST in a row


def test_dwell_fires_once_after_holding_still():
    dwell = DwellDetector(0.8)
    fired = [dwell.update((100, 100), t / 30, radius=20) for t in range(90)]  # 3 s
    assert fired.count(True) == 1
    assert fired.index(True) == 24  # 24 frames = 0.8 s


def test_dwell_restarts_when_point_leaves_radius():
    dwell = DwellDetector(0.8)
    for t in range(20):
        assert not dwell.update((100, 100), t / 30, radius=20)
    dwell.update((150, 100), 20 / 30, radius=20)  # moved away: restart
    assert dwell.progress == 0.0


def test_dwell_rearms_after_moving_away():
    dwell = DwellDetector(0.8)
    t = 0
    for pos in [(100, 100), (200, 200)]:
        hits = 0
        for _ in range(40):
            hits += dwell.update(pos, t / 30, radius=20)
            t += 1
        assert hits == 1


def test_hold_timer_fires_once_and_needs_release():
    hold = HoldTimer(1.0)
    fired = [hold.update(True, t / 30) for t in range(90)]
    assert fired.count(True) == 1 and fired.index(True) == 30
    hold.update(False, 3.0)
    assert [hold.update(True, 3.0 + t / 30) for t in range(31)].count(True) == 1


def test_hold_timer_progress_resets_on_release():
    hold = HoldTimer(1.0)
    for t in range(15):
        hold.update(True, t / 30)
    assert hold.progress == pytest.approx(14 / 30)
    hold.update(False, 0.5)
    assert hold.progress == 0.0


def test_palm_centre_ignores_finger_pose():
    # Same hand position, different fingers: the palm centre doesn't move.
    wrist_at = make_hand(Pose.FIST)[0]
    palm = make_hand(Pose.OPEN_PALM)
    shift = (wrist_at[0] - palm[0][0], wrist_at[1] - palm[0][1])
    moved_palm = [(x + shift[0], y + shift[1], z) for x, y, z in palm]
    assert palm_centre(moved_palm) == pytest.approx(palm_centre(make_hand(Pose.FIST)))


def test_hold_timer_blocked_until_release():
    hold = HoldTimer(0.5)
    hold.block_until_release()
    assert not any(hold.update(True, t / 30) for t in range(60))  # held 2 s: nothing
    hold.update(False, 2.0)
    assert any(hold.update(True, 2.0 + t / 30) for t in range(20))
