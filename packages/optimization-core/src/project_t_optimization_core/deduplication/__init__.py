from .exact import (
    DeduplicatedContextItemsResult,
    ExactDeduplicationResult,
    compute_block_hash,
    deduplicate_context_items,
    deduplicate_exact_blocks,
)
from .normalizer import normalize_line_endings, normalize_safe_whitespace
from .similarity import (
    NearDuplicateCandidate,
    find_near_duplicate_candidates,
    hamming_distance,
    jaccard_similarity_estimate,
    minhash_signature,
    simhash64,
)

__all__ = [
    "DeduplicatedContextItemsResult",
    "ExactDeduplicationResult",
    "NearDuplicateCandidate",
    "compute_block_hash",
    "deduplicate_context_items",
    "deduplicate_exact_blocks",
    "find_near_duplicate_candidates",
    "hamming_distance",
    "jaccard_similarity_estimate",
    "minhash_signature",
    "normalize_line_endings",
    "normalize_safe_whitespace",
    "simhash64",
]
