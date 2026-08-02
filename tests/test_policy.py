"""Tests for the download policy.

These are the most important tests in the project. If they pass while broken,
Molo stops being the thing it says it is.
"""

import importlib
import pathlib

import pytest

from molo import policy


@pytest.mark.parametrize(
    "url",
    [
        "https://www.netflix.com/watch/80100172",
        "https://netflix.com/title/1",
        "https://something.netflix.com/watch/2",   # subdomains too
        "https://open.spotify.com/track/abc",
        "https://www.disneyplus.com/video/x",
        "https://tv.apple.com/it/movie/y",
        "https://www.audible.com/pd/z",
    ],
)
def test_drm_services_are_refused(url):
    verdict = policy.check_url(url)
    assert not verdict.allowed
    assert "encryption" in verdict.message


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/bk6Xst6euQk",
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://vimeo.com/123456",
        "https://archive.org/details/something",
    ],
)
def test_clear_sources_pass(url):
    assert policy.check_url(url).allowed


@pytest.mark.parametrize("url", ["ftp://host/f.mp4", "file:///etc/passwd", "not a url", ""])
def test_non_http_schemes_refused(url):
    assert not policy.check_url(url).allowed


def test_lookalike_domain_is_not_blocked():
    """netflix.com.example.org is not Netflix: the match is on the suffix."""
    assert policy.check_url("https://netflix.com.example.org/video").allowed


def test_drm_flag_in_metadata():
    assert not policy.check_info({"_has_drm": True}).allowed
    assert not policy.check_info({"formats": [{"has_drm": True}, {"has_drm": True}]}).allowed


def test_mixed_content_stays_downloadable():
    """A clear trailer next to a protected film: the trailer can be taken."""
    info = {"formats": [{"format_id": "trailer"}, {"format_id": "film", "has_drm": True}]}
    assert policy.check_info(info).allowed
    assert [f["format_id"] for f in policy.usable_formats(info["formats"])] == ["trailer"]


def test_host_list_not_emptied_by_accident():
    """If a refactor empties the list, the default behaviour changes unnoticed."""
    assert len(policy.DRM_HOSTS) >= 15
    assert "netflix.com" in policy.DRM_HOSTS


def test_host_precheck_is_on_by_default():
    """The shipped behaviour. Flips if someone inverts the default."""
    assert policy.host_precheck_enabled() is True


def test_drm_metadata_check_has_no_off_switch(monkeypatch):
    """The host list is a heuristic and can be skipped. This one cannot.

    Even with the escape hatch set, encrypted content is still refused —
    there is nothing behind that door to let anyone through to.
    """
    monkeypatch.setenv("MOLO_DISABLE_HOST_PRECHECK", "1")
    reloaded = importlib.reload(policy)
    try:
        assert reloaded.check_url("https://www.netflix.com/watch/1").allowed
        assert not reloaded.check_info({"_has_drm": True}).allowed
        assert not reloaded.check_url("file:///etc/passwd").allowed
    finally:
        monkeypatch.delenv("MOLO_DISABLE_HOST_PRECHECK", raising=False)
        importlib.reload(policy)


def test_no_decryption_code_anywhere():
    """The project's real defence, verified instead of asserted.

    If a contribution introduced a CDM module or a decryption routine, this
    catches it before it reaches a release.
    """
    forbidden = ("widevine", "playready", "fairplay", "pssh", "cdm_", "decrypt_key")
    package = pathlib.Path(policy.__file__).parent

    for path in package.rglob("*.py"):
        text = path.read_text("utf-8").lower()
        for word in forbidden:
            # policy.py names them to explain what it does NOT do.
            if word in text and path.name != "policy.py":
                raise AssertionError(f"{path.name} contains '{word}'")
