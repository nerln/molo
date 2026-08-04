# Changelog

## 1.0.1

**A queue database that cannot be written to now says so.** Every attempt to
add a download returned a bare 500 with nothing on screen to explain it. Found
by breaking it accidentally: the release sweep deleted the database file while
the packaged app still held it open, and eight checks went red with no usable
diagnosis. A full disk is the realistic version of the same thing, and a
download manager is exactly the program that meets one.

## 1.0.0

Twenty-six agents reviewed this release adversarially: five reading for bugs,
interface defects, security, App Store readiness and accessibility, then one
verifier per finding whose job was to refute it. Twenty findings, ten refuted,
ten confirmed and fixed here. The refuted ten are worth as much as the
confirmed ten: a timing-attack claim on the token comparison that measurement
did not support, a watcher failure claimed to be permanent that recovers on
the next tick, a path-traversal claim on `/api/reveal` where the caller
already had the same privilege.

**A page on any website could read your queue.** Binding to `127.0.0.1` is not
a defence by itself: a site can point a hostname it controls at loopback and
the browser will send the request here with that name attached. Before this
release, `curl -H 'Host: evil.attacker.com' /api/pairing` returned the
per-install token in plain text, which defeated the point of having a token.
Separately, WebSockets have no same-origin policy, so any page could open
`ws://127.0.0.1:7788/ws` and receive a frame listing every job URL and file
path. Both are now checked, on the HTTP middleware and again inside the
WebSocket handler, because the middleware never sees a handshake.

**A running download could not be stopped.** The Stop button only rendered for
queued jobs, and promoting the running job to its own card in 0.3.0 removed it
from the row list entirely. The backend had supported cancellation the whole
time. A mis-pasted two-hour 4K link could only be stopped by quitting.

**Two concurrent downloads wrote into one card.** The active card carried no
job id and the progress handler never checked which job a frame belonged to,
so one download's percentage appeared under another's title. Default
concurrency is two, so this was the normal case, not an edge.

**A wrong-typed setting bricked the app.** `POST /api/settings` accepted
anything and persisted it; `{"max_concurrent": "abc"}` survived the restart
and then killed startup with a TypeError, leaving an app that only a hand edit
could revive. Values are now checked against their declared types and bounds.

**Light mode failed contrast where it mattered most.** `--text-3` sat at
3.35:1 on the sidebar, and `--warn` was never defined for light at all, so
dark amber leaked through at 1.56:1: the "ffmpeg missing" indicator, the one
explaining why you are capped at 720p, was effectively invisible.

Also fixed: the modal sheets had no dialog semantics, no focus management and
no live region, so a screen reader was never told one had opened and every
toast was announced to nobody; notes stopped updating on the running card;
settings changes broadcast to a second client were received and discarded.

**Cookies from your browser.** Age-restricted, members-only, and "sign in to
confirm you're not a bot" are not DRM, and they are most of what fails on
YouTube. Molo can now use your own browser session for content you already
have access to. When a download does fail it says which of those it was, and
whether anything would help.

**Signing and App Store material.** A notarisation script, hardened runtime
entitlements, sandbox entitlements, and an honest assessment in
[APPSTORE.md](packaging/APPSTORE.md). Short version: Developer ID works and is
ready; the Mac App Store almost certainly does not, and the ffmpeg licence
blocker has no clean fix.

## 0.3.0

Three bugs found by the first person to actually use the app, plus the
identity work that followed.

**"Show file" opened nothing and turned red.** The recorded path came from the
progress hook, which fires once per stream. On a merged download the last one
to finish is the temporary audio fragment, which ffmpeg consumes and deletes,
so the queue held a path to a file that no longer existed. The final path now
comes from `requested_downloads`, which yt-dlp rewrites after merging and
after every postprocessor, with a scan of the destination as a backstop. If
nothing is found the row says so instead of offering a button that fails.

**Queueing the same video twice crashed the second one.** `extract_info`
returns `None` when a video is already in the download archive rather than
raising, and that `None` went straight into `process_ie_result`. The job
failed four times over with `'NoneType' object has no attribute 'get'` for
something already sitting on disk. It now reports the skip.

**Audio downloads were thrown away when the cover art would not attach.**
YouTube serves WebP thumbnails and ffmpeg cannot write those into an m4a, so a
finished download died at the last step. Thumbnails are converted to JPEG
first, and if embedding still fails the media is kept with a note rather than
discarded. Losing two gigabytes over a picture is not a reasonable trade.

**Two downloads of the same URL no longer collide.** They shared temporary
filenames and corrupted each other. One lock per URL.

**The clipboard offer says where the link came from.** It appeared as a bare
URL with no explanation, which reads as something the app invented.

**New mark and a heavier typographic scale.** The old logo was a generic
download arrow that would suit any app in the category. It is now a solid
arrow docking onto a pier with pilings under it, which at least means
something. Display type moved to a second stack at weight 800 with tight
tracking, still system fonts only, because the app has to work offline.

Every function was then swept end to end: 35 checks covering presets, merge
and postprocessor paths, cancel, retry, reveal, the archive, watchers,
settings persistence, LAN pairing, the DRM refusals, playlists, and asset
caching. All pass. The three bugs above have regression tests.

## 0.2.0

**ffmpeg is found even when it isn't on PATH.** An app launched from Finder
inherits the bare launchd environment, which has no `/opt/homebrew/bin` in it.
So ffmpeg was installed, worked fine in a terminal, and Molo insisted it was
missing. It now checks the places package managers actually install to, and
hands yt-dlp an absolute path instead of trusting a search.

**The missing-ffmpeg warning stopped being a toast.** A missing dependency is a
state, not an event, and a warning that disappears after five seconds reads
like a glitch. It is now a panel that stays until the problem is fixed, with
the right install command for your platform.

**English first, with translations.** The interface, the source, and the
documentation are in English. Italian ships as a translation and the language
follows your system unless you pin it. Adding a language means copying one
block in `i18n.js`.

**Keyboard.** `⌘,` opens settings, `⌘1`/`⌘2` switch sections, `⌘L` jumps to the
address field, `⌘/` lists the lot. Pasting a link anywhere outside a text field
queues it. Links can be dragged onto the window.

**The running download gets its own card.** Large artwork, the percentage set
in a size you can read across the room, live speed and time remaining. A
download manager where the thing currently happening looks like every finished
row above it is telling you nothing.

**The DRM policy switch is gone from the interface.** The reasoning is in
[LEGAL.md](LEGAL.md). Briefly: it never granted any capability, because without a
decryption module an encrypted stream stays unreadable regardless. But a
checkbox that appears to offer one is a liability whatever it actually does.
The host pre-check can still be skipped through an environment variable for
people with legitimate access to unencrypted content on listed domains. The
DRM metadata check has no off switch at all, because there is nothing behind
that door to let anyone through to.

**Interface assets are versioned and no longer cached stale.** `/` and
`/static` were served without `Cache-Control`, so after an update a browser
would keep showing the old interface.

Also: contrast on secondary text now passes AA (it did not), buttons reset
`appearance` so WebKit stops drawing native chrome over them, and the sidebar
has accessible names.

## 0.1.0

First release. Queue with persistence and recovery, channel and playlist
watchers, clipboard offers, a phone-reachable mode with token auth, and builds
for macOS, Windows and Android.
