"""Checks that the interface honours what the manifest promises.

Written after finding the share target declared and never wired. The manifest
told Android that Molo accepts a shared link, Android duly opened Molo with the
link in the address bar, and nothing in the page ever looked at it. Worse, the
code path that reads the pairing token wiped the whole query string on its way
past, so the link was not merely ignored, it was destroyed. Sharing a video to
Molo opened an empty queue with nothing on screen to explain why.

Nothing here runs a browser. These are the cheapest possible checks on the one
thing that broke: a promise made in one file and kept in another.
"""

import json
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "molo" / "web"
MANIFEST = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
APP_JS = (WEB / "app.js").read_text(encoding="utf-8")
INDEX = (WEB / "index.html").read_text(encoding="utf-8")
I18N = (WEB / "i18n.js").read_text(encoding="utf-8")


def test_the_share_target_is_still_declared():
    """If this goes, the tests below are asserting nothing."""
    assert "share_target" in MANIFEST, "no share target: delete this file or restore it"
    assert MANIFEST["share_target"]["method"] == "GET", "these checks assume a GET target"


@pytest.mark.parametrize("param", sorted(set(MANIFEST["share_target"]["params"].values())))
def test_every_declared_parameter_is_actually_read(param):
    """The manifest names the query parameters. The page has to look at each one.

    Parametrised over the manifest rather than a hardcoded list, so adding a
    parameter there and forgetting the interface fails here instead of on a
    phone.
    """
    assert f'get("{param}")' in APP_JS, (
        f'the manifest promises Android a "{param}" parameter and app.js never reads it'
    )


def test_the_address_bar_is_only_wiped_after_the_link_is_taken():
    """The original bug, in one assertion.

    `history.replaceState` is what clears the query string. Whatever reads the
    shared link has to come first in the file, or the link is gone before anyone
    looks at it.
    """
    read_at = APP_JS.index('get("url")')
    wiped_at = APP_JS.index("history.replaceState")
    assert read_at < wiped_at, "the query string is wiped before the shared link is read"


def test_a_shared_title_still_yields_the_link():
    """Sharing apps often send a title with the link inside it.

    The interface pulls the link out with the same shape server.py uses, so the
    two cannot drift apart without somebody noticing.
    """
    in_js = re.search(r"const URL_IN_TEXT = /(.+)/;", APP_JS)
    assert in_js, "URL_IN_TEXT is gone from app.js"
    server_py = (
        Path(__file__).resolve().parent.parent / "molo" / "server.py"
    ).read_text(encoding="utf-8")
    assert re.search(r'URL_RE = re\.compile\(r"(.+)"\)', server_py), "URL_RE is gone from server.py"

    # The same shape, written once for a JavaScript literal and once for a
    # Python one, so the comparison has to survive their different escaping: a
    # slash is escaped between slashes, a quote is escaped between quotes.
    # Neither changes what the pattern matches.
    js = in_js.group(1).replace("\\/", "/")
    py = re.search(r'URL_RE = re\.compile\(r"(.+)"\)', server_py).group(1).replace('\\"', '"')
    assert js == py, f"the two patterns have drifted: {js!r} against {py!r}"


def test_the_offer_says_where_the_link_came_from():
    """A link that turns up unexplained is what the first tester saw.

    Both sources need their own label, and both labels need to exist in every
    language, or the box shows an empty line.
    """
    assert 'offerUrl(state.shared, "composer.shared")' in APP_JS
    assert 'offerUrl(url, "composer.clipboard")' in APP_JS
    assert I18N.count('"composer.shared"') == I18N.count('"composer.clipboard"') >= 2, (
        "composer.shared is missing from a language"
    )


def test_the_offer_shows_the_matching_icon():
    """A clipboard drawn next to a shared link is a small lie told in a picture."""
    for icon in ("sugg-icon-clipboard", "sugg-icon-shared"):
        assert f'id="{icon}"' in INDEX, f"{icon} is not in index.html"
        assert f'$("{icon}").hidden' in APP_JS, f"{icon} is never toggled"


def test_the_shared_link_is_offered_and_not_queued():
    """Sharing says which video. It does not say start now.

    Molo asks before it downloads, everywhere else too, and this path is not an
    exception. The guard here is that the shared link reaches the suggestion box
    and never `addUrl` directly.
    """
    line = next(l for l in APP_JS.splitlines() if "state.shared" in l and "offerUrl" in l)
    assert "addUrl" not in line, "a shared link starts a download without being asked"
