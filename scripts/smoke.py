"""End-to-end sweep against a running Molo instance.

This is not in the unit test suite because it downloads real videos over the
network and takes several minutes. It is what gets run before tagging a
release, and what caught the merged-path, archive-skip and cover-art bugs that
unit tests could not have.

    python -m molo --headless --port 7788    # in one terminal
    python scripts/smoke.py                  # in another

It writes to your configured download folder and clears the queue as it goes,
so point it at a scratch install if you care about what is in there.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("MOLO_URL", "http://127.0.0.1:7788")
SHORT = "https://www.youtube.com/watch?v=jNQXAC9IVRw"   # 19 seconds
BIG = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"     # ~10 min, needs merging
PLIST = "https://www.youtube.com/playlist?list=PLbpi6ZahtOH6Blw3RGYpWkSByi_T7Rygb"

ARCHIVE = os.path.expanduser("~/Library/Application Support/Molo/archive.txt")
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))


def call(path, method="GET", body=None, headers=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or "null")
        except Exception:
            return e.code, None


def state():
    return call("/api/state")[1]


def wait(job_id, timeout=420):
    end = time.time() + timeout
    while time.time() < end:
        for j in state()["jobs"]:
            if j["id"] == job_id and j["status"] in ("done", "error", "cancelled", "skipped"):
                return j
        time.sleep(2)
    return None


def queue(url, preset):
    status, res = call("/api/jobs", "POST", {"url": url, "preset": preset})
    return res["created"][0]["id"] if status == 200 else None


def forget():
    call("/api/jobs", "DELETE")
    try:
        os.remove(ARCHIVE)
    except OSError:
        pass


print("\n=== presets, and whether the recorded path actually exists ===")
for preset in ["best_compat", "720p", "audio_best", "audio_mp3"]:
    forget()
    job = wait(queue(SHORT, preset))
    path = (job or {}).get("filepath") or ""
    check(f"preset {preset}", bool(job) and job["status"] == "done" and os.path.exists(path),
          os.path.basename(path) or (job or {}).get("error", "timeout")[:60])

print("\n=== a merged download keeps the merged file, not a fragment ===")
forget()
job = wait(queue(BIG, "720p"))
path = (job or {}).get("filepath") or ""
check("merged path exists", bool(path) and os.path.exists(path), os.path.basename(path) or "NULL")
check("not a stream fragment", ".f" not in os.path.basename(path).rsplit(".", 1)[0][-6:])

print("\n=== reveal ===")
check("reveal on a real file", call("/api/reveal", "POST", {"path": path})[0] == 200)
check("reveal falls back rather than erroring",
      call("/api/reveal", "POST", {"path": "/tmp/not-here-9182.mp4"})[0] == 200)

print("\n=== the same URL twice at once is serialised ===")
forget()
a, b = queue(SHORT, "best_compat"), queue(SHORT, "audio_best")
both = [j for j in (wait(a), wait(b)) if j]
check("both finish", len(both) == 2 and all(j["status"] in ("done", "skipped") for j in both),
      " / ".join(j["status"] for j in both))
check("every finished job has its file",
      all(os.path.exists(j["filepath"]) for j in both if j["filepath"]))

print("\n=== the archive skips a repeat ===")
check("second identical download is skipped", (wait(queue(SHORT, "best_compat")) or {}).get("status") == "skipped")

print("\n=== cancel and retry ===")
call("/api/jobs", "DELETE")
jid = queue(BIG, "best_absolute")

# Wait for the job to actually be running rather than sleeping a fixed time.
# A packaged build starts more slowly than a source one, and a seven second
# sleep cancelled a job that was still resolving metadata: a red result that
# meant nothing except that the machine was busy.
deadline = time.time() + 90
while time.time() < deadline:
    if any(j["id"] == jid and j["status"] == "running" for j in state()["jobs"]):
        break
    time.sleep(1)
call(f"/api/jobs/{jid}/cancel", "POST")
check("cancel stops a running job", (wait(jid, 60) or {}).get("status") == "cancelled")
status, res = call(f"/api/jobs/{jid}/retry", "POST")
check("retry is accepted", status == 200 and res.get("job"))
if status == 200:
    call(f"/api/jobs/{res['job']['id']}/cancel", "POST")

print("\n=== policy ===")
# The host pre-check has a documented opt-out (LEGAL.md). On a machine where
# it is off, the host list is meant to pass, and reporting that as a failure
# would train people to ignore this script.
precheck_off = (os.environ.get("MOLO_DISABLE_HOST_PRECHECK", "").strip() in {"1", "true", "yes"}
                or os.path.exists(os.path.expanduser("~/Library/Application Support/Molo/host-precheck-off")))

if precheck_off:
    print("  ....  host pre-check is opted out on this machine, skipping its two checks")
else:
    status, res = call("/api/jobs", "POST", {"url": "https://www.netflix.com/watch/1"})
    check("DRM host refused with 451", status == 451, (res or {}).get("detail", "")[:50])
    check("probe refuses it too",
          call("/api/probe", "POST", {"url": "https://open.spotify.com/track/x"})[0] == 451)

check("garbage URL rejected", call("/api/jobs", "POST", {"url": "not-a-url"})[0] in (400, 451))

print("\n=== the access boundary ===")
check("rebound Host refused", call("/api/pairing", headers={"Host": "evil.attacker.com"})[0] == 400)
check("cross-origin refused", call("/api/state", headers={"Origin": "http://evil.example"})[0] == 403)
check("our own request still works", call("/api/pairing")[0] == 200)
check("wrong-typed setting refused", call("/api/settings", "POST", {"max_concurrent": "abc"})[0] == 400)
check("out-of-range setting refused", call("/api/settings", "POST", {"max_concurrent": 99})[0] == 400)

print("\n=== probe ===")
status, res = call("/api/probe", "POST", {"url": SHORT})
check("probe returns title and height", status == 200 and res.get("title") and res.get("max_height"))
status, res = call("/api/probe", "POST", {"url": PLIST})
check("probe understands a playlist", status == 200 and res.get("kind") == "playlist",
      f"n={(res or {}).get('count')}")

print("\n=== watchers ===")
status, res = call("/api/watchers", "POST", {"url": PLIST, "interval_minutes": 60})
wid = res["watchers"][-1]["id"] if status == 200 and res.get("watchers") else None
check("watcher added", bool(wid))
time.sleep(9)
w = [x for x in state()["watchers"] if x["id"] == wid]
check("first pass records without downloading",
      bool(w) and w[0]["seen_count"] > 0 and w[0]["last_new"] == 0)
check("manual check runs", call(f"/api/watchers/{wid}/check", "POST")[1].get("new") == 0)
check("watcher removed", not any(x["id"] == wid for x in call(f"/api/watchers/{wid}", "DELETE")[1]["watchers"]))

print("\n=== settings ===")
status, res = call("/api/settings", "POST", {"max_concurrent": 3, "language": "en"})
check("settings saved", status == 200 and res["settings"]["max_concurrent"] == 3)
check("token never leaves the API", "token" not in res["settings"])
check("bad folder refused", call("/api/settings", "POST", {"download_dir": "/proc/nope"})[0] == 400)
call("/api/settings", "POST", {"max_concurrent": 2, "language": "auto"})

print("\n=== static assets ===")
for path in ["/", "/static/app.css", "/static/app.js", "/static/i18n.js",
             "/manifest.webmanifest", "/sw.js", "/static/icons/icon-192.png"]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as r:
            check(f"serves {path}", r.status == 200, f"cache-control: {r.headers.get('cache-control', 'none')}")
    except Exception as exc:
        check(f"serves {path}", False, str(exc)[:40])

print("\n=== clear ===")
status, res = call("/api/jobs", "DELETE")
check("clear removes finished jobs", status == 200 and
      not [j for j in state()["jobs"] if j["status"] == "done"])

print("\n" + "=" * 60)
bad = [r for r in results if not r[1]]
print(f"  {len(results) - len(bad)}/{len(results)} passed")
for name, _, detail in bad:
    print(f"  FAILED: {name}  {detail}")
sys.exit(1 if bad else 0)
