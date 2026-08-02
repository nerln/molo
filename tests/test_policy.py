"""Test della guardia legale.

Sono i test più importanti del progetto: se questi passano di nascosto da
rotti, Molo smette di essere quello che dichiara di essere.
"""

import pytest

from molo import policy


@pytest.fixture(autouse=True)
def rigorosa():
    """Ogni test parte dalla modalità rigorosa, com'è distribuito il progetto."""
    policy.set_strict(True)
    yield
    policy.set_strict(True)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.netflix.com/watch/80100172",
        "https://netflix.com/title/1",
        "https://qualcosa.netflix.com/watch/2",   # anche i sottodomini
        "https://open.spotify.com/track/abc",
        "https://www.disneyplus.com/video/x",
        "https://tv.apple.com/it/movie/y",
        "https://www.audible.it/pd/z",
    ],
)
def test_servizi_drm_respinti(url):
    verdict = policy.check_url(url)
    assert not verdict.allowed
    assert "DRM" in verdict.message


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/bk6Xst6euQk",
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://vimeo.com/123456",
        "https://archive.org/details/qualcosa",
    ],
)
def test_sorgenti_in_chiaro_passano(url):
    assert policy.check_url(url).allowed


@pytest.mark.parametrize("url", ["ftp://host/f.mp4", "file:///etc/passwd", "non un url", ""])
def test_schemi_non_http_respinti(url):
    assert not policy.check_url(url).allowed


def test_dominio_che_contiene_il_nome_non_viene_bloccato():
    """`netflix.com.esempio.it` non è Netflix: il confronto è sul suffisso."""
    assert policy.check_url("https://netflix.com.esempio.it/video").allowed


def test_flag_drm_nei_metadati():
    assert not policy.check_info({"_has_drm": True}).allowed
    assert not policy.check_info({"formats": [{"has_drm": True}, {"has_drm": True}]}).allowed


def test_contenuto_misto_resta_scaricabile():
    """Trailer in chiaro accanto al film protetto: il trailer si può prendere."""
    info = {"formats": [{"format_id": "trailer"}, {"format_id": "film", "has_drm": True}]}
    assert policy.check_info(info).allowed
    usable = policy.usable_formats(info["formats"])
    assert [f["format_id"] for f in usable] == ["trailer"]


def test_elenco_drm_non_svuotato_per_sbaglio():
    """Se un refactor svuota l'elenco, il default cambia senza che nessuno lo noti."""
    assert len(policy.DRM_HOSTS) >= 15
    assert "netflix.com" in policy.DRM_HOSTS


# --- modalità permissiva -----------------------------------------------------

def test_default_e_rigoroso():
    """Il comportamento distribuito. Se qualcuno inverte il default, questo test cade."""
    import importlib

    fresh = importlib.reload(policy)
    assert fresh.is_strict() is True
    fresh.set_strict(True)


def test_permissiva_lascia_passare_il_pre_controllo():
    policy.set_strict(False)
    assert policy.check_url("https://www.netflix.com/watch/1").allowed
    assert policy.check_info({"_has_drm": True}).allowed


def test_permissiva_non_tocca_la_validazione_dello_schema():
    """Spegnere la policy non trasforma stringhe qualsiasi in URL scaricabili."""
    policy.set_strict(False)
    assert not policy.check_url("file:///etc/passwd").allowed
    assert not policy.check_url("non un url").allowed


def test_nessun_codice_di_decifratura_nel_pacchetto():
    """La difesa vera del progetto, verificata invece che dichiarata.

    Se un contributo introducesse un modulo CDM o una routine di decifratura,
    questo test lo intercetta prima che finisca in un rilascio.
    """
    import pathlib

    vietati = ("widevine", "playready", "fairplay", "pssh", "cdm_", "decrypt_key")
    sorgenti = pathlib.Path(policy.__file__).parent.rglob("*.py")
    for path in sorgenti:
        testo = path.read_text("utf-8").lower()
        for parola in vietati:
            # policy.py li nomina per spiegare cosa NON fa: è l'unica eccezione.
            if parola in testo and path.name != "policy.py":
                raise AssertionError(f"{path.name} contiene «{parola}»")
