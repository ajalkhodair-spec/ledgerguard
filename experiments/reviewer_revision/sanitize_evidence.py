#!/usr/bin/env python3
"""Remove host-specific paths from textual reviewer-revision evidence."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {".csv", ".json", ".jsonl", ".log", ".md", ".txt", ".yaml", ".yml", ".info"}
TARGETS = (
    ROOT / "results" / "reviewer_revision",
    ROOT / "paper_assets" / "reviewer_revision",
)
PRIVATE_PATTERNS = (
    re.compile(r"/" + r"Users/[^\s\"']+"),
    re.compile(r"/" + r"home/[^\s\"']+"),
    re.compile(r"/" + r"private/(?:tmp|var)/[^\s\"']+"),
    re.compile(r"/" + r"var/folders/[^\s\"']+"),
)


def sanitize(text: str) -> tuple[str, int]:
    replacements = 0
    for pattern in PRIVATE_PATTERNS:
        text, count = pattern.subn("<PRIVATE_PATH>", text)
        replacements += count
    return text, replacements


def main() -> int:
    files_scanned = 0
    files_changed = 0
    replacements = 0
    for target in TARGETS:
        if not target.exists():
            continue
        for path in sorted(target.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            files_scanned += 1
            original = path.read_text(encoding="utf-8", errors="replace")
            updated, count = sanitize(original)
            if count:
                path.write_text(updated, encoding="utf-8")
                files_changed += 1
                replacements += count
    print(
        f"evidence-sanitizer: PASS ({files_scanned} files scanned, "
        f"{files_changed} changed, {replacements} replacements)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
