"""Unit tests for deterministic ContentClassifier and mixed-segment splitting."""

from project_t_contracts import ContentType

from project_t_optimization_core.classifier import ContentClassifier


def test_classifies_section_7_2_developer_instruction() -> None:
    prompt = (
        "Fix the authentication issue in my React application.\n"
        "Check the JWT middleware and login API.\n"
        "Do not change the database schema."
    )
    res = ContentClassifier().classify(prompt)
    contract = res.to_contract()

    assert res.type == "developer_instruction"
    assert contract.mapped_content_type == ContentType.DEVELOPER_PROMPT
    assert contract.contains_code is False
    assert contract.contains_constraints is True


def test_classifies_json_and_tool_result() -> None:
    classifier = ContentClassifier()

    plain_json = classifier.classify('{"status": "ok", "count": 3}')
    assert plain_json.mapped_content_type == ContentType.JSON
    assert plain_json.language == "json"

    tool_json = classifier.classify('{"tool_name": "select_relevant_files", "result": []}')
    assert tool_json.mapped_content_type == ContentType.TOOL_RESULT


def test_detects_mixed_prose_and_code_json_segments() -> None:
    content = (
        "Please inspect this middleware.\n\n"
        "```python\ndef verify_jwt(token: str) -> bool:\n    return bool(token)\n```\n\n"
        'And keep this payload:\n```json\n{"user_id": 123}\n```\n'
    )
    res = ContentClassifier().classify(content)
    assert res.contains_code is True
    kinds = [seg.kind for seg in res.segments]
    assert "prose" in kinds
    assert "code_fence" in kinds
    assert "json_block" in kinds


def test_classifies_terminal_log_and_respects_explicit_hint() -> None:
    log_text = (
        "Traceback (most recent call last):\n"
        '  File "src/app.py", line 14, in <module>\n'
        "    raise ValueError('bad')\n"
        "ValueError: bad\n"
        "1 failed, 12 passed in 0.5s\n"
    )
    res = ContentClassifier().classify(log_text)
    assert res.mapped_content_type == ContentType.TERMINAL_OUTPUT

    hinted = ContentClassifier().classify("Short text", hint=ContentType.DOCUMENTATION)
    assert hinted.mapped_content_type == ContentType.DOCUMENTATION
