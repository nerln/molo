"""The download queue: persistence, concurrency, events out to the interface."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from . import config, engine, policy

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"
SKIPPED = "skipped"

TERMINAL = {DONE, ERROR, CANCELLED, SKIPPED}


class StoreUnwritable(Exception):
    """The queue database cannot be written to."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    title       TEXT,
    uploader    TEXT,
    thumbnail   TEXT,
    preset      TEXT NOT NULL,
    status      TEXT NOT NULL,
    progress    REAL DEFAULT 0,
    speed       REAL,
    eta         INTEGER,
    total_bytes INTEGER,
    filepath    TEXT,
    error       TEXT,
    note        TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created_at DESC);
"""


class Store:
    """SQLite behind a lock. The volume is a few rows per second; nothing more is needed."""

    def __init__(self, path: Path) -> None:
        self.path = path          # named in the error when writes start failing
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            # A job left "running" after a restart is a leftover: no thread is
            # following it any more. Send it back to the queue, the partial
            # file on disk makes it resume rather than start over.
            self._db.execute("UPDATE jobs SET status=? WHERE status=?", (QUEUED, RUNNING))
            self._db.commit()

    def insert(self, job: dict) -> None:
        cols = ",".join(job)
        marks = ",".join("?" * len(job))
        try:
            with self._lock:
                self._db.execute(f"INSERT INTO jobs ({cols}) VALUES ({marks})", list(job.values()))
                self._db.commit()
        except sqlite3.OperationalError as exc:
            # A full disk, a revoked permission, or the file deleted out from
            # under a running process all arrive here as one opaque message.
            # Untranslated it surfaced as a bare 500 on every single add, with
            # nothing on screen to say what had gone wrong.
            raise StoreUnwritable(
                f"Molo cannot write its queue database at {self.path}. "
                f"Check there is free disk space and that the file is writable. "
                f"({exc})"
            ) from exc

    def patch(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = time.time()
        sets = ",".join(f"{k}=?" for k in fields)
        with self._lock:
            self._db.execute(
                f"UPDATE jobs SET {sets} WHERE id=?", [*fields.values(), job_id]
            )
            self._db.commit()

    def all(self, limit: int = 300) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def pending(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY created_at ASC", (QUEUED,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_finished(self) -> int:
        with self._lock:
            cur = self._db.execute(
                "DELETE FROM jobs WHERE status IN (?,?,?,?)", (DONE, ERROR, CANCELLED, SKIPPED)
            )
            self._db.commit()
            return cur.rowcount


class Manager:
    """Takes jobs off the queue and runs them within the concurrency limit."""

    def __init__(self, settings, broadcast: Callable[[dict], Any]) -> None:
        self.settings = settings
        self.store = Store(config.db_path())
        self.broadcast = broadcast
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._cancels: dict[str, threading.Event] = {}
        self._workers: list[asyncio.Task] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_emit: dict[str, float] = {}
        # Two jobs for the same URL at once write to the same temporary files
        # and corrupt each other. Queue the same link twice at two qualities
        # and you get one broken download and one confusing error. One lock
        # per URL keeps them in single file without slowing anything else.
        self._url_locks: dict[str, asyncio.Lock] = {}

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        for job in self.store.pending():  # pick up whatever was left hanging
            await self._queue.put(job["id"])
        for _ in range(max(1, self.settings.max_concurrent)):
            self._workers.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        for event in self._cancels.values():
            event.set()
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    # -- API ----------------------------------------------------------------

    async def add(self, url: str, preset_key: str | None = None, meta: dict | None = None) -> dict:
        preset_key = preset_key or self.settings.preset
        if preset_key not in engine.PRESETS:
            raise ValueError(f"Unknown preset: {preset_key}")

        verdict = policy.check_url(url)
        if not verdict.allowed:
            raise policy.PolicyError(verdict.message)

        meta = meta or {}
        now = time.time()
        job = {
            "id": uuid.uuid4().hex[:12],
            "url": url,
            "title": meta.get("title") or url,
            "uploader": meta.get("uploader") or "",
            "thumbnail": meta.get("thumbnail") or "",
            "preset": preset_key,
            "status": QUEUED,
            "progress": 0.0,
            "speed": None,
            "eta": None,
            "total_bytes": None,
            "filepath": None,
            "error": None,
            "note": meta.get("note") or "",
            "created_at": now,
            "updated_at": now,
        }
        self.store.insert(job)
        await self._queue.put(job["id"])
        await self._emit({"type": "job", "job": job})
        return job

    async def add_many(self, urls: list[str], preset_key: str | None = None) -> list[dict]:
        return [await self.add(u, preset_key) for u in urls]

    async def cancel(self, job_id: str) -> bool:
        event = self._cancels.get(job_id)
        if event:
            event.set()
            return True
        job = self.store.get(job_id)
        if job and job["status"] == QUEUED:
            self.store.patch(job_id, status=CANCELLED)
            await self._emit({"type": "job", "job": self.store.get(job_id)})
            return True
        return False

    async def retry(self, job_id: str) -> dict | None:
        job = self.store.get(job_id)
        if not job or job["status"] not in TERMINAL:
            return None
        return await self.add(job["url"], job["preset"], {"title": job["title"], "thumbnail": job["thumbnail"]})

    async def clear(self) -> int:
        count = self.store.delete_finished()
        await self._emit({"type": "cleared"})
        return count

    def snapshot(self) -> list[dict]:
        return self.store.all()

    # -- internals ----------------------------------------------------------

    async def _worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._run(job_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # one job must never kill the worker
                self.store.patch(job_id, status=ERROR, error=str(exc)[:400])
                await self._emit({"type": "job", "job": self.store.get(job_id)})
            finally:
                self._queue.task_done()

    async def _run(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if not job or job["status"] != QUEUED:
            return

        cancel = threading.Event()
        self._cancels[job_id] = cancel
        self.store.patch(job_id, status=RUNNING, error=None)
        await self._emit({"type": "job", "job": self.store.get(job_id)})

        # The real title is fetched here: at insert time we only had the URL,
        # and probing during add would make the interface feel sluggish.
        loop = asyncio.get_running_loop()
        if job["title"] == job["url"]:
            try:
                info = await loop.run_in_executor(None, engine.probe, job["url"])
                summary = engine.summarize(info)
                self.store.patch(
                    job_id,
                    title=summary.get("title") or job["url"],
                    uploader=summary.get("uploader") or "",
                    thumbnail=summary.get("thumbnail") or "",
                )
                await self._emit({"type": "job", "job": self.store.get(job_id)})
            except policy.PolicyError as exc:
                self._cancels.pop(job_id, None)
                self.store.patch(job_id, status=ERROR, error=str(exc))
                await self._emit({"type": "job", "job": self.store.get(job_id)})
                return
            except Exception:
                pass  # the title is a luxury, the download is not

        preset = engine.PRESETS[job["preset"]]
        archive = config.archive_path() if self.settings.write_archive else None
        lock = self._url_locks.setdefault(job["url"], asyncio.Lock())

        def on_progress(d: dict) -> None:
            loop.call_soon_threadsafe(self._progress, job_id, d)

        try:
            async with lock:
                result = await loop.run_in_executor(
                    None,
                    engine.download,
                    job["url"],
                    self.settings,
                    preset,
                    on_progress,
                    cancel,
                    archive,
                )
            if result.get("skipped"):
                self.store.patch(job_id, status=SKIPPED, progress=100, note="skipped")
            else:
                self.store.patch(
                    job_id,
                    status=DONE,
                    progress=100,
                    filepath=result.get("filepath"),
                    # A machine-readable note, rendered per language in the
                    # interface. Prose here would pin the app to one language.
                    # One attempt is the normal case and worth no words.
                    note=(
                        "nocover" if result.get("cosmetic_error")
                        else f"attempts:{result['attempts']}" if result.get("attempts", 1) > 1
                        else ""
                    ),
                )
        except engine.Cancelled:
            self.store.patch(job_id, status=CANCELLED)
        except policy.PolicyError as exc:
            self.store.patch(job_id, status=ERROR, error=str(exc), note="why:drm")
        except Exception as exc:
            # The note carries a diagnosis the interface turns into advice.
            # "It failed" sends people hunting for a setting that does not exist.
            why = engine.diagnose(str(exc))
            self.store.patch(
                job_id,
                status=ERROR,
                error=engine._short(str(exc), 400),
                note=f"why:{why}" if why else "",
            )
        finally:
            self._cancels.pop(job_id, None)
            self._last_emit.pop(job_id, None)
            await self._emit({"type": "job", "job": self.store.get(job_id)})

    def _progress(self, job_id: str, d: dict) -> None:
        """Runs on the loop, called from yt-dlp's thread. Has to stay cheap."""
        status = d.get("status")

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            pct = (done / total * 100) if total else 0.0

            # yt-dlp fires up to fifty hooks a second. Without this throttle
            # the WebSocket and SQLite become the bottleneck.
            now = time.monotonic()
            if now - self._last_emit.get(job_id, 0) < 0.4 and pct < 100:
                return
            self._last_emit[job_id] = now

            self.store.patch(
                job_id,
                progress=round(pct, 2),
                speed=d.get("speed"),
                eta=d.get("eta"),
                total_bytes=total,
            )
            asyncio.create_task(
                self._emit(
                    {
                        "type": "progress",
                        "id": job_id,
                        "progress": round(pct, 2),
                        "speed": d.get("speed"),
                        "eta": d.get("eta"),
                        "total_bytes": total,
                    }
                )
            )
        elif status in {"recovering", "retrying"}:
            note = (
                f"retry:{d.get('attempt')}:{d.get('wait')}"
                if status == "retrying"
                else f"recover:{d.get('error', '')}"
            )
            self.store.patch(job_id, note=note)
            asyncio.create_task(self._emit({"type": "note", "id": job_id, "note": note}))
        elif status == "postprocessing":
            note = f"process:{d.get('postprocessor', '')}"
            self.store.patch(job_id, note=note)
            asyncio.create_task(self._emit({"type": "note", "id": job_id, "note": note}))

    async def _emit(self, message: dict) -> None:
        result = self.broadcast(message)
        if asyncio.iscoroutine(result):
            await result


def presets_payload() -> list[dict]:
    return [
        {"key": p.key, "label": p.label, "hint": p.hint, "audio_only": p.audio_only}
        for p in engine.PRESETS.values()
    ]
