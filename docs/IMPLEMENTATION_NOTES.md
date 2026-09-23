# Implementation notes — 21 September 2026

The PRD, `docs/DESIGN.md`, `docs/ARCHITECTURE.md`, and root `API_CONTRACT.md` guided this implementation. The supplied workspace did not contain CLAUDE.md or a separate implementation-plan file. The PRD phase sequence was used, with implementation and checks performed incrementally.

## Changes to architecture decisions

- API and frontend response types implement the existing root API contract; no public endpoints were renamed.
- Repository metadata, progress and derived results use validated JSONB snapshots. Files, symbols, chunks, 768-dimensional embeddings, questions, answers and source references have separate tables and cascading foreign keys. This is a simpler physical schema than the original field-by-field proposal.
- Exact cosine search is scoped to repository and embedding model. No HNSW index is needed at the configured MVP size.
- Single-process jobs use a concurrency semaphore and PostgreSQL advisory transaction locks for submission. The first repository request marks interrupted jobs failed after a restart. Deploy exactly one API worker for this MVP.
- A native parser failure was observed on a real repository. Each supported file is now parsed in an isolated subprocess, with an eight-second timeout. That process runs RepoMentor's parser only; it never imports or executes downloaded source. Failed parses produce warnings while text remains available for chunking.
- Modules are directory groups. Graph edges come from a limited local-import resolver. Data-flow steps inferred from imports are explicitly marked inferred; execution order is not proven. Framework-specific route/call tracing remains limited.
- Summaries are deterministic in this implementation. Gemini generates structured Q&A, with server-built source references and an insufficient-evidence fallback. Model citation checks reduce hallucination risk but do not prove semantic correctness.
- Setup instructions are extracted conservatively from README code blocks, package engines and environment examples. Empty sections are retained when evidence was not extracted.
- Read-only source downloads have URL, path, file-size, file-count and tree limits. Request bodies have a 16 KiB cap. Per-client rate limits are in-process and do not trust forwarded client headers.
- Production assets can be built with `frontend/Dockerfile.production` and served through Nginx. Production deployment needs a deliberate reverse-proxy, TLS and client-rate-limit configuration before public exposure.

## Provider references consulted

- [Gemini embeddings REST API](https://ai.google.dev/api/embeddings)
- [Tree-sitter Python bindings](https://github.com/tree-sitter/py-tree-sitter/blob/master/README.md)

Model names remain configurable. Actual Gemini calls require a supplied API key and quota; no live provider acceptance is claimed without them.
