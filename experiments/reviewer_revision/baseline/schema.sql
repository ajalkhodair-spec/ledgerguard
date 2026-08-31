PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = FULL;

CREATE TABLE actors (
  actor_id TEXT PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('VENDOR', 'SECURITY', 'REGULATOR', 'OPERATOR', 'AUDITOR')),
  token_hash TEXT NOT NULL UNIQUE,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE policies (
  device_type TEXT PRIMARY KEY,
  approval_threshold INTEGER NOT NULL CHECK (approval_threshold > 0),
  success_threshold_bps INTEGER NOT NULL CHECK (success_threshold_bps BETWEEN 1 AND 10000),
  kill_switch INTEGER NOT NULL DEFAULT 0 CHECK (kill_switch IN (0, 1))
);

CREATE TABLE releases (
  release_id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_type TEXT NOT NULL REFERENCES policies(device_type),
  version INTEGER NOT NULL,
  cid TEXT NOT NULL,
  firmware_hash TEXT NOT NULL,
  sbom_hash TEXT NOT NULL,
  provenance_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED', 'APPROVED', 'DEPRECATED')),
  created_by TEXT NOT NULL REFERENCES actors(actor_id),
  created_at_ns INTEGER NOT NULL,
  UNIQUE(device_type, version)
);

CREATE TABLE approvals (
  release_id INTEGER NOT NULL REFERENCES releases(release_id),
  actor_id TEXT NOT NULL REFERENCES actors(actor_id),
  role TEXT NOT NULL,
  created_at_ns INTEGER NOT NULL,
  PRIMARY KEY (release_id, actor_id)
);

CREATE TABLE rollouts (
  release_id INTEGER PRIMARY KEY REFERENCES releases(release_id),
  rollout_id TEXT NOT NULL UNIQUE,
  phase TEXT NOT NULL CHECK (phase IN ('CANARY', 'BATCH', 'GLOBAL', 'COMPLETED', 'HALTED')),
  transition_nonce INTEGER NOT NULL,
  expected_count INTEGER NOT NULL CHECK (expected_count > 0),
  updated_at_ns INTEGER NOT NULL
);

CREATE TABLE outcome_summaries (
  release_id INTEGER NOT NULL REFERENCES releases(release_id),
  epoch INTEGER NOT NULL,
  rollout_id TEXT NOT NULL,
  cohort_id TEXT NOT NULL,
  cohort_commitment TEXT NOT NULL,
  deadline_ns INTEGER NOT NULL,
  merkle_root TEXT NOT NULL,
  expected_count INTEGER NOT NULL,
  received_count INTEGER NOT NULL,
  success_count INTEGER NOT NULL,
  rollback_count INTEGER NOT NULL,
  fail_count INTEGER NOT NULL,
  rejected_count INTEGER NOT NULL,
  missing_count INTEGER NOT NULL,
  aggregator_id TEXT NOT NULL REFERENCES actors(actor_id),
  witness_id TEXT REFERENCES actors(actor_id),
  state TEXT NOT NULL CHECK (state IN ('PROPOSED', 'FINALIZED')),
  created_at_ns INTEGER NOT NULL,
  finalized_at_ns INTEGER,
  PRIMARY KEY (release_id, epoch),
  CHECK (received_count = success_count + rollback_count + fail_count + rejected_count),
  CHECK (expected_count = received_count + missing_count)
);

CREATE TABLE audit_log (
  audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at_ns INTEGER NOT NULL,
  actor_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  release_id INTEGER,
  payload_json TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL UNIQUE
);

CREATE TRIGGER audit_log_no_update
BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER audit_log_no_delete
BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER finalized_summary_no_update
BEFORE UPDATE ON outcome_summaries
WHEN OLD.state = 'FINALIZED'
BEGIN SELECT RAISE(ABORT, 'finalized outcome summary is immutable'); END;

CREATE TRIGGER outcome_summary_no_delete
BEFORE DELETE ON outcome_summaries BEGIN SELECT RAISE(ABORT, 'outcome summary is append-only'); END;
