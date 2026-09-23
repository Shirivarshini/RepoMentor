"""Public wire schemas matching the root API contract."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Status = Literal["QUEUED", "ANALYZING", "COMPLETED", "FAILED"]


class AnalyzeRequest(BaseModel):
    repository_url: str = Field(max_length=200)
    force_reanalyze: bool = False


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

    @field_validator("question", mode="before")
    @classmethod
    def trim(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class Source(BaseModel):
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    symbol: str | None = None


class ErrorInfo(BaseModel):
    code: str
    message: str


class AnalyzeResponse(BaseModel):
    repository_id: UUID
    owner: str
    name: str
    url: str
    status: Status
    message: str


class StatusResponse(BaseModel):
    repository_id: UUID
    status: Status
    stage: str | None
    progress: int = Field(ge=0, le=100)
    message: str
    error: ErrorInfo | None
    updated_at: str


class LanguageInfo(BaseModel):
    name: str
    file_count: int
    percentage: float


class Framework(BaseModel):
    name: str
    category: str
    evidence: list[Source]


class Summary(BaseModel):
    purpose: str
    architecture_summary: str
    technologies: list[str]
    source: Literal["ai", "deterministic"]


class Stats(BaseModel):
    files_analyzed: int
    files_skipped: int
    languages_detected: int
    modules_found: int
    entry_points_found: int
    symbols_found: int
    chunks_created: int
    truncated: bool


class ModuleSummary(BaseModel):
    id: str
    name: str
    purpose: str


class Module(ModuleSummary):
    files: list[str]
    symbol_count: int
    depends_on: list[str]


class ImportantFile(BaseModel):
    path: str
    language: str | None
    reason: str


class EntryPoint(BaseModel):
    file_path: str
    kind: str
    symbol: str | None
    reason: str


class RepositoryDetail(BaseModel):
    repository_id: UUID
    owner: str
    name: str
    url: str
    description: str | None
    default_branch: str | None
    commit_sha: str | None
    status: Status
    error: ErrorInfo | None
    qa_available: bool
    warnings: list[str]
    created_at: str
    updated_at: str
    analyzed_at: str | None
    analysis_version: str | None
    languages: list[LanguageInfo]
    frameworks: list[Framework]
    summary: Summary | None
    stats: Stats | None
    important_modules: list[ModuleSummary]
    important_files: list[ImportantFile]
    entry_points: list[EntryPoint]


class Symbol(BaseModel):
    name: str
    symbol_type: str
    start_line: int
    end_line: int
    parent: str | None


class FileEntry(BaseModel):
    path: str
    language: str | None
    size: int
    purpose: str | None
    is_important: bool
    is_entry_point: bool
    symbol_count: int
    symbols: list[Symbol]


class FilesResponse(BaseModel):
    repository_id: UUID
    total: int
    limit: int
    offset: int
    files: list[FileEntry]


class ModulesResponse(BaseModel):
    repository_id: UUID
    modules: list[Module]


class Node(BaseModel):
    id: str
    label: str
    type: str
    description: str
    files: list[str]
    inferred: bool


class Edge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None
    inferred: bool


class ArchitectureResponse(BaseModel):
    repository_id: UUID
    nodes: list[Node]
    edges: list[Edge]
    summary: str
    generated_at: str


class FlowStep(BaseModel):
    order: int
    label: str
    kind: str
    file_path: str | None
    symbol: str | None
    start_line: int | None
    end_line: int | None
    inferred: bool


class Flow(BaseModel):
    id: str
    name: str
    summary: str
    steps: list[FlowStep]


class FlowsResponse(BaseModel):
    repository_id: UUID
    flows: list[Flow]
    message: str | None


class SetupItem(BaseModel):
    title: str
    description: str | None
    commands: list[str]
    sources: list[Source]


class EnvironmentVariable(BaseModel):
    name: str
    description: str | None
    required: bool | None
    default: str | None
    source: Source | None


class CommonIssue(BaseModel):
    issue: str
    resolution: str
    sources: list[Source]


class SetupResponse(BaseModel):
    repository_id: UUID
    prerequisites: list[SetupItem]
    installation: list[SetupItem]
    environment_variables: list[EnvironmentVariable]
    database: list[SetupItem]
    run: list[SetupItem]
    common_issues: list[CommonIssue]
    message: str | None


class Evidence(BaseModel):
    statement: str
    sources: list[Source] = Field(min_length=1)


class AnswerResponse(BaseModel):
    question_id: UUID
    answer_id: UUID
    question: str
    answer: str
    explanation: str | None
    evidence: list[Evidence]
    interpretation: str | None
    sources: list[Source]
    confidence: float = Field(ge=0, le=1)
    grounded: bool
    created_at: str
