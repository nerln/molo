"""Test della guardia legale.

Sono i test più importanti del progetto: se questi passano di nascosto da
rotti, Molo smette di essere quello che dichiara di essere.
"""

import pytest

from molo import policy


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
    """Se un refactor svuota l'elenco, il progetto perde la sua difesa in silenzio."""
    assert len(policy.DRM_HOSTS) >= 15
    assert "netflix.com" in policy.DRM_HOSTS
