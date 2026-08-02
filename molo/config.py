"""Percorsi, impostazioni persistenti e token di accesso."""

from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "Molo"
VERSION = "0.1.0"


def data_dir() -> Path:
    """Dove Molo tiene database, impostazioni e log, secondo le convenzioni di ogni OS."""
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
    # Distribuito acceso. Vedi molo/policy.py per cosa cambia spegnendolo
    # (meno di quanto suggerisca il nome: nessuna capacità nuova).
    strict_policy: bool = True
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
            self.path.chmod(0o600)  # contiene il token di accesso
        except OSError:
            pass

    def update(self, changes: dict) -> None:
        for key, value in changes.items():
            if key in self.__dataclass_fields__ and key != "token":
                setattr(self, key, value)
        self.save()


def db_path() -> Path:
    return data_dir() / "molo.db"


def archive_path() -> Path:
    return data_dir() / "archive.txt"


def web_dir() -> Path:
    """La cartella statica, sia in sviluppo sia dentro il bundle PyInstaller."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "molo" / "web"
    return Path(__file__).parent / "web"
