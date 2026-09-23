# RepoMentor API Contract

**Contract version:** 1.0.0 (finalized in Phase 0)
**API version:** `/api/v1`
**Status:** Canonical. This is the single source of truth for endpoints, request/response schemas, errors, status values, and versioning. Do not create a duplicate under `docs/`.

---

## Contract Rules

- Frontend must never guess response shapes.
- Backend changes to endpoint names or response schemas require updating this document.
- Breaking API changes require a coordinated versioned change.
- IDs are stable UUID strings.
- Timestamps use ISO 8601.
- Repository-derived answers must include source references where available.
- AI responses must distinguish repository evidence from interpretation.
- API errors use the standard error envelope below.
- Long-running repository analysis must expose an explicit analysis status.
- Never expose secrets, stack traces, or internal credentials in API responses.

---

# Conventions

| Topic | Rule |
|---|---|
| Format | JSON, UTF-8, `Content-Type: application/json`. |
| Naming | `snake_case` for all fields. |
| Base path | `/api/v1` for all endpoints except `/health`. |
| Timestamps | ISO 8601, UTC, `Z` suffix, e.g. `2026-09-19T10:15:30Z`. |
| IDs | UUID v4 strings (`repository_id`, `question_id`, `answer_id`). |
| Presence | Every documented field is **always present**. Unknown scalar/object values are `null`; unknown lists are `[]`. Fields are never omitted. |
| Paths | Repository file paths are POSIX-style, relative to the repository root, no leading `/`. |
| Lines | Line numbers are 1-based and inclusive. |
| State enums | `UPPER_SNAKE_CASE` (`AnalysisStatus`, `AnalysisStage`). |
| Classification enums | `lower_snake_case` (`NodeType`, `SymbolType`, ...). |
| Unknown enum values | Clients must tolerate unknown enum values (render a generic fallback). Adding an enum value is non-breaking. |
| Unknown fields | Clients must ignore unknown fields. Adding an optional field is non-breaking. |
| Text fields | `answer`, `explanation`, `interpretation`, `summary`, `purpose`, and `description` are plain text with limited Markdown (paragraphs, lists, inline code, fenced code). **Clients must never render raw HTML** from any API field. |
| Repository-derived text | File paths, symbol names, and quoted repository content are untrusted data. Clients render them as text only. |
| Request tracing | Every response carries an `X-Request-ID` header. Error bodies repeat it as `error.request_id`. |

## Breaking vs non-breaking

Breaking: removing or renaming a field or endpoint, changing a type, changing field semantics, removing an enum value, tightening validation.
Non-breaking: adding an optional response field, adding an enum value, adding an optional request field or query parameter, adding an endpoint.

## Success status codes

| Code | Meaning |
|---|---|
| `200 OK` | Successful read, or existing analysis returned. |
| `202 Accepted` | A new analysis run was queued. |

Error status codes are listed in [Error Codes](#error-codes).

## Client polling guidance

After `POST /repositories/analyze`, poll `GET /repositories/{repository_id}/status` about every 2 seconds while `status` is `QUEUED` or `ANALYZING`. Stop on `COMPLETED` or `FAILED`.

---

# Shared Types

## AnalysisStatus

- `QUEUED`
- `ANALYZING`
- `COMPLETED`
- `FAILED`

## AnalysisStage

Present in the status response while `ANALYZING`, and on `FAILED` (the stage where the failure occurred). `null` otherwise.

- `FETCHING_REPOSITORY`
- `ANALYZING_STRUCTURE`
- `PARSING_CODE`
- `CHUNKING`
- `EMBEDDING`
- `GENERATING_INSIGHTS`
- `FINALIZING`

## SourceReference

A pointer to repository evidence. Sources are produced by the backend from stored chunk/symbol metadata and are never taken from free-form model text.

| Field | Type | Notes |
|---|---|---|
| `file_path` | string | Exists in the analyzed repository. |
| `start_line` | integer \| null | `null` for whole-file references. |
| `end_line` | integer \| null | `null` for whole-file references. |
| `symbol` | string \| null | Function/class/method name when available. |

```json
{
  "file_path": "backend/services/auth_service.py",
  "start_line": 24,
  "end_line": 58,
  "symbol": "authenticate_user"
}
```

## ErrorInfo

Used in `status.error` and `RepositoryDetail.error` when analysis failed.

| Field | Type | Notes |
|---|---|---|
| `code` | string | One of the [Error Codes](#error-codes). |
| `message` | string | Human-readable, safe to display. |

## Enumerations (classification)

| Name | Values |
|---|---|
| `FrameworkCategory` | `frontend`, `backend`, `database`, `testing`, `build`, `other` |
| `EntryPointKind` | `application`, `api`, `frontend`, `cli`, `other` |
| `SymbolType` | `function`, `class`, `method`, `interface`, `type`, `route`, `other` |
| `NodeType` | `frontend`, `backend`, `api`, `service`, `data_access`, `database`, `external`, `infrastructure`, `other` |
| `FlowStepKind` | `ui`, `route`, `middleware`, `controller`, `service`, `data_access`, `database`, `external`, `other` |

## Evidence vs interpretation

Any relationship that is directly supported by parsed repository evidence (imports, route declarations, dependency files, configuration) has `inferred: false`. A relationship proposed by AI or heuristics without direct proof has `inferred: true`. Clients must present inferred items distinctly and must not rely on color alone.

---

# Endpoint Index

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health. |
| POST | `/api/v1/repositories/analyze` | Start or retrieve analysis. |
| GET | `/api/v1/repositories/{repository_id}` | Repository metadata and high-level analysis. |
| GET | `/api/v1/repositories/{repository_id}/status` | Analysis status/progress. |
| GET | `/api/v1/repositories/{repository_id}/architecture` | Architecture graph. |
| GET | `/api/v1/repositories/{repository_id}/modules` | Important modules. |
| GET | `/api/v1/repositories/{repository_id}/files` | Analyzed files and symbols. |
| GET | `/api/v1/repositories/{repository_id}/data-flow` | Request/data flows. |
| GET | `/api/v1/repositories/{repository_id}/setup` | Generated setup guide. |
| POST | `/api/v1/repositories/{repository_id}/ask` | Repository-grounded Q&A. |

**Availability rule:** `GET /repositories/{repository_id}` and `/status` always respond (`200`) for an existing repository. All other sub-resource endpoints and `/ask` return `409 ANALYSIS_NOT_READY` unless `status` is `COMPLETED`. An unknown `repository_id` returns `404 NOT_FOUND`.

---

# Core Endpoints

## Health

### GET `/health`

Liveness check. Unversioned and unauthenticated.

```json
{
  "status": "ok"
}
```

---

# Repository Analysis

## POST `/api/v1/repositories/analyze`

Starts or retrieves analysis for a public GitHub repository.

### Request

| Field | Type | Required | Notes |
|---|---|---|---|
| `repository_url` | string | yes | `https://github.com/{owner}/{repository}`. Optional trailing `/` or `.git`. Max 200 characters. |
| `force_reanalyze` | boolean | no | Default `false`. When `true`, a `COMPLETED` repository is analyzed again. |

```json
{
  "repository_url": "https://github.com/owner/repository",
  "force_reanalyze": false
}
```

**URL rules.** Scheme must be `https`. Host must be exactly `github.com`. No credentials, port, query string, or fragment. Path must be exactly `/{owner}/{repository}` (optional trailing `/` or `.git`, optionally followed by nothing else). Any other input returns `422 VALIDATION_ERROR`.

### Response

`202 Accepted` when a run is queued; `200 OK` when an existing repository is returned without starting a run.

| Field | Type | Notes |
|---|---|---|
| `repository_id` | string (UUID) | Stable per `owner/name` (case-insensitive). |
| `owner` | string | Canonical casing from GitHub. |
| `name` | string | Canonical casing from GitHub. |
| `url` | string | Canonical `https://github.com/{owner}/{name}`. |
| `status` | AnalysisStatus | |
| `message` | string | Human-readable. |

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "owner": "owner",
  "name": "repository",
  "url": "https://github.com/owner/repository",
  "status": "QUEUED",
  "message": "Repository analysis started."
}
```

### Behavior

| Existing state | `force_reanalyze` | Result |
|---|---|---|
| No record | any | Validate, verify repository exists on GitHub, create record, queue run. `202`, `QUEUED`. |
| `QUEUED` / `ANALYZING` | any | No new run. `200`, current status. |
| `COMPLETED` | `false` | No new run. `200`, `COMPLETED`, message "Analysis already completed." |
| `COMPLETED` | `true` | Reset and queue a new run. `202`, `QUEUED`. |
| `FAILED` | any | Queue a new run (retry). `202`, `QUEUED`. |

The request performs URL validation and one GitHub metadata lookup **synchronously**, so invalid URLs, missing/private repositories, and GitHub rate limiting are reported immediately as HTTP errors rather than as a later `FAILED` status. All remaining work runs asynchronously.

### Errors

`422 VALIDATION_ERROR`, `404 REPOSITORY_NOT_FOUND`, `429 RATE_LIMIT_EXCEEDED`, `503 GITHUB_RATE_LIMIT`, `502 GITHUB_API_ERROR`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

## GET `/api/v1/repositories/{repository_id}`

Returns repository metadata and high-level analysis. Always `200` for an existing repository. Analysis fields are `null` (objects) or `[]` (lists) until `status` is `COMPLETED`.

### Response (`RepositoryDetail`)

| Field | Type | Notes |
|---|---|---|
| `repository_id` | string (UUID) | |
| `owner`, `name`, `url` | string | |
| `description` | string \| null | From GitHub. |
| `default_branch` | string \| null | |
| `commit_sha` | string \| null | Commit analyzed (40 hex chars). |
| `status` | AnalysisStatus | |
| `error` | ErrorInfo \| null | Set when `status` is `FAILED`. |
| `qa_available` | boolean | `true` when repository chunks are embedded and `/ask` can be used. |
| `warnings` | string[] | Non-fatal issues (e.g. embeddings unavailable, unsupported languages). |
| `created_at`, `updated_at` | string | |
| `analyzed_at` | string \| null | Completion time of the current analysis. |
| `analysis_version` | string \| null | Analysis schema version. |
| `languages` | Language[] | See below. |
| `frameworks` | Framework[] | Detected from evidence only. |
| `summary` | Summary \| null | |
| `stats` | Stats \| null | |
| `important_modules` | ModuleSummary[] | Full detail at `/modules`. |
| `important_files` | ImportantFile[] | Ordered by recommended reading order. |
| `entry_points` | EntryPoint[] | |

**Language:** `{ "name": string, "file_count": integer, "percentage": number }`. `percentage` is the share of analyzed source bytes (one decimal).

**Framework:** `{ "name": string, "category": FrameworkCategory, "evidence": SourceReference[] }`. `evidence` is never empty.

**Summary:** `{ "purpose": string, "architecture_summary": string, "technologies": string[], "source": "ai" | "deterministic" }`. `source` is `deterministic` when AI generation was unavailable.

**Stats:** `{ "files_analyzed", "files_skipped", "languages_detected", "modules_found", "entry_points_found", "symbols_found", "chunks_created": integer, "truncated": boolean }`. `truncated` is `true` when the analyzed-file cap was reached and lower-priority files were left out.

**ModuleSummary:** `{ "id": string, "name": string, "purpose": string }`.

**ImportantFile:** `{ "path": string, "language": string | null, "reason": string }`.

**EntryPoint:** `{ "file_path": string, "kind": EntryPointKind, "symbol": string | null, "reason": string }`.

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "owner": "owner",
  "name": "repository",
  "url": "https://github.com/owner/repository",
  "description": "Example full-stack application.",
  "default_branch": "main",
  "commit_sha": "9fceb02d0ae598e95dc970b74767f19372d61af8",
  "status": "COMPLETED",
  "error": null,
  "qa_available": true,
  "warnings": [],
  "created_at": "2026-09-19T10:15:30Z",
  "updated_at": "2026-09-19T10:17:02Z",
  "analyzed_at": "2026-09-19T10:17:02Z",
  "analysis_version": "1",
  "languages": [
    { "name": "Python", "file_count": 42, "percentage": 61.5 },
    { "name": "TypeScript", "file_count": 30, "percentage": 38.5 }
  ],
  "frameworks": [
    {
      "name": "FastAPI",
      "category": "backend",
      "evidence": [
        { "file_path": "backend/requirements.txt", "start_line": 3, "end_line": 3, "symbol": null }
      ]
    }
  ],
  "summary": {
    "purpose": "A web application with a React frontend and a FastAPI backend.",
    "architecture_summary": "The React frontend calls a FastAPI service layer backed by PostgreSQL.",
    "technologies": ["Python", "FastAPI", "React", "PostgreSQL"],
    "source": "ai"
  },
  "stats": {
    "files_analyzed": 72,
    "files_skipped": 310,
    "languages_detected": 2,
    "modules_found": 4,
    "entry_points_found": 2,
    "symbols_found": 388,
    "chunks_created": 401,
    "truncated": false
  },
  "important_modules": [
    { "id": "authentication", "name": "Authentication", "purpose": "Handles user authentication." }
  ],
  "important_files": [
    { "path": "README.md", "language": "Markdown", "reason": "Project documentation and setup clues." }
  ],
  "entry_points": [
    {
      "file_path": "backend/app/main.py",
      "kind": "application",
      "symbol": "app",
      "reason": "Creates the FastAPI application instance."
    }
  ]
}
```

### Errors

`404 NOT_FOUND`, `422 VALIDATION_ERROR` (malformed UUID), `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

## GET `/api/v1/repositories/{repository_id}/status`

Returns analysis status. Cheap; intended for polling.

| Field | Type | Notes |
|---|---|---|
| `repository_id` | string (UUID) | |
| `status` | AnalysisStatus | |
| `progress` | integer | 0–100, non-decreasing within one analysis run. `100` only when `COMPLETED`. |
| `stage` | AnalysisStage \| null | |
| `message` | string | Human-readable. |
| `error` | ErrorInfo \| null | Set when `FAILED`. |
| `updated_at` | string | |

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "status": "COMPLETED",
  "progress": 100,
  "stage": null,
  "message": "Analysis completed.",
  "error": null,
  "updated_at": "2026-09-19T10:17:02Z"
}
```

In-progress example:

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "status": "ANALYZING",
  "progress": 62,
  "stage": "EMBEDDING",
  "message": "Generating embeddings.",
  "error": null,
  "updated_at": "2026-09-19T10:16:10Z"
}
```

Failed example:

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "status": "FAILED",
  "progress": 18,
  "stage": "FETCHING_REPOSITORY",
  "message": "Analysis failed.",
  "error": {
    "code": "REPOSITORY_TOO_LARGE",
    "message": "The repository exceeds the supported size."
  },
  "updated_at": "2026-09-19T10:15:55Z"
}
```

### Errors

`404 NOT_FOUND`, `422 VALIDATION_ERROR`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

## GET `/api/v1/repositories/{repository_id}/architecture`

Returns structured architecture data for React Flow.

| Field | Type | Notes |
|---|---|---|
| `repository_id` | string (UUID) | |
| `summary` | string \| null | Human-readable explanation. |
| `nodes` | ArchitectureNode[] | |
| `edges` | ArchitectureEdge[] | |
| `generated_at` | string | |

**ArchitectureNode:** `{ "id": string, "label": string, "type": NodeType, "description": string | null, "files": string[], "inferred": boolean }`.
**ArchitectureEdge:** `{ "id": string, "source": string, "target": string, "label": string | null, "inferred": boolean }`.

**Guarantees:** node `id`s are unique; every edge `source`/`target` matches a node `id`; every path in `files` exists in the analyzed repository; every node has at least one file (nodes without repository evidence are not returned); edge `id`s are unique.

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "summary": "A React frontend calls a FastAPI backend that persists data in PostgreSQL.",
  "nodes": [
    {
      "id": "frontend",
      "label": "Frontend",
      "type": "frontend",
      "description": "React application.",
      "files": ["frontend/src/main.tsx"],
      "inferred": false
    },
    {
      "id": "backend",
      "label": "Backend",
      "type": "backend",
      "description": "FastAPI application.",
      "files": ["backend/app/main.py"],
      "inferred": false
    },
    {
      "id": "database",
      "label": "PostgreSQL",
      "type": "database",
      "description": "Primary datastore.",
      "files": ["docker-compose.yml"],
      "inferred": false
    }
  ],
  "edges": [
    { "id": "frontend-backend", "source": "frontend", "target": "backend", "label": "HTTP /api", "inferred": false },
    { "id": "backend-database", "source": "backend", "target": "database", "label": "SQL", "inferred": true }
  ],
  "generated_at": "2026-09-19T10:17:01Z"
}
```

### Errors

`404 NOT_FOUND`, `409 ANALYSIS_NOT_READY`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

## GET `/api/v1/repositories/{repository_id}/modules`

Returns important repository modules.

**Module:** `{ "id": string, "name": string, "purpose": string, "files": string[], "symbol_count": integer, "depends_on": string[] }`.

- `files` — important file paths in the module.
- `symbol_count` — extracted symbols across the module's files.
- `depends_on` — `id`s of other modules this module imports from (evidence-based).

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "modules": [
    {
      "id": "authentication",
      "name": "Authentication",
      "purpose": "Handles user authentication.",
      "files": [
        "backend/routes/auth.py",
        "backend/services/auth_service.py"
      ],
      "symbol_count": 14,
      "depends_on": ["users"]
    }
  ]
}
```

### Errors

`404 NOT_FOUND`, `409 ANALYSIS_NOT_READY`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

## GET `/api/v1/repositories/{repository_id}/files`

Returns the analyzed repository file list and metadata. The frontend builds the tree from `path`. Skipped files (ignored, binary, oversized) are not listed; their count is in `stats.files_skipped`.

### Query parameters

| Name | Type | Default | Notes |
|---|---|---|---|
| `limit` | integer | `500` | 1–2000. |
| `offset` | integer | `0` | ≥ 0. |
| `language` | string | none | Exact language name filter. |

### Response

| Field | Type | Notes |
|---|---|---|
| `repository_id` | string (UUID) | |
| `total` | integer | Total matching files. |
| `limit`, `offset` | integer | Echoed. |
| `files` | FileEntry[] | Sorted by `path`. |

**FileEntry:** `{ "path": string, "language": string | null, "size": integer, "purpose": string | null, "is_important": boolean, "is_entry_point": boolean, "symbol_count": integer, "symbols": Symbol[] }`. `size` is bytes.
**Symbol:** `{ "name": string, "symbol_type": SymbolType, "start_line": integer, "end_line": integer, "parent": string | null }`. `parent` is the enclosing class/symbol name (for methods).

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "total": 72,
  "limit": 500,
  "offset": 0,
  "files": [
    {
      "path": "backend/services/auth_service.py",
      "language": "Python",
      "size": 2210,
      "purpose": "Authentication business logic.",
      "is_important": true,
      "is_entry_point": false,
      "symbol_count": 3,
      "symbols": [
        { "name": "AuthService", "symbol_type": "class", "start_line": 10, "end_line": 70, "parent": null },
        { "name": "authenticate_user", "symbol_type": "method", "start_line": 24, "end_line": 58, "parent": "AuthService" }
      ]
    }
  ]
}
```

### Errors

`404 NOT_FOUND`, `409 ANALYSIS_NOT_READY`, `422 VALIDATION_ERROR`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

## GET `/api/v1/repositories/{repository_id}/data-flow`

Returns structured request/data-flow information. A repository may have several flows; the list is empty when none could be supported by evidence.

**Flow:** `{ "id": string, "name": string, "summary": string, "steps": FlowStep[] }`.
**FlowStep:** `{ "order": integer, "label": string, "kind": FlowStepKind, "file_path": string | null, "symbol": string | null, "start_line": integer | null, "end_line": integer | null, "inferred": boolean }`.

`order` starts at 1 and is contiguous. When `file_path` is set it exists in the analyzed repository.

| Field | Type | Notes |
|---|---|---|
| `repository_id` | string (UUID) | |
| `flows` | Flow[] | May be empty. |
| `message` | string \| null | Explains an empty result. |

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "flows": [
    {
      "id": "user-registration",
      "name": "User registration",
      "summary": "The registration form posts to the auth route, which calls the user service and persists the user.",
      "steps": [
        { "order": 1, "label": "Registration Form", "kind": "ui", "file_path": "frontend/src/Register.tsx", "symbol": "Register", "start_line": 1, "end_line": 80, "inferred": false },
        { "order": 2, "label": "POST /api/register", "kind": "route", "file_path": "backend/routes/auth.py", "symbol": "register", "start_line": 12, "end_line": 30, "inferred": false },
        { "order": 3, "label": "User Service", "kind": "service", "file_path": "backend/services/user_service.py", "symbol": "create_user", "start_line": 5, "end_line": 40, "inferred": false },
        { "order": 4, "label": "PostgreSQL", "kind": "database", "file_path": "backend/repositories/user_repository.py", "symbol": "insert_user", "start_line": 8, "end_line": 25, "inferred": true }
      ]
    }
  ],
  "message": null
}
```

### Errors

`404 NOT_FOUND`, `409 ANALYSIS_NOT_READY`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

## GET `/api/v1/repositories/{repository_id}/setup`

Returns generated setup instructions derived from repository evidence (README, dependency files, Dockerfiles, environment examples). Commands are **display-only text**: RepoMentor never executes them, and they must be treated as untrusted content by users and clients.

Response sections:

- prerequisites
- installation
- environment variables
- database setup
- run commands
- common issues

| Field | Type | Notes |
|---|---|---|
| `repository_id` | string (UUID) | |
| `prerequisites` | SetupItem[] | |
| `installation` | SetupItem[] | |
| `environment_variables` | EnvironmentVariable[] | |
| `database` | SetupItem[] | |
| `run` | SetupItem[] | |
| `common_issues` | CommonIssue[] | |
| `message` | string \| null | Explains sparse or empty results. |

**SetupItem:** `{ "title": string, "description": string | null, "commands": string[], "sources": SourceReference[] }`. `commands` is `[]` when there is nothing to run; render commands in monospace.
**EnvironmentVariable:** `{ "name": string, "description": string | null, "required": boolean | null, "default": string | null, "source": SourceReference | null }`. `required` is `null` when unknown. Secret-looking default values are never returned.
**CommonIssue:** `{ "issue": string, "resolution": string, "sources": SourceReference[] }`.

An empty section array means no supporting evidence was found; clients show an empty state rather than inventing content.

```json
{
  "repository_id": "3f2b8c1e-5a4d-4e7b-9c1a-2d6f8e0b7a11",
  "prerequisites": [
    {
      "title": "Python 3.11+",
      "description": "Declared in pyproject.toml.",
      "commands": [],
      "sources": [{ "file_path": "backend/pyproject.toml", "start_line": 5, "end_line": 5, "symbol": null }]
    }
  ],
  "installation": [
    {
      "title": "Install backend dependencies",
      "description": null,
      "commands": ["pip install -r requirements.txt"],
      "sources": [{ "file_path": "README.md", "start_line": 20, "end_line": 24, "symbol": null }]
    }
  ],
  "environment_variables": [
    {
      "name": "DATABASE_URL",
      "description": "PostgreSQL connection string.",
      "required": true,
      "default": null,
      "source": { "file_path": ".env.example", "start_line": 1, "end_line": 1, "symbol": null }
    }
  ],
  "database": [],
  "run": [
    {
      "title": "Start the API",
      "description": null,
      "commands": ["uvicorn app.main:app --reload"],
      "sources": [{ "file_path": "README.md", "start_line": 30, "end_line": 32, "symbol": null }]
    }
  ],
  "common_issues": [],
  "message": null
}
```

### Errors

`404 NOT_FOUND`, `409 ANALYSIS_NOT_READY`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

# Repository Q&A

## POST `/api/v1/repositories/{repository_id}/ask`

Asks a natural-language question about the repository. Requires `status` = `COMPLETED` and `qa_available` = `true`.

### Request

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string | yes | 3–1000 characters after trimming whitespace. |

```json
{
  "question": "How does user authentication work?"
}
```

### Response

| Field | Type | Notes |
|---|---|---|
| `question_id` | string (UUID) | |
| `answer_id` | string (UUID) | |
| `question` | string | Echo of the trimmed question. |
| `answer` | string | Direct answer. |
| `explanation` | string \| null | Supporting explanation. |
| `evidence` | EvidenceItem[] | Claims backed by repository sources. |
| `interpretation` | string \| null | Model reasoning that goes beyond the cited evidence. Kept separate from `evidence`. |
| `sources` | SourceReference[] | All cited sources, deduplicated. |
| `confidence` | number | 0.0–1.0. A retrieval/grounding heuristic, **not** a probability of correctness. |
| `grounded` | boolean | `true` only when the answer is supported by retrieved repository evidence. |
| `created_at` | string | |

**EvidenceItem:** `{ "statement": string, "sources": SourceReference[] }`. `sources` is never empty.

```json
{
  "question_id": "b7d0c2a4-1f0e-4c65-8f35-6a2b9d5e3c10",
  "answer_id": "0c9e1a3d-7b52-4d1c-a1c8-52f7f4e60d99",
  "question": "How does user authentication work?",
  "answer": "Authentication is handled by the auth route and authentication service.",
  "explanation": "The login route validates the request and delegates credential checking to authenticate_user.",
  "evidence": [
    {
      "statement": "The login route delegates to the authentication service.",
      "sources": [
        { "file_path": "backend/routes/auth.py", "start_line": 10, "end_line": 45, "symbol": "login" }
      ]
    },
    {
      "statement": "authenticate_user verifies the supplied credentials.",
      "sources": [
        { "file_path": "backend/services/auth_service.py", "start_line": 1, "end_line": 60, "symbol": "authenticate_user" }
      ]
    }
  ],
  "interpretation": "This looks like a session-token approach, but the retrieved code does not show how tokens are issued.",
  "sources": [
    {
      "file_path": "backend/routes/auth.py",
      "start_line": 10,
      "end_line": 45,
      "symbol": "login"
    },
    {
      "file_path": "backend/services/auth_service.py",
      "start_line": 1,
      "end_line": 60,
      "symbol": "authenticate_user"
    }
  ],
  "confidence": 0.88,
  "grounded": true,
  "created_at": "2026-09-19T10:20:00Z"
}
```

### Grounding Rule

If sufficient repository evidence cannot be retrieved, the backend must return an answer indicating that the repository does not contain enough evidence.

It must not invent files, functions, dependencies, or behavior.

The insufficient-evidence response is a normal `200` with `grounded: false`, the exact answer text below, `explanation` and `interpretation` set to `null`, and empty `evidence` and `sources`.

```json
{
  "question_id": "b7d0c2a4-1f0e-4c65-8f35-6a2b9d5e3c11",
  "answer_id": "0c9e1a3d-7b52-4d1c-a1c8-52f7f4e60d9a",
  "question": "Does this project support OAuth?",
  "answer": "I couldn't find enough evidence in the repository to determine this.",
  "explanation": null,
  "evidence": [],
  "interpretation": null,
  "sources": [],
  "confidence": 0.0,
  "grounded": false,
  "created_at": "2026-09-19T10:21:00Z"
}
```

Every `file_path` in `sources` and `evidence` refers to a file that exists in the analyzed repository. Repository content quoted in an answer is data, never an instruction to the backend.

### Errors

`404 NOT_FOUND`, `409 ANALYSIS_NOT_READY` (also when `qa_available` is `false`; `details.reason` distinguishes `analysis_not_completed` from `embeddings_unavailable`), `422 VALIDATION_ERROR`, `429 RATE_LIMIT_EXCEEDED`, `503 AI_PROVIDER_ERROR`, `503 EMBEDDING_ERROR`, `503 DATABASE_ERROR`, `500 INTERNAL_ERROR`.

---

# Standard Error

Every non-2xx response uses this envelope.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": {},
    "request_id": "8a1f6c0e2b5d4e7f"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `code` | string | Stable machine-readable code. |
| `message` | string | Safe to display. Never contains stack traces, secrets, or internal identifiers. |
| `details` | object | Code-specific, may be `{}`. Never contains secrets or internals. |
| `request_id` | string | Matches the `X-Request-ID` response header. |

Examples of `details`:

- `VALIDATION_ERROR`: `{ "field": "repository_url", "reason": "Host must be github.com." }`
- `GITHUB_RATE_LIMIT`: `{ "reset_at": "2026-09-19T11:00:00Z" }`
- `RATE_LIMIT_EXCEEDED`: `{ "retry_after_seconds": 30 }` (also sent as a `Retry-After` header)
- `ANALYSIS_NOT_READY`: `{ "status": "ANALYZING", "reason": "analysis_not_completed" }`
- `AI_PROVIDER_ERROR`: `{ "retry_after_seconds": 20 }` when known

## Error Codes

| Code | HTTP | Notes |
|---|---:|---|
| `VALIDATION_ERROR` | 422 | Invalid URL, question, UUID, or query parameter. |
| `REPOSITORY_NOT_FOUND` | 404 | GitHub repository does not exist **or is not public** (GitHub does not distinguish for unauthenticated access). |
| `NOT_FOUND` | 404 | Unknown `repository_id` or route. |
| `ANALYSIS_NOT_READY` | 409 | Repository analysis is not `COMPLETED`, or Q&A is unavailable. |
| `RATE_LIMIT_EXCEEDED` | 429 | RepoMentor request limit exceeded. |
| `GITHUB_RATE_LIMIT` | 503 | Upstream GitHub rate limit. |
| `GITHUB_API_ERROR` | 502 | GitHub returned an error or timed out after retries. |
| `AI_PROVIDER_ERROR` | 503 | LLM provider failure, quota, or invalid model response. |
| `EMBEDDING_ERROR` | 503 | Embedding generation failure. |
| `DATABASE_ERROR` | 503 | Database unavailable or query failure. |
| `INTERNAL_ERROR` | 500 | Unexpected failure. Generic message only. |
| `ANALYSIS_FAILED` | n/a | Appears in `error` of a `FAILED` analysis (unclassified pipeline failure). |
| `REPOSITORY_TOO_LARGE` | n/a | Appears in `error` of a `FAILED` analysis. |
| `EMPTY_REPOSITORY` | n/a | Appears in `error` of a `FAILED` analysis. |
| `UNSUPPORTED_REPOSITORY` | n/a | Appears in `error` of a `FAILED` analysis (no analyzable files after filtering). |

Codes marked `n/a` occur only inside `status.error` / `RepositoryDetail.error` because the failure happens asynchronously. The upstream codes (`GITHUB_RATE_LIMIT`, `GITHUB_API_ERROR`, `EMBEDDING_ERROR`, `DATABASE_ERROR`) may appear in both places.

---

# Repository Analysis Rules

The API must safely handle:

| Condition | Behavior |
|---|---|
| Invalid GitHub URLs | `422 VALIDATION_ERROR` at `analyze`. |
| Missing or private repositories | `404 REPOSITORY_NOT_FOUND` at `analyze`. |
| GitHub rate limits | `503 GITHUB_RATE_LIMIT` at `analyze`; `FAILED` with the same code if hit mid-analysis. |
| Network timeouts | Retried with backoff; then `502 GITHUB_API_ERROR` or `FAILED`. |
| Empty repositories | `FAILED`, `EMPTY_REPOSITORY`. |
| Large repositories | Over the hard limit: `FAILED`, `REPOSITORY_TOO_LARGE`. Otherwise lower-priority files are omitted and `stats.truncated` is `true`. |
| Large files | Skipped; counted in `stats.files_skipped`. |
| Binary files | Skipped; counted in `stats.files_skipped`. |
| Unsupported languages | Files still listed with no symbols; a `warnings` entry is added. If no analyzable files remain: `FAILED`, `UNSUPPORTED_REPOSITORY`. |
| Embedding or AI failure during analysis | Structural analysis still completes with `summary.source` = `deterministic`; `qa_available` is `false` and `warnings` explains. `POST analyze` with `force_reanalyze: true` retries. |

Repository code must never be executed.

---

# Rate Limiting

RepoMentor limits requests per client. Exceeding a limit returns `429 RATE_LIMIT_EXCEEDED` with a `Retry-After` header. Limits are configurable; `analyze` and `ask` have stricter limits than read endpoints. Concrete defaults are defined in `docs/ARCHITECTURE.md` (configuration), not in this contract.

---

# Client-visible Limits

| Item | Limit |
|---|---|
| `repository_url` length | ≤ 200 characters |
| `question` length | 3–1000 characters (trimmed) |
| `files` page size | 1–2000, default 500 |

Repository size and file limits are server-side and configurable; they are surfaced through `stats`, `warnings`, and `REPOSITORY_TOO_LARGE`.

---

# API Versioning

Current version:

`/api/v1`

Any breaking change requires a coordinated versioned API change and an update to this contract.

---

# Changelog

## 1.0.0 — Phase 0 finalization

Finalized before any implementation existed, so none of the following are breaking changes to a released API. The draft contract left several schemas undefined; the changes below close those gaps and align the contract with `docs/DESIGN.md`, the PRD, and the implementation plan.

- Added Conventions, Shared Types, Endpoint Index, and per-endpoint field tables.
- `analyze`: added optional `force_reanalyze`; defined idempotent behavior, `202`/`200` semantics, synchronous validation and GitHub existence check, and strict URL rules.
- `GET /repositories/{id}`: defined the full `RepositoryDetail` schema (languages with percentages, evidence-backed frameworks, summary with `source`, stats, important modules/files, entry points, `qa_available`, `warnings`, `error`).
- `status`: added `stage`, `error`, `updated_at`.
- `architecture`: added `summary`, `generated_at`, node `description`/`files`/`inferred`, edge `id`/`label`/`inferred`, and structural guarantees.
- `modules`: added `id`, `symbol_count`, `depends_on`.
- `files`: defined the `FileEntry`/`Symbol` schema, pagination, and `language` filter.
- `data-flow`: replaced the single `flow` array with `flows[]` (each with `summary` and typed `steps`, including symbol and line references) to satisfy the PRD requirement for explanations, file references, and function references.
- `setup`: defined section schemas (`SetupItem`, `EnvironmentVariable`, `CommonIssue`) with sources; commands are display-only.
- `ask`: added `question_id`, `answer_id`, `explanation`, `evidence`, `interpretation`, `created_at`; made `SourceReference` line fields nullable; defined the insufficient-evidence response; clarified `confidence` semantics.
- Errors: added `request_id`; added `ANALYSIS_NOT_READY`, `RATE_LIMIT_EXCEEDED`, `REPOSITORY_TOO_LARGE`, `EMPTY_REPOSITORY`; added HTTP status mapping.
- Added the evidence-vs-interpretation (`inferred`) convention and the availability rule for sub-resources.
