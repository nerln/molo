"""Il motore: ispezione, scelta del formato, download con recupero automatico.

Usa yt-dlp come libreria, non come sottoprocesso. Costa un po' di attenzione in
più nella gestione delle eccezioni, ma in cambio il progresso arriva dagli hook
nativi invece che dal parsing di righe di testo, e non c'è un binario da
impacchettare per ogni piattaforma.
"""

from __future__ import annotations

import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yt_dlp

from . import policy


class Cancelled(Exception):
    """Sollevata dentro un hook per fermare yt-dlp a metà download."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


# ---------------------------------------------------------------------------
# Preset
#
# `format_sort` conta più di `format`: è l'ordinamento con cui yt-dlp decide
# cosa sia "meglio" a parità di selettore. Senza, su alcuni video si porta a
# casa un VP9 a bitrate più basso convinto di aver scelto il massimo.
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
        label="Massima qualità",
        hint="Il meglio che si apre ovunque senza riconvertire: H.264 + AAC in MP4.",
        fmt="bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b",
        sort=["res", "fps", "vcodec:h264", "br"],
        container="mp4",
    ),
    "best_absolute": Preset(
        key="best_absolute",
        label="Massima qualità assoluta",
        hint="Il bitrate più alto in assoluto, anche AV1 o VP9. File in MKV, non tutti i player lo digeriscono.",
        fmt="bv*+ba/b",
        sort=["res", "fps", "hdr:12", "br"],
        container="mkv",
    ),
    "1080p": Preset(
        key="1080p",
        label="1080p",
        hint="Tetto a Full HD quando il 4K non serve e pesa dieci volte tanto.",
        fmt="bv*[height<=1080]+ba/b[height<=1080]",
        sort=["res:1080", "fps", "vcodec:h264", "br"],
        container="mp4",
    ),
    "720p": Preset(
        key="720p",
        label="720p",
        hint="Leggero, per guardare e basta.",
        fmt="bv*[height<=720]+ba/b[height<=720]",
        sort=["res:720", "fps", "vcodec:h264", "br"],
        container="mp4",
    ),
    "audio_best": Preset(
        key="audio_best",
        label="Solo audio (originale)",
        hint="La traccia audio migliore così com'è, senza riconversione: nessuna perdita aggiunta.",
        fmt="ba/b",
        sort=["abr", "asr"],
        audio_only=True,
    ),
    "audio_mp3": Preset(
        key="audio_mp3",
        label="Solo audio (MP3 320)",
        hint="Riconvertito in MP3 per lettori vecchi. Ricodifica, quindi perde qualcosa.",
        fmt="ba/b",
        sort=["abr", "asr"],
        audio_only=True,
        to_mp3=True,
    ),
}

# Rotazione dei client YouTube per il recupero dopo un 403.
#
# Un 403 a metà download quasi mai significa "non puoi": significa che l'URL
# firmato è scaduto o che quel client è stato limitato. Cambiare client e
# riprovare risolve la stragrande maggioranza dei casi, e il file parziale
# resta su disco perché `continuedl` riprende da dove si era fermato.
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
        "windowsfilenames": True,  # nomi validi anche se la cartella finisce su una chiavetta
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

    if not ffmpeg_available():
        # Senza ffmpeg non si possono unire flussi separati: ripieghiamo sui
        # formati già completi, che di norma si fermano a 720p.
        opts["format"] = "b/bv*+ba"
        return opts

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
        opts["postprocessors"].append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    if settings.embed_subs and not preset.audio_only:
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = [s.strip() for s in settings.sub_langs.split(",") if s.strip()]
        opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

    return opts


def probe(url: str) -> dict:
    """Ispeziona senza scaricare. Solleva PolicyError se il contenuto è sotto DRM."""
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
    """Riduce l'info dict di yt-dlp a quel poco che serve all'interfaccia."""
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
    """Scarica con recupero automatico. Bloccante: va chiamata in un thread.

    Restituisce un dict con il percorso finale. Solleva l'ultima eccezione se
    tutti i tentativi falliscono.
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
            # Attesa interrompibile: se l'utente annulla non deve aspettare 15s.
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
                result["filepath"] = d.get("info_dict", {}).get("filepath") or d.get("filename")
            on_progress(d)

        opts["progress_hooks"] = [hook]
        opts["postprocessor_hooks"] = [lambda d: on_progress({**d, "status": "postprocessing"})]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

                pol = policy.check_info(ydl.sanitize_info(info))
                if not pol.allowed:
                    raise policy.PolicyError(pol.message)

                info = ydl.process_ie_result(info, download=True)
                info = ydl.sanitize_info(info)

            path = result.get("filepath") or info.get("requested_downloads", [{}])[0].get("filepath")
            return {
                "filepath": path,
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
            if "has already been recorded in the archive" in message:
                return {"filepath": None, "skipped": True, "title": url}
            # Solo gli errori che il cambio di client può curare meritano un altro giro.
            if not _worth_retrying(message):
                raise
            on_progress({"status": "recovering", "error": _short(message)})
        except Exception as exc:  # rete che cade, disco pieno, ...
            last_error = exc
            on_progress({"status": "recovering", "error": _short(str(exc))})

    raise last_error or RuntimeError("Download fallito senza un errore riportato")


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


def update_ytdlp() -> tuple[bool, str]:
    """Aggiorna yt-dlp con pip nell'ambiente corrente.

    Sta qui e non in un modulo a parte perché è l'unica manutenzione che Molo
    fa da solo, ed è quella che evita il 90% dei fallimenti: yt-dlp vecchio di
    qualche mese smette semplicemente di funzionare su YouTube.
    """
    import subprocess
    import sys

    before = current_version()

    # Dentro un bundle PyInstaller non c'è pip e `sys.executable` è l'app
    # stessa: un `pip install` qui fallirebbe in modo oscuro. Meglio dirlo.
    # Il rimedio vero (yt-dlp come binario esterno sostituibile a caldo) è
    # segnato fra i limiti noti nel README.
    if getattr(sys, "frozen", False):
        return (
            False,
            f"yt-dlp {before} arriva con l'app: in questa versione impacchettata "
            f"si aggiorna insieme a Molo. Se ti serve subito l'ultima, usa "
            f"l'installazione da sorgente.",
        )

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"Aggiornamento non riuscito: {exc}"

    if proc.returncode != 0:
        return False, _short(proc.stderr or "pip ha restituito un errore")

    try:
        out = subprocess.run(
            [sys.executable, "-c", "import yt_dlp,sys; sys.stdout.write(yt_dlp.version.__version__)"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        after = out.stdout.strip() or before
    except (subprocess.SubprocessError, OSError):
        after = before

    if after != before:
        return True, f"yt-dlp aggiornato: {before} → {after}. Riavvia Molo per usarlo."
    return True, f"yt-dlp è già aggiornato ({before})."


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
