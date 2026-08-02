"""Confini di ciò che Molo accetta di scaricare.

Questo modulo è la ragione per cui Molo può stare su GitHub senza dover
sperare nella clemenza di nessuno. Non è un disclaimer: è un controllo che
gira prima di ogni download e che fa fallire il job.

La linea che tracciamo è una sola, e non è "copyright sì / copyright no" --
quella distinzione un software non può farla, perché dipende da chi sei tu e
da che accordi hai con la fonte. La linea è la **misura tecnologica di
protezione**:

  - Scaricare un flusso servito in chiaro replica ciò che il browser fa già
    da solo. Può violare i termini di servizio di un sito (questione
    contrattuale, fra te e il sito) ma non aggira nessuna protezione.

  - Scaricare un flusso cifrato con DRM (Widevine, PlayReady, FairPlay)
    richiede di rompere quella cifratura. È l'atto che il DMCA §1201 negli
    Stati Uniti e l'art. 6 della direttiva 2001/29/CE in Europa colpiscono
    di per sé, a prescindere da cosa poi fai del file.

Molo rifiuta categoricamente la seconda categoria, e non contiene nessun
codice di decifratura. È la stessa posizione che ha tenuto in piedi
youtube-dl quando la RIAA ne chiese la rimozione da GitHub nel 2020: la
EFF rispose che lo strumento non aggira alcuna protezione e ha usi legittimi
sostanziali, e il repository fu ripristinato.

Nota onesta: nessuno di questi controlli è una consulenza legale, e nessuno
ti mette al riparo dall'uso che fai dei file. Servono a dire una cosa sola,
in modo verificabile leggendo il codice: questo strumento non è progettato
per aggirare protezioni.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Blocco statico: servizi il cui catalogo è interamente sotto DRM.
#
# Non li blocchiamo perché "hanno contenuti protetti da copyright" -- ce
# l'hanno anche YouTube. Li blocchiamo perché per arrivare al flusso video
# bisogna per forza passare da una decifratura, quindi qualunque tentativo
# ricadrebbe nell'aggiramento. Meglio fermarsi all'ingresso con un messaggio
# chiaro che far fallire yt-dlp trenta secondi dopo con un errore oscuro.
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


class PolicyError(Exception):
    """Il download è stato rifiutato da Molo, non da yt-dlp."""

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
    """Primo cancello: prima ancora di interrogare la rete.

    Confronta l'host con l'elenco dei servizi interamente sotto DRM. Il
    confronto è sul suffisso di dominio, così `qualcosa.netflix.com` non
    scappa dal controllo.
    """
    if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
        return Verdict(False, "Serve un indirizzo http:// o https://.", "")

    host = _host(url)
    if not host:
        return Verdict(False, "Indirizzo non leggibile.", "")

    for blocked, name in DRM_HOSTS.items():
        if host == blocked or host.endswith("." + blocked):
            return Verdict(
                False,
                f"{name} distribuisce i suoi contenuti cifrati con DRM. "
                f"Scaricarli richiederebbe di aggirare quella cifratura, che è "
                f"illecito di per sé nell'UE (art. 6 dir. 2001/29/CE) e negli "
                f"USA (DMCA §1201). Molo non lo fa e non contiene il codice "
                f"per farlo.",
                name,
            )

    return Verdict(True)


def check_info(info: dict) -> Verdict:
    """Secondo cancello: dopo che yt-dlp ha ispezionato la pagina.

    Il blocco per host non può essere esaustivo -- esistono migliaia di siti e
    ogni tanto anche una piattaforma aperta serve un singolo contenuto sotto
    DRM. yt-dlp lo segnala: marca i formati protetti con `has_drm` e chiama
    `report_drm()` sugli estrattori. Qui leggiamo quel segnale e ci fermiamo,
    così la protezione vale anche per i siti che non abbiamo mai visto.
    """
    if info.get("_has_drm") or info.get("has_drm"):
        return Verdict(False, _DRM_MSG, info.get("extractor_key", ""))

    formats = info.get("formats") or []
    if formats and all(f.get("has_drm") for f in formats):
        return Verdict(False, _DRM_MSG, info.get("extractor_key", ""))

    return Verdict(True)


def usable_formats(formats: list[dict]) -> list[dict]:
    """Toglie dalla scelta i singoli formati protetti.

    Caso reale: una piattaforma serve il trailer in chiaro e il film sotto
    DRM nella stessa pagina. Il trailer resta scaricabile, il film sparisce
    dall'elenco invece di comparire e fallire.
    """
    return [f for f in formats if not f.get("has_drm")]


_DRM_MSG = (
    "Questo contenuto è protetto da DRM. Molo si ferma qui per scelta: "
    "aggirare una misura tecnologica di protezione è illecito a prescindere "
    "dall'uso che se ne fa, e nel codice non esiste nulla per farlo."
)
