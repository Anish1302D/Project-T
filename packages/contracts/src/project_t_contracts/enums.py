"""Canonical enums aligned with packages/contracts/schemas/contracts.v1.schema.json."""

from enum import StrEnum


class OptimizationMode(StrEnum):
    SAFE = "safe"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class ContentType(StrEnum):
    PROMPT = "prompt"
    DEVELOPER_PROMPT = "developer_prompt"
    SOURCE_CODE = "source_code"
    JSON = "json"
    DOCUMENTATION = "documentation"
    TERMINAL_OUTPUT = "terminal_output"
    CONVERSATION = "conversation"
    TOOL_RESULT = "tool_result"


class AccuracyLevel(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"


class IntegrationSource(StrEnum):
    VSCODE = "vscode"
    BROWSER = "browser"
    MCP = "mcp"
    GATEWAY = "gateway"
    CLI = "cli"
    API = "api"


class OptimizationStatus(StrEnum):
    VALIDATED = "validated"
    FALLBACK_VALIDATION_FAILED = "fallback_validation_failed"
    FALLBACK_NO_SAVINGS = "fallback_no_savings"
    FALLBACK_ERROR = "fallback_error"
