# Security

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository
(Security → Report a vulnerability), or the email address on the maintainer's
profile. Please do not open a public issue for something exploitable.

Expect a first reply within a week. This is a side project, not a company with
an on-call rota, and pretending otherwise would only mislead you.

## What Molo exposes

Worth understanding before you assess anything:

**It binds to `127.0.0.1` by default.** Nothing is reachable from the network
until you turn on "Reachable from your phone" in settings.

**Network access is token-gated.** With LAN access on, the server binds
`0.0.0.0` and every request that does not come from loopback must carry a
token generated per installation and stored in `settings.json` with mode
`0600`. The token is never returned through the API.

**Traffic on your network is plain HTTP.** There is no TLS. The pairing link
carries the token in a query string, and the interface moves it into
`sessionStorage` and strips it from the URL on first load, but anyone
sniffing your local network sees it. If that matters to you, put Molo behind a
reverse proxy with TLS.

**It writes files where you tell it to**, and runs ffmpeg on them. It does not
execute anything downloaded.

**yt-dlp does the fetching.** Vulnerabilities in extractors belong upstream at
[yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp), though tell us too if Molo
makes one worse.

## Known and accepted

**The Android client permits cleartext traffic.** Android's network security
configuration cannot express "private address ranges", only domains, so
allowing local HTTP means allowing cleartext generally. The trade-off is
documented in
[`network_security_config.xml`](packaging/android/app/src/main/res/xml/network_security_config.xml).

**Builds are unsigned.** Notarising for macOS needs a paid Developer ID and
Windows signing needs an EV certificate. Verify what you download against the
CI logs if that concerns you: every release artifact is built in public by
GitHub Actions from a tagged commit.

## Out of scope

Reports that Molo can download copyrighted material. That is what a downloader
does, the policy around it is deliberate, and [LEGAL.md](LEGAL.md) explains
where the line is and why.
