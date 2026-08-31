# GitHub Release Checklist

Use this checklist before pushing or uploading the project.

## Commit

- Include source files, contracts, scripts, docs, `.env.example`, and `requirements.txt`.
- Do not include `.env`, generated firmware bundles, Besu node keys, IPFS data, raw experiment output, workbook output, or Python caches.
- Run `./poc doctor` before publishing.
- Run `./poc run --adversarial` and `./poc results` when validating locally.
- Run `./poc run --suite q1` and `./poc results --suite q1` when regenerating paper-style result tables.

## Recommended public repository description

LedgerGuard PoC: permissioned-DLT firmware governance, artifact anchoring, staged rollout control, and Merkle-rooted update accountability.

## Recommended topics

`firmware-security`, `blockchain`, `dlt`, `hyperledger-besu`, `ipfs`, `solidity`, `supply-chain-security`, `proof-of-concept`

## Results policy

Keep generated results out of the main repository by default. If a paper review or artifact-evaluation process requires results, publish them as a GitHub Release asset or in a separate archival artifact with a clear timestamp and scope statement.
