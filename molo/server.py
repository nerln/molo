"""HTTP and WebSocket API. One shared core: the same instance serves the
window on the Mac, the browser on Windows, and the phone on your network."""

from __future__ import annotations

import asyncio
import platform
import re
import socket
import subprocess
import sys
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, engine, jobs, policy, watch

URL_RE = re.compile(r"https?://[^\s<>\"']{6,}")

settings = config.Settings.load()
manager: jobs.Manager | None = None
watch_store = watch.WatchStore()
watch_loop: watch.WatchLoop | None = None
sockets: set[WebSocket] = set()


async def broadcast(message: dict) -> None:
    """Send to every connected client, pruning dead sockets as we go."""
    dead = []
    for ws in list(sockets):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global manager, watch_loop
    manager = jobs.Manager(settings, broadcast)
    await manager.start()

    watch_loop = watch.WatchLoop(watch_store, manager, broadcast)
    watch_loop.start()

    tasks = [asyncio.create_task(_clipboard_loop())] if settings.watch_clipboard else []
    if settings.auto_update_ytdlp:
        tasks.append(asyncio.create_task(_auto_update()))

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*tasks, return_exceptions=True)
        if watch_loop:
            await watch_loop.stop()
        if manager:
            await manager.stop()


app = FastAPI(title="Molo", version=config.VERSION, lifespan=lifespan)


# ---------------------------------------------------------------------------
# Access
#
# No friction locally. The moment the server is reachable from the network,
# which is how you use it from a phone, the token is required: without it,
# anyone on the same wifi could make your machine write files to disk.
# ---------------------------------------------------------------------------
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _bare_host(value: str) -> str:
    """Host without the port, IPv6 brackets stripped."""
    host = (value or "").split(",")[0].strip().lower()
    if host.startswith("["):
        return host[1:].split("]")[0]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def allowed_host(header: str) -> bool:
    """Is this `Host:` one of ours?

    Binding to 127.0.0.1 is not a defence on its own. A page on any website
    can point a name it controls at 127.0.0.1, and the browser will happily
    send the request to this server with that name in the Host header: DNS
    rebinding. Without this check `GET /api/pairing` handed out the per-install
    token to anyone who could get a browser to ask, which defeats the point of
    having a token at all. The port range is small and fixed, so discovery is
    not a barrier either.
    """
    host = _bare_host(header)
    if host in LOOPBACK or host == "":
        return True
    if settings.allow_lan:
        # The address we hand out in the pairing link, and nothing else.
        lan = lan_url().replace("http://", "").rsplit(":", 1)[0]
        if lan and host == lan:
            return True
    return False


def allowed_origin(header: str) -> bool:
    """WebSockets have no same-origin policy of their own.

    Any page the user visits can open ws://127.0.0.1:7788/ws, and the server
    used to accept it and immediately send every job URL and file path in the
    hello frame. A browser always sends Origin on a WebSocket handshake, so a
    missing one means a non-browser client, which is fine.
    """
    if not header:
        return True
    origin = header.strip().lower()
    for scheme in ("http://", "https://", "ws://", "wss://"):
        if origin.startswith(scheme):
            return allowed_host(origin[len(scheme):])
    return False


@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path

    # Host first: a rebound name is a different problem from a missing token,
    # and it has to be refused before anything else reads the request.
    if not allowed_host(request.headers.get("host", "")):
        return JSONResponse({"detail": "Unrecognised Host header"}, status_code=400)

    if path.startswith("/api") or path == "/ws":
        if not allowed_origin(request.headers.get("origin", "")):
            return JSONResponse({"detail": "Cross-origin request refused"}, status_code=403)
        if not _authorized(request.client.host if request.client else "", dict(request.query_params),
                           request.headers.get("x-molo-token", "")):
            return JSONResponse({"detail": "Missing or wrong access key"}, status_code=401)

    response = await call_next(request)

    # Senza questa riga il browser applica la propria euristica di freschezza a
    # `/` e a `/static/*`, che non hanno un hash nel nome: dopo un aggiornamento
    # di Molo ti ritroveresti l'interfaccia vecchia senza capire perché.
    # `no-cache` non disattiva la cache, impone di rivalidare: con l'ETag la
    # risposta resta un 304 di pochi byte quando il file non è cambiato.
    if path == "/" or path.startswith("/static") or path.endswith((".js", ".webmanifest")):
        response.headers["Cache-Control"] = "no-cache"

    return response


def _authorized(host: str, params: dict, header: str) -> bool:
    if host in LOOPBACK:
        return True
    return (params.get("token") or header) == settings.token


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
WEB = config.web_dir()
app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/manifest.webmanifest")
async def manifest() -> FileResponse:
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    return FileResponse(WEB / "sw.js", media_type="application/javascript")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.get("/api/state")
async def state() -> dict:
    return {
        "version": config.VERSION,
        "ytdlp": engine.current_version(),
        "ffmpeg": engine.ffmpeg_available(),
        "ffmpeg_path": engine.find_ffmpeg() or "",
        "presets": jobs.presets_payload(),
        "settings": _settings_payload(),
        "jobs": manager.snapshot() if manager else [],
        "watchers": watch_store.public(),
        "lan": {"enabled": settings.allow_lan, "url": lan_url()},
        "platform": platform.system(),
    }


def _settings_payload() -> dict:
    from dataclasses import asdict

    data = asdict(settings)
    data.pop("token", None)  # never leaves the server through the API  # non esce mai dal server via API
    return data


@app.post("/api/probe")
async def probe(payload: dict) -> dict:
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "No URL given")
    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, engine.probe, url)
    except policy.PolicyError as exc:
        raise HTTPException(451, str(exc))  # 451: refused for legal reasons
    except Exception as exc:
        raise HTTPException(400, engine._short(str(exc), 300))
    return engine.summarize(info)


@app.post("/api/jobs")
async def create_jobs(payload: dict) -> dict:
    preset = payload.get("preset")
    urls = payload.get("urls") or ([payload["url"]] if payload.get("url") else [])
    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        raise HTTPException(400, "No URL given")
    try:
        created = await manager.add_many(urls, preset)
    except policy.PolicyError as exc:
        raise HTTPException(451, str(exc))
    except jobs.StoreUnwritable as exc:
        # 507: the request was fine, the machine cannot store the result.
        raise HTTPException(507, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"created": created}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    return {"ok": await manager.cancel(job_id)}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str) -> dict:
    job = await manager.retry(job_id)
    if not job:
        raise HTTPException(404, "That job cannot be retried")
    return {"job": job}


@app.post("/api/jobs/{job_id}/redownload")
async def redownload_job(job_id: str) -> dict:
    """Fetch again a file that is no longer on disk.

    Not the same as retry: this one also clears the video from the download
    archive, which would otherwise turn the repeat into a no-op.
    """
    job = await manager.redownload(job_id)
    if not job:
        raise HTTPException(404, "That job cannot be downloaded again")
    return {"job": job}


@app.delete("/api/jobs")
async def clear_jobs() -> dict:
    return {"removed": await manager.clear()}


@app.post("/api/settings")
async def update_settings(payload: dict) -> dict:
    if "download_dir" in payload:
        path = Path(payload["download_dir"]).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(400, f"That folder cannot be used: {exc}")
        payload["download_dir"] = str(path)
    try:
        settings.update(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await broadcast({"type": "settings", "settings": _settings_payload()})
    return {"settings": _settings_payload(), "lan": {"enabled": settings.allow_lan, "url": lan_url()}}


@app.post("/api/update-ytdlp")
async def update_ytdlp() -> dict:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, engine.update_ytdlp)
    return {
        "ok": result.ok,
        "message": result.message,
        # `version` is the engine running right now, which a successful update
        # does not change: the new one is on disk and starts being used at the
        # next launch. `pending` is what that will be.
        "version": engine.current_version(),
        "pending": result.after if result.changed else "",
    }


@app.get("/api/pairing")
async def pairing() -> dict:
    """The tokenised link to open on the phone."""
    url = lan_url()
    return {
        "enabled": settings.allow_lan,
        "url": f"{url}/?token={settings.token}" if url else "",
        "token": settings.token,
    }


@app.post("/api/watchers")
async def add_watcher(payload: dict) -> dict:
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "No URL given")
    verdict = policy.check_url(url)
    if not verdict.allowed:
        raise HTTPException(451, verdict.message)
    watcher = watch_store.add(url, payload.get("preset") or settings.preset,
                              int(payload.get("interval_minutes") or 60))
    asyncio.create_task(watch_loop.check(watcher))  # take the first census now
    return {"watchers": watch_store.public()}


@app.delete("/api/watchers/{watcher_id}")
async def remove_watcher(watcher_id: str) -> dict:
    watch_store.remove(watcher_id)
    return {"watchers": watch_store.public()}


@app.post("/api/watchers/{watcher_id}/check")
async def check_watcher(watcher_id: str) -> dict:
    watcher = watch_store.items.get(watcher_id)
    if not watcher:
        raise HTTPException(404, "No such watcher")
    found = await watch_loop.check(watcher)
    return {"new": found, "watchers": watch_store.public()}


@app.post("/api/reveal")
async def reveal(payload: dict) -> dict:
    """Reveal the file in the system file manager. Local only: opening windows
    on someone else's computer over the network makes no sense."""
    target = Path(payload.get("path") or settings.download_dir).expanduser()

    # A file can be moved or deleted between finishing and being clicked on.
    # Falling back to the folder is more use than a red error, so we only
    # refuse when there is nothing sensible left to open.
    if not target.exists():
        for fallback in (target.parent, Path(settings.download_dir).expanduser()):
            if fallback.is_dir():
                target = fallback
                break
        else:
            raise HTTPException(404, "That file is no longer where Molo left it")

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(target)], check=False, timeout=10)
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", f"/select,{target}"], check=False, timeout=10)
        else:
            subprocess.run(["xdg-open", str(target.parent)], check=False, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(500, str(exc))
    return {"ok": True}


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    host = ws.client.host if ws.client else ""

    # The HTTP middleware never sees a WebSocket handshake, so these two checks
    # have to be repeated here. Without them any page the user happened to
    # visit could open this socket and read the hello frame, which carries
    # every job URL and file path on the machine.
    if not allowed_host(ws.headers.get("host", "")) or not allowed_origin(ws.headers.get("origin", "")):
        await ws.close(code=4403)
        return

    if not _authorized(host, dict(ws.query_params), ws.headers.get("x-molo-token", "")):
        await ws.close(code=4401)
        return
    await ws.accept()
    sockets.add(ws)
    try:
        await ws.send_json({"type": "hello", "jobs": manager.snapshot() if manager else []})
        while True:
            await ws.receive_text()  # keeps the connection open
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        sockets.discard(ws)


# ---------------------------------------------------------------------------
# System-level automation
# ---------------------------------------------------------------------------
def _read_clipboard() -> str:
    try:
        if sys.platform == "darwin":
            return subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=4).stdout
        if sys.platform.startswith("win"):
            return subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=6,
            ).stdout
        for cmd in (["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"]):
            try:
                return subprocess.run(cmd, capture_output=True, text=True, timeout=4).stdout
            except FileNotFoundError:
                continue
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


async def _clipboard_loop() -> None:
    """Copy a link and Molo offers it. It offers; it does not download.

    Downloading automatically on every copy would be an excellent way to fill
    a disk by accident.
    """
    loop = asyncio.get_running_loop()
    last = ""
    while True:
        await asyncio.sleep(1.5)
        if not settings.watch_clipboard:
            continue
        try:
            text = (await loop.run_in_executor(None, _read_clipboard)).strip()
        except Exception:
            continue
        if not text or text == last or len(text) > 2000:
            continue
        last = text
        match = URL_RE.search(text)
        if not match:
            continue
        url = match.group(0)
        if not policy.check_url(url).allowed:
            continue
        await broadcast({"type": "clipboard", "url": url})


async def _auto_update() -> None:
    """One check at startup, without holding up the interface.

    This used to decide whether to say anything by looking for the word
    "aggiornato:" in a message the engine writes in English, so it never said
    anything at all. `Result.changed` is the same answer as a fact instead of a
    guess about wording.
    """
    await asyncio.sleep(3)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, engine.update_ytdlp)
    except Exception:
        return
    if result.changed:
        await broadcast({"type": "toast", "level": "ok", "message": result.message})


def lan_url() -> str:
    """The address to type on the phone. No packet leaves the local network."""
    if not settings.allow_lan:
        return ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(("192.168.255.255", 1))  # sends nothing; just picks the interface
            ip = sock.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    return f"http://{ip}:{settings.port}"
