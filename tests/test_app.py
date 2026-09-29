from pathlib import Path

import pytest

from poly.app import DEFAULT_MODEL_PATH, handle_debug_key, parse_args
from poly.config import DEFAULT_CONFIG
from poly.modes import Mode, ModeMachine
from poly.pointer import PointerMode


def test_default_args():
    args = parse_args([])
    assert args.camera == 0
    assert args.model == DEFAULT_MODEL_PATH
    assert args.source is None
    assert args.debug_keys is False
    assert args.sound is False
    assert args.control_cursor is False
    assert args.screen is None
    assert args.camera_backend == "auto"
    assert args.resolution is None and args.fps is None
    assert args.pointer is PointerMode.TABLET


def test_all_args():
    args = parse_args(["--camera", "2", "--model", "m.task", "--source", "clip.mp4", "--debug-keys", "--sound",
                       "--control-cursor", "--screen", "2560x1440",
                       "--camera-backend", "dshow", "--resolution", "1280x720", "--fps", "60",
                       "--pointer", "trackpad"])
    assert args.camera == 2
    assert args.model == Path("m.task")
    assert args.source == Path("clip.mp4")
    assert args.debug_keys is True
    assert args.sound is True
    assert args.control_cursor is True
    assert args.screen == (2560, 1440)
    assert args.camera_backend == "dshow"
    assert args.resolution == (1280, 720) and args.fps == 60
    assert args.pointer is PointerMode.TRACKPAD


def test_debug_keys_draw_close_and_clear():
    m = ModeMachine(DEFAULT_CONFIG)
    for tip in [(0.0, 0.0), (100.4, 0.0), (100.0, 99.6)]:
        assert handle_debug_key(ord("d"), m, tip)
    assert m.polygon.vertices == [(0, 0), (100, 0), (100, 100)]
    assert handle_debug_key(ord("f"), m, None) == "[debug] Polygon closed."
    assert m.mode is Mode.ACTIVE
    assert handle_debug_key(ord("r"), m, None) == "[debug] Cleared."
    assert m.polygon.vertices == [] and m.mode is Mode.DRAWING


def test_debug_add_without_fingertip_does_nothing():
    m = ModeMachine(DEFAULT_CONFIG)
    assert handle_debug_key(ord("d"), m, None) is None
    assert m.polygon.vertices == []


def test_debug_close_with_too_few_points_does_nothing():
    m = ModeMachine(DEFAULT_CONFIG)
    handle_debug_key(ord("d"), m, (0, 0))
    assert handle_debug_key(ord("f"), m, None) is None
    assert m.mode is Mode.DRAWING


def test_unrelated_key_does_nothing():
    m = ModeMachine(DEFAULT_CONFIG)
    assert handle_debug_key(ord("x"), m, (0, 0)) is None
    assert handle_debug_key(255, m, (0, 0)) is None  # no key pressed


def test_bad_screen_size_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--screen", "big"])


def test_unknown_camera_backend_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--camera-backend", "magic"])
