import importlib
import json
import subprocess
import sys
from pathlib import PurePosixPath
from typing import Any

from tree_sitter import Language, Node, Parser

LANGUAGES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".go": "Go",
}
KINDS = {
    "function_definition": "function",
    "function_declaration": "function",
    "method_definition": "method",
    "method_declaration": "method",
    "class_definition": "class",
    "class_declaration": "class",
    "class_specifier": "class",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "type_declaration": "type",
}


def parse_isolated(path: str, content: str) -> tuple[list[dict[str, Any]], list[str], bool]:
    """A native grammar crash or pathological parse cannot kill or block the API."""
    if PurePosixPath(path).suffix not in LANGUAGES:
        return [], [], False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "app.analyzers.worker"],
            input=json.dumps({"path": path, "content": content}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=8,
            check=True,
        )
        symbols, imports, has_error = json.loads(result.stdout)
        return symbols, imports, has_error
    except (subprocess.SubprocessError, ValueError):
        return [], [], True


def parse_code(path: str, content: str) -> tuple[list[dict[str, Any]], list[str], bool]:
    suffix = PurePosixPath(path).suffix
    language = LANGUAGES.get(suffix)
    if not language:
        return [], [], False
    grammar = {"C++": "cpp", "TypeScript": "typescript"}.get(language, language.lower())
    module = importlib.import_module("tree_sitter_" + grammar)
    factory = getattr(
        module,
        "language_tsx"
        if suffix == ".tsx"
        else "language_typescript"
        if grammar == "typescript"
        else "language",
    )
    parser = Parser(Language(factory()))
    raw = content.encode("utf-8")
    tree = parser.parse(raw)
    symbols, imports = [], []
    stack: list[tuple[Node, str | None]] = [(tree.root_node, None)]
    while stack:
        node, parent = stack.pop()
        kind = KINDS.get(node.type)
        name = node.child_by_field_name("name")
        if node.type == "variable_declarator" and any(
            c.type in {"arrow_function", "function_expression"} for c in node.named_children
        ):
            kind = "function"
        if kind and name is None:
            declarator = node.child_by_field_name("declarator")
            while declarator is not None and declarator.type not in {
                "identifier",
                "field_identifier",
            }:
                declarator = declarator.child_by_field_name("declarator")
            name = declarator
        if kind and name is not None:
            label = raw[name.start_byte : name.end_byte].decode("utf-8")
            if kind == "function" and parent:
                kind = "method"
            symbols.append(
                {
                    "name": label,
                    "symbol_type": kind,
                    "start_line": node.start_point.row + 1,
                    "end_line": node.end_point.row + 1,
                    "parent": parent,
                }
            )
            parent = label
        if node.type in {
            "import_statement",
            "import_from_statement",
            "import_declaration",
            "import_spec",
            "preproc_include",
            "export_statement",
        }:
            imports.append(raw[node.start_byte : node.end_byte].decode("utf-8"))
        stack.extend((child, parent) for child in reversed(node.named_children))
    return symbols, imports, tree.root_node.has_error


def chunk_file(file: dict[str, Any], max_tokens: int) -> list[dict[str, Any]]:
    """Partition by top-level symbols, then bound sections by character budget and lines."""
    lines = file["content"].splitlines()
    boundaries = {0, len(lines)}
    for symbol in file["symbols"]:
        if symbol["parent"] is None:
            boundaries.update({symbol["start_line"] - 1, min(symbol["end_line"], len(lines))})
    ordered = sorted(boundaries)
    chunks = []
    buffer: list[str]
    for begin, end in zip(ordered, ordered[1:], strict=False):
        start, buffer, count = begin, [], 0
        for index in range(begin, end):
            line = lines[index]
            if buffer and (count + len(line) > max_tokens * 3 or len(buffer) >= 80):
                chunks.append(_chunk(file, start, index, buffer))
                start, buffer, count = index, [], 0
            # A minified single line must not exceed the embedding context budget.
            buffer.append(line[: max_tokens * 3])
            count += len(buffer[-1]) + 1
        if buffer:
            chunks.append(_chunk(file, start, end, buffer))
    return [c for c in chunks if c["content"].strip()]


def _chunk(file: dict[str, Any], start: int, end: int, lines: list[str]) -> dict[str, Any]:
    symbol = next(
        (s for s in file["symbols"] if s["start_line"] <= start + 1 <= s["end_line"]), None
    )
    return {
        "file_path": file["path"],
        "start_line": start + 1,
        "end_line": end,
        "symbol": symbol["name"] if symbol else None,
        "content": "\n".join(lines),
        "chunk_type": symbol["symbol_type"] if symbol else "file_section",
    }
