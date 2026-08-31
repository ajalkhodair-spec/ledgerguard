# LedgerGuard V1 to V2 Migration

## Strategy

The reviewer revision uses a clean V2 redeployment. No proxy upgrade is introduced.
V1 contracts and roots remain available for V1 verification, while new V2 cohorts
and epochs begin at fresh V2 addresses.

## Compatibility Matrix

| Item | V1 | V2 | Migration treatment |
|---|---|---|---|
| Release metadata | Existing registry records | May reference exported metadata | Export with V1 address and chain ID |
| Receipt authentication | Unsigned | EIP-712 signed | Cannot be retrofitted to V1 receipts |
| Outcome root | Integrity-only | Completeness-aware | Never reinterpret V1 root as V2 root |
| Counters | success/fail/rollback | success/rollback/fail/rejected/missing | Preserve original V1 schema |
| Expected cohort | Absent | Immutable commitment and count | Configure only for new V2 epoch |
| Witness | Absent | Active auditor confirmation | New V2 workflow only |
| Storage | V1 layout retained | Separate V2 layout | No in-place storage migration |
| ABI/events | V1 retained | Versioned V2 ABI/events | Consumers select by protocol version |

## Required Compatibility Tests

- Exported V1 release metadata retains its V1 contract and chain provenance.
- A preserved V1 root remains readable from the V1 contract.
- V2 starts with no inherited finalized epoch.
- A V1 root cannot be submitted as a valid completeness-aware V2 summary without
  the required cohort, counters, and witness confirmation.
- V1 and V2 events are distinguishable by address and event signature.
