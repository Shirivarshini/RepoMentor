import asyncio
import logging
from typing import Any

from app.ai.provider import GeminiProvider
from app.analyzers.structure import analyze, insights
from app.core.exceptions import AppError
from app.github.client import GitHubClient
from app.models.entities import now
from app.schemas.repository import (
    ArchitectureResponse,
    FlowsResponse,
    RepositoryDetail,
    SetupResponse,
)
from app.services.store import chunk_hash

logger = logging.getLogger("app.pipeline")


class JobRunner:
    """Single-process MVP runner. Jobs are persisted before scheduling."""

    def __init__(self, store: Any, settings: Any) -> None:
        self.store, self.settings = store, settings
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_analyses)
        self.tasks: set[asyncio.Task[None]] = set()
        self.recovered = False
        self.recovery_lock = asyncio.Lock()

    async def recover(self) -> Any:
        async with self.recovery_lock:
            if not self.recovered:
                await self.store.recover()
                self.recovered = True

    def submit(self, repository_id: str) -> Any:
        task = asyncio.create_task(self.run(repository_id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def close(self) -> Any:
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def run(self, repository_id: str) -> None:
        try:
            async with self.semaphore, asyncio.timeout(900):
                row = await self.store.get(repository_id)
                detail = dict(row.detail)
                await self.store.progress(repository_id, "FETCHING_REPOSITORY", 5)
                github = GitHubClient(self.settings)
                sha, files, skipped, truncated = await github.snapshot(
                    detail["owner"], detail["name"], detail["default_branch"]
                )
                await self.store.progress(repository_id, "ANALYZING_STRUCTURE", 25)
                await self.store.progress(repository_id, "PARSING_CODE", 35)
                result = await asyncio.to_thread(
                    analyze,
                    files,
                    detail["description"],
                    self.settings.max_chunk_tokens,
                    self.settings.max_chunks_per_repository,
                )
                await self.store.progress(repository_id, "CHUNKING", 50)
                vectors = None
                await self.store.progress(repository_id, "EMBEDDING", 60)
                provider = GeminiProvider(self.settings)
                try:
                    cache = await self.store.embedding_cache(
                        repository_id, self.settings.embedding_model
                    )
                    missing = [c for c in result["chunks"] if chunk_hash(c) not in cache]
                    if missing:
                        generated = await provider.embed(
                            [c["file_path"] + "\n" + c["content"] for c in missing]
                        )
                        cache.update(
                            {chunk_hash(c): v for c, v in zip(missing, generated, strict=True)}
                        )
                    vectors = [cache[chunk_hash(c)] for c in result["chunks"]]
                except AppError as exc:
                    result["warnings"].append(
                        "Embeddings unavailable. Structural analysis is complete; "
                        f"{exc.message}"
                    )
                await self.store.progress(repository_id, "GENERATING_INSIGHTS", 85)
                views = insights(result)
                timestamp = now().isoformat().replace("+00:00", "Z")
                views["modules"] = {"repository_id": repository_id, "modules": result["modules"]}
                for key in ("architecture", "data_flow", "setup"):
                    views[key]["repository_id"] = repository_id
                views["architecture"]["generated_at"] = timestamp
                ArchitectureResponse.model_validate(views["architecture"])
                FlowsResponse.model_validate(views["data_flow"])
                SetupResponse.model_validate(views["setup"])
                detail.update(
                    status="COMPLETED",
                    commit_sha=sha,
                    analyzed_at=timestamp,
                    updated_at=timestamp,
                    analysis_version="1",
                    qa_available=bool(vectors),
                    warnings=result["warnings"],
                    error=None,
                    **{
                        k: result[k]
                        for k in [
                            "languages",
                            "frameworks",
                            "summary",
                            "important_files",
                            "entry_points",
                        ]
                    },
                    important_modules=[
                        {k: m[k] for k in ["id", "name", "purpose"]} for m in result["modules"]
                    ],
                    stats={
                        "files_analyzed": len(files),
                        "files_skipped": skipped,
                        "languages_detected": len(result["languages"]),
                        "modules_found": len(result["modules"]),
                        "entry_points_found": len(result["entry_points"]),
                        "symbols_found": sum(f["symbol_count"] for f in files),
                        "chunks_created": len(result["chunks"]),
                        "truncated": truncated,
                    },
                )
                RepositoryDetail.model_validate(detail)
                await self.store.progress(repository_id, "FINALIZING", 95)
                await self.store.publish(
                    repository_id, detail, result, views, vectors, self.settings.embedding_model
                )
        except asyncio.CancelledError:
            await self._fail(
                repository_id, "ANALYSIS_FAILED", "Analysis interrupted. Please retry."
            )
            raise
        except AppError as exc:
            await self._fail(repository_id, exc.code.value, exc.message)
        except Exception:
            logger.error("analysis_failed", extra={"repository_id": repository_id})
            await self._fail(
                repository_id, "ANALYSIS_FAILED", "Analysis could not finish. Please retry."
            )

    async def _fail(self, repository_id: Any, code: Any, message: Any) -> Any:
        try:
            await self.store.fail(repository_id, code, message)
        except Exception:
            logger.error("analysis_failure_persistence_unavailable")
