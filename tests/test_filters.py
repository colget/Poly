import math
import random
import statistics

import pytest

from poly.filters import OneEuroFilter, PointFilter, smoothing_factor

FPS = 30
DT = 1 / FPS


def make_filter():
    return OneEuroFilter(min_cutoff_hz=0.5, beta=0.01, d_cutoff_hz=1.0)


def test_smoothing_factor_matches_formula():
    # tau = 1 / (2*pi*fc); alpha = 1 / (1 + tau/Te)
    tau = 1 / (2 * math.pi * 1.0)
    assert smoothing_factor(DT, 1.0) == pytest.approx(1 / (1 + tau / DT))


def test_first_sample_passes_through():
    assert make_filter()(42.0, 0.0) == 42.0


def test_constant_signal_stays_constant():
    f = make_filter()
    assert all(f(10.0, i * DT) == pytest.approx(10.0) for i in range(30))


def test_jitter_is_strongly_reduced_when_still():
    rng = random.Random(1)
    f = make_filter()
    raw = [100 + rng.uniform(-4, 4) for _ in range(300)]
    out = [f(x, i * DT) for i, x in enumerate(raw)]
    # Compare after the first 2 s, once the filter has settled.
    assert statistics.pstdev(out[60:]) < statistics.pstdev(raw[60:]) / 3.5


def test_fast_movement_has_little_lag():
    # Sweep at 600 px/s: the speed term raises the cutoff so we stay close behind.
    f = make_filter()
    out = [f(600 * i * DT, i * DT) for i in range(30)]
    true_final = 600 * 29 * DT
    assert true_final - out[-1] < 40  # well under 0.1 s of lag


def test_duplicate_timestamp_returns_previous_value():
    f = make_filter()
    f(0.0, 0.0)
    v = f(10.0, DT)
    assert f(99.0, DT) == v


def test_reset_forgets_history():
    f = make_filter()
    for i in range(10):
        f(0.0, i * DT)
    f.reset()
    assert f(500.0, 1.0) == 500.0


def test_point_filter_smooths_both_axes():
    f = PointFilter(1.0, 0.01, 1.0)
    f((0.0, 0.0), 0.0)
    x, y = f((10.0, -10.0), DT)
    assert 0 < x < 10 and -10 < y < 0
