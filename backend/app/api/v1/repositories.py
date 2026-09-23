from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.ai.provider import GeminiProvider
from app.ai.rag import answer_question
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.github.client import GitHubClient, parse_url
from app.models.entities import now
from app.schemas.errors import ErrorCode
from app.schemas.repository import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnswerResponse,
    ArchitectureResponse,
    AskRequest,
    FilesResponse,
    FlowsResponse,
    ModulesResponse,
    RepositoryDetail,
    SetupResponse,
    StatusResponse,
)


async def ready_service(request: Request) -> Any:
    await request.app.state.runner.recover()


router = APIRouter(
    prefix="/repositories", tags=["repositories"], dependencies=[Depends(ready_service)]
)


def limit(request: Request, kind: str) -> Any:
    settings = get_settings()
    count = {
        "analyze": settings.rate_limit_analyze,
        "ask": settings.rate_limit_ask,
        "read": settings.rate_limit_read,
    }[kind]
    request.app.state.limiter.check(
        request.client.host if request.client else "unknown",
        kind,
        count,
        3600 if kind == "analyze" else 60,
    )


async def repository(request: Request, repository_id: UUID, completed: Any = False) -> Any:
    limit(request, "read")
    row = await request.app.state.store.get(str(repository_id))
    if row is None:
        raise NotFoundError("Repository analysis not found.")
    if completed and row.status != "COMPLETED":
        raise AppError(
            ErrorCode.ANALYSIS_NOT_READY,
            "Repository analysis is not complete.",
            details={"status": row.status, "reason": "analysis_not_completed"},
        )
    return row


@router.post("/analyze", response_model=AnalyzeResponse)
async def start(body: AnalyzeRequest, request: Request, response: Response) -> Any:
    limit(request, "analyze")
    owner, name = parse_url(body.repository_url)
    metadata = await GitHubClient(get_settings()).metadata(owner, name)
    owner, name = metadata["owner"]["login"], metadata["name"]
    timestamp = now().isoformat().replace("+00:00", "Z")
    detail = {
        "owner": owner,
        "name": name,
        "url": f"https://github.com/{owner}/{name}",
        "description": metadata.get("description"),
        "default_branch": metadata.get("default_branch"),
        "commit_sha": None,
        "status": "QUEUED",
        "error": None,
        "qa_available": False,
        "warnings": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "analyzed_at": None,
        "analysis_version": None,
        "languages": [],
        "frameworks": [],
        "summary": None,
        "stats": None,
        "important_modules": [],
        "important_files": [],
        "entry_points": [],
    }
    row, queued = await request.app.state.store.queue(
        f"{owner}/{name}".lower(), detail, body.force_reanalyze
    )
    if queued:
        request.app.state.runner.submit(row.id)
    response.status_code = 202 if queued else 200
    return {
        "repository_id": row.id,
        "owner": owner,
        "name": name,
        "url": detail["url"],
        "status": row.status,
        "message": "Repository analysis started."
        if queued
        else "Analysis already completed."
        if row.status == "COMPLETED"
        else "Analysis is already running.",
    }


@router.get("/{repository_id}", response_model=RepositoryDetail)
async def detail(repository_id: UUID, request: Request) -> Any:
    return (await repository(request, repository_id)).detail


@router.get("/{repository_id}/status", response_model=StatusResponse)
async def status(repository_id: UUID, request: Request) -> Any:
    return (await repository(request, repository_id)).progress


async def view(repository_id: Any, request: Any, name: Any) -> Any:
    await repository(request, repository_id, completed=True)
    return (await request.app.state.store.views(str(repository_id)))[name]


@router.get("/{repository_id}/architecture", response_model=ArchitectureResponse)
async def architecture(repository_id: UUID, request: Request) -> Any:
    return await view(repository_id, request, "architecture")


@router.get("/{repository_id}/modules", response_model=ModulesResponse)
async def modules(repository_id: UUID, request: Request) -> Any:
    return await view(repository_id, request, "modules")


@router.get("/{repository_id}/data-flow", response_model=FlowsResponse)
async def flows(repository_id: UUID, request: Request) -> Any:
    return await view(repository_id, request, "data_flow")


@router.get("/{repository_id}/setup", response_model=SetupResponse)
async def setup(repository_id: UUID, request: Request) -> Any:
    return await view(repository_id, request, "setup")


@router.get("/{repository_id}/files", response_model=FilesResponse)
async def files(
    repository_id: UUID,
    request: Request,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    language: str | None = None,
) -> Any:
    await repository(request, repository_id, completed=True)
    entries = await request.app.state.store.files(str(repository_id))
    if language:
        entries = [f for f in entries if f["language"] == language]
    return {
        "repository_id": repository_id,
        "total": len(entries),
        "limit": limit,
        "offset": offset,
        "files": entries[offset : offset + limit],
    }


@router.post("/{repository_id}/ask", response_model=AnswerResponse)
async def ask(repository_id: UUID, body: AskRequest, request: Request) -> Any:
    limit(request, "ask")
    row = await repository(request, repository_id, completed=True)
    if not row.detail["qa_available"]:
        raise AppError(
            ErrorCode.ANALYSIS_NOT_READY,
            "Embeddings are unavailable. Retry repository analysis after configuring Gemini.",
            details={"status": row.status, "reason": "embeddings_unavailable"},
        )
    async with request.app.state.ask_semaphore:
        return await answer_question(
            str(repository_id),
            body.question,
            request.app.state.store,
            GeminiProvider(get_settings()),
            get_settings(),
        )
