import pytest

from poly.config import DEFAULT_CONFIG as CFG
from poly.pointer import TrackpadPointer, acceleration_gain

SCREEN = (1920, 1080)
FPS = 30


def slide(pointer, start, delta, seconds, hand=80.0, t0=0.0, current=(960, 540)):
    """Move the fingertip in a straight line at constant speed; return last position."""
    n = round(seconds * FPS)
    pos = pointer.move(start, hand, t0, current)
    for i in range(1, n + 1):
        f = i / n
        tip = (start[0] + delta[0] * f, start[1] + delta[1] * f)
        pos = pointer.move(tip, hand, t0 + i / FPS, pos)
    return pos


def test_gain_rises_smoothly_with_speed():
    speeds = [0, 0.5, 1, 1.75, 2.5, 3, 10]
    gains = [acceleration_gain(s, CFG) for s in speeds]
    assert gains[0] == gains[1] == CFG.trackpad_min_gain
    assert gains[-1] == gains[-2] == CFG.trackpad_max_gain
    assert gains == sorted(gains)


def test_touching_down_does_not_jump():
    p = TrackpadPointer(SCREEN, CFG)
    assert p.move((500, 300), 80, 0.0, (100, 200)) == (100, 200)


def test_slow_movement_is_fine_and_precise():
    p = TrackpadPointer(SCREEN, CFG)
    # 0.2 hand sizes in 1 s = 0.2 hands/s: below the slow threshold -> min gain.
    end = slide(p, (300, 300), (16, 0), 1.0)
    expected = 0.2 * CFG.trackpad_min_gain * SCREEN[0]
    assert end[0] - 960 == pytest.approx(expected, abs=2)
    assert end[1] == 540


def test_fast_movement_goes_further_for_the_same_distance():
    slow = slide(TrackpadPointer(SCREEN, CFG), (300, 300), (40, 0), 2.0)
    fast = slide(TrackpadPointer(SCREEN, CFG), (300, 300), (40, 0), 0.1)
    assert fast[0] - 960 > 3 * (slow[0] - 960)


def test_same_real_movement_at_any_distance_from_the_camera():
    # Far away the hand (and its movement) look 4x smaller in the image.
    near = slide(TrackpadPointer(SCREEN, CFG), (300, 300), (40, 0), 0.5, hand=160)
    far = slide(TrackpadPointer(SCREEN, CFG), (300, 300), (10, 0), 0.5, hand=40)
    assert near == far


def test_big_screen_moves_the_same_fraction_of_the_screen():
    small = slide(TrackpadPointer((1920, 1080), CFG), (300, 300), (40, 0), 0.5,
                  current=(960, 540))
    big = slide(TrackpadPointer((3840, 2160), CFG), (300, 300), (40, 0), 0.5,
                current=(1920, 1080))
    assert (big[0] - 1920) / 3840 == pytest.approx((small[0] - 960) / 1920, abs=0.001)


def test_pointer_stops_at_screen_edges():
    p = TrackpadPointer(SCREEN, CFG)
    end = slide(p, (300, 300), (-2000, -2000), 0.3)
    assert end == (0, 0)


def test_lift_and_touch_down_elsewhere_does_not_jump():
    p = TrackpadPointer(SCREEN, CFG)
    pos = slide(p, (300, 300), (20, 0), 0.5)
    p.lift()
    assert p.move((100, 400), 80, 5.0, pos) == pos  # finger came back somewhere else
    pos2 = p.move((104, 400), 80, 5.0 + 1 / FPS, pos)
    assert pos2[0] > pos[0] and pos2[1] == pos[1]  # and carries on from there


def test_follows_a_pointer_moved_by_the_real_mouse():
    p = TrackpadPointer(SCREEN, CFG)
    slide(p, (300, 300), (20, 0), 0.5)
    # Someone nudged the real mouse to (10, 10): continue from there.
    assert p.move((320, 300), 80, 1.0, (10, 10)) == (10, 10)


def test_unknown_pointer_position_starts_in_the_centre():
    assert TrackpadPointer(SCREEN, CFG).move((0, 0), 80, 0.0, None) == (960, 540)
