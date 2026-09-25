import json
import re
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from app.analyzers.code import LANGUAGES, chunk_file, parse_isolated


def source(path: str, start: Any = None, end: Any = None, symbol: Any = None) -> dict[str, Any]:
    return {"file_path": path, "start_line": start, "end_line": end, "symbol": symbol}


def analyze(
    files: list[dict[str, Any]], description: str | None, max_tokens: int, max_chunks: int
) -> dict[str, Any]:
    languages: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    modules: dict[str, Any] = {}
    frameworks: list[dict[str, Any]] = []
    entry_points: list[dict[str, Any]] = []
    important: list[dict[str, Any]] = []
    warnings: list[str] = []
    chunks: list[dict[str, Any]] = []
    known = {
        "react": ("React", "frontend"),
        "next": ("Next.js", "frontend"),
        "fastapi": ("FastAPI", "backend"),
        "flask": ("Flask", "backend"),
        "django": ("Django", "backend"),
        "express": ("Express", "backend"),
        "spring-boot": ("Spring Boot", "backend"),
        "sqlalchemy": ("SQLAlchemy", "database"),
        "pytest": ("pytest", "testing"),
        "vite": ("Vite", "build"),
    }
    for file in files:
        path, content = file["path"], file["content"]
        name = PurePosixPath(path).name.lower()
        language = LANGUAGES.get(PurePosixPath(path).suffix)
        file.update(language=language, purpose=None, is_important=False, is_entry_point=False)
        symbols, imports, parse_error = parse_isolated(path, content)
        file.update(symbols=symbols, imports=imports, symbol_count=len(symbols))
        if parse_error:
            warnings.append(f"Partial parse: {path}; extracted symbols may be incomplete.")
        if language:
            languages[language][0] += 1
            languages[language][1] += file["size"]
        dependency_file = name in {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "pom.xml",
            "go.mod",
        }
        if dependency_file:
            for dependency, (label, category) in known.items():
                for number, line in enumerate(content.splitlines(), 1):
                    if re.search(
                        r"(?<![\w-])" + re.escape(dependency) + r"(?![\w-])", line.lower()
                    ):
                        existing = next((f for f in frameworks if f["name"] == label), None)
                        ref = source(path, number, number)
                        if existing:
                            existing["evidence"].append(ref)
                        else:
                            frameworks.append(
                                {"name": label, "category": category, "evidence": [ref]}
                            )
                        break
        is_entry = name in {
            "main.py",
            "app.py",
            "manage.py",
            "__main__.py",
            "main.go",
            "main.tsx",
            "main.jsx",
            "index.tsx",
            "server.js",
            "server.ts",
        }
        file["is_entry_point"] = is_entry
        file["is_important"] = (
            dependency_file or is_entry or name.startswith("readme") or name == "dockerfile"
        )
        file["purpose"] = (
            "Likely application entry point (filename convention)."
            if is_entry
            else "Dependency declarations."
            if dependency_file
            else "Project documentation."
            if name.startswith("readme")
            else None
        )
        if is_entry:
            entry_points.append(
                {
                    "file_path": path,
                    "kind": "frontend"
                    if name.endswith(("tsx", "jsx"))
                    else "cli"
                    if name in {"manage.py", "__main__.py"}
                    else "application",
                    "symbol": None,
                    "reason": file["purpose"],
                }
            )
        if file["is_important"]:
            important.append(
                {
                    "path": path,
                    "language": language,
                    "reason": file["purpose"] or "Build configuration.",
                }
            )
        module_id = path.split("/")[0] if "/" in path else "root"
        module = modules.setdefault(
            module_id,
            {
                "id": module_id,
                "name": module_id,
                "purpose": f"Files under {module_id}; inspect sources for responsibilities.",
                "files": [],
                "symbol_count": 0,
                "depends_on": [],
            },
        )
        module["files"].append(path)
        module["symbol_count"] += len(symbols)
        chunks.extend(chunk_file(file, max_tokens))
    total = sum(v[1] for v in languages.values()) or 1
    return {
        "files": files,
        "chunks": chunks[:max_chunks],
        "modules": list(modules.values()),
        "frameworks": frameworks,
        "entry_points": entry_points,
        "important_files": important,
        "languages": [
            {"name": k, "file_count": v[0], "percentage": round(v[1] / total * 100, 1)}
            for k, v in sorted(languages.items(), key=lambda pair: -pair[1][1])
        ],
        "warnings": warnings
        + (
            ["Chunk limit reached; Q&A covers only part of this repository."]
            if len(chunks) > max_chunks
            else []
        ),
        "summary": {
            "purpose": description or "No project description provided by GitHub.",
            "architecture_summary": f"{len(files)} files in {len(modules)} directory groups. "
            "Relationships below are based on resolvable local imports.",
            "technologies": list(languages) + [f["name"] for f in frameworks],
            "source": "deterministic",
        },
    }


def insights(result: dict[str, Any]) -> dict[str, Any]:
    files = result["files"]
    paths = {f["path"] for f in files}

    def resolve_import(base: str) -> str | None:
        """Resolve an import to an analyzed file, including repositories in a subdirectory."""
        candidates = [base] + [base + ext for ext in LANGUAGES]
        candidates += [base + "/__init__.py", base + "/index.ts", base + "/index.tsx"]
        for candidate in candidates:
            if candidate in paths:
                return candidate
            nested = sorted(path for path in paths if path.endswith("/" + candidate))
            if nested:
                return nested[0]
        return None

    def architecture_group(path: str) -> tuple[str, str, str]:
        """Return a role-sized component, rather than a top-level directory module."""
        parts = path.split("/")
        if len(parts) >= 3 and parts[0] == "backend" and parts[1] == "app":
            layer = parts[2]
            if "." in layer:
                return ("backend-app", "Backend application", "backend")
            labels = {
                "api": ("API", "api"), "services": ("Services", "service"),
                "ai": ("AI & retrieval", "ai"), "db": ("Database access", "database"),
                "models": ("Data models", "model"), "analyzers": ("Code analysis", "analyzer"),
                "github": ("GitHub integration", "external"), "core": ("Application core", "core"),
            }
            label, kind = labels.get(layer, (f"Backend / {layer}", "backend"))
            return (f"backend-app-{layer}", label, kind)
        if len(parts) >= 3 and parts[0] == "frontend" and parts[1] == "src":
            layer = parts[2]
            if "." in layer:
                return ("frontend-app", "Frontend application", "frontend")
            labels = {
                "pages": ("Application screens", "ui"), "components": ("UI components", "ui"),
                "services": ("Frontend API client", "client"), "types": ("Frontend types", "model"),
            }
            label, kind = labels.get(layer, (f"Frontend / {layer}", "frontend"))
            return (f"frontend-src-{layer}", label, kind)
        root = parts[0] if len(parts) > 1 else "root"
        return (root, root.replace("-", " ").title(), "configuration")

    links = set()
    for file in files:
        for statement in file["imports"]:
            candidates = re.findall(r"[\"\']([^\"\']+)[\"\']", statement)
            candidates += re.findall(r"(?:from|import)\s+([\w.]+)", statement)
            for candidate in candidates:
                bases = [candidate.replace(".", "/")]
                if candidate.startswith("."):
                    import posixpath

                    bases = [
                        posixpath.normpath(
                            str(PurePosixPath(file["path"]).parent) + "/" + candidate
                        )
                    ]
                for base in bases:
                    target = resolve_import(base)
                    if target and target != file["path"]:
                        links.add((file["path"], target))
    component_for = {file["path"]: architecture_group(file["path"])[0] for file in files}
    components: dict[str, dict[str, Any]] = {}
    for file in files:
        component_id, label, kind = architecture_group(file["path"])
        component = components.setdefault(
            component_id,
            {"id": component_id, "label": label, "type": kind, "files": [], "inferred": False},
        )
        component["files"].append(file["path"])
    edges = set()
    for origin, target in links:
        a, b = component_for[origin], component_for[target]
        if a != b:
            edges.add((a, b))
    nodes = []
    for component in components.values():
        component["description"] = (
            f"{len(component['files'])} analyzed files in the {component['label'].lower()} component."
        )
        nodes.append(component)
    graph = {
        "nodes": nodes,
        "edges": [
            {"id": f"edge-{i}", "source": a, "target": b, "label": "imports", "inferred": False}
            for i, (a, b) in enumerate(sorted(edges))
        ],
        "summary": "Component-level dependencies derived from resolved local imports. "
        "This is a structural view, not a runtime trace.",
    }
    flows: list[dict[str, Any]] = []
    for entry in result["entry_points"]:
        start = entry["file_path"]
        visited: list[str] = []
        queue = [start]
        while queue and len(visited) < 6:
            path = queue.pop(0)
            if path in visited:
                continue
            visited.append(path)
            queue.extend(sorted(b for a, b in links if a == path and b not in visited))
        if len(visited) > 1:
            flows.append(
                {
                    "id": f"flow-{len(flows)}",
                    "name": f"From {start}",
                    "summary": "Possible flow inferred from imports; execution order is not proven.",  # noqa: E501
                    "steps": [
                        {
                            "order": i + 1,
                            "label": p,
                            "kind": "other",
                            "file_path": p,
                            "symbol": None,
                            "start_line": None,
                            "end_line": None,
                            "inferred": True,
                        }
                        for i, p in enumerate(visited)
                    ],
                }
            )
    setup: dict[str, Any] = {
        k: []
        for k in [
            "prerequisites",
            "installation",
            "environment_variables",
            "database",
            "run",
            "common_issues",
        ]
    }
    for file in files:
        name = PurePosixPath(file["path"]).name.lower()
        if name in {".env.example", ".env.sample"}:
            for number, line in enumerate(file["content"].splitlines(), 1):
                match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
                if match:
                    setup["environment_variables"].append(
                        {
                            "name": match[1],
                            "description": None,
                            "required": None,
                            "default": None,
                            "source": source(file["path"], number, number),
                        }
                    )
        if name.startswith("readme"):
            lines = file["content"].splitlines()
            for match in re.finditer(
                r"```(?:bash|sh|shell|console|powershell)?\n(.*?)```", file["content"], re.S
            ):
                commands = [line for line in match[1].splitlines() if line.strip()]
                if not commands:
                    continue
                number = file["content"][: match.start()].count("\n") + 1
                key = (
                    "installation"
                    if any("install" in c or "clone " in c for c in commands)
                    else "run"
                )
                setup[key].append(
                    {
                        "title": f"From {file['path']}:{number}",
                        "description": "Repository-provided commands. Review before running.",
                        "commands": commands,
                        "sources": [
                            source(
                                file["path"], number, min(number + len(commands) + 1, len(lines))
                            )
                        ],
                    }
                )
        if name == "package.json":
            try:
                package = json.loads(file["content"])
                for engine, version in package.get("engines", {}).items():
                    setup["prerequisites"].append(
                        {
                            "title": f"{engine} {version}",
                            "description": "Declared runtime requirement.",
                            "commands": [],
                            "sources": [source(file["path"])],
                        }
                    )
            except (ValueError, AttributeError):
                pass
    setup["message"] = (
        "Only repository-documented instructions are shown; "
        "missing sections have no extracted evidence."
    )
    return {
        "architecture": graph,
        "data_flow": {
            "flows": flows,
            "message": None
            if flows
            else "No supported multi-file flow could be established from local imports.",
        },
        "setup": setup,
    }
