import hashlib
from dataclasses import dataclass
from typing import List, Tuple


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def merkle_parent(a: bytes, b: bytes) -> bytes:
    # Canonical concatenation (a||b) then sha256
    return sha256(a + b)


def merkle_root(leaves: List[bytes]) -> bytes:
    if not leaves:
        return b"\x00" * 32

    level = leaves[:]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [merkle_parent(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


@dataclass
class ProofItem:
    sibling: bytes
    is_left: bool  # True if sibling is left of current hash


def merkle_proof(leaves: List[bytes], index: int) -> List[ProofItem]:
    if index < 0 or index >= len(leaves):
        raise IndexError("index out of range")

    proof: List[ProofItem] = []
    idx = index
    level = leaves[:]

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])

        sibling_idx = idx ^ 1
        sibling = level[sibling_idx]
        is_left = sibling_idx < idx
        proof.append(ProofItem(sibling=sibling, is_left=is_left))

        # Move to next level
        next_level = [merkle_parent(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        idx //= 2
        level = next_level

    return proof


def verify_proof(leaf: bytes, proof: List[ProofItem], root: bytes) -> bool:
    h = leaf
    for p in proof:
        if p.is_left:
            h = merkle_parent(p.sibling, h)
        else:
            h = merkle_parent(h, p.sibling)
    return h == root
