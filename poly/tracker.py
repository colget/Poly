"""MediaPipe wrapper. This is the ONLY module that imports mediapipe; everything
else works with plain tuples, which keeps the rest of the code easy to test."""

from __future__ import annotations

from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from poly.config import Config

# 21 landmarks per hand, each (x, y, z). x and y are normalised to 0-1 across the
# image; z is relative depth (smaller = closer to the camera).
Landmarks = list[tuple[float, float, float]]


class MonotonicTimestamper:
    """Turn clock readings (seconds) into strictly increasing integer milliseconds.

    Why: `detect_for_video` raises ValueError unless every timestamp is larger than
    the previous one. Two frames can land in the same millisecond, and a clock can
    repeat a value, so whenever a reading would not increase we bump it by 1 ms.
    The clock reading is passed in (not read here) so tests can feed fake times.
    """

    def __init__(self) -> None:
        self._last_ms: int | None = None

    def __call__(self, now_s: float) -> int:
        ms = int(now_s * 1000)
        if self._last_ms is not None and ms <= self._last_ms:
            ms = self._last_ms + 1
        self._last_ms = ms
        return ms


class HandTracker:
    """Finds one hand per frame and returns its landmarks as plain tuples."""

    def __init__(self, model_path: Path, config: Config) -> None:
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            # VIDEO mode reuses the previous frame's result to track the hand,
            # which is faster and steadier than detecting from scratch every frame.
            running_mode=vision.RunningMode.VIDEO,
            num_hands=config.max_hands,
            min_hand_detection_confidence=config.min_hand_detection_confidence,
            min_hand_presence_confidence=config.min_hand_presence_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._timestamper = MonotonicTimestamper()

    def detect(self, frame_bgr: np.ndarray, now_s: float) -> Landmarks | None:
        """Detect a hand in an OpenCV BGR frame captured at `now_s` seconds.

        Returns the first hand's 21 landmarks, or None if no hand was found.
        """
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)  # MediaPipe expects RGB
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, self._timestamper(now_s))
        if not result.hand_landmarks:
            return None
        return [(lm.x, lm.y, lm.z) for lm in result.hand_landmarks[0]]

    def close(self) -> None:
        """Release MediaPipe's native resources."""
        self._landmarker.close()

    def __enter__(self) -> HandTracker:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
