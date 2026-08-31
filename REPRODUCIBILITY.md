# Reproducibility

## Evidence Classes

The reviewer-revision package separates local Besu measurements, local persistent-backend measurements, authenticated software emulation, application-shaped local IPFS execution, executed local cache behavior, analytical scaling, and not-run hardware work.

## Requirements

- macOS or Linux with at least 8 GB RAM and 5 GB free disk space.
- Python 3.11 or newer.
- Foundry with Solidity 0.8.24 support.
- A local Solidity 0.8.24 compiler and Slither 0.11.6.
- Hyperledger Besu 25.12.0 for native block-period and validator-fault runs.
- Docker Desktop or Docker Engine with Compose v2 for the standard local Besu/IPFS stack.
- `curl`, `jq`, `openssl`, `tar`, and `sha256sum` or `shasum`.

Install Python dependencies in an isolated environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-reviewer.txt
```

## Commands

```bash
./scripts/reproduce_reviewer_revision.sh --smoke
./scripts/reproduce_reviewer_revision.sh --analysis-only
./scripts/reproduce_reviewer_revision.sh --full
./scripts/reproduce_reviewer_revision.sh --full --resume
```

`--smoke` compiles sources and runs the Python and Foundry tests. `--analysis-only` regenerates statistical summaries and validation from preserved raw evidence. `--full` starts from a fresh local stack, executes V2 experiments, analyzes the outputs, and builds the evidence package. `--resume` preserves completed outputs and continues only missing phases.

Analysis requires the full raw evidence archive, including the final protocol
fingerprint, LCOV report, and raw operation-gas samples; the public sample alone
is not sufficient. It reruns Python tests, reconstructs outcome distributions,
retains every network observation, and verifies source fingerprints, gas-table
statistics, accountability formulas, and security status before packaging.
The HTTP baseline tests require permission to bind a localhost port.

Full execution also performs retrospective source/ABI/runtime verification
against the local chain. A missing historical Git execution commit is recorded
as missing, not reconstructed from a later commit. See `docs/evidence_freeze.md`
for the present checkpoint and post-campaign Git-freeze procedure.

The post-campaign freeze is generated after committing the public snapshot:
`python -m experiments.reviewer_revision.generate_evidence_package --preserve-public-sample --require-frozen`.
The strict mode refuses a dirty or uncommitted public worktree. It leaves the
tracked representative sample unchanged and writes the expanded revision
manifest and checksums into ignored `release/`. Archived sample metadata retains
its generation-time provenance; the release binds all file bytes to the final
revision without pretending the original campaign recorded that commit.

Set `BESU_NATIVE_BIN`, `FORGE_BIN`, `CAST_BIN`, `SOLC_BIN`, and `SLITHER_BIN`
when those programs are not on `PATH`. `SOLC_BIN` must identify a Solidity
0.8.24 executable because security runs are offline and compiler-pinned. Full
execution reads local demo keys from `.env`; `.env` is never part of the evidence
package.

## Expected Resources

- Smoke: approximately 2 minutes and less than 500 MB temporary disk use.
- Analysis only: approximately 10 to 25 minutes, dominated by verification of 96,000 signatures.
- Full: approximately 20 to 45 minutes on a modern developer workstation and 1 to 3 GB temporary disk use.

Times are planning estimates, not benchmark results.

## Outputs

- Raw evidence: `results/reviewer_revision/raw/`
- Row-level CSVs: `results/reviewer_revision/csv/`
- Statistical summaries: `results/reviewer_revision/statistics/`
- Validation and checksums: `results/reviewer_revision/validation/`
- Public subset: `results_sample/`
- Full bundle: `release/LedgerGuard_Reviewer_Revision_Evidence.zip`

## Resume and Failure Handling

Do not delete a failed observation and rerun into the same path. Archive the partial evidence or use `--resume` where supported. The block-period exclusion register documents invalid environment starts separately from valid slow observations.

Common failures include unavailable Docker, a busy RPC port, native Besu libraries failing to load, a stopped IPFS gateway, and existing output paths. The environment doctor reports missing tools before a full run.

## Checksum Verification

From the repository root:

```bash
shasum -a 256 -c release/SHA256SUMS
```

On Linux, `sha256sum -c` accepts the same file format. The manifest also records file size, evidence type, source command, generation time, and Git revision when available.
