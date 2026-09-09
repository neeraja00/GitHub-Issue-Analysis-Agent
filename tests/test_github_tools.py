"""Tests for GitHub API Client and LLM Tools."""

import pytest
from src.github.client import GitHubClient
from src.github.tools import GitHubTools


@pytest.mark.asyncio
async def test_mock_list_issues():
    client = GitHubClient(force_mock=True)
    tools = GitHubTools(client=client, dry_run=True)

    issues = await tools.list_issues(repo="mock/demo-repo", limit=5)
    assert len(issues) == 5
    assert issues[0]["number"] == 101
    assert "Crash on startup" in issues[0]["title"]
    assert issues[0]["labels"] == ["bug", "crash", "os:windows"]


@pytest.mark.asyncio
async def test_mock_get_issue_detail():
    client = GitHubClient(force_mock=True)
    tools = GitHubTools(client=client, dry_run=True)

    detail = await tools.get_issue_detail(repo="mock/demo-repo", issue_number=101)
    assert detail["number"] == 101
    assert "AccessViolationException" in detail["body"]
    assert len(detail["comments"]) >= 2
    assert detail["comments"][0]["author"] == "sara_qa"


@pytest.mark.asyncio
async def test_mock_search_similar_issues():
    client = GitHubClient(force_mock=True)
    tools = GitHubTools(client=client, dry_run=True)

    # Issue #103 discusses native_core.dll AccessViolation on Windows 11
    candidates = await tools.search_similar_issues(
        repo="mock/demo-repo",
        query="AccessViolationException native_core.dll Windows 11 startup",
        exclude_number=103,
        limit=3,
    )
    assert len(candidates) > 0
    # Candidate #101 should be the top match
    assert candidates[0]["number"] == 101
    assert candidates[0]["similarity_score"] > 0.5


@pytest.mark.asyncio
async def test_dry_run_safety():
    client = GitHubClient(force_mock=True)
    tools = GitHubTools(client=client, dry_run=True)

    label_res = await tools.label_issue(
        repo="mock/demo-repo", issue_number=101, labels=["triage:bug"]
    )
    assert label_res["dry_run"] is True
    assert label_res["status"] == "simulated"

    comment_res = await tools.post_comment(
        repo="mock/demo-repo",
        issue_number=101,
        body="Automated triage comment.",
    )
    assert comment_res["dry_run"] is True
    assert comment_res["status"] == "simulated"

    close_res = await tools.close_issue(
        repo="mock/demo-repo", issue_number=106, reason="not_planned"
    )
    assert close_res["dry_run"] is True
    assert close_res["status"] == "simulated"
