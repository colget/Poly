"""One Euro filter: smooths a jittery signal without making fast movements laggy.

Reference: Casiez, Roussel & Vogel, "1€ Filter: A Simple Speed-based Low-pass
Filter for Noisy Input in Interactive Systems", CHI 2012.

Why this filter: a plain moving average has a fixed trade-off - smooth enough to
hide jitter means sluggish when you move. The One Euro filter changes its cutoff
frequency every sample based on how fast the signal is moving, so a finger held
still is rock steady while a quick sweep still feels immediate.
"""

from __future__ import annotations

import math


def smoothing_factor(elapsed_s: float, cutoff_hz: float) -> float:
    """Blend weight for a first-order low-pass filter.

    A low-pass filter with cutoff fc has time constant tau = 1 / (2*pi*fc). For a
    sample that arrives `elapsed_s` after the previous one, the new sample's weight
    is alpha = 1 / (1 + tau / elapsed_s). Lower cutoff -> smaller alpha -> smoother.
    """
    r = 2 * math.pi * cutoff_hz * elapsed_s
    return r / (r + 1)


class FpsMeter:
    """Frames per second, smoothed so the on-screen number is readable.

    Each frame's interval is blended into a running average (exponential moving
    average). `smoothing` is the weight kept from the old average: 0.9 means a
    new frame nudges the estimate by 10%, so the number settles within ~1 s.
    """

    def __init__(self, smoothing: float = 0.9) -> None:
        self.smoothing = smoothing
        self._last: float | None = None
        self._interval: float | None = None

    def tick(self, now_s: float) -> float | None:
        """Record a frame at `now_s`; return the current estimate (None at first)."""
        if self._last is not None and now_s > self._last:
            dt = now_s - self._last
            if self._interval is None:
                self._interval = dt
            else:
                self._interval = self.smoothing * self._interval + (1 - self.smoothing) * dt
        self._last = now_s
        return self.fps

    @property
    def fps(self) -> float | None:
        """Current smoothed frames per second, or None before two frames."""
        return 1.0 / self._interval if self._interval else None


class OneEuroFilter:
    """One Euro filter for a single number. Timestamps are passed in (seconds)."""

    def __init__(self, min_cutoff_hz: float, beta: float, d_cutoff_hz: float) -> None:
        self.min_cutoff_hz = min_cutoff_hz
        self.beta = beta
        self.d_cutoff_hz = d_cutoff_hz
        self.reset()

    def reset(self) -> None:
        """Forget history, e.g. after the hand has been lost (otherwise the first
        new sample would be smoothed towards a stale position)."""
        self._value: float | None = None
        self._speed = 0.0
        self._time: float | None = None

    def __call__(self, value: float, now_s: float) -> float:
        """Feed a new sample taken at `now_s`; return the smoothed value."""
        if self._value is None or self._time is None:
            self._value, self._time = value, now_s
            return value
        elapsed = now_s - self._time
        if elapsed <= 0:  # same or older timestamp: nothing sensible to add
            return self._value

        # 1) Estimate the speed, itself smoothed with a fixed cutoff so a single
        #    noisy sample doesn't look like a sudden fast movement.
        raw_speed = (value - self._value) / elapsed
        a_d = smoothing_factor(elapsed, self.d_cutoff_hz)
        self._speed = a_d * raw_speed + (1 - a_d) * self._speed

        # 2) Faster movement -> higher cutoff -> less smoothing, less lag.
        cutoff = self.min_cutoff_hz + self.beta * abs(self._speed)
        a = smoothing_factor(elapsed, cutoff)
        self._value = a * value + (1 - a) * self._value
        self._time = now_s
        return self._value


class PointFilter:
    """One Euro filter applied to x and y independently."""

    def __init__(self, min_cutoff_hz: float, beta: float, d_cutoff_hz: float) -> None:
        self._x = OneEuroFilter(min_cutoff_hz, beta, d_cutoff_hz)
        self._y = OneEuroFilter(min_cutoff_hz, beta, d_cutoff_hz)

    def reset(self) -> None:
        """Forget history on both axes."""
        self._x.reset()
        self._y.reset()

    def __call__(self, point: tuple[float, float], now_s: float) -> tuple[float, float]:
        """Smooth a 2-D point sampled at `now_s`."""
        return self._x(point[0], now_s), self._y(point[1], now_s)
