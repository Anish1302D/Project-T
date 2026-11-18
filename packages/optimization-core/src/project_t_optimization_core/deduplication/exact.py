"""Stages 2-3 & 5: SHA-256 block hashing and safe exact duplicate removal."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from project_t_contracts import ContentType

from .._segments import split_segments
from .normalizer import normalize_line_endings

_UNSAFE_INTRA_DEDUP_TYPES = frozenset(
    {ContentType.SOURCE_CODE, ContentType.JSON, ContentType.TOOL_RESULT}
)
_MIN_DEDUP_BLOCK_CHARS = 24
_HEADING_ONLY_RE = re.compile(r"^#{1,6}\s+\S[^\n]*$")


@dataclass(frozen=True, slots=True)
class ExactDeduplicationResult:
    """Outcome of intra-request exact block deduplication."""

    text: str
    removed_blocks: int
    block_hashes: tuple[str, ...]
    applied: bool


@dataclass(frozen=True, slots=True)
class DeduplicatedContextItemsResult:
    """Outcome of multi-item exact deduplication preserving pinned items and provenance."""

    kept_items: tuple[dict[str, object], ...]
    removed_item_ids: tuple[str, ...]
    duplicate_map: dict[str, str]
    applied: bool


def compute_block_hash(block: str) -> str:
    """Compute a stable SHA-256 hex digest over line-normalized block content."""
    canonical = normalize_line_endings(block).strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_range_protected(
    start: int,
    end: int,
    protected_ranges: tuple[tuple[int, int], ...],
) -> bool:
    return any(not (end <= p_start or start >= p_end) for p_start, p_end in protected_ranges)


def deduplicate_exact_blocks(
    text: str,
    *,
    content_type: ContentType,
    protected_ranges: tuple[tuple[int, int], ...] = (),
    pinned_texts: frozenset[str] = frozenset(),
) -> ExactDeduplicationResult:
    """
    Remove exact repeated paragraph/section blocks within a single request when safe.

    Never deduplicates pure source_code, json, or tool_result payloads internally,
    nor blocks overlapping protected ranges or pinned texts.
    """
    if content_type in _UNSAFE_INTRA_DEDUP_TYPES or not text.strip():
        return ExactDeduplicationResult(
            text=text,
            removed_blocks=0,
            block_hashes=(),
            applied=False,
        )

    normalized = normalize_line_endings(text)
    seen_hashes: set[str] = set()
    kept_segments: list[str] = []
    recorded_hashes: list[str] = []
    removed_count = 0

    for seg in split_segments(normalized):
        if seg.kind in {"code_fence", "json_block"}:
            block_hash = compute_block_hash(seg.text)
            recorded_hashes.append(block_hash)
            # Only remove repeated identical fenced blocks if outside protected ranges
            if (
                block_hash in seen_hashes
                and seg.text.strip() not in pinned_texts
                and not _is_range_protected(seg.start, seg.end, protected_ranges)
            ):
                removed_count += 1
                continue
            seen_hashes.add(block_hash)
            kept_segments.append(seg.text)
            continue

        # Partition prose segment by blank lines while tracking offsets
        parts = re.split(r"(\n{2,})", seg.text)
        offset = seg.start
        prose_out: list[str] = []
        pending_sep = ""
        for part in parts:
            part_start = offset
            part_end = offset + len(part)
            offset = part_end
            if not part:
                continue
            if re.fullmatch(r"\n{2,}", part):
                pending_sep = part
                continue

            stripped = part.strip()
            if (
                len(stripped) < _MIN_DEDUP_BLOCK_CHARS
                or _HEADING_ONLY_RE.match(stripped)
                or stripped in pinned_texts
                or _is_range_protected(part_start, part_end, protected_ranges)
            ):
                if prose_out and pending_sep:
                    prose_out.append(pending_sep)
                elif not prose_out and pending_sep and seg.start > 0:
                    prose_out.append(pending_sep)
                prose_out.append(part)
                pending_sep = ""
                continue

            block_hash = compute_block_hash(part)
            recorded_hashes.append(block_hash)
            if block_hash in seen_hashes:
                removed_count += 1
                pending_sep = ""
                continue

            seen_hashes.add(block_hash)
            if prose_out and pending_sep:
                prose_out.append(pending_sep)
            elif not prose_out and pending_sep and seg.start > 0:
                prose_out.append(pending_sep)
            prose_out.append(part)
            pending_sep = ""

        if pending_sep and prose_out:
            prose_out.append(pending_sep)
        prose_joined = re.sub(r"\n{3,}", "\n\n", "".join(prose_out))
        kept_segments.append(prose_joined)

    result_text = "".join(kept_segments).strip("\n")
    return ExactDeduplicationResult(
        text=result_text if removed_count > 0 else text,
        removed_blocks=removed_count,
        block_hashes=tuple(recorded_hashes),
        applied=removed_count > 0,
    )


def deduplicate_context_items(
    items: list[dict[str, object]],
    *,
    project_id: str | None = None,
) -> DeduplicatedContextItemsResult:
    """
    Deduplicate multi-item context collections by project-scoped content hash.

    Pinned items are always kept (canonicalizing any duplicate unpinned items after them).
    """
    scope_prefix = f"{project_id}:" if project_id else "default:"
    # Ensure pinned occurrences claim canonical priority if identical content appears both pinned & unpinned
    ordered = sorted(
        enumerate(items),
        key=lambda pair: (0 if bool(pair[1].get("pinned", False)) else 1, pair[0]),
    )
    canonical_by_hash: dict[str, str] = {}
    kept_indices: set[int] = set()
    removed_ids: list[str] = []
    duplicate_map: dict[str, str] = {}

    for idx, item in ordered:
        item_id = str(item["id"])
        content = str(item.get("content", ""))
        pinned = bool(item.get("pinned", False))
        scoped_hash = hashlib.sha256(
            f"{scope_prefix}{normalize_line_endings(content).strip()}".encode("utf-8")
        ).hexdigest()

        if scoped_hash in canonical_by_hash and not pinned:
            removed_ids.append(item_id)
            duplicate_map[item_id] = canonical_by_hash[scoped_hash]
        else:
            canonical_by_hash.setdefault(scoped_hash, item_id)
            kept_indices.add(idx)

    kept_items = tuple(item for idx, item in enumerate(items) if idx in kept_indices)
    return DeduplicatedContextItemsResult(
        kept_items=kept_items,
        removed_item_ids=tuple(removed_ids),
        duplicate_map=duplicate_map,
        applied=len(removed_ids) > 0,
    )
