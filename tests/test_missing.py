"""A finished download whose file was deleted outside Molo.

Reported on 19/10/2026: a file removed with a forced delete kept showing as
done, with a Show file button that could only fail. The row is worth keeping,
since it is the only record of what you had and the only thing that knows how
to fetch it again, so it stays and says what happened instead.
"""

import asyncio

import pytest

from molo import config, jobs


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path)
    return tmp_path


def _done(path, **extra):
    return {"id": "j1", "status": jobs.DONE, "filepath": str(path), **extra}


def test_a_present_file_is_not_missing(tmp_path):
    f = tmp_path / "song [abc123xyz].webm"
    f.write_bytes(b"x")
    assert jobs._decorate(_done(f))["file_missing"] is False


def test_a_deleted_file_is_missing(tmp_path):
    assert jobs._decorate(_done(tmp_path / "gone [abc123xyz].webm"))["file_missing"] is True


@pytest.mark.parametrize("status", [jobs.QUEUED, jobs.RUNNING, jobs.ERROR, jobs.SKIPPED])
def test_only_finished_jobs_can_be_missing(tmp_path, status):
    """A queued job has no file yet, which is not the same as having lost it."""
    job = {"id": "j", "status": status, "filepath": str(tmp_path / "nope.webm")}
    assert jobs._decorate(job)["file_missing"] is False


def test_the_archive_line_goes_and_the_others_stay(data):
    archive = config.archive_path()
    archive.write_text("youtube aaaaaaaaaaa\nyoutube W26wpmlIMuA\nvimeo 123456789\n", "utf-8")

    manager = jobs.Manager(config.Settings(), lambda m: None)
    manager._forget_in_archive("W26wpmlIMuA")

    assert archive.read_text("utf-8") == "youtube aaaaaaaaaaa\nvimeo 123456789\n"


def test_the_id_is_found_with_or_without_the_column(data):
    manager = jobs.Manager(config.Settings(), lambda m: None)
    assert manager._video_id_of({"video_id": "fromcolumn1"}) == "fromcolumn1"
    # Jobs finished before 1.0.2 have no column, but the name carries the id.
    assert manager._video_id_of({"filepath": "/x/Title [W26wpmlIMuA].webm"}) == "W26wpmlIMuA"
    assert manager._video_id_of({"filepath": None}) is None


def test_redownload_bypasses_the_archive_even_without_an_id(data):
    """The case met for real: a SKIPPED job has no filepath and no id, so no
    archive line can be found, and without the bypass the repeat is skipped
    again forever."""
    async def scenario():
        manager = jobs.Manager(config.Settings(), lambda m: None)
        first = await manager.add("https://www.youtube.com/watch?v=W26wpmlIMuA", "audio_best")
        manager.store.patch(first["id"], status=jobs.SKIPPED)

        fresh = await manager.redownload(first["id"])
        assert fresh and fresh["id"] != first["id"]
        assert fresh["id"] in manager._ignore_archive

    asyncio.run(scenario())


def test_an_old_database_gains_the_column(tmp_path):
    """1.0.1 databases have no video_id. CREATE TABLE IF NOT EXISTS will not
    add one, so the migration has to."""
    import sqlite3

    db = tmp_path / "molo.db"
    con = sqlite3.connect(db)
    con.executescript(jobs.SCHEMA.replace("    note        TEXT,\n", "    note        TEXT,\n"))
    con.close()

    jobs.Store(db)
    cols = {row[1] for row in sqlite3.connect(db).execute("PRAGMA table_info(jobs)")}
    assert "video_id" in cols
