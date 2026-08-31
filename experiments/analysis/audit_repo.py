#!/usr/bin/env python3
"""Write a repository audit and environment-version record for LedgerGuard."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def rels(pattern: str) -> list[str]:
    return sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern) if p.is_file())


def command_version(name: str, args: list[str]) -> dict[str, str]:
    exe = shutil.which(name)
    if not exe:
        return {"available": "false", "version": "unavailable"}
    try:
        proc = subprocess.run([exe, *args], cwd=ROOT, text=True, capture_output=True, timeout=8)
        text = (proc.stdout or proc.stderr).strip().splitlines()
        return {"available": "true", "path": exe, "version": text[0] if text else "available"}
    except Exception as exc:  # pragma: no cover - environment-specific
        return {"available": "true", "path": exe, "version": f"error: {exc}"}


def write_audit() -> None:
    validation = ROOT / "results/validation"
    validation.mkdir(parents=True, exist_ok=True)

    versions = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "os": platform.platform(),
        "python": platform.python_version(),
        "node": command_version("node", ["--version"]),
        "npm": command_version("npm", ["--version"]),
        "docker": command_version("docker", ["--version"]),
        "forge": command_version("forge", ["--version"]),
        "solc": command_version("solc", ["--version"]),
        "besu": command_version("besu", ["--version"]),
        "slither": command_version("slither", ["--version"]),
        "myth": command_version("myth", ["--version"]),
        "tc": command_version("tc", ["-V"]),
    }
    (validation / "environment_versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    contracts = rels("contracts/src/*.sol")
    tests = rels("contracts/test/*.sol")
    scripts = rels("scripts/*.sh") + rels("scripts/*.py") + rels("experiments/runners/*.sh")
    result_files = rels("results/csv/*.csv") + rels("results/validation/*") + rels("results/security/*")
    figures_tables = rels("paper_assets/figures/*") + rels("paper_assets/tables/*") + rels("results/figures/*")

    docker_ok = shutil.which("docker") is not None
    docker_accessible = False
    if docker_ok:
        try:
            docker_accessible = subprocess.run(["docker", "info"], cwd=ROOT, capture_output=True, timeout=8).returncode == 0
        except Exception:
            docker_accessible = False

    lines = [
        "# LedgerGuard Repository Audit",
        "",
        f"- generated_at_utc: {versions['generated_at_utc']}",
        f"- repository: {ROOT}",
        "",
        "## Existing Contracts",
        "",
        *[f"- {item}" for item in contracts],
        "",
        "## Existing Tests",
        "",
        *[f"- {item}" for item in tests],
        "",
        "## Existing Scripts",
        "",
        *[f"- {item}" for item in scripts],
        "",
        "## Existing Result Files",
        "",
        *[f"- {item}" for item in result_files],
        "",
        "## Existing Figures and Tables",
        "",
        *[f"- {item}" for item in figures_tables],
        "",
        "## Missing or Optional Dependencies",
        "",
    ]
    for key in ["docker", "forge", "solc", "besu", "slither", "myth", "tc", "node", "npm"]:
        value = versions[key]
        lines.append(f"- {key}: {value.get('version', 'unavailable')}")
    lines.extend(
        [
            "",
            "## Experiments Runnable on This Machine",
            "",
            "- SQLite centralized OTA baseline: runnable with Python standard library.",
            "- Formula/scenario accountability outputs: runnable with Python standard library.",
            "- Result aggregation and validation: runnable with Python standard library.",
            "",
            "## Experiments Requiring Additional Environment",
            "",
            f"- Docker/Besu governance timing: {'available' if docker_accessible else 'requires accessible Docker daemon and generated Besu network'}.",
            "- Traffic-shaped network tests: require tc/netem or equivalent network shaping plus retrieval workflow logs.",
            "- Slither/Mythril checks: require local installation or containerized security tooling.",
            "- Distributed validators: require configured remote Docker contexts or host list.",
            "- HIL tests: require hardware config, supported bootloader/agent, and device logs.",
        ]
    )
    (validation / "repo_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_audit()
