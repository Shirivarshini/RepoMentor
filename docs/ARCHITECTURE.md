# RepoMentor — Architecture

**Status:** Phase 0 blueprint. No application code exists yet.
**Audience:** Implementers of Phases 1–9.

This document describes *how* RepoMentor is built. It deliberately does **not** duplicate:

- API endpoints, request/response schemas, error codes, or status values → see the root [`API_CONTRACT.md`](../API_CONTRACT.md) (canonical).
- Visual design tokens and component rules → see `docs/DESIGN.md`.
- Product requirements → see `RepoMentor_MVP_PRD.md`.
- Phase task lists → see `Implementation_Plan.md`.

Contents:

1. [Product scope](#1-product-scope)
2. [System overview](#2-system-overview)
3. [Frontend architecture](#3-frontend-architecture)
4. [Backend architecture](#4-backend-architecture)
5. [Database schema](#5-database-schema)
6. [GitHub integration](#6-github-integration)
7. [Analysis pipeline and code intelligence](#7-analysis-pipeline-and-code-intelligence)
8. [Chunking and embeddings](#8-chunking-and-embeddings)
9. [RAG pipeline](#9-rag-pipeline)
10. [Architecture and data-flow generation](#10-architecture-and-data-flow-generation)
11. [Security model](#11-security-model)
12. [Configuration](#12-configuration)
13. [Folder structure](#13-folder-structure)
14. [Development phases](#14-development-phases)
15. [Testing strategy](#15-testing-strategy)
16. [Decision log](#16-decision-log)
17. [Assumptions to verify](#17-assumptions-to-verify)

---

# 1. Product scope

RepoMentor helps a developer understand an unfamiliar **public** GitHub repository. It is a code-understanding tool, not a code executor.

## 1.1 In scope (MVP)

| # | Capability | Delivered in |
|---|---|---|
| 1 | Validate a public GitHub URL and fetch metadata, tree, and relevant files | Phase 2 |
| 2 | Detect languages, frameworks (from evidence), important files/directories, entry points | Phase 3 |
| 3 | Parse Python/JS/TS (then Java/C/C++/Go where practical) with Tree-sitter; extract symbols and line ranges | Phase 4 |
| 4 | Persist repository intelligence; chunk logically; embed into pgvector | Phase 5 |
| 5 | Repository-grounded Q&A with source references and insufficient-evidence behavior | Phase 6 |
| 6 | Architecture graph and data-flow structures | Phase 7 |
| 7 | Dashboard: overview, architecture, modules, files, data flow, setup, ask | Phase 8 |
| 8 | Tests, security controls, Docker, CI, README | Phase 9 |

The setup guide is generated in Phase 7 alongside architecture and data flow (it is deterministic-first, like the rest of the analysis) and displayed in Phase 8.

## 1.2 Out of scope

Kubernetes, microservices, billing/Stripe, enterprise SSO, RBAC, multi-org management, autonomous coding agents, automatic PRs/issue fixing, full IDE, mobile app, real-time collaboration, private repositories, user accounts, Q&A history endpoints. Interfaces are designed so these can be added later (see Section 16).

## 1.3 Design principles

1. **Evidence first.** Structure is derived deterministically from repository evidence. AI explains and labels; it does not invent structure.
2. **Untrusted input.** Repository contents are data, never instructions, never executed, never written to disk.
3. **Degrade, don't die.** If GitHub or Gemini is unavailable, the app shows a clear state and keeps working with whatever it has.
4. **Smallest reliable path.** No infrastructure beyond FastAPI + PostgreSQL/pgvector + Gemini.

---

# 2. System overview

```text
                     ┌──────────────────────────┐
                     │  React SPA (Vite, TS)    │
                     │  Tailwind · TanStack Q   │
                     └────────────┬─────────────┘
                                  │ HTTPS/JSON  (API_CONTRACT.md)
                     ┌────────────▼─────────────┐
                     │  FastAPI  (thin routes)  │
                     │  errors · limits · logs  │
                     └────────────┬─────────────┘
                                  │
                     ┌────────────▼─────────────┐
                     │        Services          │
                     │ repository · analysis ·  │
                     │ qa · architecture · setup│
                     └───┬──────────┬───────┬───┘
                         │          │       │
              ┌──────────▼──┐  ┌────▼─────┐ ┌▼──────────┐
              │ GitHub      │  │ Analyzers│ │ AI layer  │
              │ integration │  │ Tree-    │ │ Provider  │
              │ (httpx)     │  │ sitter   │ │ abstraction│
              └──────┬──────┘  └────┬─────┘ └─────┬─────┘
                     │              │             │
              api.github.com   (in-memory)   Gemini API
              raw.githubusercontent.com
                                  │
                     ┌────────────▼─────────────┐
                     │ Data-access layer        │
                     │ PostgreSQL + pgvector    │
                     └──────────────────────────┘
```

## 2.1 Layering rule (backend)

```text
api  →  services  →  { github | analyzers | ai }  →  data_access  →  db
```

- Routes never contain business logic, SQL, or GitHub/Gemini calls.
- Services orchestrate. They are the only layer that combines GitHub, analyzers, AI, and data access.
- `github`, `analyzers`, and `ai` never import from `api` or `services`.
- Only `data_access` executes SQL.
- Dependencies point downward only; enforced by review and an import-lint check in Phase 9.

## 2.2 End-to-end flow

```text
POST analyze ─► validate URL ─► GitHub metadata (sync) ─► create record ─► 202
                                              │
                         background job (in-process runner)
                                              ▼
  fetch tree ► filter ► fetch contents ► detect langs/frameworks ► parse (Tree-sitter)
  ► entry points/modules ► chunk ► embed ► generate insights ► persist ► COMPLETED

GET status (polling) ─► progress/stage
GET architecture | modules | files | data-flow | setup ─► stored results
POST ask ─► embed question ─► vector search ─► context ─► Gemini ─► validated answer + sources
```

---

# 3. Frontend architecture

## 3.1 Stack

React 19, Vite 8, TypeScript 6 (strict, no `any`), Tailwind CSS v4, React Router, TanStack Query, Axios, Lucide React, oxlint (linting, from the Vite template), and React Flow (added in Phase 8, when the architecture graph is built). Exact versions are pinned in `frontend/package-lock.json`.

Component library: `shadcn/ui` (mentioned in the PRD, absent from `CLAUDE.md`) is **not** adopted by default. The design system (pill controls, hairline borders, custom tokens) is bespoke, and fewer dependencies is a project rule. If a component needs non-trivial accessibility behavior (e.g. tabs), a single primitive may be added in Phase 8.

## 3.2 Routes

| Route | Screen |
|---|---|
| `/` | Landing (hero, repository input, product preview). |
| `/repositories/:repositoryId` | Redirects to `overview`. Shows analysis progress until `COMPLETED`. |
| `/repositories/:repositoryId/overview` | Header, stats, technologies, important files, entry points. |
| `/repositories/:repositoryId/architecture` | React Flow graph plus accessible components/connections list. |
| `/repositories/:repositoryId/modules` | Module cards. |
| `/repositories/:repositoryId/files` | File explorer. |
| `/repositories/:repositoryId/data-flow` | Flow diagrams. |
| `/repositories/:repositoryId/setup` | Setup guide. |
| `/repositories/:repositoryId/ask` | Ask RepoMentor. |
| `*` | Not found. |

The repository id lives in the URL so views are refresh-safe and shareable. Navigation is real links with `aria-current` (not client-only tabs). Labels and order follow `docs/DESIGN.md` (Overview, Architecture, Modules, Files, Data Flow, Setup, Ask).

## 3.3 Data layer

- `services/apiClient.ts`: one Axios instance (`VITE_API_BASE_URL`, timeouts). A response interceptor converts the error envelope into a typed `ApiError` (`code`, `message`, `details`, `status`, `requestId`).
- `types/api.ts`: TypeScript types mirroring `API_CONTRACT.md` exactly. Types change only when the contract changes. Unknown enum values map to a fallback branch.
- `hooks/`: one TanStack Query hook per resource (`useRepository`, `useAnalysisStatus`, `useArchitecture`, `useModules`, `useFiles`, `useDataFlow`, `useSetup`) plus `useAnalyzeRepository` and `useAskQuestion` mutations.
- Polling: `useAnalysisStatus` uses `refetchInterval` (~2s) only while status is `QUEUED`/`ANALYZING`; on `COMPLETED` it invalidates the repository queries. Sub-resource queries are enabled only once `COMPLETED`.
- Server state lives in TanStack Query. Local UI state (form input, conversation list) lives in component state. No global store.
- Q&A history is in-memory only (the contract exposes no history endpoint).

## 3.4 Component map (aligned with `docs/DESIGN.md`)

| Group | Components |
|---|---|
| `ui/` | `Button` (primary/ghost), `Tag`, `StatusBadge`, `Card`, `StatDisplay`, `CodeBlock`, `EmptyState`, `ErrorState`, `Skeleton` |
| `repository/` | `RepositoryInput`, `RepositoryHeader`, `AnalysisProgress`, `TechnologyTags` |
| `overview/` | `StatGrid`, `ImportantFiles`, `EntryPoints` |
| `architecture/` | `ArchitectureGraph` (React Flow), `ComponentList` (text alternative) |
| `modules/` | `ModuleCard` |
| `files/` | `FileExplorer`, `FileTree`, `SymbolList` |
| `dataflow/` | `DataFlowDiagram`, `FlowStep` |
| `setup/` | `SetupSection`, `CommandBlock` |
| `ask/` | `QuestionForm`, `AnswerCard`, `EvidenceList`, `SourceReference` |

Size guideline: components ≤ 250 lines; split by responsibility.

## 3.5 Frontend rules derived from the design and security model

- **Status is never color-only.** `StatusBadge` always shows text (`ANALYZING`, `COMPLETED`, `FAILED`; `QUEUED` is shown as a queued state) plus an icon.
- **Inferred vs evidenced.** Items with `inferred: true` use a distinct style (dashed edge, "inferred" label). Answer cards separate *Evidence* (with sources) from *Interpretation*.
- **Repository evidence is prominent.** `AnswerCard` order: Answer → Explanation → Relevant files → Symbols → Confidence/grounding metadata. It must not resemble a generic chat bubble UI.
- **No hover-only information.** The architecture and data-flow views expose the same information as text (node list, connection list, ordered steps).
- **XSS.** API text is rendered as text. No `dangerouslySetInnerHTML`. Limited Markdown rendering must use a renderer with raw HTML disabled (dependency decision in Phase 8).
- **Fonts.** Ivy Presto is a licensed typeface; the MVP uses the documented fallback (Playfair Display), self-hosted through the package manager, via the `--font-ivy-presto` token. Inter for UI (`--font-inter`).
- **Tokens.** `docs/DESIGN.md` CSS tokens become the Tailwind theme in `styles/tokens.css` using Tailwind v4's CSS-first `@theme` (there is no `tailwind.config.ts`). The design tokens already use Tailwind v4's theme namespaces (`--color-*`, `--font-*`, `--radius-*`), so they map to utilities 1:1 (`text-copper`, `rounded-pill`, `font-ivy-presto`). The default Tailwind palette is removed so no color exists outside the design system. Semantic status colors are chosen in Phase 8 and must meet contrast requirements on Carbon/Onyx.
- **React Flow layout.** Layered left-to-right layout computed from `NodeType` ranks (frontend → api/backend → service → data_access → database/external). No layout dependency unless the simple layout proves inadequate.
- **Error and loading states.** Each view has skeleton, empty (e.g. "No evidence found in repository"), and error states; `ApiError.code` maps to user-facing copy (rate limits show retry time).
- **Config.** `VITE_API_BASE_URL`; dev server proxies `/api` and `/health` to the backend to avoid CORS in development.

---

# 4. Backend architecture

## 4.1 Stack

Python 3.12 (confirmed in Phase 1), FastAPI, Pydantic v2 + `pydantic-settings`, SQLAlchemy 2.x (async) with `asyncpg`, Alembic, `pgvector` (SQLAlchemy type), `httpx`, Tree-sitter (Phase 4), Gemini SDK isolated behind the provider interface (Phase 6). Test tooling: `pytest`, `pytest-asyncio`, `respx`, `ruff`, `mypy`.

## 4.2 Package responsibilities

| Package | Responsibility |
|---|---|
| `api/` | FastAPI routers, dependency injection, exception handlers, request-id middleware. Translates HTTP ↔ service calls. |
| `core/` | Settings, structured logging with redaction, domain exception types, rate limiter, security helpers. |
| `db/` | Engine/session factory, declarative base. Migrations live in `backend/alembic/`. |
| `models/` | SQLAlchemy ORM models. Never returned from the API. |
| `schemas/` | Pydantic request/response models mirroring `API_CONTRACT.md`, plus internal analysis result models. |
| `data_access/` | All SQL. One store per aggregate (`RepositoryStore`, `FileStore`, `SymbolStore`, `ChunkStore`, `AnalysisStore`, `QAStore`). |
| `github/` | URL parsing/validation, GitHub HTTP client, file filtering. |
| `analyzers/` | Language/framework detection, structure and entry-point analysis, Tree-sitter parsers, chunker, import graph, secret redaction. Pure functions where possible; no I/O. |
| `ai/` | `LLMProvider`/`EmbeddingProvider` interfaces, `GeminiProvider`, retrieval, context builder, prompts, answer validation, fake providers for tests. |
| `services/` | Orchestration: analysis pipeline, job runner, Q&A, architecture/data-flow/setup generation. |

## 4.3 Analysis job runner

- `POST analyze` persists the repository record, then submits the run to an in-process **`JobRunner`** (started and stopped in the FastAPI lifespan), not to request-scoped background tasks.
- Concurrency: a global semaphore (`MAX_CONCURRENT_ANALYSES`, default 2) and a per-repository guard implemented as an atomic status transition (`UPDATE … WHERE status NOT IN ('QUEUED','ANALYZING')`). Duplicate requests attach to the running job.
- Status, progress, and stage are persisted at stage boundaries so `GET status` is a cheap read and survives client reconnects.
- Startup recovery: rows left `QUEUED`/`ANALYZING` by a previous process are marked `FAILED` (`ANALYSIS_FAILED`, "interrupted by a restart") so the user can retry.
- The runner sits behind a small interface, so a real queue (e.g. a worker process) can replace it later without touching services or the API. This satisfies the PRD note that large analysis should be able to become asynchronous later.
- CPU-bound work (Tree-sitter parsing) runs in a thread pool via `asyncio.to_thread` so the event loop stays responsive.

## 4.4 Errors

- Services raise typed domain exceptions (`ValidationFailed`, `RepositoryNotFound`, `GitHubRateLimited`, `AnalysisNotReady`, …) carrying a contract error code.
- One exception handler maps exceptions to the standard error envelope and HTTP status from `API_CONTRACT.md`, adds `request_id`, and logs internals server-side.
- Unhandled exceptions produce `INTERNAL_ERROR` with a generic message. Stack traces are logged, never returned. This conversion happens in the request-context middleware, which sits *inside* the CORS middleware, so 500 responses keep their CORS headers and the browser can read the error envelope.
- FastAPI's default 422 body is replaced with the envelope.

## 4.5 Logging

Structured JSON logs with request id, route, status, and latency. A redaction filter removes API keys, tokens, `Authorization` headers, and credentials embedded in URLs, both from messages and from structured fields. Inbound `X-Request-ID` values are accepted only if well-formed; otherwise a new id is generated (prevents log injection). The middleware writes the single access-log line per request (uvicorn's own access log is silenced; `/health` is logged at DEBUG so container health checks stay out of the logs). Repository content and user questions are not logged at INFO level.

## 4.6 Rate limiting

In-memory per-client-IP limiter (sufficient for the single-process MVP; the interface allows a shared store later). Stricter limits on `analyze` and `ask` (defaults in Section 12). Behind a reverse proxy, the client IP comes from a configured trusted-proxy header only when explicitly enabled.

## 4.7 Provider interfaces (`ai/`)

| Interface | Methods (conceptual) | MVP implementation |
|---|---|---|
| `LLMProvider` | `generate(prompt, …)`, `generate_structured(prompt, schema, …)` | `GeminiProvider` |
| `EmbeddingProvider` | `embed_documents(texts)`, `embed_query(text)` | `GeminiProvider` |

Both are selected by config (`LLM_PROVIDER=gemini`), so the provider is replaceable. `FakeLLMProvider`/`FakeEmbeddingProvider` (deterministic) are used in tests and can back an offline demo mode.

Provider behavior: timeouts, bounded retries with backoff for transient errors and quota responses, and mapping of failures to `AI_PROVIDER_ERROR`/`EMBEDDING_ERROR`. Free-tier limits are handled by batching embeddings and throttling.

---

# 5. Database schema

PostgreSQL 16 with the `vector` extension (pinned `pgvector/pgvector` image in Docker). SQLAlchemy 2.x models; Alembic migrations; the first migration runs `CREATE EXTENSION IF NOT EXISTS vector`. All primary keys are UUIDs; all timestamps are `timestamptz` (UTC).

## 5.1 Entity relationships

```text
repositories 1───1 repository_analyses
     │ 1
     ├───* repository_files 1───* code_symbols (self-ref parent)
     │            │ 1
     │            └───* code_chunks 1───1 embeddings
     └───* questions 1───1 answers 1───* source_references
```

`code_chunks` and `embeddings` also carry `repository_id` (denormalized) so retrieval filters by repository without joins. All child tables use `ON DELETE CASCADE` from `repositories`.

## 5.2 Tables

### `repositories`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `owner`, `name` | text NOT NULL | Canonical casing from GitHub. |
| `url` | text NOT NULL | Canonical URL. |
| `description` | text NULL | |
| `default_branch` | text NULL | |
| `commit_sha` | char(40) NULL | Analyzed commit. |
| `analysis_status` | enum NOT NULL | `QUEUED`, `ANALYZING`, `COMPLETED`, `FAILED`. |
| `analysis_stage` | text NULL | |
| `analysis_progress` | smallint NOT NULL DEFAULT 0 | CHECK 0–100. |
| `error_code`, `error_message` | text NULL | Safe messages only. |
| `qa_available` | boolean NOT NULL DEFAULT false | |
| `warnings` | jsonb NOT NULL DEFAULT `[]` | |
| `created_at`, `updated_at` | timestamptz NOT NULL | |
| `analyzed_at` | timestamptz NULL | |

Unique index on `(lower(owner), lower(name))`.

### `repository_files`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `repository_id` | uuid FK NOT NULL | |
| `path` | text NOT NULL | POSIX, relative. |
| `language` | text NULL | |
| `size` | integer NOT NULL | Bytes. |
| `content_hash` | char(64) NOT NULL | SHA-256 of content. |
| `purpose` | text NULL | |
| `is_important` | boolean NOT NULL DEFAULT false | |
| `importance_rank` | integer NULL | Reading order. |
| `is_entry_point` | boolean NOT NULL DEFAULT false | |
| `entry_point_kind` | text NULL | |
| `imports` | jsonb NOT NULL DEFAULT `[]` | Import specifiers, used for the import graph and ranking. |

Unique `(repository_id, path)`; index `(repository_id, language)`. Only analyzed files are stored; skipped files are counted, not stored.

### `code_symbols`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `file_id` | uuid FK NOT NULL | |
| `parent_symbol_id` | uuid FK NULL | Enclosing class/function. |
| `name` | text NOT NULL | |
| `qualified_name` | text NULL | |
| `symbol_type` | enum NOT NULL | `function`, `class`, `method`, `interface`, `type`, `route`, `other`. |
| `start_line`, `end_line` | integer NOT NULL | CHECK `start_line <= end_line`. |
| `signature` | text NULL | |
| `metadata` | jsonb NOT NULL DEFAULT `{}` | E.g. route method/path. |

Indexes: `(file_id)`, `(name)`.

### `code_chunks`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `repository_id` | uuid FK NOT NULL | Denormalized. |
| `file_id` | uuid FK NOT NULL | |
| `symbol_id` | uuid FK NULL | ON DELETE SET NULL. |
| `chunk_type` | enum NOT NULL | `function`, `method`, `class`, `file_section`, `doc_section`, `config`. |
| `content` | text NOT NULL | Redacted (Section 11) raw content. |
| `content_hash` | char(64) NOT NULL | Hash of path + content; used to reuse embeddings. |
| `start_line`, `end_line` | integer NOT NULL | |
| `token_estimate` | integer NOT NULL | |

Indexes: `(repository_id)`, `(file_id)`, `(repository_id, content_hash)`.

### `embeddings`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `chunk_id` | uuid FK NOT NULL UNIQUE | |
| `repository_id` | uuid FK NOT NULL | Denormalized filter column. |
| `model` | text NOT NULL | Embedding model id. |
| `dimensions` | smallint NOT NULL | |
| `embedding` | `vector(768)` NOT NULL | Dimension configured via `EMBEDDING_DIMENSIONS`; fixed by migration. |
| `created_at` | timestamptz NOT NULL | |

Cosine distance (`<=>`); similarity = `1 − distance`. Index: `(repository_id)` plus an HNSW index with `vector_cosine_ops`. At MVP scale (per-repository chunk cap) exact search filtered by `repository_id` is also acceptable; recall of filtered HNSW queries is verified in Phase 5 (pgvector iterative scan may be needed). Changing the embedding model or dimension requires a migration and re-embedding.

### `repository_analyses`

One current row per repository (`UNIQUE repository_id`); replaced on re-analysis.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `repository_id` | uuid FK NOT NULL UNIQUE | |
| `analysis_version` | text NOT NULL | Bump when stored JSON shapes change. |
| `summary` | jsonb NOT NULL | |
| `languages`, `frameworks` | jsonb NOT NULL | |
| `modules` | jsonb NOT NULL | |
| `important_files`, `entry_points` | jsonb NOT NULL | |
| `stats` | jsonb NOT NULL | |
| `architecture` | jsonb NOT NULL | Validated before storage. |
| `data_flow` | jsonb NOT NULL | Validated before storage. |
| `setup_instructions` | jsonb NOT NULL | |
| `created_at`, `updated_at` | timestamptz NOT NULL | |

The PRD's `RepositoryAnalysis` entity lists fewer fields; the additional JSONB columns hold the derived results the API serves. They are validated against internal Pydantic models on write and shaped into contract responses on read.

### `questions`, `answers`, `source_references`

| Table | Columns |
|---|---|
| `questions` | `id`, `repository_id` FK, `question` text, `created_at` |
| `answers` | `id`, `question_id` FK UNIQUE, `answer` text, `explanation` text NULL, `evidence` jsonb, `interpretation` text NULL, `grounded` boolean, `confidence` real, `model` text NULL, `created_at` |
| `source_references` | `id`, `answer_id` FK, `position` smallint, `file_path` text, `start_line` int NULL, `end_line` int NULL, `symbol` text NULL |

## 5.3 Re-analysis and data lifecycle

- One `repositories` row per `owner/name`. A new run replaces derived data (files, symbols, chunks, embeddings, analysis) for that repository.
- Embeddings are reused when a chunk's `content_hash` is unchanged and the embedding model/dimension match, avoiding regeneration.
- Q&A rows are retained until the repository is deleted. Only public repositories are analyzed; stored chunks are copies of public code. User-submitted question text is stored as-is; this is documented in the README.
- No repository content is ever written to the local filesystem.

---

# 6. GitHub integration

## 6.1 Access strategy

| Need | Source | Reason |
|---|---|---|
| Metadata | `GET api.github.com/repos/{owner}/{repo}` | Existence, visibility, default branch, description. |
| Tree | Git Trees API (recursive) for the commit of the default branch | One call yields all paths, sizes, and blob SHAs; reports truncation. |
| File contents | `raw.githubusercontent.com/{owner}/{repo}/{commit_sha}/{path}` | Pinned to one commit; does not consume the REST API quota. |

Rejected alternative: downloading the repository tarball. It fetches everything (including files we would filter), needs stream-and-abort size guards, and redirects to another host. Per-file raw fetches let us filter *before* downloading and cap total bytes precisely.

An optional `GITHUB_TOKEN` raises the REST rate limit (unauthenticated: 60 requests/hour; authenticated: much higher). The metadata and tree calls use few requests, but a token is recommended. This is verified in Phase 2.

## 6.2 URL validation (Phase 2)

- Only `https://github.com/{owner}/{repo}` (optional trailing `/` or `.git`); rules in `API_CONTRACT.md`.
- Owner: 1–39 chars, alphanumeric and `-`, no leading/trailing `-`. Repository: 1–100 chars of `[A-Za-z0-9._-]`; `.` and `..` rejected.
- **Outbound URLs are constructed from the validated owner/name/sha/path only.** User-supplied URLs are never fetched directly.

## 6.3 HTTP client policy

- Fixed host allow-list: `api.github.com`, `raw.githubusercontent.com`.
- Redirects disabled (or only followed to the allow-list).
- Timeouts (connect/read), bounded retries with exponential backoff on network errors and 5xx.
- Bounded concurrency for file fetches; streaming reads with a per-file byte cap (aborts even if the tree lied about size).
- Rate limits: detect `403`/`429` with an exhausted quota header; surface `GITHUB_RATE_LIMIT` with the reset time.
- `404` → `REPOSITORY_NOT_FOUND` (missing **or** private). Empty repository, truncated tree, or too many entries → the failure states in `API_CONTRACT.md`.

## 6.4 File filtering

Applied to the tree **before** any content download.

| Rule | Behavior |
|---|---|
| Ignored directories (required) | `.git/`, `node_modules/`, `venv/`, `.venv/`, `__pycache__/`, `dist/`, `build/`, `coverage/`, `.cache/`, `.idea/`, `.vscode/` |
| Extended ignored directories (configurable) | `vendor/`, `.next/`, `target/`, `out/`, `.gradle/`, `.tox/`, `.pytest_cache/`, `.mypy_cache/`, `site-packages/` |
| Media, archives, binaries | Skipped by extension (images, video, audio, fonts, `zip`/`tar`/`gz`, `exe`/`dll`/`so`/`class`/`jar`, etc.). |
| Generated/noisy files | Minified assets (`*.min.js`), source maps, lock files (`package-lock.json`, `yarn.lock`, `poetry.lock`, …) are not chunked. Dependency manifests (`package.json`, `requirements.txt`, `pyproject.toml`, …) are always kept. |
| Secret-bearing files | `.env` and `.env.*` (except `.env.example`, `.env.sample`, `.env.template`), private keys (`*.pem`, `id_rsa*`, `*.key`) are never downloaded. |
| Size | Files over `MAX_FILE_SIZE_BYTES` are skipped. |
| Repository cap | Tree entries over `MAX_TREE_ENTRIES` (or a truncated tree) → `REPOSITORY_TOO_LARGE`. |
| File-count cap | Remaining files are prioritized and the top `MAX_ANALYZED_FILES` are analyzed; `stats.truncated` is set if any were dropped. |

**Priority order** when capping: README/docs at the root → dependency and configuration files → likely entry points → source files by directory importance (`src`, `app`, `api`, `routes`, `services`, `models`, …) → tests → everything else.

Skipped-file counts are recorded in `stats.files_skipped`. All limits are configurable.

## 6.5 Path handling

Paths from the tree are treated as opaque strings: stored as data, URL-encoded into outbound URLs, never joined to a filesystem path, and rejected if they contain `..` segments, absolute prefixes, backslashes, or NUL bytes. Nothing is written to disk, so path traversal has no filesystem target.

---

# 7. Analysis pipeline and code intelligence

## 7.1 Stages and progress

Progress is monotonic 0–100 and persisted at stage boundaries. Stage names are the `AnalysisStage` values in `API_CONTRACT.md`.

| Stage | Progress | Work |
|---|---:|---|
| (queued) | 0 | Record created. |
| `FETCHING_REPOSITORY` | 1–25 | Metadata (already fetched at request time), tree, filtering, prioritization, content download. |
| `ANALYZING_STRUCTURE` | 25–40 | Languages, frameworks, dependency/config files, important directories and files, entry-point candidates, README analysis. |
| `PARSING_CODE` | 40–55 | Tree-sitter symbols, imports, routes, line ranges; refined entry points. |
| `CHUNKING` | 55–60 | Logical chunks (Section 8). |
| `EMBEDDING` | 60–85 | Batched embeddings, with content-hash reuse. |
| `GENERATING_INSIGHTS` | 85–97 | Summary, module purposes, architecture, data flow, setup guide. |
| `FINALIZING` | 97–100 | Validate, persist, set `COMPLETED`. |

## 7.2 Deterministic analysis (Phases 3–4)

Nothing in this section calls an LLM. It must be sufficient to describe the repository's structure on its own.

- **Languages:** by extension/filename mapping; percentage by analyzed source bytes.
- **Frameworks:** rule table of evidence patterns — dependency entries (`package.json`, `requirements.txt`, `pyproject.toml`, `pom.xml`, `go.mod`), config files (`next.config.*`, `vite.config.*`), and characteristic imports. Every detected framework carries `SourceReference` evidence; no evidence, no framework.
- **Important directories:** name heuristics (`src`, `app`, `api`, `routes`, `controllers`, `services`, `models`, `components`, `database`, `utils`) validated by contents.
- **Important files:** README, dependency manifests, Dockerfile/compose, configuration, main application files, routing and database files. Ranked into a reading order.
- **Entry points:** rules per ecosystem, e.g. FastAPI/Flask app instantiation, `if __name__ == "__main__"`, `package.json` `main`/`scripts`, Vite `index.html` → `main.tsx`, Go `func main`, Java `public static void main`/Spring Boot application class. Each has a `reason` citing the evidence.
- **Modules:** groups of files by directory and naming convention, with a module dependency graph from resolved imports.
- **Symbols:** via Tree-sitter (below).

## 7.3 Tree-sitter (Phase 4)

- Language registry maps file extension → parser + symbol query. Phase 4 order: Python, JavaScript, TypeScript (including TSX/JSX), then Java, C, C++, Go where practical.
- Extracted: functions, classes, methods, interfaces/types, imports/exports, routes (framework decorators/calls such as FastAPI/Flask decorators, Express `app.get(...)`) where detectable, with 1-based inclusive line ranges and parent relationships.
- Per-language modules (≤ 300 lines each) behind one parser interface; unsupported languages get no symbols and a warning, but the file remains listed and chunkable as text.
- Parse failures are per-file: the file is kept without symbols and counted; the run continues.
- **Not** full static analysis. Import/call relationships are best-effort and are labeled as such (`inferred`) when used in generated flows.
- Grammar packaging (individual grammar packages vs a language-pack) is decided at the start of Phase 4 after verifying current availability.

---

# 8. Chunking and embeddings

## 8.1 Chunking rules (Phase 5)

Prefer logical boundaries; never split blindly by character count.

| Source | Chunk |
|---|---|
| Function / method | One chunk per symbol, including decorators and docstring. |
| Class | Class header + docstring + member signatures; each method is also its own chunk. |
| Oversized symbol | Split on logical blocks (blank-line/statement boundaries) up to `MAX_CHUNK_TOKENS`, each with correct line ranges. |
| Top-level leftovers (imports, constants, small statements) | Grouped into a `file_section` chunk. |
| Markdown/docs | One chunk per heading section (`doc_section`). |
| Config/manifest files | Whole file if small (`config`); otherwise by top-level section. |
| Unsupported languages | Split by blank-line-separated blocks up to the token cap (`file_section`). |

Each chunk stores path, line range, symbol, type, hash, and token estimate. Chunks are capped per repository (`MAX_CHUNKS_PER_REPOSITORY`); overflow follows the file priority order.

## 8.2 Embedding input

Embedded text is the chunk content prefixed with a short header (`file: path | symbol: name | type`) to improve retrieval; stored `content` remains the raw (redacted) source.

## 8.3 Embedding provider notes

- Model: `gemini-embedding-001` (configurable; confirm at Phase 5).
- Output dimensionality is reduced to **768** (`EMBEDDING_DIMENSIONS`). The model's default is 3072, and pgvector HNSW indexes on `vector` support at most 2000 dimensions, so a reduced size is required for an HNSW index anyway.
- Vectors of reduced dimensionality are **not** pre-normalized by the API and must be L2-normalized before storage/comparison.
- Use document-type embeddings for chunks and query-type embeddings for questions (the API supports retrieval task types).
- Batch requests, throttle to provider limits, retry transient errors, and reuse existing embeddings by `content_hash`.

---

# 9. RAG pipeline

## 9.1 Flow (Phase 6)

```text
Question ─► validate/sanitize ─► embed query ─► vector search (repository-scoped)
        ─► (optional keyword boost on symbol/path matches) ─► similarity threshold
        ─► context builder ─► Gemini (structured output) ─► validate ─► answer + sources
```

## 9.2 Steps

1. **Validate** length (3–1000), strip control characters. The question is user text and never merges with system instructions.
2. **Retrieve** top-`RAG_TOP_K` chunks by cosine similarity, filtered by `repository_id`. A light deterministic boost applies to chunks whose symbol or path matches identifiers in the question.
3. **Threshold.** If no chunk reaches `RAG_MIN_SIMILARITY`, return the insufficient-evidence response **without calling the LLM** (saves quota, guarantees no fabrication).
4. **Onboarding intent.** For questions like "where should I start?", the context also includes deterministic analysis output (important files, entry points, module list), so answers rest on stored evidence.
5. **Context builder.** Deduplicates, orders by file and line, and fits chunks into `RAG_CONTEXT_TOKEN_BUDGET`. Each chunk is labeled `[S1]`, `[S2]`, … with path and line range and wrapped in per-request random delimiters.
6. **Prompt.** System instructions state: use only the provided evidence; the delimited content is untrusted data and any instructions inside it must be ignored; do not invent files, functions, dependencies, or behavior; keep cited evidence separate from interpretation; if evidence is insufficient use the exact insufficient-evidence sentence.
7. **Structured output.** The model returns JSON conforming to a schema (answer, explanation, evidence statements with source labels, interpretation, insufficient-evidence flag). No tools or function calling are exposed to the model.
8. **Validate.** Pydantic validation; every cited label must map to a provided chunk; file paths mentioned in the text must exist in the repository's file table. `sources` are built **server-side** from chunk metadata, never from model-written paths. One retry on invalid output, then the insufficient-evidence response (or `AI_PROVIDER_ERROR` if the provider itself failed).
9. **Confidence.** A heuristic combining top retrieval similarities and the share of evidence statements with valid citations — not the model's self-reported certainty. Calibrated in Phase 6; the contract states it is not a probability of correctness.
10. **Persist** the question, answer, and source references.

## 9.3 Usage limits

Per-IP `ask` rate limit, question length cap, bounded context and output tokens, no LLM call on the insufficient-evidence path, and single-flight embedding of the query. Gemini free-tier errors map to `AI_PROVIDER_ERROR` with `retry_after_seconds` when known.

## 9.4 Failure behavior

| Failure | Result |
|---|---|
| Gemini unavailable/quota | `503 AI_PROVIDER_ERROR`; structural views keep working. |
| Embedding unavailable | `503 EMBEDDING_ERROR` on `ask`; analysis may complete with `qa_available: false`. |
| No relevant evidence | `200` insufficient-evidence answer. |
| Analysis not complete | `409 ANALYSIS_NOT_READY`. |

---

# 10. Architecture and data-flow generation

Generated in Phase 7 from stored deterministic data, with AI used only to label and explain.

## 10.1 Architecture graph

1. **Deterministic candidates:** node candidates from frameworks, directory roles, entry points, Docker/compose services, and database evidence (ORM models, connection config, migration files). Edge candidates from resolved import relationships between node file sets and from HTTP client/route correspondences where detectable.
2. **AI labeling (optional):** given the deterministic facts and symbol inventory, the model proposes labels, descriptions, and additional edges as structured JSON.
3. **Validation:** schema-validated. Nodes must reference existing files (nodes with no evidence are dropped). Edges must reference existing nodes. Edges supported by parsed evidence are `inferred: false`; AI-only edges are `inferred: true`.
4. **Fallback:** if AI is unavailable, the graph is built from deterministic candidates only (`summary` may be `null`).

## 10.2 Data flow

1. Start from detected route symbols and UI entry points.
2. Trace handler → imported/called functions through the import graph (name-based, best-effort) into service, data-access, and database files.
3. Score candidate chains by evidence strength; keep the strongest few per feature area (e.g. registration, login).
4. AI writes the flow name and human-readable summary; steps come from the traced chain. Steps proven by imports/calls are `inferred: false`; connective steps are `inferred: true`.
5. Return no flows (with an explanatory `message`) when nothing is supported.

## 10.3 Setup guide

Built from README sections, dependency manifests, Dockerfiles/compose, `.env.example`-style files, and scripts. Commands are extracted as display-only text with sources. Empty sections stay empty rather than filled with generic advice. Secret-looking values are never emitted.

---

# 11. Security model

Repository content and user input are untrusted. RepoMentor never executes, builds, installs, or clones repository code.

## 11.1 Threats and controls

| # | Threat | Vector | Controls | Phase |
|---|---|---|---|---|
| T1 | Execution of malicious repository code | Scripts, build files, package hooks | Never execute, install, clone, or write repository content to disk; content stays in memory and the database as text. | 2 |
| T2 | Prompt injection | README, comments, docstrings, filenames, commit text, user question | Repository content delimited as data with per-request random delimiters; system prompt forbids following embedded instructions; structured output only; no tools for the model; server-built sources; output validation; user question kept separate from instructions. | 6 |
| T3 | SSRF | Crafted `repository_url`, redirects | Strict URL parsing; fixed host allow-list; outbound URLs built from validated tokens; redirects disabled or allow-listed; no user-supplied URLs fetched. | 2 |
| T4 | Path traversal | Tree paths such as `../..` | Paths treated as opaque data; validated; never joined to filesystem paths; no filesystem writes. | 2 |
| T5 | Oversized repositories/files, resource exhaustion | Huge repos, huge files, decompression tricks | Filter before download; per-file streaming byte cap; entry, file, and chunk caps; no archive downloads or extraction; parse timeouts per file. | 2–5 |
| T6 | API abuse and denial of service | Rapid `analyze`/`ask` calls | Per-IP rate limits; concurrency cap and per-repository single-flight; timeouts; request size limits. | 3, 9 |
| T7 | Excessive LLM usage/cost | Repeated or long questions, forced re-analysis | Question length cap; bounded context/output; no LLM call without evidence; embedding reuse by hash; `ask` and `analyze` limits. | 6, 9 |
| T8 | Secret leakage (ours) | Logs, responses, images, repo | Keys only via environment; never in code, logs, responses, or Docker images; log redaction; errors omit internals; `.env` in `.gitignore`. | 1, 9 |
| T9 | Secret leakage (repository's) | Committed credentials in public repos | Secret-bearing files are not downloaded; regex-based redaction of key/token patterns in chunks before storage, embedding, and LLM use; secret-looking env defaults never returned. Best-effort, not a guarantee. | 2, 5 |
| T10 | XSS via repo-derived text | Malicious file names, symbols, README in answers | API text rendered as text; no raw HTML; sanitized Markdown; CSP headers in production. | 8, 9 |
| T11 | SQL injection | User input in queries | SQLAlchemy parameterized queries only; no string-built SQL. | 1+ |
| T12 | Information disclosure via errors | Stack traces, DB errors | Global exception handler; generic messages; server-side logging with request ids. | 1 |
| T13 | Log injection/leakage | Repo strings or questions in logs | Structured logs; no repository content or questions at INFO; control characters escaped. | 1, 9 |
| T14 | Misconfigured CORS | Wide-open origins | Explicit `CORS_ALLOWED_ORIGINS`; no wildcard with credentials. | 1 |
| T15 | Container/supply-chain risk | Base images, dependencies | Pinned image tags and dependency versions; non-root containers; CI dependency audit. | 9 |
| T16 | Hallucinated repository facts | Model invention | Threshold-gated retrieval, grounding validation, insufficient-evidence path, evidence/interpretation split, `inferred` flags. | 6, 7 |
| T17 | Executing displayed commands | Users copy setup commands from a malicious repo | Commands are labeled as repository-derived, displayed only, never executed by RepoMentor; README notes to review before running. | 8 |

## 11.2 Residual risks (accepted for MVP)

- The API is unauthenticated; abuse is bounded by rate limits and caps only. Requests from behind shared IPs share limits.
- The in-memory rate limiter and job runner assume a single backend process.
- Regex-based secret redaction cannot catch every secret format.
- Prompt-injection defenses reduce, but cannot eliminate, model manipulation; the no-tools design and server-built sources limit the impact to answer text.
- Free-tier LLM quotas can throttle the service under load.
- Repository licenses are not evaluated; stored chunks are copies of public code.

---

# 12. Configuration

All configuration is via environment variables (Pydantic Settings). `.env.example` includes only variables actually used; each variable is added in the phase that first uses it. Secrets are never committed.

| Variable | Purpose | Default / example | Phase |
|---|---|---|---|
| `ENVIRONMENT` | `development` / `production` | `development` | 1 |
| `LOG_LEVEL` | Log verbosity | `INFO` | 1 |
| `DATABASE_URL` | Async PostgreSQL DSN | (required) | 1 |
| `CORS_ALLOWED_ORIGINS` | Allowed browser origins | `http://localhost:5173` | 1 |
| `GITHUB_TOKEN` | Optional GitHub token (higher rate limit) | empty | 2 |
| `GITHUB_HTTP_TIMEOUT_SECONDS` | GitHub request timeout | `10` | 2 |
| `MAX_TREE_ENTRIES` | Hard repository size limit | `50000` | 2 |
| `MAX_ANALYZED_FILES` | Files analyzed after prioritization | `500` | 2 |
| `MAX_FILE_SIZE_BYTES` | Per-file limit | `200000` | 2 |
| `EXTRA_IGNORED_DIRS` | Extended ignore list | see Section 6.4 | 2 |
| `MAX_CONCURRENT_ANALYSES` | Analysis concurrency | `2` | 3 |
| `MAX_CHUNK_TOKENS` | Chunk size cap | `800` | 5 |
| `MAX_CHUNKS_PER_REPOSITORY` | Chunk cap | `5000` | 5 |
| `EMBEDDING_MODEL` | Embedding model id | `gemini-embedding-001` | 5 |
| `EMBEDDING_DIMENSIONS` | Vector size | `768` | 5 |
| `LLM_PROVIDER` | Provider selector | `gemini` | 6 |
| `GEMINI_API_KEY` | Gemini credential | (required for AI) | 5–6 |
| `GEMINI_GENERATION_MODEL` | Generation model id | chosen at Phase 6 | 6 |
| `RAG_TOP_K` | Retrieved chunks | `12` | 6 |
| `RAG_MIN_SIMILARITY` | Evidence threshold | calibrated in Phase 6 | 6 |
| `RAG_CONTEXT_TOKEN_BUDGET` | Context size | `6000` | 6 |
| `MAX_QUESTION_LENGTH` | Question cap | `1000` | 6 |
| `RATE_LIMIT_ANALYZE` | Analyze limit per client | e.g. `10/hour` | 9 |
| `RATE_LIMIT_ASK` | Ask limit per client | e.g. `10/minute` | 9 |

Default values are starting points and are validated during their phase. Limits must remain configurable.

---

# 13. Folder structure

```text
repomentor/
├── API_CONTRACT.md                # canonical API contract (root)
├── CLAUDE.md
├── README.md                      # Phase 1, completed in Phase 9
├── docker-compose.yml             # Phase 1
├── .env.example                   # Phase 1
├── .gitignore
├── .github/workflows/ci.yml       # Phase 9
├── docs/
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_STATUS.md
│   └── DESIGN.md                  # visual source of truth
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json          # + tsconfig.app.json, tsconfig.node.json
│   ├── .oxlintrc.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── routes.tsx
│       ├── pages/                 # Landing, Overview, Architecture, Modules, Files, DataFlow, Setup, Ask, NotFound
│       ├── layouts/               # AppLayout, RepositoryLayout
│       ├── components/
│       │   ├── ui/
│       │   ├── repository/
│       │   ├── overview/
│       │   ├── architecture/
│       │   ├── modules/
│       │   ├── files/
│       │   ├── dataflow/
│       │   ├── setup/
│       │   └── ask/
│       ├── hooks/                 # TanStack Query hooks
│       ├── services/              # apiClient.ts, repositoriesApi.ts
│       ├── types/                 # api.ts (mirrors API_CONTRACT.md)
│       ├── lib/                   # formatting, error mapping, class helpers
│       └── styles/                # tokens.css, index.css
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── requirements-dev.txt   # test and lint tools
    ├── pyproject.toml         # tool configuration only (pytest, ruff, mypy)
    ├── alembic.ini
    ├── alembic/versions/
    ├── app/
    │   ├── main.py
    │   ├── api/
    │   │   ├── errors.py          # exception handlers -> error envelope
    │   │   ├── health.py
    │   │   ├── middleware.py      # request id, access log, last-resort 500 handling
    │   │   ├── deps.py            # added when the first dependency is needed (Phase 2+)
    │   │   └── v1/                # router.py (Phase 1), repositories.py (Phase 3)
    │   ├── core/                  # config.py, logging.py, exceptions.py, rate_limit.py, security.py
    │   ├── db/                    # base.py, session.py
    │   ├── models/                # repository, repository_file, code_symbol, code_chunk, embedding, repository_analysis, qa
    │   ├── schemas/               # common, repository, architecture, modules, files, data_flow, setup, qa, errors
    │   ├── data_access/           # repository_store, file_store, symbol_store, chunk_store, analysis_store, qa_store
    │   ├── github/                # url_parser, client, file_filter
    │   ├── analyzers/
    │   │   ├── language_detector.py
    │   │   ├── framework_detector.py
    │   │   ├── structure_analyzer.py
    │   │   ├── entry_points.py
    │   │   ├── module_detector.py
    │   │   ├── import_graph.py
    │   │   ├── chunker.py
    │   │   ├── secret_redactor.py
    │   │   └── parsing/           # registry.py + one module per language
    │   ├── ai/                    # provider.py, gemini_provider.py, embeddings.py, retrieval.py, context_builder.py, prompts.py, answer_validator.py, fakes.py
    │   └── services/              # repository_service, analysis_service, job_runner, qa_service, architecture_service, data_flow_service, setup_service
    └── tests/
        ├── unit/
        ├── integration/
        └── fixtures/              # tiny sample repositories as static data
```

Notes:

- `docs/API.md` (listed in the PRD's sample structure) and `docs/04_API_CONTRACT.md` are intentionally **not** created; the root `API_CONTRACT.md` is canonical.
- `data_access/` is used instead of `repositories/` (PRD sample structure) because "repository" already means a GitHub repository throughout the domain.
- Files stay within the size guidelines (frontend components ≤ 250 lines, backend modules ≤ 300 lines); split by responsibility rather than by line count alone.

---

# 14. Development phases

Each phase ends at a clean boundary: verify, document (`IMPLEMENTATION_STATUS.md`), update the contract if the API changed, then stop.

| Phase | Deliverable | Depends on | Verification gate |
|---|---|---|---|
| 0 — Architecture & Planning | This document, finalized `API_CONTRACT.md`, `IMPLEMENTATION_STATUS.md` | — | Acceptance criteria in the status file. |
| 1 — Scaffolding | Frontend and backend skeletons, settings, error envelope, `/health`, Alembic + pgvector, Dockerfiles, compose, `.env.example`, README stub | 0 | `docker compose up --build`; `/health` returns ok; frontend loads. |
| 2 — GitHub integration | URL validation, metadata, tree, filtering, content fetch, limits, failure mapping, repository persistence, and a service-level "register repository" operation (URL validation + GitHub lookup + record). The HTTP `analyze` endpoint is **not** exposed yet, so no repository can be left `QUEUED` without a runner. | 1 | URL/filter/client tests (mocked HTTP); manual fetch of a small public repo via a service call. |
| 3 — Repository analyzer | Languages, frameworks, files, directories, entry points, README analysis, stored summary; `JobRunner`, status/progress persistence, and the `analyze`, repository detail, and `status` endpoints | 2 | Analyzer tests on fixtures; `analyze` → status progresses to `COMPLETED`. |
| 4 — Code intelligence | Tree-sitter parsers, symbols, imports, routes, line ranges, refined entry points | 3 | Parser tests per language; symbols returned for fixtures. |
| 5 — Database + embeddings | Full schema and migrations, chunker, embedding service, vector search | 4 | Migration up/down; chunking tests; similarity search test against a real pgvector database. |
| 6 — AI/RAG | Provider interfaces, retrieval, context builder, prompts, `ask`, insufficient-evidence behavior, injection defenses | 5 | RAG tests with fake provider; grounding and injection tests; manual Gemini check. |
| 7 — Architecture + data flow | Architecture, data-flow, setup generation and validation; endpoints | 6 (deterministic parts may start after 4) | Schema-validation and invariant tests; endpoints return contract-shaped data. |
| 8 — Frontend dashboard | All pages, states, React Flow, file explorer, Ask UI, responsive/accessible layout | 7 | Type check and build; component tests; full journey in a browser. |
| 9 — Testing + security + Docker | Coverage of test areas, security controls, rate limiting, CI, final README | 8 | `docker compose up --build`; CI green; security checklist complete. |

**Rules for every phase:** inspect before editing; implement only the current phase; do not rewrite working code; update tests and docs; never claim verification that did not happen.

---

# 15. Testing strategy

| Layer | Tooling | Notes |
|---|---|---|
| Backend unit | `pytest` | URL validation, file filtering, analyzers, chunker, redaction, answer validation, context builder. |
| GitHub integration | `pytest` + `respx` | HTTP mocked: success, 404, rate limit, timeout, truncated tree, empty repo. |
| Parsing | `pytest` + fixtures | Small fixture files per language with expected symbols and line ranges. |
| Database / vector | `pytest` against a real PostgreSQL+pgvector container | Migrations, stores, similarity search. |
| RAG | `pytest` with fake providers | Retrieval ordering, threshold, insufficient evidence, injection strings in fixtures, invalid model output. |
| API | `httpx` async test client | Contract shapes, error envelope, availability rule, rate limits. |
| Frontend | Vitest + Testing Library; `tsc`, build | Repository input, status polling states, dashboard views, Ask flow (API mocked). |
| End-to-end (manual, documented) | Browser + Docker | The demo scenario from `Implementation_Plan.md`. |

Contract conformance: response models in `schemas/` are the single Pydantic definition of the contract; frontend types mirror it. Contract changes update both plus tests.

---

# 16. Decision log

| # | Decision | Rationale |
|---|---|---|
| D1 | Root `API_CONTRACT.md` is the only API spec. | Required by `CLAUDE.md`, PRD, and the plan; avoids drift. |
| D2 | Analysis runs in an in-process job runner behind an interface. | No queue infrastructure for the MVP; replaceable later. |
| D3 | `analyze` verifies the repository on GitHub synchronously. | Immediate, clear errors for the most common user mistakes. |
| D4 | File contents from `raw.githubusercontent.com` pinned to the commit SHA. | Filter before download; avoids REST quota; consistent snapshot. |
| D5 | Deterministic analysis first; AI labels and explains. | Satisfies "no LLM-invented structure" and keeps the demo working without AI. |
| D6 | Structural analysis completes even if embeddings/AI fail (`qa_available: false`). | Reliability rule: remain demoable when external dependencies fail. |
| D7 | 768-dimension embeddings, L2-normalized. | Fits HNSW limits, recommended quality/storage balance, one migration-fixed size. |
| D8 | Insufficient-evidence check happens before calling the LLM. | Prevents fabrication, saves free-tier quota. |
| D9 | Sources are built server-side from chunk metadata. | Model cannot invent file references. |
| D10 | `inferred` flag on graph edges, flow steps, and evidence vs interpretation in answers. | Contract rule: distinguish evidence from interpretation. |
| D11 | `data_access/` instead of `repositories/`. | Avoids ambiguity with GitHub repositories. |
| D12 | No `shadcn/ui` by default. | Bespoke design system; fewer dependencies. |
| D13 | One current analysis row per repository (JSONB result columns). | Simple, sufficient for MVP; versioned via `analysis_version`. |
| D14 | Playfair Display fallback for Ivy Presto. | Ivy Presto is licensed; fallback is specified by the design system. |
| D15 | No accounts, private repos, or history endpoint. | Out of MVP scope; interfaces leave room for them. |
| D16 | Tailwind CSS v4 with CSS-first `@theme`; no `tailwind.config.ts`. | The design tokens in `docs/DESIGN.md` already use v4 theme namespaces, so they map to utilities directly. (Phase 1) |
| D17 | Run uvicorn with `--factory` (`app.main:create_app`); no module-level `app`. | Importing the module never reads settings, so tests and tools import safely. (Phase 1) |
| D18 | Unhandled exceptions are converted in the request-context middleware, inside CORS. | Starlette's outermost error handler bypasses CORS, which would hide 500 bodies from the browser. (Phase 1) |
| D19 | Database engine is created lazily; `/health` is liveness only and never touches the database. | The API starts and reports liveness even while PostgreSQL is down; readiness can be added later without breaking the contract. (Phase 1) |
| D20 | Compose runs `alembic upgrade head` before starting the API in development. | The database schema is always current when the stack starts. (Phase 1) |

**Extension points kept open:** `LLMProvider`/`EmbeddingProvider`, `JobRunner`, rate-limit store, GitHub client (token/OAuth for private repositories), analysis version, additional Tree-sitter languages.

---

# 17. Assumptions to verify

These are stated in the design but must be confirmed at the start of the relevant phase.

| Item | Verify in |
|---|---|
| ✅ Verified in Phase 1: Python 3.12 and Node 22 LTS; direct dependencies pinned in `backend/requirements*.txt` and `frontend/package-lock.json`. | 1 |
| GitHub unauthenticated/authenticated rate limits and Git Trees API truncation limits; raw-content behavior for large/LFS files. | 2 |
| Tree-sitter Python packaging and available grammar packages for each language. | 4 |
| `pgvector` version in the chosen Docker image; HNSW recall with `repository_id` filtering (iterative scan vs exact search). | 5 |
| Current Gemini embedding model name, supported dimensions, task types, batch limits, and free-tier quotas. | 5 |
| Current Gemini generation model name, structured-output support, and free-tier quotas; `GEMINI_GENERATION_MODEL` default. | 6 |
| `RAG_MIN_SIMILARITY` and confidence heuristic calibration on real repositories. | 6 |
| Semantic-status color tokens and contrast. | 8 |
