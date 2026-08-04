"""Paths, persisted settings, and the access token."""

from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "Molo"
VERSION = "1.0.1"


def data_dir() -> Path:
    """Where Molo keeps its database, settings and logs, per OS convention."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "molo"
    base.mkdir(parents=True, exist_ok=True)
    return base


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / APP_NAME


@dataclass
class Settings:
    download_dir: str = field(default_factory=lambda: str(default_download_dir()))
    preset: str = "best_compat"
    max_concurrent: int = 2
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    embed_subs: bool = False
    sub_langs: str = "it,en"
    write_archive: bool = True
    auto_update_ytdlp: bool = True
    watch_clipboard: bool = True
    # "auto" follows the system; "en" and "it" pin it.
    language: str = "auto"
    # "none", or a browser name yt-dlp knows: safari, chrome, firefox, brave,
    # edge, chromium, opera, vivaldi.
    cookies_from_browser: str = "none"
    port: int = 7788
    allow_lan: bool = False
    accepted_terms: bool = False
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))

    @property
    def path(self) -> Path:
        return data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        path = data_dir() / "settings.json"
        if path.exists():
            try:
                raw = json.loads(path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
            known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        obj = cls()
        obj.save()
        return obj

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), "utf-8")
        tmp.replace(self.path)
        try:
            self.path.chmod(0o600)  # it holds the access token
        except OSError:
            pass

    # Sane ranges for the numeric fields. Outside these the app either wastes
    # bandwidth or refuses to start.
    _BOUNDS = {"max_concurrent": (1, 8), "port": (1024, 65535)}

    def update(self, changes: dict) -> None:
        """Apply changes, rejecting anything of the wrong shape.

        This used to `setattr` whatever arrived. A string where an int belongs
        was written to settings.json, survived the restart, and then killed
        startup with a TypeError deep in the worker pool, leaving an app that
        could only be revived by hand-editing the file. Refusing at the door
        is cheaper than that.
        """
        for key, value in changes.items():
            if key not in self.__dataclass_fields__ or key == "token":
                continue

            expected = self.__dataclass_fields__[key].type
            expected = expected if isinstance(expected, str) else getattr(expected, "__name__", "")

            if expected == "bool":
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be true or false")
            elif expected == "int":
                # bool is an int in Python, and silently accepting True for a
                # count would be its own small horror.
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"{key} must be a whole number")
                low, high = self._BOUNDS.get(key, (None, None))
                if low is not None and not low <= value <= high:
                    raise ValueError(f"{key} must be between {low} and {high}")
            elif expected == "str":
                if not isinstance(value, str):
                    raise ValueError(f"{key} must be text")

            setattr(self, key, value)
        self.save()


def store_build() -> bool:
    """Is this the build destined for an app store?

    App Review Guideline 2.5.2 forbids downloading and running code that was
    not shipped inside the bundle, which is exactly what the engine updater
    does. A store build therefore has to do without it, and the marker is a
    file placed in the bundle at build time rather than a runtime setting,
    because it must not be something a user can flip.
    """
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled and (Path(bundled) / "APP_STORE").exists():
        return True
    return os.environ.get("MOLO_APP_STORE", "").strip() in {"1", "true", "yes"}


def db_path() -> Path:
    return data_dir() / "molo.db"


def archive_path() -> Path:
    return data_dir() / "archive.txt"


def web_dir() -> Path:
    """The static folder, both in development and inside a PyInstaller bundle."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "molo" / "web"
    return Path(__file__).parent / "web"
