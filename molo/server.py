"""API HTTP e WebSocket. È il cuore condiviso: la stessa istanza serve la
finestra sul Mac, il browser su Windows e il telefono sulla rete di casa."""

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
    """Manda a tutti i client connessi. I socket morti si potano al volo."""
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
    policy.set_strict(settings.strict_policy)
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
# Accesso
#
# In locale nessun attrito. Appena il server è raggiungibile dalla rete (che è
# il modo in cui lo usi dal telefono) serve il token: senza, chiunque sia
# connesso al wifi potrebbe far scrivere file sul tuo disco.
# ---------------------------------------------------------------------------
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api") or path == "/ws":
        if not _authorized(request.client.host if request.client else "", dict(request.query_params),
                           request.headers.get("x-molo-token", "")):
            return JSONResponse({"error": "Token mancante o errato"}, status_code=401)

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
# Statici
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
    data.pop("token", None)  # non esce mai dal server via API
    return data


@app.post("/api/probe")
async def probe(payload: dict) -> dict:
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "URL mancante")
    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, engine.probe, url)
    except policy.PolicyError as exc:
        raise HTTPException(451, str(exc))  # 451: rifiutato per ragioni legali
    except Exception as exc:
        raise HTTPException(400, engine._short(str(exc), 300))
    return engine.summarize(info)


@app.post("/api/jobs")
async def create_jobs(payload: dict) -> dict:
    preset = payload.get("preset")
    urls = payload.get("urls") or ([payload["url"]] if payload.get("url") else [])
    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        raise HTTPException(400, "Nessun URL")
    try:
        created = await manager.add_many(urls, preset)
    except policy.PolicyError as exc:
        raise HTTPException(451, str(exc))
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
        raise HTTPException(404, "Job non ripetibile")
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
            raise HTTPException(400, f"Cartella non utilizzabile: {exc}")
        payload["download_dir"] = str(path)
    settings.update(payload)
    # La modalità rigorosa vive anche in una variabile di modulo in policy.py:
    # va riallineata subito, o la modifica avrebbe effetto solo al riavvio.
    policy.set_strict(settings.strict_policy)
    await broadcast({"type": "settings", "settings": _settings_payload()})
    return {"settings": _settings_payload(), "lan": {"enabled": settings.allow_lan, "url": lan_url()}}


@app.post("/api/update-ytdlp")
async def update_ytdlp() -> dict:
    loop = asyncio.get_running_loop()
    ok, message = await loop.run_in_executor(None, engine.update_ytdlp)
    return {"ok": ok, "message": message, "version": engine.current_version()}


@app.get("/api/pairing")
async def pairing() -> dict:
    """Il link con token da aprire sul telefono."""
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
        raise HTTPException(400, "URL mancante")
    verdict = policy.check_url(url)
    if not verdict.allowed:
        raise HTTPException(451, verdict.message)
    watcher = watch_store.add(url, payload.get("preset") or settings.preset,
                              int(payload.get("interval_minutes") or 60))
    asyncio.create_task(watch_loop.check(watcher))  # primo censimento subito
    return {"watchers": watch_store.public()}


@app.delete("/api/watchers/{watcher_id}")
async def remove_watcher(watcher_id: str) -> dict:
    watch_store.remove(watcher_id)
    return {"watchers": watch_store.public()}


@app.post("/api/watchers/{watcher_id}/check")
async def check_watcher(watcher_id: str) -> dict:
    watcher = watch_store.items.get(watcher_id)
    if not watcher:
        raise HTTPException(404, "Monitor inesistente")
    found = await watch_loop.check(watcher)
    return {"new": found, "watchers": watch_store.public()}


@app.post("/api/reveal")
async def reveal(payload: dict) -> dict:
    """Apre il file nel gestore file del sistema. Solo da locale: aprire finestre
    sul computer di qualcun altro attraverso la rete non ha senso."""
    target = Path(payload.get("path") or settings.download_dir).expanduser()
    if not target.exists():
        raise HTTPException(404, "Percorso inesistente")
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
    if not _authorized(host, dict(ws.query_params), ws.headers.get("x-molo-token", "")):
        await ws.close(code=4401)
        return
    await ws.accept()
    sockets.add(ws)
    try:
        await ws.send_json({"type": "hello", "jobs": manager.snapshot() if manager else []})
        while True:
            await ws.receive_text()  # tiene aperta la connessione
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        sockets.discard(ws)


# ---------------------------------------------------------------------------
# Automatismi di sistema
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
    """Se copi un link, Molo lo propone. Non scarica niente da solo: propone.

    Un download automatico a ogni copia sarebbe un ottimo modo per riempire il
    disco per sbaglio.
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
    """Un controllo all'avvio, senza bloccare la partenza dell'interfaccia."""
    await asyncio.sleep(3)
    loop = asyncio.get_running_loop()
    try:
        ok, message = await loop.run_in_executor(None, engine.update_ytdlp)
    except Exception:
        return
    if ok and "aggiornato:" in message:
        await broadcast({"type": "toast", "level": "ok", "message": message})


def lan_url() -> str:
    """L'indirizzo da digitare sul telefono. Nessun pacchetto lascia la rete locale."""
    if not settings.allow_lan:
        return ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(("192.168.255.255", 1))  # non invia nulla, serve solo a scegliere l'interfaccia
            ip = sock.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    return f"http://{ip}:{settings.port}"
