"""Watchers: channels and playlists that download themselves when something new appears.

Each watcher keeps the list of ids it has already seen. On the first pass it
records everything and downloads nothing — otherwise adding a channel with 800
videos would fill your disk — and from then on it queues only what is new.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yt_dlp

from . import config


@dataclass
class Watcher:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    url: str = ""
    title: str = ""
    preset: str = "best_compat"
    interval_minutes: int = 60
    enabled: bool = True
    last_check: float = 0.0
    last_new: int = 0
    seen: list[str] = field(default_factory=list)
    error: str = ""

    def public(self) -> dict:
        data = asdict(self)
        data["seen_count"] = len(self.seen)
        data.pop("seen")
        return data


class WatchStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.data_dir() / "watchers.json")
        self.items: dict[str, Watcher] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in raw:
            known = {k: v for k, v in item.items() if k in Watcher.__dataclass_fields__}
            watcher = Watcher(**known)
            self.items[watcher.id] = watcher

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(w) for w in self.items.values()], indent=2), "utf-8")
        tmp.replace(self.path)

    def add(self, url: str, preset: str, interval: int, title: str = "") -> Watcher:
        watcher = Watcher(url=url, preset=preset, interval_minutes=max(5, interval), title=title or url)
        self.items[watcher.id] = watcher
        self.save()
        return watcher

    def remove(self, watcher_id: str) -> bool:
        if self.items.pop(watcher_id, None):
            self.save()
            return True
        return False

    def toggle(self, watcher_id: str, enabled: bool) -> Watcher | None:
        watcher = self.items.get(watcher_id)
        if watcher:
            watcher.enabled = enabled
            self.save()
        return watcher

    def public(self) -> list[dict]:
        return [w.public() for w in self.items.values()]


def _list_entries(url: str) -> tuple[str, list[dict]]:
    """Flat listing: reads the playlist without opening every single video."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "playlistend": 60,  # new items are at the top; the rest is history
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.sanitize_info(ydl.extract_info(url, download=False))
    entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
    return info.get("title") or url, entries


class WatchLoop:
    """The polling loop. One task for every watcher: they are few and slow."""

    def __init__(self, store: WatchStore, manager, broadcast) -> None:
        self.store = store
        self.manager = manager
        self.broadcast = broadcast
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # one broken watcher must not stop the others
            await asyncio.sleep(60)

    async def _tick(self) -> None:
        now = time.time()
        for watcher in list(self.store.items.values()):
            if not watcher.enabled:
                continue
            if now - watcher.last_check < watcher.interval_minutes * 60:
                continue
            await self.check(watcher)

    async def check(self, watcher: Watcher) -> int:
        loop = asyncio.get_running_loop()
        watcher.last_check = time.time()
        try:
            title, entries = await loop.run_in_executor(None, _list_entries, watcher.url)
        except Exception as exc:
            watcher.error = str(exc)[:200]
            self.store.save()
            await self._notify()
            return 0

        watcher.error = ""
        if not watcher.title or watcher.title == watcher.url:
            watcher.title = title

        known = set(watcher.seen)
        fresh = [e for e in entries if e["id"] not in known]

        if not known:
            # First pass: take note, nothing else. No surprise downloads.
            watcher.seen = [e["id"] for e in entries]
            watcher.last_new = 0
            self.store.save()
            await self._notify()
            return 0

        for entry in fresh:
            url = entry.get("url") or entry.get("webpage_url")
            if not url:
                continue
            await self.manager.add(
                url,
                watcher.preset,
                {"title": entry.get("title") or url, "note": f"from:{watcher.title}"},
            )
            watcher.seen.append(entry["id"])

        watcher.seen = watcher.seen[-2000:]  # cap the file's growth
        watcher.last_new = len(fresh)
        self.store.save()
        await self._notify()
        return len(fresh)

    async def _notify(self) -> None:
        result = self.broadcast({"type": "watchers", "watchers": self.store.public()})
        if asyncio.iscoroutine(result):
            await result
