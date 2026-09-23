"""Opt-in database checks against an already migrated PostgreSQL/pgvector database.

Only uniquely named test rows are created and removed; no schema is dropped.
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.session import dispose_engine, get_sessionmaker
from app.models.entities import Repository
from app.services.store import Store


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL for pgvector integration"
)
@pytest.mark.asyncio
async def test_persistence_vector_search_and_repository_isolation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    get_settings.cache_clear()
    store, ids = Store(), []
    try:
        for number in range(2):
            detail = {"created_at": "2026-09-21T00:00:00Z", "updated_at": "2026-09-21T00:00:00Z"}
            row, queued = await store.queue("test-" + str(uuid4()), detail, False)
            ids.append(row.id)
            assert queued
            await store.progress(row.id, "PARSING_CODE", 35)
            assert (await store.get(row.id)).status == "ANALYZING"
            file = {"path": "main.py", "content": "def run(): return 1", "symbols": []}
            chunk = {
                "file_path": "main.py",
                "content": file["content"],
                "start_line": 1,
                "end_line": 1,
                "symbol": "run",
            }
            vector = [0.0] * 768
            vector[number] = 1.0
            await store.publish(
                row.id,
                detail,
                {"files": [file], "chunks": [chunk]},
                {"modules": []},
                [vector],
                "test-model",
            )
        matches = await store.retrieve(ids[0], [1.0] + [0.0] * 767, "test-model")
        assert len(matches) == 1 and matches[0]["similarity"] == pytest.approx(1.0)
        assert matches[0]["source"]["file_path"] == "main.py"
        assert len(await store.embedding_cache(ids[0], "test-model")) == 1
        assert (await store.files(ids[0]))[0]["path"] == "main.py"
        assert (await store.get(ids[0])).status == "COMPLETED"
        _, queued = await store.queue((await store.get(ids[0])).key, {}, False)
        assert not queued
    finally:
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(delete(Repository).where(Repository.id.in_(ids)))
        await dispose_engine()
        get_settings.cache_clear()
