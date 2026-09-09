"""Unit tests for Pydantic domain models."""

from datetime import datetime, timezone
from src.models import (
    GitHubIssue,
    IssueCategory,
    IssueClassification,
    PriorityLevel,
    PriorityFactors,
    PriorityScore,
    DuplicateCandidate,
    DeduplicationResult,
    ActionType,
    DraftedAction,
    TriageSummaryStats,
    TriageRunReport,
)


def test_issue_model_validation():
    now = datetime.now(timezone.utc)
    issue = GitHubIssue(
        number=101,
        title="App crashes on Windows 11 startup",
        body="When launching the exe on Win 11 23H2, segmentation fault occurs immediately.",
        author="alice_dev",
        labels=["bug", "windows"],
        comments_count=3,
        created_at=now,
        updated_at=now,
        html_url="https://github.com/example/repo/issues/101",
    )
    assert issue.number == 101
    assert "crashes" in issue.full_text
    assert issue.labels == ["bug", "windows"]


def test_classification_model():
    classification = IssueClassification(
        issue_number=101,
        category=IssueCategory.BUG,
        confidence=0.95,
        reasoning="Explicit segmentation fault error reported on application startup.",
        tags=["crash", "windows"],
        suggested_labels=["bug", "os:windows"],
    )
    assert classification.category == IssueCategory.BUG
    assert classification.confidence == 0.95
    assert "crash" in classification.tags


def test_priority_model():
    priority = PriorityScore(
        issue_number=101,
        level=PriorityLevel.CRITICAL,
        numerical_score=92,
        factors=PriorityFactors(
            content_severity=0.95,
            age_factor=0.8,
            activity_factor=0.85,
            label_modifier=0.9,
        ),
        justification="Total crash blocking all Windows 11 users.",
        sla_urgency="immediate",
    )
    assert priority.level == PriorityLevel.CRITICAL
    assert priority.numerical_score == 92


def test_deduplication_model():
    candidate = DuplicateCandidate(
        target_issue_number=45,
        similarity_score=0.88,
        matching_aspects=["identical segfault address", "Windows 11 startup"],
        rationale="Shares identical traceback at boot sequence.",
    )
    result = DeduplicationResult(
        issue_number=101,
        is_duplicate=True,
        confidence=0.88,
        best_match=candidate,
        all_candidates=[candidate],
    )
    assert result.is_duplicate is True
    assert result.best_match.target_issue_number == 45


def test_action_model():
    action = DraftedAction(
        issue_number=101,
        action_type=ActionType.ESCALATE_CRITICAL,
        headline="Escalate crash to core team and ask for crash dump",
        reasoning="Critical crash on standard OS startup.",
        draft_comment="Thank you for reporting this. Could you please share the generated minidump file?",
        labels_to_add=["priority:critical", "investigating"],
    )
    assert action.action_type == ActionType.ESCALATE_CRITICAL
    assert "minidump" in action.draft_comment
