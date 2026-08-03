"""Keeping yt-dlp current without repackaging Molo.

A yt-dlp more than a few months old stops working on YouTube, and that is by far
the most common reason a download fails. The 403 that started this project was
exactly that. So the engine has to be replaceable without waiting for a new
build of Molo.

`pip install --upgrade` cannot do it. Inside a PyInstaller bundle there is no
pip, and `sys.executable` is the app itself, so the command either fails
obscurely or installs somewhere nothing will ever read. Molo used to detect that
case and say so plainly, which was honest and not much help.

What works is the wheel. yt-dlp publishes `py3-none-any`, meaning pure Python,
identical on every platform: nothing to compile, nothing to package per OS, and
no second copy of the engine inside the app. Molo unpacks it into its own data
folder and puts that folder first on `sys.path`, so `import yt_dlp` finds the
new one. yt-dlp stays a library, which is the whole point: the progress hooks
keep working and there is no subprocess output to parse.

The wheel comes from PyPI rather than from the GitHub release, because the
GitHub release does not publish one. It ships binaries and an sdist, and either
would mean giving up the library.

**On trust.** The wheel is checked against the sha256 PyPI publishes for it,
over HTTPS. That catches a truncated or corrupted download, and it is the same
trust model pip uses. It is not a signature check and it does not protect
against a compromised release. Calling it "verified" without that sentence would
be a bigger claim than this code makes good on.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

PYPI = "https://pypi.org/pypi/yt-dlp/json"
TIMEOUT = 30
KEEP = 2  # how many downloaded engines stay on disk


@dataclass(frozen=True)
class Wheel:
    version: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Result:
    ok: bool
    changed: bool
    message: str
    before: str = ""
    after: str = ""


def _root() -> Path:
    from .config import data_dir

    return data_dir() / "engine"


def as_numbers(version: str) -> tuple[int, ...]:
    """(2026, 7, 4) from either 2026.7.4 or 2026.07.04.

    PyPI normalises the version and the GitHub tag does not, so the two spellings
    of the same release have to compare equal. Comparing the parts as numbers is
    what makes that true.
    """
    parts = []
    for chunk in version.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def installed() -> list[tuple[tuple[int, ...], str, Path]]:
    """Every unpacked engine in the data folder, newest first."""
    root = _root()
    if not root.is_dir():
        return []
    found = []
    for entry in root.iterdir():
        if entry.is_dir() and (entry / "yt_dlp" / "version.py").is_file():
            found.append((as_numbers(entry.name), entry.name, entry))
    return sorted(found, reverse=True)


class _EngineFinder:
    """Resolve `yt_dlp` from a folder, ahead of anything else that has one.

    `sys.path.insert(0, ...)` is not enough and the reason only shows up in the
    build that matters. PyInstaller puts its own importer in `sys.meta_path`, and
    every finder there runs before the ones that consult `sys.path`. In a
    packaged Molo the engine frozen into the app would win, the downloaded one
    would sit on disk unused, and nothing would say so: the feature would look
    installed and do nothing, in exactly the case it exists for.

    Sitting at the front of `sys.meta_path` is what puts this ahead of the frozen
    importer. Only the top level name is claimed; once `yt_dlp` itself comes from
    the folder, its `__path__` points there and the submodules follow on their
    own.
    """

    def __init__(self, folder: Path) -> None:
        self._where = [str(folder)]

    def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002
        if fullname != "yt_dlp":
            return None
        from importlib.machinery import PathFinder

        return PathFinder.find_spec(fullname, self._where)


#: The engine folder in use, so prune() never deletes the one being read.
_active: Path | None = None


def active() -> Path | None:
    return _active


def activate() -> str | None:
    """Make the newest unpacked engine the one `import yt_dlp` finds.

    Called from `molo/__init__.py`, the only place early enough: `engine` and
    `watch` both import yt_dlp when they load, so this has to be in place before
    either of them is touched.

    Everything here is best effort on purpose. A half written folder, a disk that
    went away, a Python that refuses the import: none of it is worth stopping the
    app for, because the engine shipped inside Molo is still there and still
    works.
    """
    global _active
    try:
        engines = installed()
    except OSError:
        return None
    if not engines:
        return None
    _, name, folder = engines[0]
    sys.meta_path.insert(0, _EngineFinder(folder))
    # Kept as well, so anything that reads sys.path rather than importing (a
    # subprocess, a traceback, somebody debugging) sees the same answer.
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    _active = folder
    return name


def latest() -> Wheel | None:
    """The newest pure Python wheel PyPI has, or None if the question failed."""
    try:
        with urllib.request.urlopen(PYPI, timeout=TIMEOUT) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    version = data.get("info", {}).get("version")
    if not version:
        return None
    for f in data.get("releases", {}).get(version, []):
        # py3-none-any and nothing else: a wheel built for one platform would
        # defeat the reason for doing it this way.
        if f.get("packagetype") == "bdist_wheel" and f.get("filename", "").endswith(
            "-py3-none-any.whl"
        ):
            sha = f.get("digests", {}).get("sha256")
            if sha and f.get("url"):
                return Wheel(version, f["url"], sha, int(f.get("size") or 0))
    return None


def _fetch(wheel: Wheel, target: Path) -> None:
    """Download, and refuse anything whose hash is not the one PyPI published."""
    digest = hashlib.sha256()
    with urllib.request.urlopen(wheel.url, timeout=TIMEOUT) as response, target.open("wb") as f:
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            f.write(chunk)
    if digest.hexdigest() != wheel.sha256:
        target.unlink(missing_ok=True)
        raise ValueError(
            f"the downloaded file is not the one PyPI describes "
            f"(expected {wheel.sha256[:12]}…, got {digest.hexdigest()[:12]}…)"
        )


def _unpack(wheel_file: Path, into: Path) -> None:
    """Unpack only `yt_dlp/`, and only entries that stay inside the folder.

    A wheel is a zip, and a zip can name any path it likes, including `..` and
    absolute ones. No yt-dlp wheel has ever done that, which is exactly why the
    check belongs in the code rather than in the assumption.
    """
    into.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel_file) as z:
        for name in z.namelist():
            if not name.startswith("yt_dlp/"):
                continue
            inside = Path(name)
            if inside.is_absolute() or ".." in inside.parts:
                raise ValueError(f"the wheel contains a path that leaves the folder: {name}")
            z.extract(name, into)
    if not (into / "yt_dlp" / "version.py").is_file():
        raise ValueError("the wheel does not contain a usable yt_dlp package")


def prune(keep: int = KEEP) -> None:
    """Keep the newest few engines and delete the rest.

    Whatever is in use stays: on Windows its files are open and cannot be
    removed, and on any platform pulling it out from under a running download
    would be worse than a little wasted disk.
    """
    for _, _, folder in installed()[keep:]:
        if _active is not None and folder == _active:
            continue
        shutil.rmtree(folder, ignore_errors=True)


def install(current: str) -> Result:
    """Fetch the newest engine if it beats `current`, and leave it where activate() looks."""
    wheel = latest()
    if wheel is None:
        return Result(False, False, "Could not reach PyPI to ask which yt-dlp is current.")

    if as_numbers(wheel.version) <= as_numbers(current):
        return Result(True, False, f"yt-dlp is already current ({current}).", current, current)

    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    final = root / wheel.version
    if (final / "yt_dlp" / "version.py").is_file():
        return Result(
            True,
            False,
            f"yt-dlp {wheel.version} is already downloaded. Restart Molo to use it.",
            current,
            wheel.version,
        )

    staging = root / f".{wheel.version}.partial"
    archive = root / f".{wheel.version}.whl"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        _fetch(wheel, archive)
        _unpack(archive, staging)
        # The last step is a rename, so a reader finds either a complete folder
        # or none at all, never half of one.
        shutil.rmtree(final, ignore_errors=True)
        staging.rename(final)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, zipfile.BadZipFile) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        return Result(False, False, f"Update failed: {exc}", current, current)
    finally:
        archive.unlink(missing_ok=True)

    prune()
    return Result(
        True,
        True,
        f"yt-dlp updated: {current} → {wheel.version}. Restart Molo to use it.",
        current,
        wheel.version,
    )


__all__ = [
    "Wheel",
    "Result",
    "activate",
    "active",
    "installed",
    "latest",
    "install",
    "prune",
    "as_numbers",
]
