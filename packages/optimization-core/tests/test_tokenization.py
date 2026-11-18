"""Unit tests for engine-side TokenEstimator and savings accounting."""

from project_t_contracts import AccuracyLevel

from project_t_optimization_core.tokenization import (
    GenericOfflineEstimator,
    TokenEstimator,
    TokenizerProtocol,
    calculate_savings_percentage,
)
from project_t_provider_adapters import OpenAITokenizerAdapter


class _FailingAdapter:
    provider = "broken"

    def count_text(self, text: str, model: str):
        raise RuntimeError("Simulated provider adapter failure")


def test_token_estimator_defaults_to_offline_estimated() -> None:
    estimator = TokenEstimator()
    assert isinstance(GenericOfflineEstimator(), TokenizerProtocol)

    res = estimator.count("Optimize prompt context safely.", "generic")
    assert res.accuracy == AccuracyLevel.ESTIMATED
    assert res.provider == "local"
    assert res.count > 0


def test_token_estimator_supports_injected_adapter_and_recovers_on_error() -> None:
    openai_est = TokenEstimator(adapter=OpenAITokenizerAdapter(allow_tiktoken=True))
    exact_res = openai_est.count("Fix the JWT middleware.", "gpt-4o")
    assert exact_res.accuracy == AccuracyLevel.EXACT
    assert exact_res.provider == "openai"

    resilient = TokenEstimator(adapter=_FailingAdapter())
    fallback_res = resilient.count("Fix the JWT middleware.", "gpt-4o")
    assert fallback_res.accuracy == AccuracyLevel.ESTIMATED
    assert fallback_res.provider == "local"
    assert fallback_res.count > 0


def test_savings_percentage_formula_matches_section_7_8() -> None:
    assert calculate_savings_percentage(2400, 1610) == 32.92
    assert calculate_savings_percentage(1200, 820) == 31.67
    assert calculate_savings_percentage(0, 0) == 0.0
