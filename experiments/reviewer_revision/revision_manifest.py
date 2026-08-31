"""Post-commit provenance and explicit campaign boundaries for evidence packaging."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/reviewer_revision"
CAMPAIGNS = {
    "control_plane_timing": {"execution": "real_local_besu_transactions", "inputs": "fixture_commitments_and_counters",
                             "fleet_generation_in_timed_path": False, "firmware_fetch_in_timed_path": False},
    "fleet": {"execution": "real_software_signing_verification_and_merkle_construction", "outcomes": "software_generated",
              "per_device_besu_transaction": False, "physical_installation": False},
    "ipfs": {"execution": "real_local_artifact_transfer", "shaping": "application_delay_and_read_pacing", "physical_wan": False},
    "cache": {"execution": "local_ipfs_fetch_and_in_process_payload_reuse", "distributed_gateway": False},
    "accountability_paths": {"execution": "real_local_besu_reporting_paths", "paths_per_mode": 50},
    "accountability_projections": {"execution": "analytical_fleet_and_batch_calculations", "basis": "executed_complete_path_gas_medians"},
    "block_period": {"execution": "local_set_signer_transactions", "complete_workflow_per_profile": False},
    "validator_faults": {"execution": "local_process_crash_and_restoration", "active_byzantine_injection": False},
}


def git_state():
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    if head.returncode:
        return {"status": "PENDING_NO_COMMIT", "revision_commit": None, "tree": None, "clean_worktree": False}
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT).strip()
    return {"status": "FROZEN" if not dirty else "PENDING_DIRTY_WORKTREE", "revision_commit": head.stdout.strip(),
            "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip(),
            "clean_worktree": not bool(dirty)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(file_entries, require_frozen=False):
    state = git_state()
    if require_frozen and state["status"] != "FROZEN":
        raise RuntimeError("freeze requires a committed revision and clean public worktree")
    fingerprint = json.loads((RESULTS / "validation/protocol_fingerprint.json").read_text())
    configuration = json.loads((RESULTS / "validation/execution_configuration_snapshot.json").read_text())
    configurations = sorted((ROOT / "experiments/configs").glob("*.yaml")) + [
        ROOT / "contracts/foundry.toml", ROOT / "docker-compose.yml",
        RESULTS / "validation/execution_configuration_snapshot.json"]
    analysis = sorted((ROOT / "experiments/reviewer_revision").rglob("*.py"))
    return {"schema_version": 1, **state,
            "historical_campaign_commit": None,
            "binding_method": "Retrospective exact source/runtime verification plus post-campaign revision commit and per-file SHA-256 manifest",
            "protocol_version": fingerprint["protocol_version"], "contracts": fingerprint["contracts"],
            "receipt_schema_version": fingerprint["receipt_schema_version"],
            "receipt_schema_sha256": digest(RESULTS / "validation/receipt_schema_v2.json"),
            "source_set_sha256": fingerprint["source_set_sha256"],
            "original_private_genesis_file_sha256": configuration["original_genesis_file_sha256"],
            "sanitized_genesis_sha256": configuration["sanitized_genesis_sha256"],
            "genesis_capture_type": configuration["capture_type"],
            "configuration_sha256": {str(path.relative_to(ROOT)): digest(path) for path in configurations},
            "analysis_script_sha256": {str(path.relative_to(ROOT)): digest(path) for path in analysis},
            "raw_evidence_sha256": {row["path"]: row["sha256"] for row in file_entries if row["path"].startswith("results/reviewer_revision/raw/")},
            "campaigns": CAMPAIGNS,
            "full_file_index": "evidence_manifest.json",
            "limitation": "The original campaign predates the revision commit. A later commit cannot establish contemporaneous provenance. Older representative sample manifests retain their generation-time metadata; the full archive binds their bytes to this revision."}
