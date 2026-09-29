"""Save and load profiles: the zone plus preferred settings, as JSON files.

Why profiles: the user shouldn't have to redraw the zone or retype options every
time - and with dirty or sterile hands there's no keyboard to pick a file with. So
the last used profile loads automatically at startup, and changes save
automatically.

The zone is stored *normalised*: every vertex as a fraction (0-1) of the camera
image's width and height, plus the resolution it was drawn at. Why: pixel
coordinates break as soon as the camera resolution changes (a vertex at x=1000
doesn't even exist in a 640-wide image), while "60% across" means the same spot at
any resolution.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poly.geometry import Point

FORMAT_VERSION = 1
DEFAULT_PROFILE = "default"
_LAST_USED_FILE = "last_used.json"
# Names become file names, so keep them to safe characters (no "../", no spaces).
_VALID_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

NormPoint = tuple[float, float]
Settings = dict[str, Any]


def valid_profile_name(name: str) -> bool:
    """True if `name` is safe to use as a profile (file) name."""
    return bool(_VALID_NAME.match(name))


def normalise(vertices: list[Point], frame_size: tuple[int, int]) -> list[NormPoint]:
    """Pixel vertices -> fractions of the image size (0-1)."""
    w, h = frame_size
    return [(x / w, y / h) for x, y in vertices]


def denormalise(zone: list[NormPoint], frame_size: tuple[int, int]) -> list[Point]:
    """Fractions of the image size -> pixel vertices for this image size."""
    w, h = frame_size
    return [(int(round(u * w)), int(round(v * h))) for u, v in zone]


@dataclass
class Profile:
    """A saved zone (normalised, or None if there isn't one) and settings."""

    name: str
    zone: list[NormPoint] | None = None
    frame_size: tuple[int, int] | None = None  # camera resolution the zone was drawn at
    settings: Settings = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready representation."""
        return {
            "version": FORMAT_VERSION,
            "name": self.name,
            "frame_size": list(self.frame_size) if self.frame_size else None,
            "zone": [[round(u, 6), round(v, 6)] for u, v in self.zone] if self.zone else None,
            "settings": dict(self.settings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Build a Profile from parsed JSON. Raises ValueError if it doesn't make sense."""
        if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION:
            raise ValueError("not a Poly profile (or an unsupported version)")
        zone = data.get("zone")
        if zone is not None:
            zone = [(float(u), float(v)) for u, v in zone]
            if len(zone) < 3 or not all(0 <= c <= 1 for p in zone for c in p):
                raise ValueError("zone must have 3+ points with coordinates between 0 and 1")
        frame_size = data.get("frame_size")
        if frame_size is not None:
            frame_size = (int(frame_size[0]), int(frame_size[1]))
        settings = data.get("settings") or {}
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        return cls(name=str(data.get("name", "")), zone=zone, frame_size=frame_size,
                   settings=settings)


class ProfileStore:
    """Profiles as `<directory>/<name>.json`, plus a note of the last one used."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def path(self, name: str) -> Path:
        """File path for profile `name` (which must be a valid name)."""
        if not valid_profile_name(name):
            raise ValueError(f"invalid profile name {name!r}: use letters, digits, - and _")
        return self.directory / f"{name}.json"

    def load(self, name: str) -> Profile | None:
        """The saved profile, or None if there isn't one. A damaged file is reported
        and ignored rather than crashing the app - the user can simply redraw."""
        path = self.path(name)
        if not path.exists():
            return None
        try:
            profile = Profile.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            print(f"Warning: ignoring unreadable profile {path}: {exc}")
            return None
        profile.name = name
        return profile

    def save(self, profile: Profile) -> None:
        """Write the profile. Written to a temporary file first and then swapped in,
        so a crash mid-write can never leave a half-written (corrupt) profile."""
        self._write_json(self.path(profile.name), profile.to_dict())

    def last_used(self) -> str | None:
        """Name of the profile used last time, if known."""
        try:
            name = json.loads((self.directory / _LAST_USED_FILE).read_text(encoding="utf-8"))["name"]
        except (OSError, ValueError, TypeError, KeyError):
            return None
        return name if isinstance(name, str) and valid_profile_name(name) else None

    def set_last_used(self, name: str) -> None:
        """Remember `name` as the profile to load next time."""
        self._write_json(self.directory / _LAST_USED_FILE, {"name": name})

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def resolve_settings(cli: Settings, saved: Settings, defaults: Settings) -> Settings:
    """Combine settings: typed on the command line > saved in the profile > default.

    `cli` holds only options that were actually typed (others are absent or None),
    so a saved preference is never overwritten by an option you didn't give.
    """
    result = dict(defaults)
    for key in defaults:
        if saved.get(key) is not None:
            result[key] = saved[key]
        if cli.get(key) is not None:
            result[key] = cli[key]
    return result
