"""Stage 4 (P1): Deterministic SimHash and MinHash near-duplicate candidate detection."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from project_t_contracts import ContentType

_UNSAFE_SIMILARITY_TYPES = frozenset(
    {ContentType.SOURCE_CODE, ContentType.JSON, ContentType.TOOL_RESULT}
)
_WORD_RE = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True, slots=True)
class NearDuplicateCandidate:
    """Candidate pair of prose/log blocks exhibiting high lexical similarity."""

    first_index: int
    second_index: int
    similarity: float
    hamming_distance: int


def _tokens_for_similarity(text: str) -> list[str]:
    words = _WORD_RE.findall(text.lower())
    if len(words) < 2:
        return words
    return [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]


def _hash64(value: str, seed: int = 0) -> int:
    digest = hashlib.blake2b(f"{seed}:{value}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def simhash64(text: str) -> int:
    """Compute a deterministic 64-bit SimHash fingerprint over 3-word shingles."""
    shingles = _tokens_for_similarity(text)
    if not shingles:
        return 0
    weights = [0] * 64
    for shingle in shingles:
        h = _hash64(shingle)
        for bit in range(64):
            weights[bit] += 1 if (h >> bit) & 1 else -1
    fingerprint = 0
    for bit, weight in enumerate(weights):
        if weight > 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """Return Hamming bit distance between two 64-bit SimHash values."""
    return (a ^ b).bit_count()


def minhash_signature(text: str, num_hashes: int = 64) -> tuple[int, ...]:
    """Compute a deterministic MinHash signature over unique shingles."""
    shingles = set(_tokens_for_similarity(text))
    if not shingles:
        return tuple([0] * num_hashes)
    return tuple(min(_hash64(s, seed=seed) for s in shingles) for seed in range(num_hashes))


def jaccard_similarity_estimate(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    """Estimate Jaccard similarity in [0.0, 1.0] from two equal-length MinHash signatures."""
    if not sig_a or len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b, strict=True) if a == b)
    return matches / len(sig_a)


def find_near_duplicate_candidates(
    blocks: list[str],
    *,
    content_type: ContentType,
    threshold: float = 0.85,
) -> list[NearDuplicateCandidate]:
    """
    Detect high-similarity candidate blocks for prose/log content only.

    Always returns [] for source_code, json, and tool_result per deduplication safety policy.
    """
    if content_type in _UNSAFE_SIMILARITY_TYPES or len(blocks) < 2:
        return []

    simhashes = [simhash64(b) for b in blocks]
    minhashes = [minhash_signature(b) for b in blocks]
    candidates: list[NearDuplicateCandidate] = []

    for i in range(len(blocks)):
        if len(blocks[i].strip()) < 24:
            continue
        for j in range(i + 1, len(blocks)):
            if len(blocks[j].strip()) < 24:
                continue
            sim = jaccard_similarity_estimate(minhashes[i], minhashes[j])
            dist = hamming_distance(simhashes[i], simhashes[j])
            if sim >= threshold or dist <= 4:
                candidates.append(
                    NearDuplicateCandidate(
                        first_index=i,
                        second_index=j,
                        similarity=round(sim, 4),
                        hamming_distance=dist,
                    )
                )
    return candidates
