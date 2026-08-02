# Legal notes

**This is not legal advice.** I am not a lawyer. What follows explains the
basis on which Molo is designed and distributed, so that anyone using or
forking it can judge for themselves instead of taking my word for it.

---

## Where the line is, and why it is there

A program cannot know whether you have the right to download a given file. It
depends on who you are, what you agreed to, where you live, and what you plan
to do with it. No automated check decides that for you.

There is one distinction a program can enforce, and the whole design rests on
it: the difference between reading a stream served in the clear and breaking
encryption.

**A stream in the clear.** Your browser downloads it already; that is how it
plays the video. Saving it to disk rather than to a cache circumvents no
technical protection. It may breach a site's terms of service, which is a
contract matter between you and that site, not a criminal one.

**A stream encrypted with DRM** (Widevine, PlayReady, FairPlay). Reaching the
video means breaking that encryption, and that act is unlawful in itself:

- **European Union**: Article 6 of Directive 2001/29/EC, implemented in Italy
  by Article 102-quater of Law 633/1941.
- **United States**: DMCA §1201.

The violation is in the circumvention, not in what you do afterwards. Even
downloading something you pay a subscription for would still be circumvention.

**Molo contains no code to circumvent anything.** No CDM module, no keys, no
decryption routine, and none will be accepted. This is the load-bearing fact
and it is not configurable, because it is a statement about what is in the
repository rather than a setting.

---

## The pre-check, and its off switch

Above that fixed point sits a pre-check in
[`molo/policy.py`](molo/policy.py), which runs before every download:

1. On the address, before touching the network: services whose entire
   catalogue sits behind DRM are refused with an explicit message.
2. On the metadata yt-dlp returns: if the content is marked `has_drm`, the job
   stops. This covers the thousands of sites no host list will ever enumerate.

These two are different kinds of thing, and an earlier version of this project
made the mistake of collapsing them into one switch.

**The host list is a heuristic.** It is a list of domains in a text file. It is
right most of the time and wrong at the edges: a paid Udemy lesson, your own
upload, a public clip on a platform that uses DRM elsewhere. People with
legitimate access to unencrypted content on those domains need a way past it,
and there is no honest argument for making them patch the source. It can be
skipped by setting `MOLO_DISABLE_HOST_PRECHECK=1`.

**The `has_drm` check has no off switch.** It is not a heuristic. It is yt-dlp
reporting that the stream is encrypted, and there is nothing behind that door
to let anyone through to: without a decryption module the bytes are noise.
Leaving it permanently on costs no legitimate user anything.

There is deliberately no checkbox for either. A control labelled "turn off the
DRM policy" is a liability regardless of what it actually does, because it
reads as an invitation, and inducement is what sank Grokster. An environment
variable found by someone reading the legal documentation is not marketing.

Worth stating plainly: a list of hosts in a text file is not a security
barrier. Anyone who forks the project deletes it in ten seconds. It is there so
the tool's default behaviour matches what the project claims about itself. The
real defence is the other one, that no circumvention code exists anywhere in
it, and there is a test that fails if someone tries to add any.

---

## The precedent

In October 2020 the RIAA asked GitHub to remove youtube-dl, citing DMCA §1201.
GitHub took it down. The Electronic Frontier Foundation replied on behalf of
the maintainers, arguing that the tool circumvents no technological protection
measure and has substantial non-infringing uses. **On 16 November 2020 GitHub
restored the repository** and set up a one million dollar fund to defend
developers in similar cases.

Two principles from that episode, which are design choices here rather than
slogans:

**Substantial non-infringing uses.** From the doctrine in *Sony Corp. of
America v. Universal City Studios* (1984): a tool capable of substantial
non-infringing uses is not liable for contributory infringement merely because
someone misuses it. Molo has many such uses, and they are not pretexts:
archiving your own lectures, keeping copies of your own uploads, saving openly
licensed material, building research corpora, accessibility, and backing up
public content that has a habit of disappearing.

**Inducement matters.** From *MGM Studios v. Grokster* (2005): promoting a tool
*for* infringement makes you liable for that promotion, however neutral the
code is. Which is why nothing in this project presents subscription services as
a use case, no guide here explains getting past a paywall, and contributions
heading that way are not accepted. That is not timidity. It is the difference
between a defensible position and one lost before it starts.

---

## Italy, private copying, and a common misreading

Article 71-sexies of Law 633/1941 permits private reproduction of phonograms
and videograms for strictly personal use, without profit and without directly
or indirectly commercial purposes, against the levy in Article 71-septies that
is already built into the price of discs and storage.

**But the fourth paragraph of that same article excludes works protected by
technological protection measures, and works made available on demand under
agreed contractual terms.** Private copying is therefore not a pass for
subscription streaming. That is precisely the case the exception leaves out.

There is no shortcut where "in Italy it's allowed". There is a boundary, and
Molo is built to stay inside it in the part a program can control.

---

## Distribution choices

**ffmpeg is not bundled.** The common builds are compiled with GPL components.
Shipping one inside Molo would extend GPL obligations across the whole package,
which is MIT, and anyone forking it would inherit constraints they did not
choose. Molo detects ffmpeg and tells you how to install it if it is missing.

**yt-dlp is a dependency, not a fork.** yt-dlp is public domain (Unlicense) and
releases fixes every few days. Forking it would mean chasing upstream forever
and losing its fixes.

**No keys, no decryption modules.** The repository contains no CDM, no Widevine
components and no decryption code, and will not accept any. A test in
`tests/test_policy.py` enforces this in CI.

**No third party trademarks.** Molo does not use the names, logos or icons of
video platforms, and does not present itself as authorised by or affiliated
with any of them.

**No protected content in the tests.** Tests use openly licensed material or
fixtures generated on the spot.

---

## If you are a rights holder

Open an issue, or use the contact on the maintainer's GitHub profile. Reasoned
reports get a reply. Blanket takedown requests resting on the fact that the
software *could* be misused will meet the reasoning above.

---

## In one line

Molo circumvents nothing, is not promoted for infringement, and does not decide
for you whether you have the right to download that file. That part stays
yours.
