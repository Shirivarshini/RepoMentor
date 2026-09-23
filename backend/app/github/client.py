"""Bounded GitHub downloads. No cloning, archive extraction or code execution."""

import asyncio
import re
from pathlib import PurePosixPath
from typing import Any, cast
from urllib.parse import quote, urlsplit

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError, ValidationFailed
from app.schemas.errors import ErrorCode

IGNORED = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "coverage",
    ".cache",
    "__pycache__",
    ".idea",
    ".vscode",
    "vendor",
    ".next",
}
TEXT_EXT = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".go",
    ".md",
    ".rst",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".css",
    ".html",
    ".sql",
    ".sh",
    ".xml",
    ".mod",
    ".sum",
    ".rs",
    ".rb",
    ".example",
}


def parse_url(value: str) -> tuple[str, str]:
    try:
        url = urlsplit(value)
        valid = (
            len(value) <= 200
            and url.scheme == "https"
            and url.netloc == "github.com"
            and not url.query
            and not url.fragment
            and "?" not in value
            and "#" not in value
        )
        match = re.fullmatch(r"/([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9_.-]+)/?", url.path)
        if not valid or not match:
            raise ValueError
        owner, name = match.groups()
        name = name.removesuffix(".git")
        if name in {"", ".", ".."}:
            raise ValueError
        return owner, name
    except ValueError as exc:
        raise ValidationFailed(
            "Enter a public https://github.com/owner/repository URL.", field="repository_url"
        ) from exc


def safe_path(path: str) -> bool:
    return (
        bool(path)
        and not path.startswith("/")
        and "\\" not in path
        and not any(p in {"", ".", ".."} for p in path.split("/"))
        and not any(ord(c) < 32 for c in path)
    )


def eligible(entry: dict[str, Any], maximum: int) -> bool:
    path = entry["path"]
    name = PurePosixPath(path).name.lower()
    return (
        entry.get("type") == "blob"
        and entry.get("mode") not in {"120000", "160000"}
        and safe_path(path)
        and not (set(path.split("/")) & IGNORED)
        and entry.get("size", maximum + 1) <= maximum
        and (not name.startswith(".env") or name in {".env.example", ".env.sample"})
        and not name.endswith((".pem", ".key", ".lock", "-lock.json", ".min.js", ".map"))
        and (
            PurePosixPath(name).suffix in TEXT_EXT or name in {"dockerfile", "makefile", "license"}
        )
    )


def priority(entry: dict[str, Any]) -> tuple[int, str]:
    name = PurePosixPath(entry["path"]).name.lower()
    return (
        0
        if name.startswith("readme")
        else 1
        if name
        in {
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "dockerfile",
            "docker-compose.yml",
            ".env.example",
            "go.mod",
            "pom.xml",
        }
        else 2
        if name.startswith(("main.", "app.", "index."))
        else 4
        if "test" in entry["path"]
        else 3,
        entry["path"],
    )


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _get(self, url: str, limit: int, *, api: bool = True) -> bytes:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoMentor"}
        if api and self.settings.github_token.get_secret_value():
            headers["Authorization"] = "Bearer " + self.settings.github_token.get_secret_value()
        for attempt in range(3):
            try:
                async with (
                    httpx.AsyncClient(
                        timeout=self.settings.github_http_timeout_seconds, follow_redirects=False
                    ) as client,
                    client.stream("GET", url, headers=headers) as response,
                ):
                    if response.status_code in {403, 429}:
                        raise AppError(
                            ErrorCode.GITHUB_RATE_LIMIT,
                            "GitHub rate limit reached. Retry later.",
                        )
                    if response.status_code == 404:
                        raise AppError(
                            ErrorCode.REPOSITORY_NOT_FOUND,
                            "Repository is missing or not public.",
                        )
                    if response.status_code == 409:
                        raise AppError(ErrorCode.EMPTY_REPOSITORY, "Repository has no commits.")
                    if response.status_code >= 500:
                        response.raise_for_status()
                    if response.status_code != 200:
                        raise AppError(
                            ErrorCode.GITHUB_API_ERROR, "GitHub could not return this resource."
                        )
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise AppError(
                                ErrorCode.REPOSITORY_TOO_LARGE,
                                "Download exceeds the configured limit.",
                            )
                    return bytes(body)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                if attempt == 2:
                    raise AppError(
                        ErrorCode.GITHUB_API_ERROR, "GitHub is unavailable. Retry later."
                    ) from None
                await asyncio.sleep(0.5 * 2**attempt)
        raise RuntimeError("Unreachable")

    async def json(self, path: str) -> dict[str, Any]:
        import json

        return cast(
            dict[str, Any], json.loads(await self._get("https://api.github.com" + path, 16_000_000))
        )

    async def metadata(self, owner: str, name: str) -> dict[str, Any]:
        data = await self.json(f"/repos/{owner}/{name}")
        if data.get("private") or data.get("visibility", "public") != "public":
            raise AppError(ErrorCode.REPOSITORY_NOT_FOUND, "Repository is missing or not public.")
        return data

    async def snapshot(
        self, owner: str, name: str, branch: str
    ) -> tuple[str, list[Any], int, bool]:
        commit = await self.json(f"/repos/{owner}/{name}/commits/{quote(branch, safe='')}")
        sha = commit["sha"]
        tree = await self.json(f"/repos/{owner}/{name}/git/trees/{sha}?recursive=1")
        entries = tree.get("tree", [])
        if tree.get("truncated") or len(entries) > self.settings.max_tree_entries:
            raise AppError(
                ErrorCode.REPOSITORY_TOO_LARGE, "Repository tree exceeds the configured limit."
            )
        selected = sorted(
            (e for e in entries if eligible(e, self.settings.max_file_size_bytes)), key=priority
        )
        truncated = len(selected) > self.settings.max_analyzed_files
        selected = selected[: self.settings.max_analyzed_files]
        semaphore = asyncio.Semaphore(6)

        async def download(entry: dict[str, Any]) -> Any:
            async with semaphore:
                try:
                    raw = await self._get(
                        f"https://raw.githubusercontent.com/{owner}/{name}/{sha}/"
                        + quote(entry["path"], safe="/"),
                        self.settings.max_file_size_bytes,
                        api=False,
                    )
                except AppError as exc:
                    if exc.code == ErrorCode.REPOSITORY_TOO_LARGE:
                        return None
                    raise
                if b"\x00" in raw:
                    return None
                try:
                    return {"path": entry["path"], "content": raw.decode("utf-8"), "size": len(raw)}
                except UnicodeDecodeError:
                    return None

        files = [f for f in await asyncio.gather(*(download(e) for e in selected)) if f]
        if not files:
            raise AppError(ErrorCode.UNSUPPORTED_REPOSITORY, "No analyzable text files were found.")
        return sha, files, sum(e["type"] == "blob" for e in entries) - len(files), truncated
