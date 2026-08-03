"""Tests for replacing the engine.

The dangerous parts here are the two that touch the outside world: a file
arriving over the network, and a zip deciding where its contents land. Both are
tested by handing them something wrong on purpose and checking that they refuse
it, because the version that quietly accepts a bad wheel looks exactly like the
version that works.

Nothing here reaches the network. `latest()` is the only function that would,
and it is replaced wherever it is used.
"""

import hashlib
import io
import zipfile

import pytest

from molo import upgrade


# ---------------------------------------------------------------------------
# Version numbers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "a,b",
    [
        ("2026.7.4", "2026.07.04"),      # PyPI normalises, the git tag does not
        ("2026.07.04", "2026.7.4"),
        ("2026.1.1", "2026.01.01"),
    ],
)
def test_the_two_spellings_of_a_release_are_the_same_release(a, b):
    assert upgrade.as_numbers(a) == upgrade.as_numbers(b)


@pytest.mark.parametrize(
    "older,newer",
    [
        ("2026.06.30", "2026.07.04"),
        ("2025.12.31", "2026.01.01"),
        ("2026.07.04", "2026.07.04.232919"),   # a nightly is after the release
        ("2026.7.4", "2026.07.05"),
    ],
)
def test_order(older, newer):
    assert upgrade.as_numbers(older) < upgrade.as_numbers(newer)


def test_a_version_that_makes_no_sense_does_not_raise():
    # Whatever this returns, it must not be an exception: it is read from a
    # folder name, and a folder name can be anything.
    assert isinstance(upgrade.as_numbers("nonsense"), tuple)
    assert isinstance(upgrade.as_numbers(""), tuple)


# ---------------------------------------------------------------------------
# Finding what is already unpacked
# ---------------------------------------------------------------------------
def _make_engine(root, version, complete=True):
    folder = root / version / "yt_dlp"
    folder.mkdir(parents=True)
    if complete:
        (folder / "version.py").write_text(f'__version__ = "{version}"\n')
    return root / version


@pytest.fixture
def engines(tmp_path, monkeypatch):
    root = tmp_path / "engine"
    root.mkdir()
    monkeypatch.setattr(upgrade, "_root", lambda: root)
    return root


def test_installed_is_newest_first(engines):
    for v in ("2026.06.30", "2026.07.04", "2025.12.31"):
        _make_engine(engines, v)
    assert [name for _, name, _ in upgrade.installed()] == [
        "2026.07.04",
        "2026.06.30",
        "2025.12.31",
    ]


def test_a_half_written_folder_is_not_offered(engines):
    _make_engine(engines, "2026.07.04", complete=False)
    assert upgrade.installed() == []


def test_activate_puts_the_newest_first_and_says_which(engines, monkeypatch):
    monkeypatch.setattr(upgrade.sys, "path", ["/somewhere"])
    monkeypatch.setattr(upgrade.sys, "meta_path", [])
    monkeypatch.setattr(upgrade, "_active", None)
    _make_engine(engines, "2026.06.30")
    _make_engine(engines, "2026.07.04")
    assert upgrade.activate() == "2026.07.04"
    assert upgrade.sys.path[0] == str(engines / "2026.07.04")
    assert isinstance(upgrade.sys.meta_path[0], upgrade._EngineFinder)


def test_activate_with_nothing_downloaded_leaves_the_path_alone(engines, monkeypatch):
    monkeypatch.setattr(upgrade.sys, "path", ["/somewhere"])
    monkeypatch.setattr(upgrade.sys, "meta_path", ["already here"])
    assert upgrade.activate() is None
    assert upgrade.sys.path == ["/somewhere"]
    assert upgrade.sys.meta_path == ["already here"]


def test_the_downloaded_engine_beats_one_that_is_already_importable(engines, monkeypatch):
    """The case that only shows up in a packaged build.

    PyInstaller serves the engine frozen into the app through `sys.meta_path`,
    and everything there is consulted before `sys.path`. If Molo only inserted a
    path, the downloaded engine would sit unused and nothing would say so. Here
    a stand-in for the frozen importer is already in `meta_path`, and the
    downloaded one still has to win.
    """
    _make_engine(engines, "2026.07.04")
    (engines / "2026.07.04" / "yt_dlp" / "__init__.py").write_text(
        "from .version import __version__\n"
    )

    bundled = engines.parent / "bundled"
    (bundled / "yt_dlp").mkdir(parents=True)
    (bundled / "yt_dlp" / "__init__.py").write_text('__version__ = "1999.01.01"\n')

    class PretendFrozenImporter:
        """Stands in for PyInstaller's importer: answers from `bundled`."""

        def find_spec(self, fullname, path=None, target=None):
            if fullname != "yt_dlp":
                return None
            from importlib.machinery import PathFinder

            return PathFinder.find_spec(fullname, [str(bundled)])

    # In front of the real chain, not instead of it: the standard finders still
    # have to be there or nothing can resolve `yt_dlp.version` afterwards.
    monkeypatch.setattr(
        upgrade.sys, "meta_path", [PretendFrozenImporter(), *upgrade.sys.meta_path]
    )
    monkeypatch.setattr(upgrade.sys, "path", [])
    monkeypatch.setattr(upgrade, "_active", None)
    monkeypatch.delitem(upgrade.sys.modules, "yt_dlp", raising=False)

    # Without activate(), the stand-in wins: that is the bug being guarded.
    import importlib

    assert importlib.import_module("yt_dlp").__version__ == "1999.01.01"
    monkeypatch.delitem(upgrade.sys.modules, "yt_dlp", raising=False)

    assert upgrade.activate() == "2026.07.04"
    assert importlib.import_module("yt_dlp").__version__ == "2026.07.04"
    monkeypatch.delitem(upgrade.sys.modules, "yt_dlp", raising=False)


def test_activate_survives_a_data_folder_that_cannot_be_read(engines, monkeypatch):
    def refuse():
        raise OSError("the disk went away")

    monkeypatch.setattr(upgrade, "installed", refuse)
    # A data folder that cannot be read is not a reason to stop: Molo still has
    # the engine it ships with, and starting is better than being right.
    assert upgrade.activate() is None


# ---------------------------------------------------------------------------
# The wheel itself
# ---------------------------------------------------------------------------
def _wheel_bytes(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, body in entries.items():
            z.writestr(name, body)
    return buffer.getvalue()


def test_a_wheel_that_tries_to_write_outside_the_folder_is_refused(tmp_path):
    evil = tmp_path / "evil.whl"
    evil.write_bytes(_wheel_bytes({"yt_dlp/../../escaped.py": "print('hi')"}))
    with pytest.raises(ValueError, match="leaves the folder"):
        upgrade._unpack(evil, tmp_path / "out")


def test_only_the_package_comes_out(tmp_path):
    good = tmp_path / "good.whl"
    good.write_bytes(
        _wheel_bytes(
            {
                "yt_dlp/version.py": '__version__ = "2026.07.04"\n',
                "yt_dlp/__init__.py": "",
                "yt_dlp-2026.7.4.dist-info/RECORD": "junk",
                "somethingelse/mine.py": "",
            }
        )
    )
    out = tmp_path / "out"
    upgrade._unpack(good, out)
    assert (out / "yt_dlp" / "version.py").is_file()
    assert not (out / "somethingelse").exists()
    assert not list(out.glob("*.dist-info"))


def test_a_wheel_without_yt_dlp_in_it_is_refused(tmp_path):
    empty = tmp_path / "empty.whl"
    empty.write_bytes(_wheel_bytes({"yt_dlp/README": "no version.py here"}))
    with pytest.raises(ValueError, match="usable yt_dlp package"):
        upgrade._unpack(empty, tmp_path / "out")


def test_a_download_whose_hash_is_wrong_is_thrown_away(tmp_path, monkeypatch):
    payload = b"not the file PyPI described"

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        upgrade.urllib.request, "urlopen", lambda *a, **k: FakeResponse(payload)
    )
    wheel = upgrade.Wheel("2026.07.04", "https://example.invalid/w.whl", "0" * 64, len(payload))
    target = tmp_path / "w.whl"
    with pytest.raises(ValueError, match="not the one PyPI describes"):
        upgrade._fetch(wheel, target)
    # Nothing half downloaded is left behind to be mistaken for a good copy.
    assert not target.exists()


def test_a_download_whose_hash_matches_is_kept(tmp_path, monkeypatch):
    payload = b"pretend this is a wheel"

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        upgrade.urllib.request, "urlopen", lambda *a, **k: FakeResponse(payload)
    )
    wheel = upgrade.Wheel(
        "2026.07.04",
        "https://example.invalid/w.whl",
        hashlib.sha256(payload).hexdigest(),
        len(payload),
    )
    target = tmp_path / "w.whl"
    upgrade._fetch(wheel, target)
    assert target.read_bytes() == payload


# ---------------------------------------------------------------------------
# install(), without the network
# ---------------------------------------------------------------------------
def test_nothing_happens_when_the_running_engine_is_already_the_newest(engines, monkeypatch):
    monkeypatch.setattr(
        upgrade, "latest", lambda: upgrade.Wheel("2026.07.04", "https://x.invalid", "a" * 64, 1)
    )
    result = upgrade.install("2026.7.4")     # same release, the other spelling
    assert result.ok and not result.changed
    assert "already current" in result.message


def test_a_pypi_that_will_not_answer_is_a_clean_failure(engines, monkeypatch):
    monkeypatch.setattr(upgrade, "latest", lambda: None)
    result = upgrade.install("2026.01.01")
    assert not result.ok and not result.changed
    assert "Could not reach PyPI" in result.message


def test_an_engine_already_on_disk_is_not_downloaded_again(engines, monkeypatch):
    _make_engine(engines, "2026.07.04")
    monkeypatch.setattr(
        upgrade, "latest", lambda: upgrade.Wheel("2026.07.04", "https://x.invalid", "a" * 64, 1)
    )

    def explode(*a, **k):
        raise AssertionError("it went to the network when it did not need to")

    monkeypatch.setattr(upgrade, "_fetch", explode)
    result = upgrade.install("2026.01.01")
    assert result.ok and not result.changed
    assert "already downloaded" in result.message


def test_a_failed_download_leaves_no_folder_behind(engines, monkeypatch):
    monkeypatch.setattr(
        upgrade, "latest", lambda: upgrade.Wheel("2026.07.04", "https://x.invalid", "a" * 64, 1)
    )

    def fail(*a, **k):
        raise OSError("the network went away halfway through")

    monkeypatch.setattr(upgrade, "_fetch", fail)
    result = upgrade.install("2026.01.01")
    assert not result.ok and not result.changed
    # The next launch must not find a folder that looks usable and is not.
    assert upgrade.installed() == []
    assert not list(engines.glob(".*"))


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------
def test_prune_keeps_the_newest_and_never_the_one_in_use(engines, monkeypatch):
    for v in ("2026.04.01", "2026.05.01", "2026.06.01", "2026.07.01"):
        _make_engine(engines, v)
    in_use = engines / "2026.04.01"
    monkeypatch.setattr(upgrade, "_active", in_use)
    upgrade.prune(keep=2)
    left = {name for _, name, _ in upgrade.installed()}
    assert "2026.07.01" in left and "2026.06.01" in left
    assert "2026.04.01" in left, "the engine being used was deleted from under it"
    assert "2026.05.01" not in left
