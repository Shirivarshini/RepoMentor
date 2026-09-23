"""PostgreSQL persistence; all snapshots publish in one transaction."""

import hashlib
from typing import Any

from sqlalchemy import delete, select, text

from app.db.session import get_sessionmaker
from app.models.entities import (
    Answer,
    CodeChunk,
    CodeSymbol,
    Embedding,
    Question,
    Repository,
    RepositoryAnalysis,
    RepositoryFile,
    SourceReference,
    now,
    uid,
)


class Store:
    async def get(self, repository_id: str) -> Any:
        async with get_sessionmaker()() as session:
            return await session.get(Repository, repository_id)

    async def queue(self, key: str, detail: dict[str, Any], force: bool) -> Any:
        async with get_sessionmaker()() as session, session.begin():
            # Serializes creation as well as re-analysis across requests.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key}
            )
            row = await session.scalar(
                select(Repository).where(Repository.key == key).with_for_update()
            )
            if row and (
                row.status in {"QUEUED", "ANALYZING"} or row.status == "COMPLETED" and not force
            ):
                return row, False
            if row is None:
                row = Repository(id=uid(), key=key)
                session.add(row)
            detail["repository_id"] = row.id
            if row.detail:
                detail["created_at"] = row.detail["created_at"]
            row.detail = detail
            row.status = "QUEUED"
            row.progress = {
                "repository_id": row.id,
                "status": "QUEUED",
                "stage": None,
                "progress": 0,
                "message": "Waiting for analysis.",
                "error": None,
                "updated_at": detail["updated_at"],
            }
            row.updated_at = now()
            return row, True

    async def progress(self, repository_id: str, stage: str, progress: int) -> Any:
        async with get_sessionmaker()() as session, session.begin():
            row = await session.get(Repository, repository_id)
            assert row is not None
            timestamp = now().isoformat().replace("+00:00", "Z")
            row.status = "ANALYZING"
            row.updated_at = now()
            row.detail = {**row.detail, "status": "ANALYZING", "updated_at": timestamp}
            row.progress = {
                **row.progress,
                "status": "ANALYZING",
                "stage": stage,
                "progress": progress,
                "message": stage.replace("_", " ").capitalize(),
                "updated_at": timestamp,
            }

    async def fail(self, repository_id: str, code: str, message: str) -> Any:
        async with get_sessionmaker()() as session, session.begin():
            row = await session.get(Repository, repository_id)
            assert row is not None
            timestamp = now().isoformat().replace("+00:00", "Z")
            error = {"code": code, "message": message}
            row.status = "FAILED"
            row.updated_at = now()
            row.detail = {**row.detail, "status": "FAILED", "error": error, "updated_at": timestamp}
            row.progress = {
                **row.progress,
                "status": "FAILED",
                "error": error,
                "message": message,
                "updated_at": timestamp,
            }

    async def embedding_cache(self, repository_id: str, model: str) -> dict[str, Any]:
        async with get_sessionmaker()() as session:
            rows = await session.execute(
                select(CodeChunk.content_hash, Embedding.vector)
                .join(Embedding, Embedding.chunk_id == CodeChunk.id)
                .where(CodeChunk.repository_id == repository_id, Embedding.model == model)
            )
            return {key: list(vector) for key, vector in rows}

    async def publish(
        self,
        repository_id: str,
        detail: dict[str, Any],
        result: dict[str, Any],
        views: dict[str, Any],
        vectors: list[Any] | None,
        model: str,
    ) -> Any:
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(
                delete(RepositoryFile).where(RepositoryFile.repository_id == repository_id)
            )
            await session.execute(
                delete(RepositoryAnalysis).where(RepositoryAnalysis.repository_id == repository_id)
            )
            file_ids = {}
            for file in result["files"]:
                file_id = uid()
                file_ids[file["path"]] = file_id
                session.add(
                    RepositoryFile(
                        id=file_id,
                        repository_id=repository_id,
                        path=file["path"],
                        content_hash=hashlib.sha256(file["content"].encode()).hexdigest(),
                        data={k: v for k, v in file.items() if k not in {"content", "imports"}},
                    )
                )
            await session.flush()
            for file in result["files"]:
                for symbol in file["symbols"]:
                    session.add(CodeSymbol(file_id=file_ids[file["path"]], data=symbol))
            for index, chunk in enumerate(result["chunks"]):
                chunk_id = uid()
                session.add(
                    CodeChunk(
                        id=chunk_id,
                        repository_id=repository_id,
                        file_id=file_ids[chunk["file_path"]],
                        content=chunk["content"],
                        content_hash=chunk_hash(chunk),
                        source={
                            k: chunk[k] for k in ["file_path", "start_line", "end_line", "symbol"]
                        },
                    )
                )
                await session.flush()
                if vectors is not None:
                    session.add(
                        Embedding(
                            chunk_id=chunk_id,
                            repository_id=repository_id,
                            model=model,
                            vector=vectors[index],
                        )
                    )
            session.add(RepositoryAnalysis(repository_id=repository_id, data=views))
            row = await session.get(Repository, repository_id)
            assert row is not None
            row.status, row.detail, row.updated_at = "COMPLETED", detail, now()
            row.progress = {
                "repository_id": repository_id,
                "status": "COMPLETED",
                "stage": None,
                "progress": 100,
                "message": "Analysis completed.",
                "error": None,
                "updated_at": detail["updated_at"],
            }

    async def views(self, repository_id: str) -> dict[str, Any]:
        async with get_sessionmaker()() as session:
            row = await session.scalar(
                select(RepositoryAnalysis).where(RepositoryAnalysis.repository_id == repository_id)
            )
            assert row is not None
            return row.data

    async def files(self, repository_id: str) -> list[Any]:
        async with get_sessionmaker()() as session:
            rows = await session.scalars(
                select(RepositoryFile)
                .where(RepositoryFile.repository_id == repository_id)
                .order_by(RepositoryFile.path)
            )
            return [row.data for row in rows]

    async def retrieve(self, repository_id: str, vector: list[Any], model: str) -> list[Any]:
        async with get_sessionmaker()() as session:
            distance = Embedding.vector.cosine_distance(vector)
            rows = await session.execute(
                select(CodeChunk, distance.label("distance"))
                .join(Embedding, Embedding.chunk_id == CodeChunk.id)
                .where(Embedding.repository_id == repository_id, Embedding.model == model)
                .order_by(distance)
                .limit(8)
            )
            return [
                {"content": chunk.content, "source": chunk.source, "similarity": 1 - float(dist)}
                for chunk, dist in rows
            ]

    async def save_answer(self, repository_id: str, answer: dict[str, Any]) -> Any:
        async with get_sessionmaker()() as session, session.begin():
            session.add(
                Question(
                    id=answer["question_id"],
                    repository_id=repository_id,
                    question=answer["question"],
                )
            )
            await session.flush()
            session.add(
                Answer(id=answer["answer_id"], question_id=answer["question_id"], data=answer)
            )
            await session.flush()
            for ref in answer["sources"]:
                session.add(SourceReference(answer_id=answer["answer_id"], **ref))

    async def recover(self) -> Any:
        async with get_sessionmaker()() as session:
            ids = list(
                await session.scalars(
                    select(Repository.id).where(Repository.status.in_(["QUEUED", "ANALYZING"]))
                )
            )
        for repository_id in ids:
            await self.fail(
                repository_id,
                "ANALYSIS_FAILED",
                "Analysis interrupted by server restart. Please retry.",
            )


def chunk_hash(chunk: dict[str, Any]) -> str:
    return hashlib.sha256((chunk["file_path"] + "\n" + chunk["content"]).encode()).hexdigest()
