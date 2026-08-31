PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS releases (
  release_id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_type TEXT NOT NULL,
  version INTEGER NOT NULL,
  cid_fw TEXT NOT NULL,
  sha256_fw TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sbom_hash TEXT NOT NULL,
  provenance_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
  release_id INTEGER NOT NULL,
  signer_role TEXT NOT NULL,
  signer_id TEXT NOT NULL,
  created_at_utc TEXT NOT NULL,
  UNIQUE(release_id, signer_id),
  FOREIGN KEY(release_id) REFERENCES releases(release_id)
);

CREATE TABLE IF NOT EXISTS rollout_state (
  release_id INTEGER PRIMARY KEY,
  phase TEXT NOT NULL,
  started_at_utc TEXT NOT NULL,
  updated_at_utc TEXT NOT NULL,
  FOREIGN KEY(release_id) REFERENCES releases(release_id)
);

CREATE TABLE IF NOT EXISTS outcomes (
  outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
  release_id INTEGER NOT NULL,
  epoch INTEGER NOT NULL,
  merkle_root TEXT NOT NULL,
  success_count INTEGER NOT NULL,
  fail_count INTEGER NOT NULL,
  rollback_count INTEGER NOT NULL,
  created_at_utc TEXT NOT NULL,
  UNIQUE(release_id, epoch),
  FOREIGN KEY(release_id) REFERENCES releases(release_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  operation TEXT NOT NULL,
  actor TEXT NOT NULL,
  release_id INTEGER,
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL
);
