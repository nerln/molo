# Project state

The context someone needs before touching this repository, whether that is a
new contributor, another agent, or the person tracking several projects at
once. It replaces reading the commit history.

**Updated:** 2 August 2026, at v0.3.0
**Repository:** https://github.com/nerln/molo
**Page:** https://nerln.github.io/molo/
**Licence:** MIT. yt-dlp is a dependency, not a fork.

---

## What Molo is, in one paragraph

A local interface for yt-dlp. One download queue that several devices can see:
the server runs on the computer with the disk and the bandwidth, and a phone is
just another window onto it. macOS, Windows and Android. The distinguishing
feature is the shared queue. Everything else on that list already exists, done
well, one platform at a time.

## Where it stands

| Area | State | Verified how |
|---|---|---|
| Download engine | working | 35-check end-to-end sweep, all presets, files confirmed on disk |
| Queue, persistence, recovery | working | cancel, retry, restart resume, archive skip |
| Watchers | working | first pass records without downloading, manual check, removal |
| Interface, English with Italian | working | in the browser and in the packaged app |
| Keyboard, drag and drop | working | events dispatched and asserted |
| macOS build | working | DMG mounted from the release, app launched, real download |
| Windows build | compiles, never run | CI artifact, ZIP contents inspected |
| Android APK | compiles, never run | CI artifact, package contents inspected |
| Notarisation and signing | not done | needs paid certificates |

The Windows and Android gap is the honest one. Both produce valid packages in
CI and nobody has installed either. That needs a real PC and a real phone.

## Decisions that are settled

**No circumvention code, ever.** No CDM, no keys, no decryption. This is not a
policy that can be relaxed by a setting; it is a statement about the contents
of the repository, and `tests/test_policy.py` fails if anyone adds any. The
reasoning, with statutes, is in [LEGAL.md](../LEGAL.md).

**The DRM switch stays out of the interface.** It was there in 0.1, and it was
removed in 0.2 after testing showed it granted nothing: with no decryption
module, an encrypted stream fails either way. A control that appears to offer
a capability is a liability regardless of what it does. The host pre-check can
still be skipped with `MOLO_DISABLE_HOST_PRECHECK=1`, documented in LEGAL.md
rather than advertised. The `has_drm` check has no off switch.

**ffmpeg is not bundled.** Common builds are GPL and Molo is MIT. It is
detected on the system instead, including outside `PATH`, because an app
launched from Finder gets the bare launchd environment.

**No build step for the interface.** Hand-written HTML, CSS and JS. Anyone
should be able to change a button without installing a toolchain.

**English is the source language.** Interface strings live in
`molo/web/i18n.js`; the server sends machine-readable notes like `retry:2:8`
and never prose.

## What is worth doing next

1. **Run the Windows and Android builds on real hardware.** The only claim in
   the README that rests on nothing but a green CI job.
2. **yt-dlp as a swappable external binary.** A packaged build cannot update it
   today, because there is no pip inside a PyInstaller bundle. This is the
   single highest-value fix: a stale engine is the most common cause of a
   failed download.
3. **A queue that survives the server moving.** Right now the phone needs the
   desktop awake. Worth deciding whether that is a limitation or the design.
4. **Signing.** macOS notarisation and a Windows certificate, if this is ever
   handed to people who do not read release notes.

## How to check it still works

```bash
pytest tests -q                                    # 36 unit and regression tests
python -m molo --headless                          # then exercise the interface
./packaging/build_macos.sh && open dist/Molo.app   # the packaged path
```

The end-to-end sweep used for releases is not in the repository because it
downloads real videos and takes several minutes. Its checks are listed in the
0.3.0 entry of [CHANGELOG.md](../CHANGELOG.md).

## Bugs that came from real use, and what they taught

Kept because each one hid behind a plausible wrong theory, and the wrong
theory is the useful part.

**"Show file" opened nothing.** Looked like a sandbox or permissions problem.
It was the progress hook: it fires once per stream, so a merged download
recorded a temporary fragment that had already been deleted. Anything that
reports a path has to read it after postprocessing, not during.

**ffmpeg reported missing while installed.** Looked like a broken install. An
app launched from Finder does not inherit the shell `PATH`, so `shutil.which`
alone finds nothing. Anything a packaged desktop app shells out to needs
looking up by absolute path.

**A repeated download failed with a `NoneType` error.** Looked like a race.
`extract_info` returns `None` for a video already in the archive instead of
raising, and the `None` was passed straight on.

**Cover art failure killed a finished download.** yt-dlp treats a
postprocessor error as fatal. Distinguish decoration from substance before
throwing work away.
