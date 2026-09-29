import numpy as np
import pytest

from poly.app import DEFAULT_MODEL_PATH
from poly.config import DEFAULT_CONFIG
from poly.tracker import HandTracker, MonotonicTimestamper


def test_timestamps_follow_the_clock():
    ts = MonotonicTimestamper()
    assert [ts(1.0), ts(1.5), ts(2.0)] == [1000, 1500, 2000]


def test_repeated_time_still_increases():
    # A webcam often reports the same position (e.g. 0 ms) for every frame.
    ts = MonotonicTimestamper()
    assert [ts(0.0), ts(0.0), ts(0.0)] == [0, 1, 2]


def test_frames_within_one_millisecond_still_increase():
    ts = MonotonicTimestamper()
    assert [ts(5.0001), ts(5.0004), ts(5.0009)] == [5000, 5001, 5002]


def test_clock_going_backwards_never_decreases_timestamp():
    ts = MonotonicTimestamper()
    assert ts(10.0) == 10000
    assert ts(9.0) == 10001
    assert ts(10.5) == 10500


def test_default_model_path_points_at_repo_model():
    assert DEFAULT_MODEL_PATH.name == "hand_landmarker.task"
    assert DEFAULT_MODEL_PATH.exists()


def test_tracker_finds_no_hand_in_blank_frames():
    # Smoke test of the real MediaPipe model. Skipped where MediaPipe's native
    # library can't load (e.g. a headless Linux box without OpenGL/EGL).
    try:
        tracker = HandTracker(DEFAULT_MODEL_PATH, DEFAULT_CONFIG)
    except OSError as exc:
        pytest.skip(f"MediaPipe native library unavailable: {exc}")
    with tracker:
        blank = np.zeros((240, 320, 3), np.uint8)
        # Same time twice: would raise ValueError without the timestamper.
        assert tracker.detect(blank, 0.0) is None
        assert tracker.detect(blank, 0.0) is None
