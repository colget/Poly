import sys
import types

import pytest

from poly.cursor import PreviewCursor, SystemCursor, make_cursor, parse_screen_size


def test_parse_screen_size():
    assert parse_screen_size("1920x1080") == (1920, 1080)
    assert parse_screen_size("2560X1440") == (2560, 1440)


@pytest.mark.parametrize("bad", ["1920", "axb", "0x100", "1920x1080x2"])
def test_parse_screen_size_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        parse_screen_size(bad)


def test_preview_never_needs_the_real_mouse():
    cursor = make_cursor(False)
    assert type(cursor) is PreviewCursor and not cursor.controls_mouse
    cursor.move_to((10, 20))
    assert cursor.position == (10, 20)


def test_system_cursor_moves_pointer_only_when_position_changes(monkeypatch):
    moves = []

    class FakeController:
        @property
        def position(self):
            return moves[-1] if moves else (0, 0)

        @position.setter
        def position(self, value):
            moves.append(value)

        def click(self, button):
            moves.append(("click", button))

    fake = types.ModuleType("pynput.mouse")
    fake.Controller = FakeController
    fake.Button = types.SimpleNamespace(left="left")
    monkeypatch.setitem(sys.modules, "pynput", types.ModuleType("pynput"))
    monkeypatch.setitem(sys.modules, "pynput.mouse", fake)

    cursor = make_cursor(True)
    assert isinstance(cursor, SystemCursor) and cursor.controls_mouse
    for pos in [(1, 1), (1, 1), (2, 3)]:
        cursor.move_to(pos)
    assert moves == [(1, 1), (2, 3)]
    cursor.click()
    assert moves[-1] == ("click", "left") and cursor.clicks == 1


def test_preview_counts_clicks():
    cursor = make_cursor(False)
    cursor.click()
    assert cursor.clicks == 1
