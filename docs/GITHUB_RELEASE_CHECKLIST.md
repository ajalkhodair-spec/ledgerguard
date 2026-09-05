# GitHub Release Checklist

Use this checklist before pushing or uploading the project.

## Commit

- Include source files, contracts, scripts, docs, `.env.example`, and `requirements.txt`.
- Do not include `.env`, generated firmware bundles, Besu node keys, IPFS data, raw experiment output, local figure previews, obsolete figure archives, workbook output, or Python caches.
- Run `./poc doctor` before publishing.
- Run `./poc run --adversarial` and `./poc results` when validating locally.
- Run `./poc run --suite q1` and `./poc results --suite q1` when regenerating paper-style result tables.

## Recommended public repository description

LedgerGuard PoC: permissioned-DLT firmware governance, artifact anchoring, staged rollout control, and Merkle-rooted update accountability.

## Recommended topics

`firmware-security`, `blockchain`, `dlt`, `hyperledger-besu`, `ipfs`, `solidity`, `supply-chain-security`, `proof-of-concept`

## Results policy

Keep raw and full generated results out of the main repository. The compact sanitized sample, final publication figures, figure-level plot data, and provenance metadata may be committed because they are directly reviewable and versioned with the analysis code. Publish the comprehensive workbook, full evidence ZIP, checksum manifest, and optional raster figure bundle as GitHub Release assets with a clear timestamp and scope statement.

## Zenodo release

- Publish only from a clean, tagged commit after all GitHub Actions checks pass.
- Use the tag and citation version `v2.0.0-poc` / `2.0.0-poc` consistently.
- Enable the public GitHub repository in Zenodo before creating the GitHub release.
- Attach the comprehensive workbook and evidence package to the GitHub release.
- After Zenodo mints the DOI, add the version DOI to `CITATION.cff` and the concept DOI badge to `README.md` in the next metadata-only commit.
