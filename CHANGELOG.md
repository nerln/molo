# Changelog

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
