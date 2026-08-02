# Changelog

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
