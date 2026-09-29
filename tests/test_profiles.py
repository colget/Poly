import json

import pytest

from poly.profiles import (
    Profile,
    ProfileStore,
    denormalise,
    normalise,
    resolve_settings,
    valid_profile_name,
)

ZONE_PX = [(128, 72), (1152, 72), (1152, 648), (128, 648)]


def test_normalise_round_trip():
    norm = normalise(ZONE_PX, (1280, 720))
    assert norm == [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
    assert denormalise(norm, (1280, 720)) == ZONE_PX


def test_zone_follows_a_resolution_change():
    # Drawn at 1280x720, loaded at 640x360: same place in the picture.
    norm = normalise(ZONE_PX, (1280, 720))
    assert denormalise(norm, (640, 360)) == [(64, 36), (576, 36), (576, 324), (64, 324)]


def test_save_and_load_round_trip(tmp_path):
    store = ProfileStore(tmp_path)
    original = Profile(name="default", zone=normalise(ZONE_PX, (1280, 720)),
                       frame_size=(1280, 720),
                       settings={"pointer": "trackpad", "resolution": [1280, 720], "sound": True})
    store.save(original)
    loaded = store.load("default")
    assert loaded == original
    assert denormalise(loaded.zone, (1280, 720)) == ZONE_PX


def test_saved_file_is_readable_json(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(Profile(name="default", zone=[(0.1, 0.2), (0.5, 0.2), (0.3, 0.6)],
                       frame_size=(640, 480)))
    data = json.loads((tmp_path / "default.json").read_text())
    assert data["version"] == 1 and data["frame_size"] == [640, 480]
    assert data["zone"][0] == [0.1, 0.2]


def test_profile_without_zone_round_trips(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(Profile(name="empty", settings={"fps": 60}))
    loaded = store.load("empty")
    assert loaded.zone is None and loaded.settings == {"fps": 60}


def test_missing_profile_is_none(tmp_path):
    assert ProfileStore(tmp_path).load("nothing-here") is None


@pytest.mark.parametrize("content", [
    "{not json",
    '{"version": 99, "zone": null}',
    '{"version": 1, "zone": [[0.1, 0.1], [0.5, 0.5]]}',            # too few points
    '{"version": 1, "zone": [[0.1, 0.1], [1.5, 0.1], [0.5, 0.5]]}',  # off the image
    '{"version": 1, "zone": null, "settings": [1, 2]}',
    '[]',
])
def test_damaged_profile_is_ignored_not_fatal(tmp_path, capsys, content):
    (tmp_path / "default.json").write_text(content)
    assert ProfileStore(tmp_path).load("default") is None
    assert "ignoring unreadable profile" in capsys.readouterr().out


def test_saving_leaves_no_temporary_files(tmp_path):
    store = ProfileStore(tmp_path)
    for i in range(3):
        store.save(Profile(name="default", settings={"fps": i}))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["default.json"]


def test_save_creates_the_folder(tmp_path):
    store = ProfileStore(tmp_path / "profiles")
    store.save(Profile(name="default"))
    assert (tmp_path / "profiles" / "default.json").exists()


@pytest.mark.parametrize("name, ok", [
    ("default", True), ("work-shop_2", True), ("../escape", False), ("a/b", False),
    ("with space", False), ("", False), ("x" * 65, False),
])
def test_profile_names_are_safe_file_names(name, ok):
    assert valid_profile_name(name) is ok


def test_unsafe_name_cannot_be_used_as_a_path(tmp_path):
    with pytest.raises(ValueError):
        ProfileStore(tmp_path).path("../../etc/passwd")


def test_last_used_round_trip(tmp_path):
    store = ProfileStore(tmp_path)
    assert store.last_used() is None
    store.set_last_used("workshop")
    assert store.last_used() == "workshop"


def test_garbled_last_used_is_ignored(tmp_path):
    (tmp_path / "last_used.json").write_text('{"name": "../../bad"}')
    assert ProfileStore(tmp_path).last_used() is None


def test_resolve_settings_precedence():
    defaults = {"pointer": "tablet", "fps": None, "sound": False}
    saved = {"pointer": "trackpad", "fps": 60}
    cli = {"pointer": None, "fps": 30, "sound": None}
    assert resolve_settings(cli, saved, defaults) == {
        "pointer": "trackpad",  # not typed -> saved value
        "fps": 30,              # typed -> beats saved
        "sound": False,         # neither -> default
    }


def test_resolve_settings_ignores_unknown_saved_keys():
    assert resolve_settings({}, {"old_option": 1}, {"fps": None}) == {"fps": None}
