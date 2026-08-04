"""Regressions for the access boundary.

Written after an adversarial review proved that binding to 127.0.0.1 is not by
itself a defence: any web page can point a hostname it controls at loopback,
and the browser will send the request here with that name in the Host header.
Before these checks, `curl -H 'Host: evil.attacker.com' /api/pairing` handed
out the per-install token.
"""

import pytest

from molo import config, server


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    """LAN access off, which is how Molo ships."""
    monkeypatch.setattr(server.settings, "allow_lan", False)


@pytest.mark.parametrize("header", [
    "127.0.0.1:7788", "localhost:7788", "127.0.0.1", "localhost",
    "[::1]:7788", "::1", "",
])
def test_our_own_names_are_accepted(header):
    assert server.allowed_host(header)


@pytest.mark.parametrize("header", [
    "evil.attacker.com",
    "evil.attacker.com:7788",
    "molo.localhost.evil.com",       # suffix trick
    "127.0.0.1.evil.com",            # prefix trick
    "192.168.1.50:7788",             # a LAN address, with LAN access off
])
def test_rebound_names_are_refused(header):
    assert not server.allowed_host(header)


def test_lan_address_only_once_lan_is_enabled(monkeypatch):
    monkeypatch.setattr(server.settings, "allow_lan", True)
    monkeypatch.setattr(server, "lan_url", lambda: "http://192.168.1.50:7788")
    assert server.allowed_host("192.168.1.50:7788")
    assert not server.allowed_host("192.168.1.99:7788")


@pytest.mark.parametrize("origin,ok", [
    ("", True),                               # not a browser
    ("http://127.0.0.1:7788", True),
    ("http://localhost:7788", True),
    ("http://evil.example", False),
    ("https://evil.example", False),
    ("ws://evil.example", False),
    ("null", False),                          # sandboxed iframe
    ("file://", False),
])
def test_origin_check(origin, ok):
    """A WebSocket has no same-origin policy of its own, so any page could open
    ws://127.0.0.1/ws and read the hello frame, which lists every job URL and
    file path on the machine."""
    assert server.allowed_origin(origin) is ok


# --- settings validation ------------------------------------------------------
#
# `POST /api/settings` used to setattr whatever arrived. A string where an int
# belonged was persisted, survived the restart, and killed startup with a
# TypeError, leaving an app that only a hand edit could revive.

def test_wrong_types_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    settings = config.Settings()

    for bad in ({"max_concurrent": "abc"}, {"max_concurrent": True},
                {"allow_lan": "yes"}, {"download_dir": 42}, {"language": None}):
        with pytest.raises(ValueError):
            settings.update(bad)


def test_numbers_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    settings = config.Settings()

    with pytest.raises(ValueError):
        settings.update({"max_concurrent": 0})
    with pytest.raises(ValueError):
        settings.update({"max_concurrent": 999})

    settings.update({"max_concurrent": 4})
    assert settings.max_concurrent == 4


def test_good_values_still_go_through(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    settings = config.Settings()

    settings.update({"allow_lan": True, "language": "it", "embed_subs": False})
    assert settings.allow_lan is True
    assert settings.language == "it"
    assert settings.embed_subs is False


def test_token_cannot_be_set_through_update(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    settings = config.Settings()
    original = settings.token

    settings.update({"token": "chosen-by-an-attacker"})
    assert settings.token == original


# --- an unwritable queue database ---------------------------------------------
#
# A full disk, a revoked permission, or the file removed under a running
# process all reach the same place. Before this, every add returned a bare 500
# with nothing on screen to explain it.

def test_unwritable_database_says_so(tmp_path):
    import os
    import sqlite3

    from molo import jobs

    store = jobs.Store(tmp_path / "molo.db")
    row = {"id": "x", "url": "u", "title": "t", "uploader": "", "thumbnail": "",
           "preset": "best_compat", "status": "queued", "progress": 0.0, "speed": None,
           "eta": None, "total_bytes": None, "filepath": None, "error": None,
           "note": "", "created_at": 1.0, "updated_at": 1.0}

    os.chmod(tmp_path, 0o500)          # SQLite cannot create its journal here
    try:
        with pytest.raises(jobs.StoreUnwritable) as caught:
            store.insert(row)
        assert str(tmp_path) in str(caught.value)
        assert "disk space" in str(caught.value)
    except sqlite3.OperationalError:
        pytest.skip("this filesystem lets root-owned processes write anyway")
    finally:
        os.chmod(tmp_path, 0o700)
