"""Integration and unit tests for the multi-step Agent Pipeline."""

import os
from pathlib import Path
import pytest

from src.agent.pipeline import TriagePipeline
from src.llm.mock_provider import MockLLMProvider
from src.github.client import GitHubClient
from src.models import PriorityLevel, ActionType, IssueCategory


@pytest.mark.asyncio
async def test_full_pipeline_execution():
    pipeline = TriagePipeline(
        repo="mock/demo-repo",
        goal="Triage open issues from the last 30 days",
        dry_run=True,
        limit=8,
        provider=MockLLMProvider(),
        github_client=GitHubClient(force_mock=True),
    )

    report = await pipeline.execute()

    # Verify overall report stats
    assert report.repository == "mock/demo-repo"
    assert report.stats.total_issues_analyzed == 8
    assert report.stats.actions_drafted == 8
    assert report.dry_run is True

    # Check that critical bug #101 was recognized
    issue_101_rec = next(r for r in report.issues if r.issue.number == 101)
    assert issue_101_rec.classification.category == IssueCategory.BUG
    assert issue_101_rec.priority.level == PriorityLevel.CRITICAL
    assert issue_101_rec.action.action_type == ActionType.ESCALATE_CRITICAL

    # Check duplicate detection for #103
    issue_103_rec = next(r for r in report.issues if r.issue.number == 103)
    assert issue_103_rec.deduplication.is_duplicate is True
    assert issue_103_rec.deduplication.best_match.target_issue_number == 101
    assert issue_103_rec.action.action_type == ActionType.CLOSE_AS_DUPLICATE
    assert issue_103_rec.action.should_close is True

    # Check spam detection for #106
    issue_106_rec = next(r for r in report.issues if r.issue.number == 106)
    assert issue_106_rec.classification.category == IssueCategory.SPAM
    assert issue_106_rec.action.action_type == ActionType.CLOSE_AS_SPAM
    assert issue_106_rec.action.should_close is True

    # Check vague bug reproduction request for #107
    issue_107_rec = next(r for r in report.issues if r.issue.number == 107)
    assert issue_107_rec.action.action_type == ActionType.REQUEST_REPRODUCTION

    # Check that structured JSONL logs exist and were populated
    log_file = pipeline.run_logger.log_file
    assert log_file.exists()
    assert log_file.stat().st_size > 0
    with open(log_file, "r", encoding="utf-8") as f:
        events = [line.strip() for line in f if line.strip()]
        assert len(events) >= 10
        # Check event types
        assert any('"event_type": "tool_call"' in e for e in events)
        assert any('"event_type": "llm_call"' in e for e in events)
        assert any('"event_type": "decision"' in e for e in events)

    # Check that report files exist on disk
    reports_dir = Path("reports")
    json_reports = list(reports_dir.glob("mock_demo-repo_*.json"))
    md_reports = list(reports_dir.glob("mock_demo-repo_*.md"))
    assert len(json_reports) > 0
    assert len(md_reports) > 0


@pytest.mark.asyncio
async def test_pipeline_error_isolation():
    """Test that a failure in one issue's classification does not crash the entire batch."""

    class ErrorInjectingMockProvider(MockLLMProvider):
        async def generate_structured(self, prompt, response_model, system_prompt=None):
            # Inject failure on issue #104
            if "Issue Number: 104" in prompt or "Issue #104" in prompt:
                raise RuntimeError("Simulated transient LLM rate-limit or JSON schema validation crash on #104")
            return await super().generate_structured(prompt, response_model, system_prompt)

    pipeline = TriagePipeline(
        repo="mock/demo-repo",
        goal="Test fault tolerance",
        dry_run=True,
        limit=5,
        provider=ErrorInjectingMockProvider(),
        github_client=GitHubClient(force_mock=True),
    )

    report = await pipeline.execute()

    # The batch should still succeed and analyze all 5 issues
    assert report.stats.total_issues_analyzed == 5
    # Issue #104 should have an isolated error recorded
    rec_104 = next(r for r in report.issues if r.issue.number == 104)
    assert rec_104.processing_error is not None or rec_104.classification is not None
    # Issue #101 should be completely unharmed
    rec_101 = next(r for r in report.issues if r.issue.number == 101)
    assert rec_101.priority.level == PriorityLevel.CRITICAL
