# RepoMentor

A full-stack onboarding assistant for unfamiliar public GitHub repositories. It fetches a commit-pinned snapshot, analyzes source structure, and displays repository evidence through a React dashboard. Gemini enables repository-grounded Q&A when configured.

**Current phase: Phase 9 — validation in progress.** See [implementation status](docs/IMPLEMENTATION_STATUS.md) for verified results and remaining acceptance work. This is an implemented MVP handoff, not a claim that every PRD acceptance criterion has passed.

## Features

- Strict public GitHub URL validation, read-only bounded downloads and filtering.
- Languages, dependency-backed frameworks, important files and likely entry points.
- Isolated Tree-sitter parsing for Python, JavaScript, TypeScript/TSX, Java, C, C++ and Go.
- PostgreSQL persistence, line-based chunks, cached 768-dimensional Gemini embeddings and repository-scoped pgvector cosine retrieval.
- Structured answers with server-built source references, evidence/interpretation separation and insufficient-evidence fallback.
- Overview, React Flow architecture, modules, file explorer/symbols, inferred data flows, setup guide and Q&A.
- Analysis progress, retries, request tracing, bounded request bodies, per-client rate limits and configurable CORS.

## Start with Docker

Requirements: Docker Desktop running with Linux containers and Docker Compose v2.

```powershell
Copy-Item .env.example .env
# Edit .env: optionally set GITHUB_TOKEN and set GEMINI_API_KEY for Q&A.
# If port 8000 is occupied, set BACKEND_PORT=8001.
docker compose up --build -d
docker compose ps
```

Open http://localhost:5173. API docs are at http://localhost:8000/docs by default, or the BACKEND_PORT you selected. This workspace currently uses **8001** because another project occupies 8000.

If .env already exists, edit it instead of overwriting it. The handoff ZIP excludes .env. Without Gemini credentials the repository dashboard still works; it reports that embeddings/Q&A are unavailable. After configuring a key:

```powershell
docker compose up -d --force-recreate backend
```

Then use **Reanalyze** in the dashboard. RepoMentor does not execute repository commands. Setup commands are displayed for review only.

## Architecture and source layout

```text
React / Vite / TypeScript / TanStack Query / React Flow
  -> FastAPI REST API
     -> GitHub snapshot -> isolated parsing -> chunking
     -> PostgreSQL + pgvector
     -> Gemini embedding + grounded Q&A provider
```

- `backend/app/github`: download and URL/file safety.
- `backend/app/analyzers`: source parsing, chunks, structure and derived views.
- `backend/app/services`: database persistence and bounded analysis jobs.
- `backend/app/ai`: provider interfaces, Gemini REST adapter and RAG validation.
- `backend/app/api`, `schemas`, `models`: API contracts and persistence models.
- `frontend/src/pages`: dashboard and section views.
- `frontend/src/services`, `types`: typed API integration.
- `backend/alembic`: migrations. Compose applies them before API startup.

Use `backend/app/main.py` and `frontend/src/pages/LandingPage.tsx` as the application entry points. The old root-level Python/TSX exports are not used and are omitted from the ZIP.

The public API is documented in [API_CONTRACT.md](API_CONTRACT.md). Architecture refinements and limitations are in [implementation notes](docs/IMPLEMENTATION_NOTES.md).

## Configuration

See `.env.example`. Important settings:

| Variable | Purpose |
|---|---|
| GEMINI_API_KEY | Enables embeddings and Q&A; never sent to the frontend |
| GITHUB_TOKEN | Optional increased quota for public GitHub API calls |
| GEMINI_GENERATION_MODEL | Default `gemini-flash-lite-latest`; configurable |
| EMBEDDING_MODEL | Default gemini-embedding-001; changing it requires reanalysis |
| DATABASE_URL | Required for direct backend startup; Compose supplies it |
| BACKEND_PORT / FRONTEND_PORT | Host ports; defaults 8000 / 5173 |
| CORS_ALLOWED_ORIGINS | Comma-separated browser origins |

The backend also supports limits shown in .env.example. When running in Docker, add custom limit overrides to the backend environment section of docker-compose.yml; root .env values are only forwarded where Compose explicitly references them.

## Tests and checks

```powershell
docker compose exec -T backend pytest -q -p no:cacheprovider
docker compose exec -T backend ruff check app tests alembic
docker compose exec -T backend ruff format --check app tests alembic
docker compose exec -T backend mypy app
docker compose exec -T frontend npm test -- --pool=threads
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run build
```

To include the real PostgreSQL/vector test with the default development credentials:

```powershell
docker compose exec -T -e TEST_DATABASE_URL=postgresql+asyncpg://repomentor:repomentor@db:5432/repomentor backend pytest -q -p no:cacheprovider
```

The integration test creates unique test rows and removes only those rows. Adjust the URL if you changed development credentials. Do not point tests at a production database.

Verified: 83 backend tests including the real database test; six frontend workflow tests in Docker; TypeScript/Vite build; Ruff and mypy. Live Flask analysis completed with 219 files and 880 chunks. Live Gemini and visual browser acceptance remain pending.

## Development outside Docker

Use Python 3.12+ and Node 22.12+. PostgreSQL must be available with pgvector and migrations applied. The Compose database is not published to the host by default; publish a free loopback port deliberately if running the backend outside Docker.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Set DATABASE_URL in the root .env to your reachable PostgreSQL instance.
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:create_app --factory --reload
```

In a second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Use `npm.cmd` on Windows when PowerShell policy blocks npm.ps1. Set BACKEND_PROXY_TARGET if your local API runs on a different port.

## Production configuration

`docker-compose.production.yml` provides a separate database volume, non-reloading API and built frontend served by unprivileged Nginx. Set a URL-safe POSTGRES_PASSWORD first, then:

```powershell
docker compose -f docker-compose.production.yml up --build -d
```

This configuration has not been deployment-tested here. It defaults to a loopback listener. Public hosting needs TLS and an explicit reverse-proxy/client-rate-limit setup. Use one API worker: jobs and rate limits are in-process. The MVP has no authentication and handles only public repositories.

## Troubleshooting

- **Port already allocated:** change BACKEND_PORT or FRONTEND_PORT; avoid stopping unrelated services.
- **Missing frontend package / vitest:** run `docker compose exec -T frontend npm ci` to refresh the dependency volume.
- **Windows test workers time out:** use the Docker frontend test command; it passes in this environment.
- **Q&A unavailable:** configure a valid Gemini key, check quotas/model access, recreate the backend and reanalyze.
- **Partial parse warnings:** some source files cannot be fully parsed; the API remains available and reports the limitation.
- **Interrupted analysis:** after restart, interrupted jobs are marked failed on the next repository request; use Reanalyze.
- **GitHub quota errors:** configure GITHUB_TOKEN or wait for quota reset.
- **Database errors:** inspect `docker compose logs backend db`; do not delete database volumes to troubleshoot.

## Handoff and roadmap

Run `python scripts/package_release.py` to produce `deliverables/RepoMentor_Phase9_Source.zip` and its SHA-256/file manifest. Dependencies, caches, local credentials and stale exported copies are excluded.

Remaining MVP acceptance: live Gemini Q&A, visual/accessibility review, production smoke tests and analysis-quality improvements. Future work: durable jobs, deeper route/call graphs, incremental analysis, private repositories with authentication, and contributor guidance.
