#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

./scripts/doctor.sh >/dev/null

mkdir -p out

echo "[results] Generating results from out/*"
docker compose run --rm results "python generate_results.py"

echo "[results] Wrote out/results.md and figure PNGs (if matplotlib available)."
