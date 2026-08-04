"""Regressions for the engine.

Every test here exists because something was broken in a way that reached a
user. The comments say which, so nobody later removes one thinking it is
hypothetical.
"""

import pytest

from molo import engine


# --- where the file ended up --------------------------------------------------
#
# "Show file" opened nothing and showed a red error. The path came from the
# progress hook, which fires once per stream, so on a merged download it held
# the temporary audio fragment that ffmpeg had already consumed.

def test_final_path_prefers_the_post_processed_entry(tmp_path):
    merged = tmp_path / "video [abc123].mp4"
    merged.write_bytes(b"x")
    fragment = tmp_path / "video [abc123].f258.m4a"   # deleted in real life

    info = {"id": "abc123", "requested_downloads": [{"filepath": str(merged)}]}
    assert engine._final_path(info, str(fragment), tmp_path) == str(merged)


def test_final_path_ignores_a_hint_that_no_longer_exists(tmp_path):
    real = tmp_path / "song [xyz789].mp3"
    real.write_bytes(b"x")
    gone = tmp_path / "song [xyz789].m4a"            # the pre-conversion name

    info = {"id": "xyz789"}
    assert engine._final_path(info, str(gone), tmp_path) == str(real)


def test_final_path_falls_back_to_scanning_for_the_id(tmp_path):
    found = tmp_path / "Some Title [vid42].mkv"
    found.write_bytes(b"x")

    assert engine._final_path({"id": "vid42"}, None, tmp_path) == str(found)


def test_final_path_skips_partial_files(tmp_path):
    (tmp_path / "clip [vid43].mp4.part").write_bytes(b"x")

    assert engine._final_path({"id": "vid43"}, None, tmp_path) is None


def test_final_path_returns_none_rather_than_a_dead_path(tmp_path):
    """A missing file is worth saying out loud. A broken button is not."""
    assert engine._final_path({"id": "nope"}, "/tmp/not-here-9182.mp4", tmp_path) is None


def test_final_path_takes_the_newest_when_debris_remains(tmp_path):
    import os
    import time

    old = tmp_path / "take [dup01].mp4"
    new = tmp_path / "take [dup01].mkv"
    old.write_bytes(b"x")
    time.sleep(0.02)
    new.write_bytes(b"x")
    os.utime(old, (1, 1))

    assert engine._final_path({"id": "dup01"}, None, tmp_path) == str(new)


# --- cosmetic failures --------------------------------------------------------
#
# A finished download was thrown away because cover art would not attach to an
# m4a. Losing two gigabytes over a thumbnail is not a reasonable trade.

@pytest.mark.parametrize("message", [
    "ERROR: Postprocessing: Unable to embed using ffprobe & ffmpeg; Conversion failed!",
    "Postprocessing: Error while embedding thumbnail",
    "postprocessing: could not write metadata",
])
def test_artwork_failures_are_cosmetic(message):
    assert engine._is_cosmetic_failure(message)


@pytest.mark.parametrize("message", [
    "Postprocessing: ffmpeg exited with code 1 while merging formats",
    "ERROR: unable to download video data: HTTP Error 403: Forbidden",
    "ERROR: Unable to embed the file into the archive",   # not postprocessing
])
def test_real_failures_are_not_cosmetic(message):
    """Merge failures leave no complete file, so they must stay fatal."""
    assert not engine._is_cosmetic_failure(message)


# --- presets ------------------------------------------------------------------

# --- telling the user why it failed -------------------------------------------
#
# "It failed" sends people hunting for a DRM switch that does not exist. Most
# YouTube refusals are a session problem, and the answer is browser cookies.

@pytest.mark.parametrize("message,expected", [
    ("ERROR: [youtube] xx: Sign in to confirm you're not a bot", "login"),
    ("ERROR: [youtube] xx: Sign in to confirm your age", "login"),
    ("ERROR: [youtube] xx: This video is age-restricted", "login"),
    ("ERROR: [youtube] xx: Join this channel to get access to members-only content", "login"),
    ("ERROR: [youtube] xx: Private video", "login"),
    ("ERROR: [youtube] xx: This video is DRM protected", "drm"),
    ("ERROR: The uploader has not made this video available in your country", "geo"),
    ("ERROR: [youtube] xx: nsig extraction failed: Some players may be broken", "stale"),
    ("ERROR: [youtube] xx: Unable to extract player response", "stale"),
])
def test_diagnosis_matches_real_yt_dlp_wording(message, expected):
    """The strings are yt-dlp's actual messages, not paraphrases. A token that
    almost matches is worth nothing, which is how the geo case was missed."""
    assert engine.diagnose(message) == expected


@pytest.mark.parametrize("message", [
    "ERROR: unable to download video data: HTTP Error 403: Forbidden",
    "ERROR: Postprocessing: ffmpeg exited with code 1",
    "",
])
def test_no_diagnosis_rather_than_a_wrong_one(message):
    """Guessing wrong is worse than saying nothing: it sends people to a
    setting that will not help."""
    assert engine.diagnose(message) is None


def test_cookies_setting_reaches_yt_dlp(tmp_path):
    from molo import config

    settings = config.Settings()
    settings.download_dir = str(tmp_path)

    settings.cookies_from_browser = "none"
    assert "cookiesfrombrowser" not in engine.base_opts(settings, engine.PRESETS["720p"], tmp_path)

    settings.cookies_from_browser = "safari"
    assert engine.base_opts(settings, engine.PRESETS["720p"], tmp_path)["cookiesfrombrowser"] == ("safari",)


def test_every_preset_has_a_translation_key():
    """The interface looks up `preset.<key>`; a new preset without one shows
    the English label inside an otherwise translated window."""
    from pathlib import Path

    strings = (Path(engine.__file__).parent / "web" / "i18n.js").read_text("utf-8")
    for key in engine.PRESETS:
        assert f'"preset.{key}"' in strings, f"no translation key for preset {key}"
        assert f'"preset.{key}.hint"' in strings, f"no hint key for preset {key}"


def test_ffmpeg_lookup_does_not_depend_on_path(monkeypatch):
    """An app launched from Finder gets the bare launchd environment, where
    /opt/homebrew/bin does not exist. shutil.which alone reported a perfectly
    installed ffmpeg as missing."""
    monkeypatch.setattr(engine.shutil, "which", lambda _: None)
    monkeypatch.setattr(engine, "_ffmpeg_checked", False)
    monkeypatch.setattr(engine, "_ffmpeg_path", None)

    found = engine.find_ffmpeg(refresh=True)
    if found is None:
        pytest.skip("no ffmpeg installed in any of the usual places")
    assert found.endswith("ffmpeg") or found.endswith("ffmpeg.exe")
