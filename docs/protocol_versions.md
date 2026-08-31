# LedgerGuard Protocol Versions

## LedgerGuard V1

V1 is the preserved original PoC protocol. It commits a Merkle root and aggregate
success, failure, and rollback counters for each sequential release epoch. Receipt
JSON is hashed but not signed. The operator is trusted to choose the receipt set
and counters.

V1 supports integrity of included receipt leaves relative to the committed root.
It does not provide expected-cohort completeness or independent witness agreement.

## LedgerGuard V2

V2 is a clean reviewer-revision deployment. It adds:

- EIP-712 authenticated software-emulated device receipts;
- chain/contract/release/rollout/epoch/cohort/deadline binding;
- immutable expected-cohort commitment and count;
- explicit rejected and missing outcomes;
- expected-count reconciliation;
- independent aggregator and witness submissions;
- append-only finalized summaries;
- replay and concurrency tests.

## Evidence Rule

Every raw record, CSV row, table, figure, and manuscript claim must include a
protocol version. V1 evidence must never be interpreted as completeness-aware V2
evidence. V2 begins with fresh contract addresses and fresh rollout/epoch state.
