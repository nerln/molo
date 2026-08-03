<div align="center">

<img src="molo/web/icons/icon-192.png" width="82" alt="">

# Molo

**One download queue, on every device you own.**

A local interface for [yt-dlp](https://github.com/yt-dlp/yt-dlp). Paste a link on your phone, the file lands on the computer with the disk and the good connection.

[Download](https://github.com/nerln/molo/releases) · [Legal notes](LEGAL.md) · [Contributing](CONTRIBUTING.md) · MIT

</div>

---

## Why this exists

Look at one platform at a time and it does not need to. The desktop already has
[yt-dlp-gui](https://github.com/imsyy/yt-dlp-gui) and
[Open Video Downloader](https://github.com/jely2002/youtube-dl-gui). Android has
[Seal](https://github.com/JunkFood02/Seal) and
[YTDLnis](https://github.com/deniscerri/ytdlnis). Servers have
[MeTube](https://github.com/alexta69/metube). These are good projects and there
is no point rebuilding them.

What none of them do is share one queue between devices. You find something on
your phone, but the phone is the wrong machine to download 2 GB onto. Molo runs
on the computer, and the phone is just another window onto the same queue.

**If you only ever use Android, install Seal.** It runs yt-dlp natively on the
device and does that job better than any remote client can. Molo earns its
place when more than one device is involved.

## What it does

Paste a link and it works out the rest. The default preset gives you the best
video and audio the site offers, merged into an MP4 that plays anywhere without
re-encoding. There is another preset for the highest bitrate available if you
do not care about compatibility, and audio-only presets if you want the sound.

It recovers on its own. A `403` halfway through a large file usually means the
signed URL expired, not that you are locked out. Molo rotates the YouTube
client, backs off, and resumes from the partial file instead of starting over.

It keeps yt-dlp current, which is the single most common fix for a download
that stopped working. Sites change and yt-dlp ships fixes every few days.

Copy a link anywhere on the computer and Molo offers to take it. It offers
rather than downloading, because downloading on every copy is a good way to
fill a disk by accident.

Watchers keep an eye on a channel or a playlist and queue whatever is new. The
first pass only records what is already there, so adding a channel with 800
videos does not immediately cost you 800 videos.

The queue survives a restart. It lives in SQLite, and anything interrupted
picks up from its partial file when you reopen the app.

## What it will not do

There is no circumvention code in the repository. No CDM, no keys, no
decryption. On an encrypted stream Molo fails, and it fails because that is a
thing it cannot do rather than a thing it declines to do.

The reasoning is in [LEGAL.md](LEGAL.md), with the statutes cited. The short
version: reading a stream served in the clear gets past no protection, while
breaking encryption is unlawful in itself under Article 6 of EU Directive
2001/29/EC and DMCA §1201.

## Install

Grab a build from [Releases](https://github.com/nerln/molo/releases).
Nothing is signed with a paid certificate, so the first launch takes one extra
step: on macOS, right-click the app and choose Open. On Windows, SmartScreen
wants "More info" then "Run anyway". On Android you need to allow installs from
unknown sources.

From source:

```bash
git clone https://github.com/nerln/molo && cd molo
python3 -m venv .venv && .venv/bin/pip install -e ".[desktop]"
.venv/bin/python -m molo
```

ffmpeg merges separate video and audio streams and is not bundled, for
licensing reasons set out in [NOTICE.md](NOTICE.md):

```bash
brew install ffmpeg
```

Without it Molo still runs, but it is limited to formats that already carry
both streams, which usually means 720p.

## On your phone

Turn on "Reachable from your phone" in settings, copy the link, and open it on
the phone. Add it to the home screen and it behaves like an app, because it is
a progressive web app. There is also an APK in the releases if you want an icon
in the app drawer.

The server listens on `127.0.0.1` until you turn that on. After that, every
request that does not come from the local machine has to carry a token
generated for your installation. Nothing is exposed to the internet.

If you want Molo running on the phone with no computer involved, Termux gives
Android a real Linux environment where yt-dlp runs natively:
`scripts/termux-install.sh`.

## Keyboard

| | |
|---|---|
| `⌘,` | Settings |
| `⌘L` | Jump to the address field |
| `⌘1` `⌘2` | Queue, watchers |
| `⌘/` | The full list |

Paste a link anywhere outside a text field and it goes straight into the queue.
Links dragged onto the window work too.

## Build it yourself

```bash
./packaging/build_macos.sh          # .app and .dmg
pyinstaller packaging/molo.spec     # Windows
cd packaging/android && gradle assembleDebug
```

[CI](.github/workflows/build.yml) builds all three on every push and attaches
them to a release on a `v*` tag.

## How it fits together

```
molo/policy.py    the download policy; runs before everything else
molo/engine.py    yt-dlp as a library: presets, recovery, ffmpeg discovery
molo/jobs.py      the queue: persistence, concurrency, events
molo/watch.py     channel and playlist watchers
molo/server.py    HTTP and WebSocket API, token auth for network access
molo/web/         the interface: hand-written HTML, CSS and JS, no build step
```

One Python process. The desktop window is the system WebView pointed at
localhost rather than a bundled Chromium, which is why the build is 44 MB
instead of 200.

The interface has no build step on purpose. Open `app.js`, change a line,
reload.

## Updating the engine

A yt-dlp more than a few months old stops working on YouTube, and that is by far
the most common reason a download fails. Molo replaces its own engine, in a
packaged build as well as from source.

It fetches the `py3-none-any` wheel from PyPI, which is pure Python and the same
file on every platform, checks it against the sha256 PyPI publishes for it,
unpacks it into Molo's data folder and puts that folder first on `sys.path`.
yt-dlp stays a library, so the progress you see still comes from its own hooks
instead of from parsing a subprocess. The engine already running was loaded at
launch and keeps running: a new one starts being used at the next launch, which
is what the message tells you.

Two things this does not claim. The sha256 catches a truncated or corrupted
download and is the same protection pip gives you over HTTPS; it is not a
signature, and it would not stop a compromised release. And from source, Molo
leaves your site-packages alone: it keeps its own copy under
`Application Support/Molo/engine/`, which you can delete to fall back to the one
Molo ships with.

## Known limitations

Builds are unsigned. Notarising for macOS needs a paid Developer ID and Windows
signing needs an EV certificate.

Android suspends background processes aggressively. Under Termux, keep the app
in the foreground for a long download or hold a wakelock.

The Windows executable and the Android APK compile in CI, and nobody has run
them on real hardware yet. Only the macOS build has been launched and used for
a full download.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). One hard limit: no circumvention code,
no CDM modules, no documentation presenting a paywall bypass as a use case. A
test enforces it, so a patch that crosses the line fails CI rather than
reaching anyone's inbox.

Translations are welcome and cheap to add. Copy the `en` block in
[`molo/web/i18n.js`](molo/web/i18n.js), translate the values, register the
code. Missing keys fall back to English, so a partial translation still works.
