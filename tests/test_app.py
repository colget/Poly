from pathlib import Path

from poly.app import DEFAULT_MODEL_PATH, handle_debug_key, parse_args
from poly.config import DEFAULT_CONFIG
from poly.geometry import PolygonDraft


def test_default_args():
    args = parse_args([])
    assert args.camera == 0
    assert args.model == DEFAULT_MODEL_PATH
    assert args.source is None
    assert args.debug_keys is False


def test_all_args():
    args = parse_args(["--camera", "2", "--model", "m.task", "--source", "clip.mp4", "--debug-keys"])
    assert args.camera == 2
    assert args.model == Path("m.task")
    assert args.source == Path("clip.mp4")
    assert args.debug_keys is True


def test_debug_keys_draw_close_and_reset():
    draft = PolygonDraft()
    for tip in [(0, 0), (100, 0), (100, 100)]:
        assert handle_debug_key(ord("d"), draft, tip, DEFAULT_CONFIG)
    assert handle_debug_key(ord("f"), draft, None, DEFAULT_CONFIG) == "Polygon finished!"
    assert draft.closed
    assert handle_debug_key(ord("r"), draft, None, DEFAULT_CONFIG) == "Reset."
    assert draft.vertices == [] and not draft.closed


def test_debug_add_without_fingertip_does_nothing():
    draft = PolygonDraft()
    assert handle_debug_key(ord("d"), draft, None, DEFAULT_CONFIG) is None
    assert draft.vertices == []


def test_debug_close_with_too_few_points_does_nothing():
    draft = PolygonDraft()
    handle_debug_key(ord("d"), draft, (0, 0), DEFAULT_CONFIG)
    assert handle_debug_key(ord("f"), draft, None, DEFAULT_CONFIG) is None
    assert not draft.closed


def test_unrelated_key_does_nothing():
    draft = PolygonDraft()
    assert handle_debug_key(ord("x"), draft, (0, 0), DEFAULT_CONFIG) is None
    assert handle_debug_key(255, draft, (0, 0), DEFAULT_CONFIG) is None  # no key pressed
