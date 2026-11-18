"""Unit tests for BM25/SQLite FTS5 ContextSelector and scoped ContextFingerprintStore."""

from project_t_optimization_core.context_selection import (
    ContextDocument,
    ContextFingerprintStore,
    ContextSelector,
)


def test_context_selector_ranks_relevant_files_tests_and_pinned_within_budget() -> None:
    docs = [
        ContextDocument(
            relative_path="src/auth/jwt_middleware.py",
            content="def verify_jwt(token: str) -> bool:\n    # validates JWT login signature\n    return True\n",
            symbols=("verify_jwt",),
            imports=("token_utils",),
            modified_epoch=200.0,
            file_hash="h1",
        ),
        ContextDocument(
            relative_path="tests/test_jwt_middleware.py",
            content="def test_verify_jwt():\n    assert True\n",
            symbols=("test_verify_jwt",),
            modified_epoch=190.0,
            file_hash="h2",
        ),
        ContextDocument(
            relative_path="src/auth/token_utils.py",
            content="def decode_claims(raw: str) -> dict:\n    return {}\n",
            symbols=("decode_claims",),
            modified_epoch=150.0,
            file_hash="h3",
        ),
        ContextDocument(
            relative_path="src/billing/invoice_pdf.py",
            content="def render_invoice_pdf():\n    return b''\n",
            symbols=("render_invoice_pdf",),
            modified_epoch=100.0,
            file_hash="h4",
        ),
        ContextDocument(
            relative_path="README.md",
            content="Project overview and pinned setup instructions.",
            modified_epoch=50.0,
            file_hash="h5",
        ),
    ]

    outcome = ContextSelector().select(
        task_description="Fix JWT login verification bug in jwt_middleware",
        documents=docs,
        pinned_files=["README.md"],
        max_files=4,
        max_tokens=500,
    )
    paths = [f.relative_path for f in outcome.selected_files]
    assert "README.md" in paths
    assert outcome.selected_files[0].pinned is True
    assert "src/auth/jwt_middleware.py" in paths
    assert "tests/test_jwt_middleware.py" in paths
    assert "src/billing/invoice_pdf.py" not in paths
    assert outcome.total_tokens <= 500


def test_context_fingerprints_isolate_by_project_and_invalidate_on_file_hash_change() -> None:
    store = ContextFingerprintStore()
    store.put(
        project_id="proj_a",
        content_version="v1",
        file_hash="hash_1",
        block_text="Shared block content",
        token_count=4,
    )

    assert (
        store.lookup(
            project_id="proj_a",
            content_version="v1",
            file_hash="hash_1",
            block_text="Shared block content",
        )
        is not None
    )
    # Cross-project lookup must miss
    assert (
        store.lookup(
            project_id="proj_b",
            content_version="v1",
            file_hash="hash_1",
            block_text="Shared block content",
        )
        is None
    )
    # Stale file_hash lookup must miss
    assert (
        store.lookup(
            project_id="proj_a",
            content_version="v1",
            file_hash="hash_2",
            block_text="Shared block content",
        )
        is None
    )
