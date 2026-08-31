# LedgerGuard

LedgerGuard is a research proof of concept for auditable firmware-release governance over a permissioned Hyperledger Besu control plane. Firmware artifacts remain off-chain in content-addressed storage; the ledger records release commitments, threshold approvals, rollout state, authenticated device outcomes, and Merkle-rooted cohort summaries.

The repository contains the original V1 PoC and a security-focused V2 protocol. V2 adds domain-separated signed receipts, device identity and revocation, expected-cohort commitments, independent summary confirmation, replay resistance, explicit rollout guards, and migration evidence. It is intended for reproducible research under controlled local conditions, not production deployment.

## Implemented Scope

- Four-validator local IBFT2 Besu control plane with role-separated governance identities.
- V1 and V2 Solidity contracts, migration checks, Foundry unit/fuzz/invariant tests, coverage, gas reporting, and reviewed Slither findings.
- Persistent HTTP/SQLite comparison implementing the same V2 authorization, approval, rollout, outcome, and audit semantics without distributed consensus.
- Local Besu timing runs: 50 repetitions and 350 successful state-changing transactions.
- Parallel-RPC conflict evaluation: 25 same-block races with one accepted transition and one mined revert per race.
- Authenticated software-fleet evaluation: 180 runs and 96,000 preserved signed receipts across fleet sizes, failure rates, and 20 seeds per configuration.
- Complete-cohort terminal commitments and dual-journal witness reconstruction covering omissions, duplicates, altered receipts, consumed nonces, key rotation, Merkle proofs, and domain separation.
- Local IPFS fetch profiles with configured application delay and read-rate limits, plus a local edge-cache ON/OFF ablation.
- Five local crash-fault trials covering zero, one, and two stopped validators and quorum restoration.
- Executed per-device, V1 integrity-root, and V2 complete witnessed accountability paths, with per-run V2 gas totals and analytical fleet/batch scaling kept explicitly separate.

## Evidence Boundaries

The evidence supports a research PoC only. Device behavior is authenticated software emulation; no physical firmware device, secure element, hardware-backed key, WAN deployment, Byzantine validator injection, production load test, or Mythril run is represented as completed. Network profiles are application-shaped local IPFS transfers, not OS-level `netem` or WAN observations. Accountability scaling rows are calculations based on local gas medians and compiler storage layouts, not fleet-scale blockchain measurements.

These boundaries are machine-readable in the full local evidence set and summarized in the public sample.

The latest cleanup and source/deployment traceability are documented in
[evidence_freeze.md](docs/evidence_freeze.md). Historical Git provenance was not
recorded; retrospective exact-bytecode verification does not invent that record.
Independent witness reconstruction does not protect against common upstream
omission or aggregator/witness collusion. The local operator and aggregator share
one software account; the witness uses a separate account and process.

## Architecture

1. A vendor packages firmware, manifest, SBOM, provenance, and signatures in content-addressed storage.
2. `FirmwareRegistry` anchors release metadata and artifact commitments.
3. `KeyManager` and V2 identity contracts enforce role, signer, and revocation policy.
4. `RolloutCoordinatorV2` applies threshold approval and guarded rollout transitions.
5. Software-emulated devices verify release bindings and sign domain-separated terminal receipts.
6. An aggregator and witness independently reconstruct signed receipts from separate append-only journals and commit one terminal leaf for every expected device.

See [experimental_setup.md](docs/experimental_setup.md), [protocol_v2_specification.md](docs/protocol_v2_specification.md), [threat_model_v2.md](docs/threat_model_v2.md), and [migration_v1_to_v2.md](docs/migration_v1_to_v2.md).

## Repository Layout

```text
contracts/                       V1/V2 contracts and Foundry tests
experiments/reviewer_revision/   runners, analyzers, validators, and packaging tools
experiments/baselines/           comparison and evaluation scaffolding
runner/                          firmware/device and Merkle utilities
scripts/                         PoC lifecycle, reproduction, and public-safety checks
docs/                            protocol, threat model, migration, and scope documents
paper_assets/reviewer_revision/  publication figures and reviewer evidence drafts
results_sample/                  compact sanitized evidence committed to Git
release/                         locally generated full evidence bundle and checksums
```

The full raw reviewer-revision result tree is intentionally excluded from Git. `results_sample/` provides traceable representative evidence suitable for public review.

## Requirements

- Docker with Compose
- Python 3.12+
- Foundry (`forge` and `cast`)
- Hyperledger Besu for native block-period and validator-fault studies
- `jq`, `curl`, and standard Unix shell tools

Install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-reviewer.txt
```

## Quick Start

Run the baseline PoC:

```bash
cp .env.example .env
./poc run
./poc status
```

The first run generates local-only demonstration keys in `.env`, creates the Besu network, starts IPFS and Besu, deploys the V1 contracts, packages a firmware artifact, executes the governance workflow, and generates signed software-device outcomes. Never commit `.env` or generated network state.

Run the adversarial checks:

```bash
./poc adversarial
```

Stop or remove local services:

```bash
./poc stop
./poc clean
```

## Reviewer Revision Reproduction

Fast source, unit, contract, and public-sample validation:

```bash
scripts/reproduce_reviewer_revision.sh --smoke
```

Reanalyze preserved full evidence and rebuild the release package:

```bash
scripts/reproduce_reviewer_revision.sh --analysis-only
```

Execute the full local evaluation from an empty reviewer-revision result directory:

```bash
scripts/reproduce_reviewer_revision.sh --full
```

Use `--resume` only to continue a deliberately interrupted full run. The complete evaluation is compute-intensive and requires Docker, native Besu, Foundry, and all reviewer dependencies. Exact evidence definitions and commands are documented in [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

## Public Evidence

`results_sample/` contains one successful Besu control-plane run, one HTTP/SQLite comparison run, one authenticated fleet run with signed receipts, all completeness cases, the selective-omission evidence, representative gas rows, and the consolidated validation report.

Validate it with:

```bash
python experiments/reviewer_revision/validate_public_sample.py
```

Generate the full local evidence archive, file manifest, and checksums:

```bash
python experiments/reviewer_revision/generate_evidence_package.py
sha256sum -c release/SHA256SUMS
```

## Security and Publication Checks

Before publishing:

```bash
bash scripts/check_public_safety.sh
forge test --root contracts -vv
python -W error::ResourceWarning -m unittest discover \
  -s experiments/reviewer_revision -p 'test*.py' -v
```

The public-safety gate scans tracked and non-ignored untracked files for private keys, generated node/IPFS state, host-specific paths, credential-like strings, and affirmative unsupported deployment claims. See [SECURITY.md](SECURITY.md) and [GITHUB_RELEASE_CHECKLIST.md](docs/GITHUB_RELEASE_CHECKLIST.md).

## License and Citation

LedgerGuard is licensed under Apache-2.0. Citation metadata is provided in [CITATION.cff](CITATION.cff).
