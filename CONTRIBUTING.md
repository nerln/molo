# Contributing

Pull requests are welcome. So are bug reports that say what you expected and
what happened instead.

## The one hard limit

No circumvention code. No CDM modules, no keys, no decryption routines, and no
documentation that presents getting past a paywall as a use case.

This is not excessive caution. It is the condition under which the project can
exist in the open, and [LEGAL.md](LEGAL.md) explains the reasoning. A test
enforces it, so a patch that crosses the line fails CI rather than reaching a
maintainer's inbox.

Everything else is open for discussion, including the parts I got wrong.

## Getting set up

```bash
git clone https://github.com/eugenionerelli/molo && cd molo
python3 -m venv .venv
.venv/bin/pip install -e ".[desktop]" pytest
.venv/bin/python -m molo
```

`--headless` skips the native window and just serves on localhost, which is
usually easier while working on the interface.

ffmpeg is needed to merge separate video and audio streams. It is not bundled,
for licensing reasons explained in [NOTICE.md](NOTICE.md):

```bash
brew install ffmpeg
```

## Before opening a pull request

```bash
.venv/bin/python -m pytest tests -q
```

The policy tests are the important ones. If you find yourself editing them to
make a change pass, stop and open an issue instead. Either the test is wrong,
which is worth discussing, or the change is.

## How the pieces fit

```
molo/policy.py    the download policy; runs before everything else
molo/engine.py    yt-dlp as a library: presets, recovery, ffmpeg discovery
molo/jobs.py      the queue: persistence, concurrency, events
molo/watch.py     channel and playlist watchers
molo/server.py    HTTP + WebSocket API, token auth for network access
molo/web/         the interface: hand-written HTML, CSS and JS, no build step
```

The interface has no build step on purpose. Open `app.js`, change a line,
reload. Nobody should need to install a toolchain to move a button.

## Style

Match the surrounding code. A few conventions worth knowing:

**Comments explain why, not what.** The code already says what it does. A
comment earns its place by recording the thing that is not visible: the bug
that made this line necessary, the platform quirk, the reason the obvious
approach fails.

**English everywhere**: code, comments, commit messages, issues. The
interface is translated, the source is not.

**Interface strings live in `molo/web/i18n.js`.** Nothing user-facing should be
hardcoded in `app.js` or returned as prose from the server. The server sends
machine-readable notes like `retry:2:8`, and the interface decides how to say
that in your language.

## Adding a language

Copy the `en` block in [`molo/web/i18n.js`](molo/web/i18n.js), translate the
values, and register the code in `LANGUAGES`. Nothing else needs touching. A
missing key falls back to English rather than showing a blank, so a partial
translation is still useful and can be finished later.

## Reporting a bug

Include your platform, whether you installed from a release or from source,
and what `ffmpeg` and `yt-dlp` versions the sidebar reports. Most download
failures come from a stale yt-dlp, and that is worth ruling out first.

If Molo refused a URL, say so explicitly. A policy refusal and a download
failure look similar from the outside and have nothing to do with each other.
