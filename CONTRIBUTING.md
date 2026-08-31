# Contributing

## Development Workflow

1. Create a focused branch.
2. Keep V1 behavior and evidence compatibility intact unless a migration is explicitly proposed.
3. Add tests for contract, baseline, or analysis behavior changes.
4. Label generated evidence by provenance: local execution, software emulation, analytical calculation, or not run.
5. Run `./scripts/reproduce_reviewer_revision.sh --smoke` and `./scripts/check_public_safety.sh` before opening a pull request.

## Evidence Rules

- Never fabricate, interpolate, or silently replace failed observations.
- Preserve exclusion reasons and rerun provenance.
- Do not commit `.env`, private keys, generated Besu node state, IPFS state, or unrestricted raw outputs.
- Do not describe analytical rows as measurements.
- Do not imply physical-device or production validation without corresponding raw evidence.

## Pull Requests

Describe the change, its behavioral impact, tests executed, evidence files affected, and remaining limitations. Contract changes must identify ABI, event, and storage-layout effects.
