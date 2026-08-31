#!/usr/bin/env python3
"""Reject secrets, private paths, generated state, and unsupported claims in public candidates."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".xlsx"}
FORBIDDEN_PATHS = (
    re.compile(r"^\.env$"), re.compile(r"\.(?:pem|key)$", re.IGNORECASE),
    re.compile(r"mnemonic", re.IGNORECASE), re.compile(r"^network/Node-[^/]+/data/key$"),
    re.compile(r"^ipfs/data/"),
)
FORBIDDEN_TEXT = (
    re.compile(r"/" + r"Users/"), re.compile(r"/" + r"home/[A-Za-z0-9._-]+"),
    re.compile(r"/" + r"private/(?:tmp|var)/"), re.compile(r"/" + r"var/folders/"),
    re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    re.compile(
        r"(?:private[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?0x[0-9a-f]{64}",
        re.IGNORECASE,
    ),
    re.compile(r"(?:api[_-]?key|access[_-]?token)\s*[:=]\s*[^\s]{12,}", re.IGNORECASE),
    re.compile(r"(?:the system|LedgerGuard) is production[- ]ready", re.IGNORECASE),
    re.compile(r"(?:was|has been) validated on (?:real|physical) devices", re.IGNORECASE),
)


def main() -> int:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], text=True, capture_output=True, check=False
    )
    if probe.returncode:
        print("public-safety: Git work tree is required", file=sys.stderr)
        return 1
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True, check=True,
    ).stdout
    paths = sorted({Path(value.decode("utf-8")) for value in listing.split(b"\0") if value})
    errors = []
    for path in paths:
        name = path.as_posix()
        if any(pattern.search(name) for pattern in FORBIDDEN_PATHS):
            errors.append(f"forbidden public-candidate path: {name}")
            continue
        if path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN_TEXT:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{name}:{line}: forbidden pattern {pattern.pattern!r}")
    if errors:
        print("public-safety: FAIL", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"public-safety: PASS ({len(paths)} tracked and non-ignored untracked files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
