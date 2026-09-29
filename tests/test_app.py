from pathlib import Path

import pytest

from poly.app import (
    DEFAULT_MODEL_PATH,
    handle_debug_key,
    parse_args,
    prepare_profile,
    save_profile,
)
from poly.config import DEFAULT_CONFIG
from poly.modes import Mode, ModeMachine
from poly.pointer import PointerMode
from poly.profiles import ProfileStore


def test_default_args():
    args = parse_args([])
    assert args.model == DEFAULT_MODEL_PATH
    assert args.source is None
    assert args.debug_keys is False
    assert args.control_cursor is False
    assert args.screen is None
    assert args.profile is None and args.fresh is False
    # Profile-able options are None until resolved, meaning "not typed".
    assert args.camera is None and args.camera_backend is None
    assert args.resolution is None and args.fps is None
    assert args.pointer is None and args.sound is None


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


@pytest.mark.parametrize("bad", ["../evil", "my profile", ""])
def test_unsafe_profile_names_are_rejected(bad):
    with pytest.raises(SystemExit):
        parse_args(["--profile", bad])


# ------------------------------------------------------------- profile startup


def start(store, argv):
    """What main() does at startup: resolve settings, then save them."""
    args = parse_args(argv)
    profile = prepare_profile(args, store)
    save_profile(store, profile)
    return args, profile


def test_first_run_uses_defaults(tmp_path):
    args, profile = start(ProfileStore(tmp_path), [])
    assert profile.name == "default" and profile.zone is None
    assert args.camera == 0 and args.camera_backend == "auto"
    assert args.resolution is None and args.fps is None
    assert args.pointer is PointerMode.TABLET and args.sound is False


def test_typed_options_are_remembered_next_time(tmp_path):
    store = ProfileStore(tmp_path)
    start(store, ["--camera-backend", "dshow", "--resolution", "1280x720", "--fps", "60",
                  "--pointer", "trackpad", "--sound"])
    args, _ = start(store, [])  # plain `python poly.py`
    assert args.camera_backend == "dshow"
    assert args.resolution == (1280, 720) and args.fps == 60
    assert args.pointer is PointerMode.TRACKPAD and args.sound is True


def test_typed_option_overrides_and_replaces_saved_one(tmp_path):
    store = ProfileStore(tmp_path)
    start(store, ["--pointer", "trackpad", "--sound"])
    args, _ = start(store, ["--pointer", "tablet", "--no-sound"])
    assert args.pointer is PointerMode.TABLET and args.sound is False
    args, _ = start(store, [])
    assert args.pointer is PointerMode.TABLET and args.sound is False


def test_control_cursor_is_never_remembered(tmp_path):
    store = ProfileStore(tmp_path)
    start(store, ["--control-cursor"])
    args, _ = start(store, [])
    assert args.control_cursor is False


def test_fresh_ignores_saved_zone_and_settings(tmp_path):
    store = ProfileStore(tmp_path)
    _, profile = start(store, ["--pointer", "trackpad"])
    profile.zone = [(0.1, 0.1), (0.5, 0.1), (0.5, 0.5)]
    save_profile(store, profile)
    args, profile = start(store, ["--fresh"])
    assert profile.zone is None and args.pointer is PointerMode.TABLET


def test_last_used_profile_loads_by_default(tmp_path):
    store = ProfileStore(tmp_path)
    start(store, ["--profile", "workshop", "--pointer", "trackpad"])
    args, profile = start(store, [])
    assert profile.name == "workshop" and args.pointer is PointerMode.TRACKPAD
    _, profile = start(store, ["--profile", "surgery"])
    assert profile.name == "surgery"
    _, profile = start(store, [])
    assert profile.name == "surgery"


def test_nonsense_saved_setting_falls_back_to_default(tmp_path, capsys):
    store = ProfileStore(tmp_path)
    _, profile = start(store, [])
    profile.settings["pointer"] = "joystick"
    profile.settings["camera_backend"] = "magic"
    store.save(profile)
    args, _ = start(store, [])
    assert args.pointer is PointerMode.TABLET and args.camera_backend == "auto"
    assert "invalid saved setting" in capsys.readouterr().out
