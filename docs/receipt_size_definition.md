# Canonical Receipt-Size Definition

Receipt size is reported for the actual signed JSON transport representation used
by the V2 software-emulation pipeline. Each receipt is serialized as compact
UTF-8 JSON with lexicographically sorted keys and separators `,` and `:`. The
per-receipt byte count excludes the JSONL newline delimiter.

The `signature` field is included. It is a 65-byte ECDSA signature encoded as a
`0x`-prefixed hexadecimal JSON string. All other variable-length values are
measured from each preserved receipt rather than assumed to have a fixed length.

The analysis reports separate columns for:

- minimum, median, and maximum unsigned payload bytes per device;
- the raw 65-byte ECDSA signature;
- minimum, median, and maximum signed transport-receipt bytes per device;
- the 32-byte receipt hash committed by a terminal record;
- minimum, median, and maximum canonical terminal-record bytes per device;
- the 32-byte terminal-leaf hash;
- aggregate signed-receipt-set bytes;
- aggregate canonical terminal-set bytes and aggregate terminal-leaf-hash bytes;
- physical JSONL file bytes, including one newline per record.

Aggregate receipt-set bytes must never be described as bytes per receipt. These
JSON transport sizes are not Solidity ABI calldata sizes and are not measured
on-chain storage growth.

The signed fields, in EIP-712 order, are:

```text
bytes32 deviceIdHash
uint256 releaseId
bytes32 rolloutId
uint32 epoch
bytes32 cohortId
uint64 deadline
uint64 targetVersion
uint8 outcome
uint64 observedAt
uint256 nonce
```

The analysis distinguishes the unsigned compact-JSON payload, 65-byte ECDSA
signature, complete signed compact-JSON receipt, 32-byte receipt hash, canonical
terminal record, 32-byte terminal-leaf hash, and both aggregate sets. Hex strings are counted in
their actual JSON transport representation, including the `0x` prefix and quote
characters; they are not reported as decoded binary bytes.
