import pytest

from app.analyzers.code import chunk_file, parse_code
from app.analyzers.structure import analyze, insights
from app.core.exceptions import AppError
from app.github.client import eligible, parse_url, safe_path


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://github.com.evil/a/b",
        "https://x@github.com/a/b",
        "https://github.com:443/a/b",
        "https://github.com/a/b?x=1",
        "https://github.com/a/b#x",
        "https://github.com/a/b/tree/main",
        "https://github.com/a/..",
        "https://127.0.0.1/a/b",
        "https://github.com/a/%2e%2e",
        "https://github.com/a/b?",
        "https://github.com/a/b#",
    ],
)
def test_url_rejects_unsafe_input(url):
    with pytest.raises(AppError):
        parse_url(url)


def test_url_normalizes_suffix():
    assert parse_url("https://github.com/Owner/project.git/") == ("Owner", "project")


@pytest.mark.parametrize(
    "path", ["../secret.py", "/app.py", "src/../../key", "a\\b.py", "a//b", "a/./b"]
)
def test_path_safety(path):
    assert not safe_path(path)


@pytest.mark.parametrize(
    "path,mode,size",
    [
        ("node_modules/a.js", "100644", 1),
        (".env", "100644", 1),
        ("secret.pem", "100644", 1),
        ("src/a.py", "120000", 1),
        ("src/a.py", "100644", 200001),
        ("package-lock.json", "100644", 1),
    ],
)
def test_filter(path, mode, size):
    assert not eligible({"path": path, "mode": mode, "size": size, "type": "blob"}, 200000)


@pytest.mark.parametrize(
    "path,code,name",
    [
        ("a.py", "class Service:\n    def run(self):\n        return 1\n", "run"),
        ("a.js", "export function run() { return 1; }", "run"),
        ("a.ts", "export const run = (): number => 1;", "run"),
        ("a.tsx", "export function App() { return <div />; }", "App"),
        ("A.java", "class A { public int run() { return 1; } }", "run"),
        ("a.c", "int run() { return 1; }", "run"),
        ("a.cpp", "int run() { return 1; }", "run"),
        ("a.go", "package main\nfunc run() int { return 1 }", "run"),
    ],
)
def test_supported_parsers(path, code, name):
    symbols, _, error = parse_code(path, code)
    assert not error
    assert name in [s["name"] for s in symbols]
    assert all(1 <= s["start_line"] <= s["end_line"] <= len(code.splitlines()) for s in symbols)


def test_chunk_coverage_and_bounds():
    content = "\n".join(f"value_{i} = {i}" for i in range(200))
    chunks = chunk_file({"path": "a.py", "content": content, "symbols": []}, 100)
    assert "\n".join(c["content"] for c in chunks) == content
    assert chunks[0]["start_line"] == 1 and chunks[-1]["end_line"] == 200
    assert all(len(c["content"]) <= 302 for c in chunks)


def test_analysis_evidence_and_import_graph():
    files = [
        {"path": p, "content": c, "size": len(c)}
        for p, c in {
            "app/main.py": (
                "from services.users import create_user\ndef main():\n    return create_user()\n"
            ),
            "services/users.py": "def create_user():\n    return {}\n",
            "requirements.txt": "fastapi==0.100\n",
            ".env.example": "API_KEY=do-not-show\n",
            "README.md": "```sh\npip install -r requirements.txt\n```\n",
        }.items()
    ]
    result = analyze(files, "Test project", 800, 100)
    views = insights(result)
    assert result["frameworks"][0]["name"] == "FastAPI"
    assert result["frameworks"][0]["evidence"][0]["start_line"] == 1
    assert views["architecture"]["edges"][0]["source"] == "app"
    assert views["architecture"]["edges"][0]["target"] == "services"
    assert views["architecture"]["nodes"][0]["description"].endswith("component.")
    assert views["data_flow"]["flows"][0]["steps"][0]["inferred"] is True
    assert views["setup"]["environment_variables"][0]["default"] is None
    assert views["setup"]["installation"][0]["commands"] == ["pip install -r requirements.txt"]
