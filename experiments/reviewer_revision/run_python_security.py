#!/usr/bin/env python3
"""Retain named Python test results, including identity-level terminal-root cases."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    command = [sys.executable, "-W", "error::ResourceWarning", "-m", "unittest", "discover",
               "-s", "experiments/reviewer_revision", "-p", "test*.py", "-v"]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = ROOT / "results/reviewer_revision/raw/security/python_final.txt"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(result.stdout, encoding="utf-8")
    match = re.search(r"Ran (\d+) tests?", result.stdout)
    status = {"status": "PASS" if result.returncode == 0 and match else "FAIL",
              "test_count": int(match[1]) if match else 0, "exit_code": result.returncode,
              "raw_report": raw.relative_to(ROOT).as_posix(),
              "command": "python3 " + " ".join(command[1:])}
    target = ROOT / "results/reviewer_revision/validation/python_final_status.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result.stdout)
    print(json.dumps(status))
    if status["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
