"""Unit tests for whitespace normalization, exact dedup, and near-duplicate detection."""

from project_t_contracts import ContentType

from project_t_optimization_core.deduplication import (
    deduplicate_context_items,
    deduplicate_exact_blocks,
    find_near_duplicate_candidates,
    normalize_safe_whitespace,
)


def test_normalizer_preserves_python_yaml_and_json_indentation() -> None:
    py_code = "def greet(name: str) -> str:\r\n    if name:\r\n        return f'hi {name}'\r\n    return 'hi'\r\n\r\n\r\n"
    norm_py = normalize_safe_whitespace(py_code, content_type=ContentType.SOURCE_CODE)
    assert "    if name:\n        return" in norm_py
    assert "\r" not in norm_py

    mixed = (
        "Line one   \r\n\r\n\r\n\r\n"
        "```yaml\nservice:\n  port: 4765\n    nested: true\n```\n"
    )
    norm_mixed = normalize_safe_whitespace(mixed, content_type=ContentType.PROMPT, max_blank_lines=1)
    assert "  port: 4765\n    nested: true" in norm_mixed
    assert "Line one\n\n```yaml" in norm_mixed


def test_exact_dedup_removes_duplicate_prose_but_protects_code_and_constraints() -> None:
    repeated = "This is a sufficiently long repeated instruction paragraph about context setup."
    content = (
        f"{repeated}\n\n"
        "Do not change the database schema or migration files.\n\n"
        f"{repeated}\n\n"
        "```python\ndef f():\n    return 1\n```\n"
    )
    res = deduplicate_exact_blocks(
        content,
        content_type=ContentType.DEVELOPER_PROMPT,
        pinned_texts=frozenset({"Do not change the database schema or migration files."}),
    )
    assert res.applied is True
    assert res.removed_blocks == 1
    assert res.text.count(repeated) == 1
    assert "Do not change the database schema" in res.text
    assert "def f():\n    return 1" in res.text


def test_exact_dedup_refuses_source_code_and_json() -> None:
    code = "def a():\n    return 1\n\ndef a():\n    return 1\n"
    res_code = deduplicate_exact_blocks(code, content_type=ContentType.SOURCE_CODE)
    assert res_code.applied is False
    assert res_code.text == code

    json_doc = '{"a": 1, "b": 1}'
    res_json = deduplicate_exact_blocks(json_doc, content_type=ContentType.JSON)
    assert res_json.applied is False
    assert res_json.text == json_doc


def test_context_items_dedup_prefers_pinned_and_scopes_by_project() -> None:
    items = [
        {"id": "unpinned_first", "content": "Shared project rule block.", "pinned": False},
        {"id": "pinned_second", "content": "Shared project rule block.", "pinned": True},
        {"id": "unique", "content": "Unique module details.", "pinned": False},
    ]
    res = deduplicate_context_items(items, project_id="proj_alpha")
    assert res.applied is True
    kept_ids = [item["id"] for item in res.kept_items]
    assert kept_ids == ["pinned_second", "unique"]
    assert res.duplicate_map == {"unpinned_first": "pinned_second"}


def test_near_duplicate_detection_works_on_prose_and_skips_code() -> None:
    blocks = [
        "Fix the login API middleware error handling without altering database schema tables.",
        "Fix the login API middleware error handling without changing database schema tables.",
        "Completely unrelated documentation about Docker deployment pipelines.",
    ]
    prose_hits = find_near_duplicate_candidates(blocks, content_type=ContentType.PROMPT, threshold=0.6)
    assert len(prose_hits) == 1
    assert prose_hits[0].first_index == 0
    assert prose_hits[0].second_index == 1

    code_hits = find_near_duplicate_candidates(blocks, content_type=ContentType.SOURCE_CODE, threshold=0.5)
    assert code_hits == []
