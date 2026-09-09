"""Tests for prompt generation and LLM structured generation."""

import pytest
from src.prompts import (
    build_classify_prompt,
    build_prioritize_prompt,
    build_deduplicate_prompt,
    build_draft_action_prompt,
)
from src.llm import get_llm_provider
from src.models import (
    IssueClassification,
    IssueCategory,
    PriorityScore,
    PriorityLevel,
    DeduplicationResult,
    DraftedAction,
    ActionType,
)


def test_prompt_builders_render():
    p1 = build_classify_prompt(101, "Crash on startup", "Segfault traceback", ["bug"])
    assert "Issue Number: 101" in p1
    assert "Crash on startup" in p1

    p2 = build_prioritize_prompt(101, "Crash", "Body", ["bug"], 3, 1.5, "bug")
    assert "Age in Days: 1.5" in p2

    p3 = build_deduplicate_prompt(103, "Boot fail", "Stacktrace", [{"number": 101, "title": "Crash", "body": "Stacktrace"}])
    assert "Issue #103: Boot fail" in p3
    assert "Candidate #101" in p3

    p4 = build_draft_action_prompt(101, "Crash", "Body", "bug", "critical")
    assert "Priority: critical" in p4


@pytest.mark.asyncio
async def test_mock_llm_structured_classification():
    provider = get_llm_provider("mock")

    prompt = build_classify_prompt(101, "Crash on startup: AccessViolationException", "Fatal error", ["bug"])
    result, telemetry = await provider.generate_structured(prompt, IssueClassification)

    assert isinstance(result, IssueClassification)
    assert result.issue_number == 101
    assert result.category == IssueCategory.BUG
    assert result.confidence >= 0.90
    assert telemetry["tokens_prompt"] > 0
    assert telemetry["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_mock_llm_structured_priority():
    provider = get_llm_provider("mock")

    prompt = build_prioritize_prompt(101, "Crash on startup: AccessViolationException", "Fatal error", ["bug"], 4, 2.0, "bug")
    result, telemetry = await provider.generate_structured(prompt, PriorityScore)

    assert isinstance(result, PriorityScore)
    assert result.issue_number == 101
    assert result.level == PriorityLevel.CRITICAL
    assert result.numerical_score >= 85
    assert telemetry["tokens_completion"] > 0


@pytest.mark.asyncio
async def test_mock_llm_structured_deduplication():
    provider = get_llm_provider("mock")

    prompt = build_deduplicate_prompt(103, "App fails to boot on Win11 - native_core.dll", "Trace", [{"number": 101, "title": "Crash on startup"}])
    result, telemetry = await provider.generate_structured(prompt, DeduplicationResult)

    assert isinstance(result, DeduplicationResult)
    assert result.is_duplicate is True
    assert result.best_match is not None
    assert result.best_match.target_issue_number == 101


@pytest.mark.asyncio
async def test_mock_llm_structured_draft_action():
    provider = get_llm_provider("mock")

    prompt = build_draft_action_prompt(106, "Best Online Casino Bonuses 2026", "Visit http://scam.biz", "spam", "low")
    result, telemetry = await provider.generate_structured(prompt, DraftedAction)

    assert isinstance(result, DraftedAction)
    assert result.action_type == ActionType.CLOSE_AS_SPAM
    assert result.should_close is True
