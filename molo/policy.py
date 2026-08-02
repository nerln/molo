"""What Molo will and will not try to download.

This module is the reason the project can sit in public without hoping nobody
looks closely. It is not a disclaimer, it runs before every download and
fails the job.

A program cannot know whether you have the right to download a given file.
That depends on who you are, what you agreed to, and where you live. No
automated check decides that for you.

There is one distinction a program *can* enforce, and everything here rests on
it: the difference between reading a stream served in the clear and breaking
encryption.

  Served in the clear
      Your browser already downloads it, that is how it plays the video.
      Saving it to disk instead of to a cache circumvents nothing. It may
      breach a site's terms of service, which is a contract matter between you
      and that site.

  Encrypted with DRM (Widevine, PlayReady, FairPlay)
      Reaching the video means breaking that encryption. That act is unlawful
      in itself under Article 6 of EU Directive 2001/29/EC and under DMCA
      §1201 in the United States, regardless of what you then do with the
      file, and regardless of whether you pay for the service.

Molo contains no code to circumvent anything: no CDM, no keys, no decryption
routine, and none will be accepted. That is the load-bearing fact, and it is
verifiable by reading the repository rather than by trusting this paragraph.

This is the same ground on which youtube-dl survived the RIAA's 2020 takedown
request: the EFF argued the tool circumvents no technological protection
measure and has substantial non-infringing uses, and GitHub restored the
repository.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Services whose catalogue is entirely behind DRM.
#
# Not blocked for being copyrighted, so is most of YouTube. Blocked because
# reaching their video streams requires decryption, so any attempt would be
# circumvention. Stopping at the door with a clear message beats letting
# yt-dlp fail thirty seconds later with something cryptic.
# ---------------------------------------------------------------------------
DRM_HOSTS: dict[str, str] = {
    "netflix.com": "Netflix",
    "disneyplus.com": "Disney+",
    "primevideo.com": "Prime Video",
    "hulu.com": "Hulu",
    "max.com": "Max",
    "hbomax.com": "HBO Max",
    "tv.apple.com": "Apple TV+",
    "peacocktv.com": "Peacock",
    "paramountplus.com": "Paramount+",
    "crunchyroll.com": "Crunchyroll",
    "dazn.com": "DAZN",
    "nowtv.it": "NOW",
    "skyshowtime.com": "SkyShowtime",
    "infinity.it": "Infinity+",
    "mediasetinfinity.mediaset.it": "Mediaset Infinity",
    "open.spotify.com": "Spotify",
    "spotify.com": "Spotify",
    "music.apple.com": "Apple Music",
    "tidal.com": "Tidal",
    "deezer.com": "Deezer",
    "audible.com": "Audible",
    "audible.it": "Audible",
    "udemy.com": "Udemy",
    "coursera.org": "Coursera",
}

# ---------------------------------------------------------------------------
# The host pre-check can be turned off. The DRM metadata check cannot.
#
# These two are not the same kind of thing, and collapsing them into one
# switch was a mistake in an earlier version.
#
#   The host list is a heuristic, a list of domains in a text file. It is
#   right most of the time and wrong at the edges: a paid Udemy lesson, your
#   own upload, a public clip on a platform that uses DRM elsewhere. People
#   with legitimate access to unencrypted content on those domains need a way
#   past it, and there is no honest argument for making them patch the source.
#
#   The `has_drm` check is not a heuristic. It is yt-dlp reporting that the
#   stream is encrypted. There is nothing behind that door to let anyone
#   through to: without a decryption module the bytes are noise. Leaving it
#   permanently on costs no legitimate user anything.
#
# So: no switch in the interface, no field in settings.json. An environment
# variable, documented plainly in LEGAL.md rather than advertised as a
# feature. A checkbox labelled "turn off the DRM policy" is a liability no
# matter what it actually does, it reads as an invitation, and inducement is
# what sank Grokster. An environment variable read by someone who found it in
# the legal documentation is not marketing.
# ---------------------------------------------------------------------------
_SKIP_HOST_PRECHECK = os.environ.get("MOLO_DISABLE_HOST_PRECHECK", "").strip() in {"1", "true", "yes"}


def host_precheck_enabled() -> bool:
    return not _SKIP_HOST_PRECHECK


class PolicyError(Exception):
    """The download was refused by Molo, not by yt-dlp."""

    def __init__(self, message: str, *, reason: str = "drm") -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    message: str = ""
    service: str = ""


def _host(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def check_url(url: str) -> Verdict:
    """First gate, before touching the network."""
    if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
        return Verdict(False, "That needs to be an http:// or https:// address.")

    host = _host(url)
    if not host:
        return Verdict(False, "I can't read that address.")

    if _SKIP_HOST_PRECHECK:
        return Verdict(True)

    for blocked, name in DRM_HOSTS.items():
        # Suffix match, so something.netflix.com does not slip past.
        if host == blocked or host.endswith("." + blocked):
            return Verdict(
                False,
                f"{name} encrypts everything it serves. Reaching those streams "
                f"would mean breaking that encryption, which is unlawful in "
                f"itself under EU Directive 2001/29/EC Article 6 and DMCA "
                f"§1201. Molo has no code that does it.",
                name,
            )

    return Verdict(True)


def check_info(info: dict) -> Verdict:
    """Second gate, after yt-dlp has looked at the page.

    Always on. yt-dlp marks protected formats with `has_drm` and calls
    `report_drm()` in its extractors; we read that signal and stop. This is
    what covers the thousands of sites no host list will ever enumerate.
    """
    if info.get("_has_drm") or info.get("has_drm"):
        return Verdict(False, DRM_MESSAGE, info.get("extractor_key", ""))

    formats = info.get("formats") or []
    if formats and all(f.get("has_drm") for f in formats):
        return Verdict(False, DRM_MESSAGE, info.get("extractor_key", ""))

    return Verdict(True)


def usable_formats(formats: list[dict]) -> list[dict]:
    """Drop individual protected formats from the choice.

    Real case: a platform serves the trailer in the clear and the film under
    DRM on the same page. The trailer stays downloadable; the film disappears
    from the list instead of appearing and then failing.
    """
    return [f for f in formats if not f.get("has_drm")]


DRM_MESSAGE = (
    "This content is encrypted with DRM. Molo stops here by design: getting "
    "past a technological protection measure is unlawful in itself, and there "
    "is no code in this program that does it."
)
