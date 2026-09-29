"""Mouse backend. This is the ONLY module that moves the real mouse pointer.

Backend: pynput. Why not pyautogui: pyautogui sleeps 0.1 s after every call by
default (which would stall the video loop) and raises an exception when the
pointer reaches a screen corner (its "fail-safe"), which our mapping does on
purpose. pynput just sets the position, with no delay.

The real mouse only moves with --control-cursor. Otherwise a PreviewCursor just
remembers where the pointer *would* go, and the app draws that on screen. Why: a
tracker glitch that hijacks the mouse is hard to stop without touching anything.
"""

from __future__ import annotations

import sys


def parse_screen_size(text: str) -> tuple[int, int]:
    """Parse "1920x1080" into (1920, 1080)."""
    try:
        w, h = (int(part) for part in text.lower().split("x"))
    except ValueError:
        raise ValueError(f"screen size must look like 1920x1080, got {text!r}") from None
    if w <= 0 or h <= 0:
        raise ValueError(f"screen size must be positive, got {text!r}")
    return w, h


def detect_screen_size() -> tuple[int, int] | None:
    """Size of the primary screen in the same units the mouse uses, or None.

    On Windows this asks user32 directly - the same API family pynput uses to move
    the pointer - so the two always agree, whatever the display scaling (125%,
    150%...) is set to.
    """
    if sys.platform == "win32":
        import ctypes

        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        size = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return size
    except Exception:  # no display, or tkinter not installed
        return None


class PreviewCursor:
    """Remembers where the pointer would go, without touching the real mouse."""

    controls_mouse = False

    def __init__(self) -> None:
        self.position: tuple[int, int] | None = None
        self.clicks = 0

    def move_to(self, position: tuple[int, int]) -> None:
        """Record `position` as the pointer position."""
        self.position = position

    def click(self) -> None:
        """Record a left click at the current position."""
        self.clicks += 1


class SystemCursor(PreviewCursor):
    """Moves the real mouse pointer (only created with --control-cursor)."""

    controls_mouse = True

    def __init__(self) -> None:
        super().__init__()
        from pynput.mouse import Button, Controller  # imported here so tests never need it

        self._mouse = Controller()
        self._left = Button.left

    def move_to(self, position: tuple[int, int]) -> None:
        """Move the real pointer, skipping calls that wouldn't change anything."""
        if position != self.position:
            self._mouse.position = position
        super().move_to(position)

    def click(self) -> None:
        """Left click wherever the real pointer is."""
        self._mouse.click(self._left)
        super().click()


def make_cursor(control_mouse: bool) -> PreviewCursor:
    """The real mouse backend if `control_mouse`, otherwise a preview-only one."""
    return SystemCursor() if control_mouse else PreviewCursor()
