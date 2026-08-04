# Shipping Molo on Apple platforms

Written after preparing both paths. The short version: **Developer ID with
notarisation works and is ready. The Mac App Store almost certainly does not,
and one of the blockers has no fix.** Everything below says why, with the
guideline numbers, so the decision is yours rather than mine.

---

## What is ready right now

Run `./packaging/build_macos.sh`, then:

```bash
IDENTITY="Developer ID Application: Your Name (TEAMID)" \
PROFILE=molo-notary ./packaging/sign_and_notarize.sh
```

That signs every nested binary innermost-first, applies the hardened runtime
with [entitlements-devid.plist](entitlements-devid.plist), notarises, and
staples. The result opens with a double click on a machine that has never seen
it: no right-click-then-Open, no unidentified developer warning.

You need a paid Apple Developer account ($99/year) and a Developer ID
Application certificate. Everything else is in the script. This has not been
run end to end here because there is no certificate on this machine, so treat
the first run as something to watch rather than fire and forget.

## The App Store, honestly

### Blocker 1: ffmpeg cannot come along, and cannot stay behind

The sandbox is mandatory for the store. A sandboxed app cannot execute a
binary outside its own container, so `/opt/homebrew/bin/ffmpeg` is
unreachable. Without ffmpeg, Molo cannot merge separate video and audio
streams and tops out around 720p, which removes the main reason to use it.

The obvious answer is to bundle ffmpeg. That is where it stops: the widely
distributed ffmpeg builds are GPL, and the GPL is incompatible with the App
Store's terms because the store imposes usage restrictions the licence forbids
passing on. This is the same wall VLC hit, twice, and the reason it is not on
the Mac App Store.

An LGPL-only ffmpeg build, compiled without the GPL components, is
theoretically permissible. It is real work: you would be building and
maintaining your own ffmpeg, verifying which encoders survive, and shipping
the LGPL relinking obligations. This is the only blocker with even a
theoretical path through, and it is not a small one.

### Blocker 2: Guideline 2.5.2, updating the engine

Molo replaces its own yt-dlp by fetching a wheel and putting it on `sys.path`.
Guideline 2.5.2 forbids downloading and executing code that did not ship in
the bundle. This one is **already handled**: `config.store_build()` detects a
store build from an `APP_STORE` marker placed in the bundle, and
`engine.update_ytdlp()` refuses with an explanation instead of quietly doing
nothing.

The cost is real though. A yt-dlp more than a few months old stops working on
YouTube, so a store build would depend on you shipping an update every few
weeks, through review each time, forever.

### Blocker 3: Guidelines 5.2.2 and 5.2.3, what the app is for

This is the one that decides it. Apps whose purpose is downloading media from
sites that do not offer downloads have a long history of rejection and
removal, and YouTube's terms of service prohibit downloading without
permission. Molo's own policy work does not change how review reads the app:
that work is about not circumventing protection, which is a different question
from whether Apple wants the category in the store.

The honest expectation is rejection under 5.2.3, and no amount of preparation
changes that. A disclaimer does not help either. If anything it confirms what
the app is for.

### Also worth knowing

**Cookies stop working.** Reading Safari or Chrome cookies means touching
files outside the container. The "Use cookies from" setting would be dead in a
store build, which removes the fix for age-restricted and members-only videos.

**Arbitrary download folders need reworking.** The sandbox reaches user-chosen
folders through security-scoped bookmarks. Molo currently stores a plain path
in `settings.json`, which works outside the sandbox and not inside it.

**A bundled interpreter is allowed** as long as it only runs code that shipped
with the app. PyInstaller is not itself a blocker.

## What I would do instead

Ship the notarised Developer ID build from GitHub Releases, which is what the
project already does and what comparable tools do. Users get one Gatekeeper
prompt at most, updates arrive immediately without review, ffmpeg stays a
system dependency with no licence conflict, and cookies keep working.

If the goal is specifically an App Store presence rather than distribution,
the honest version is a different, smaller app: one that only handles sources
that permit downloading. That is a different product, not this one with
paperwork attached.

## iOS

Not applicable. Molo is a Python server plus a WebView, and iOS allows neither
a bundled interpreter running downloaded logic nor the background networking
this needs. The Android client in this repository is a thin WebView onto the
desktop instance; the iOS equivalent would be a new app, and it would meet the
same 5.2.3 problem with less room to argue.
