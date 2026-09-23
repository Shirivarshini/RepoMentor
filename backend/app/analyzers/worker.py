"""Isolated native parser entry point. Repository text is parsed, never evaluated."""

import json
import sys

from app.analyzers.code import parse_code

if __name__ == "__main__":
    payload = json.load(sys.stdin)
    json.dump(parse_code(payload["path"], payload["content"]), sys.stdout)
