"""The engine: inspection, format choice, downloading with recovery.

yt-dlp is used as a library, not as a subprocess. That costs a little care
around exception handling, and in exchange progress arrives through native
hooks instead of by parsing lines of text, and there is no binary to package
for each platform.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yt_dlp

from . import policy, upgrade


class Cancelled(Exception):
    """Raised inside a hook to stop yt-dlp mid-download."""


# ---------------------------------------------------------------------------
# Finding ffmpeg
#
# `shutil.which` alone is not enough, and the reason is a macOS detail that
# costs everyone the same afternoon: an app launched from Finder does not
# inherit the shell's PATH. It gets the bare launchd environment, where
# /opt/homebrew/bin does not exist. So ffmpeg is installed, works fine in the
# terminal, and the app swears it is missing.
#
# We look in PATH first, then in the handful of places package managers
# actually install to. The result is cached: this runs on every settings read.
# ---------------------------------------------------------------------------
_LIKELY_DIRS = (
    "/opt/homebrew/bin",           # Homebrew, Apple silicon
    "/usr/local/bin",              # Homebrew on Intel, and most manual installs
    "/opt/local/bin",              # MacPorts
    "/snap/bin",
    "/usr/bin",
    str(Path.home() / ".local" / "bin"),
    r"C:\Program Files\ffmpeg\bin",
    r"C:\ffmpeg\bin",
    str(Path.home() / "scoop" / "shims"),
)

_ffmpeg_path: str | None = None
_ffmpeg_checked = False


def find_ffmpeg(refresh: bool = False) -> str | None:
    """Absolute path to ffmpeg, or None. Cached after the first successful look."""
    global _ffmpeg_path, _ffmpeg_checked

    if _ffmpeg_checked and not refresh and _ffmpeg_path:
        return _ffmpeg_path

    found = shutil.which("ffmpeg")
    if not found:
        name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        for directory in _LIKELY_DIRS:
            candidate = Path(directory) / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                found = str(candidate)
                break

    _ffmpeg_path, _ffmpeg_checked = found, True
    return found


def ffmpeg_available() -> bool:
    return find_ffmpeg() is not None


# ---------------------------------------------------------------------------
# Presets
#
# `format_sort` matters more than `format`: it is how yt-dlp breaks ties within
# a selector. Without it, some videos come home as a lower-bitrate VP9 while
# yt-dlp is convinced it picked the best one available.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    hint: str
    fmt: str
    sort: list[str]
    container: str | None = None
    audio_only: bool = False
    to_mp3: bool = False


PRESETS: dict[str, Preset] = {
    "best_compat": Preset(
        key="best_compat",
        label="Best quality",
        hint="The best that plays anywhere without re-encoding: H.264 + AAC in MP4.",
        fmt="bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b",
        sort=["res", "fps", "vcodec:h264", "br"],
        container="mp4",
    ),
    "best_absolute": Preset(
        key="best_absolute",
        label="Absolute best",
        hint="The highest bitrate there is, AV1 or VP9 included. Lands in MKV, which not every player takes.",
        fmt="bv*+ba/b",
        sort=["res", "fps", "hdr:12", "br"],
        container="mkv",
    ),
    "1080p": Preset(
        key="1080p",
        label="1080p",
        hint="Capped at Full HD, for when 4K is not worth ten times the size.",
        fmt="bv*[height<=1080]+ba/b[height<=1080]",
        sort=["res:1080", "fps", "vcodec:h264", "br"],
        container="mp4",
    ),
    "720p": Preset(
        key="720p",
        label="720p",
        hint="Light. For watching and nothing else.",
        fmt="bv*[height<=720]+ba/b[height<=720]",
        sort=["res:720", "fps", "vcodec:h264", "br"],
        container="mp4",
    ),
    "audio_best": Preset(
        key="audio_best",
        label="Audio only (as served)",
        hint="The best audio track exactly as served, no re-encoding, no added loss.",
        fmt="ba/b",
        sort=["abr", "asr"],
        audio_only=True,
    ),
    "audio_mp3": Preset(
        key="audio_mp3",
        label="Audio only (MP3 320)",
        hint="Re-encoded to MP3 for older players. That is a re-encode, so it loses a little.",
        fmt="ba/b",
        sort=["abr", "asr"],
        audio_only=True,
        to_mp3=True,
    ),
}

# YouTube client rotation, for recovering from a 403.
#
# A 403 halfway through a download almost never means "you may not". It means
# the signed URL expired, or that client got throttled. Switching client and
# retrying fixes the vast majority of them, and the partial file stays on disk
# because `continuedl` picks up where it stopped.
CLIENT_ROTATION: list[list[str] | None] = [
    None,
    ["tv", "ios"],
    ["web_safari", "android_vr"],
    ["ios"],
]

BACKOFF_SECONDS = [0, 3, 8, 15]


def base_opts(settings, preset: Preset, dest: Path) -> dict:
    opts: dict = {
        "format": preset.fmt,
        "format_sort": list(preset.sort),
        "paths": {"home": str(dest)},
        "outtmpl": {"default": "%(title).200B [%(id)s].%(ext)s"},
        "windowsfilenames": True,  # valid names even if the folder ends up on a USB stick
        "continuedl": True,
        "retries": 20,
        "fragment_retries": 20,
        "concurrent_fragment_downloads": 4,
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreerrors": False,
        "postprocessors": [],
    }

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        # Without ffmpeg we cannot merge separate streams, so fall back to
        # formats that already carry both. That usually tops out at 720p.
        opts["format"] = "b/bv*+ba"
        return opts

    # Hand yt-dlp the absolute path rather than trusting it to search PATH.
    # Same reason we look for it ourselves: a bundled app started from Finder
    # has a PATH that does not include Homebrew.
    opts["ffmpeg_location"] = str(Path(ffmpeg).parent)

    if preset.container and not preset.audio_only:
        opts["merge_output_format"] = preset.container

    if preset.to_mp3:
        opts["postprocessors"].append(
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}
        )

    if settings.embed_metadata:
        opts["postprocessors"].append(
            {"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True}
        )
    if settings.embed_thumbnail:
        opts["writethumbnail"] = True
        # YouTube serves WebP thumbnails, which ffmpeg cannot write into an
        # m4a or mp3 container: the whole job dies at the last step with
        # "Unable to embed using ffprobe & ffmpeg" after the download already
        # succeeded. Converting to JPEG first is yt-dlp's own remedy, and it
        # has to be queued ahead of the embed step.
        opts["postprocessors"].append(
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"}
        )
        opts["postprocessors"].append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    if settings.embed_subs and not preset.audio_only:
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = [s.strip() for s in settings.sub_langs.split(",") if s.strip()]
        opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

    return opts


def probe(url: str) -> dict:
    """Inspect without downloading. Raises PolicyError if the content is DRM protected."""
    verdict = policy.check_url(url)
    if not verdict.allowed:
        raise policy.PolicyError(verdict.message)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False))

    verdict = policy.check_info(info)
    if not verdict.allowed:
        raise policy.PolicyError(verdict.message)

    return info


def summarize(info: dict) -> dict:
    """Cut yt-dlp's info dict down to the little the interface needs."""
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        return {
            "kind": "playlist",
            "title": info.get("title") or "Playlist",
            "uploader": info.get("uploader") or info.get("channel") or "",
            "count": len(entries),
            "thumbnail": _thumb(info) or (_thumb(entries[0]) if entries else None),
            "entries": [
                {
                    "title": e.get("title") or "senza titolo",
                    "url": e.get("url") or e.get("webpage_url"),
                    "duration": e.get("duration"),
                }
                for e in entries[:200]
            ],
        }

    formats = policy.usable_formats(info.get("formats") or [])
    heights = sorted({f["height"] for f in formats if f.get("height")}, reverse=True)
    return {
        "kind": "video",
        "title": info.get("title") or "senza titolo",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": info.get("duration"),
        "thumbnail": _thumb(info),
        "webpage_url": info.get("webpage_url"),
        "extractor": info.get("extractor_key"),
        "max_height": heights[0] if heights else None,
        "heights": heights[:8],
    }


def _thumb(info: dict) -> str | None:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbs = info.get("thumbnails") or []
    return thumbs[-1].get("url") if thumbs else None


def download(
    url: str,
    settings,
    preset: Preset,
    on_progress: Callable[[dict], None],
    cancel: threading.Event,
    archive: Path | None = None,
) -> dict:
    """Download with automatic recovery. Blocking: call it on a thread.

    Returns a dict with the final path. Re-raises the last exception if every
    attempt fails.
    """
    verdict = policy.check_url(url)
    if not verdict.allowed:
        raise policy.PolicyError(verdict.message)

    dest = Path(settings.download_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)

    result: dict = {}
    last_error: Exception | None = None

    for attempt, clients in enumerate(CLIENT_ROTATION):
        if cancel.is_set():
            raise Cancelled()

        delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
        if delay:
            on_progress({"status": "retrying", "attempt": attempt + 1, "wait": delay})
            # Interruptible wait: cancelling should not make you sit out 15s.
            if cancel.wait(delay):
                raise Cancelled()

        opts = base_opts(settings, preset, dest)
        if archive is not None:
            opts["download_archive"] = str(archive)
        if clients:
            opts["extractor_args"] = {"youtube": {"player_client": clients}}

        def hook(d: dict) -> None:
            if cancel.is_set():
                raise Cancelled()
            if d.get("status") == "finished":
                # Only a hint. This hook fires once per stream, so on a merged
                # download the last one to finish is a temporary fragment that
                # ffmpeg is about to consume. The real path is read after
                # processing, below; this is the fallback for the odd extractor
                # that leaves requested_downloads empty.
                info_dict = d.get("info_dict") or {}
                result["hint"] = info_dict.get("filepath") or d.get("filename")
            on_progress(d)

        opts["progress_hooks"] = [hook]
        opts["postprocessor_hooks"] = [lambda d: on_progress({**d, "status": "postprocessing"})]

        probed: dict = {}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # yt-dlp signals "already in the download archive" by handing
                # back None, not by raising. Passing that straight on gives
                # `'NoneType' object has no attribute 'get'` four attempts in a
                # row and then a failed job for something already on disk.
                if info is None:
                    if archive is not None:
                        return {"filepath": None, "skipped": True, "title": url}
                    raise RuntimeError("The extractor returned nothing for this address")

                probed = ydl.sanitize_info(info) or {}
                pol = policy.check_info(probed)
                if not pol.allowed:
                    raise policy.PolicyError(pol.message)

                # Ask yt-dlp's own archive rather than inferring a skip from
                # an error message. Left to itself it does not raise here: it
                # logs, skips, and returns normally, so the old code reported
                # a re-run as a fresh download.
                if archive is not None and ydl.in_download_archive(probed):
                    return {
                        "filepath": _final_path(probed, None, dest),
                        "skipped": True,
                        "title": probed.get("title"),
                        "id": probed.get("id"),
                        "attempts": attempt + 1,
                    }

                info = ydl.process_ie_result(info, download=True)
                info = ydl.sanitize_info(info) or {}

            return {
                "filepath": _final_path(info, result.get("hint"), dest),
                "title": info.get("title"),
                "id": info.get("id"),
                "attempts": attempt + 1,
                "client": clients or "default",
            }

        except (Cancelled, policy.PolicyError):
            raise
        except yt_dlp.utils.DownloadError as exc:
            last_error = exc
            message = str(exc)

            # Cover art that refuses to attach is not a reason to throw away a
            # download. Some m4a files reject an embedded picture through
            # ffmpeg, and yt-dlp treats that as fatal, so a finished two
            # gigabyte file would be reported as a failure. If the media is on
            # disk, keep it and say the artwork did not make it.
            if _is_cosmetic_failure(message):
                salvaged = _final_path(probed, result.get("hint"), dest)
                if salvaged:
                    return {
                        "filepath": salvaged,
                        "title": probed.get("title"),
                        "id": probed.get("id"),
                        "attempts": attempt + 1,
                        "client": clients or "default",
                        "cosmetic_error": _short(message, 120),
                    }

            if "has already been recorded in the archive" in message:
                return {"filepath": None, "skipped": True, "title": url}
            # Only errors a different client might cure deserve another round.
            if not _worth_retrying(message):
                raise
            on_progress({"status": "recovering", "error": _short(message)})
        except Exception as exc:  # network drops, disk full, ...
            last_error = exc
            on_progress({"status": "recovering", "error": _short(str(exc))})

    raise last_error or RuntimeError("Download failed without reporting an error")


_COSMETIC = (
    "unable to embed",
    "error while embedding",
    "could not write metadata",
    "thumbnail",
)


def _is_cosmetic_failure(message: str) -> bool:
    """Did only the decoration fail, leaving usable media behind?

    Both conditions have to hold: it happened during postprocessing, and it
    was about artwork or metadata. A postprocessing failure in the merge step
    is not cosmetic, and there would be no complete file to keep.
    """
    low = message.lower()
    if "postprocessing" not in low:
        return False
    return any(token in low for token in _COSMETIC)


def _final_path(info: dict, hint: str | None, dest: Path) -> str | None:
    """Where the file actually ended up.

    Getting this wrong is how "Show file" came to open nothing. Three sources,
    in decreasing order of trust:

    1. `requested_downloads[0].filepath`. yt-dlp rewrites this after merging
       streams and after every postprocessor, so it is the only entry that
       knows an `.m4a` became an `.mp3` or that two fragments became one mp4.
    2. The last progress hook, which is right for single-file downloads and
       wrong for merged ones.
    3. A scan of the destination for the video id, which every output template
       here embeds in the name. Last resort, but better than handing the
       interface a path that was deleted thirty seconds ago.

    Returns None rather than a path that does not exist. A missing file is
    worth saying out loud; a broken button is not.
    """
    candidates: list[str] = []

    for entry in info.get("requested_downloads") or []:
        if isinstance(entry, dict) and entry.get("filepath"):
            candidates.append(entry["filepath"])
    if info.get("filepath"):
        candidates.append(info["filepath"])
    if hint:
        candidates.append(hint)

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())

    video_id = info.get("id")
    if video_id:
        matches = [p for p in dest.glob(f"*[[]{video_id}[]]*") if p.is_file() and not p.name.endswith(".part")]
        if matches:
            # Newest wins: an interrupted attempt can leave older debris.
            return str(max(matches, key=lambda p: p.stat().st_mtime).resolve())

    return None


_RETRYABLE = (
    "http error 403",
    "http error 429",
    "unable to download video data",
    "fragment",
    "read timed out",
    "connection reset",
    "temporary failure",
    "unable to download webpage",
    "sign in to confirm",
    "precondition check failed",
)


def _worth_retrying(message: str) -> bool:
    low = message.lower()
    return any(token in low for token in _RETRYABLE)


def _short(message: str, limit: int = 160) -> str:
    line = message.replace("\n", " ").strip()
    line = line.removeprefix("ERROR: ")
    return line if len(line) <= limit else line[: limit - 1] + "…"


def current_version() -> str:
    return yt_dlp.version.__version__


def update_ytdlp() -> upgrade.Result:
    """Fetch a newer yt-dlp into Molo's own data folder.

    One path for every install, packaged or from source. It used to be pip, and
    pip cannot work inside a PyInstaller bundle: there is no pip in there and
    `sys.executable` is the app itself. `upgrade.py` explains why the wheel is
    the way through, and what the sha256 check does and does not promise.

    Running from source this deliberately leaves site-packages alone. Molo
    updating its own engine should not reach into an environment somebody else
    is managing, and a folder you can delete is easier to reason about than a
    package you have to notice.
    """
    return upgrade.install(current_version())


__all__ = [
    "PRESETS",
    "Preset",
    "Cancelled",
    "probe",
    "summarize",
    "download",
    "ffmpeg_available",
    "current_version",
    "update_ytdlp",
]
