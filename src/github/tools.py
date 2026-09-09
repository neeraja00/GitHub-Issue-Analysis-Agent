"""Explicit LLM-callable tools for interacting with GitHub repositories."""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.github.client import GitHubClient
from src.models.github import GitHubIssue

logger = logging.getLogger("agent_tools")


class GitHubTools:
    """Tool execution registry binding an authenticated GitHub client to callable functions."""

    def __init__(self, client: Optional[GitHubClient] = None, dry_run: bool = True):
        self.client = client or GitHubClient()
        self.dry_run = dry_run
        self._cached_issues: Dict[str, List[GitHubIssue]] = {}

    async def list_issues(
        self,
        repo: str,
        state: str = "open",
        since: Optional[str] = None,
        labels: Optional[List[str]] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Fetch a list of issues from the given GitHub repository.

        Args:
            repo: Repository in 'owner/repo' format (e.g. 'acme-org/web-platform').
            state: Issue state to retrieve ('open', 'closed', or 'all').
            since: ISO 8601 timestamp string (YYYY-MM-DDTHH:MM:SSZ) to filter issues updated after.
            labels: List of label names to filter by.
            limit: Maximum number of issues to fetch (default 30).

        Returns:
            List of issue summary dictionaries with number, title, author, labels, and dates.
        """
        since_dt = datetime.fromisoformat(since) if since else None
        issues = await self.client.list_issues(
            repo=repo,
            state=state,
            since=since_dt,
            labels=labels,
            limit=limit,
        )
        self._cached_issues[repo] = issues

        return [
            {
                "number": issue.number,
                "title": issue.title,
                "author": issue.author,
                "labels": issue.labels,
                "comments_count": issue.comments_count,
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "html_url": issue.html_url,
                "body_preview": (issue.body[:200] + "...") if len(issue.body) > 200 else issue.body,
            }
            for issue in issues
        ]

    async def get_issue_detail(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Retrieve full details of a specific issue including its body and recent comments.

        Args:
            repo: Repository in 'owner/repo' format.
            issue_number: Unique issue number ID.

        Returns:
            Dictionary containing full title, body, comments, labels, and timestamps.
        """
        issue = await self.client.get_issue_detail(repo=repo, issue_number=issue_number)
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "author": issue.author,
            "labels": issue.labels,
            "comments_count": issue.comments_count,
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
            "html_url": issue.html_url,
            "comments": [
                {
                    "author": c.author,
                    "body": c.body,
                    "created_at": c.created_at.isoformat(),
                }
                for c in issue.comments
            ],
        }

    async def search_similar_issues(
        self,
        repo: str,
        query: str,
        exclude_number: Optional[int] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search across repository issues for matching keywords or text snippets to detect duplicates.

        Args:
            repo: Repository in 'owner/repo' format.
            query: Keywords, error strings, or symptom descriptions to search for.
            exclude_number: Issue number to exclude from search results (e.g. current issue).
            limit: Maximum candidate matches to return.

        Returns:
            List of matching issues with relevance scores and snippets.
        """
        # Ensure we have cached issues or fetch them
        if repo not in self._cached_issues:
            self._cached_issues[repo] = await self.client.list_issues(repo=repo, limit=50)

        query_tokens = set(query.lower().split())
        scored_candidates = []

        for issue in self._cached_issues[repo]:
            if exclude_number and issue.number == exclude_number:
                continue

            text = f"{issue.title} {issue.body}".lower()
            overlap_count = sum(1 for token in query_tokens if token in text and len(token) > 2)

            if overlap_count > 0:
                score = min(1.0, overlap_count / max(1, len(query_tokens)))
                scored_candidates.append(
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "similarity_score": round(score, 2),
                        "snippet": (issue.body[:150] + "...") if len(issue.body) > 150 else issue.body,
                    }
                )

        scored_candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored_candidates[:limit]

    async def label_issue(
        self,
        repo: str,
        issue_number: int,
        labels: List[str],
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Apply one or more labels to an issue. Respects dry-run flag.

        Args:
            repo: Repository in 'owner/repo' format.
            issue_number: Target issue number.
            labels: List of label names to attach.
            dry_run: Override dry-run setting (defaults to agent instance setting).

        Returns:
            Status result indicating simulated or applied status.
        """
        effective_dry_run = self.dry_run if dry_run is None else dry_run
        return await self.client.label_issue(
            repo=repo,
            issue_number=issue_number,
            labels=labels,
            dry_run=effective_dry_run,
        )

    async def post_comment(
        self,
        repo: str,
        issue_number: int,
        body: str,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Post a comment reply to an issue. Respects dry-run flag.

        Args:
            repo: Repository in 'owner/repo' format.
            issue_number: Target issue number.
            body: Markdown formatted text for the comment.
            dry_run: Override dry-run setting.

        Returns:
            Status result with comment link or simulated confirmation.
        """
        effective_dry_run = self.dry_run if dry_run is None else dry_run
        return await self.client.post_comment(
            repo=repo,
            issue_number=issue_number,
            body=body,
            dry_run=effective_dry_run,
        )

    async def close_issue(
        self,
        repo: str,
        issue_number: int,
        reason: Optional[str] = "not_planned",
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Close an issue on GitHub. Respects dry-run flag.

        Args:
            repo: Repository in 'owner/repo' format.
            issue_number: Target issue number.
            reason: GitHub close reason ('completed' or 'not_planned').
            dry_run: Override dry-run setting.

        Returns:
            Status result with closure confirmation.
        """
        effective_dry_run = self.dry_run if dry_run is None else dry_run
        return await self.client.close_issue(
            repo=repo,
            issue_number=issue_number,
            reason=reason,
            dry_run=effective_dry_run,
        )


# Tool definitions formatted for LLM Function Calling APIs (Gemini, Claude, OpenAI)
TOOL_DEFINITIONS = [
    {
        "name": "list_issues",
        "description": "Fetch a list of issues from the given GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format (e.g. 'acme-org/web-platform')",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "State of issues to fetch (default: 'open')",
                },
                "since": {
                    "type": "string",
                    "description": "Optional ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SSZ) to filter recent issues",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of issues to retrieve (default: 30)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "get_issue_detail",
        "description": "Retrieve full details and recent comments for a specific issue.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "The unique issue number ID",
                },
            },
            "required": ["repo", "issue_number"],
        },
    },
    {
        "name": "search_similar_issues",
        "description": "Search open issues in the repository for similar keywords, errors, or symptoms to identify duplicates.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "query": {
                    "type": "string",
                    "description": "Keywords, stack trace snippets, or error messages to search for",
                },
                "exclude_number": {
                    "type": "integer",
                    "description": "The current issue number to exclude from matches",
                },
            },
            "required": ["repo", "query"],
        },
    },
    {
        "name": "label_issue",
        "description": "Apply triage labels to a GitHub issue. Will simulate action if dry_run is active.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "The issue number to label",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of label strings to attach",
                },
            },
            "required": ["repo", "issue_number", "labels"],
        },
    },
    {
        "name": "post_comment",
        "description": "Post a helpful comment or reproduction request to an issue. Simulated if dry_run is active.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "The issue number",
                },
                "body": {
                    "type": "string",
                    "description": "Markdown comment text to post",
                },
            },
            "required": ["repo", "issue_number", "body"],
        },
    },
    {
        "name": "close_issue",
        "description": "Close an issue (e.g. marked as duplicate or spam). Simulated if dry_run is active.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "The issue number to close",
                },
                "reason": {
                    "type": "string",
                    "enum": ["completed", "not_planned"],
                    "description": "GitHub closure reason",
                },
            },
            "required": ["repo", "issue_number"],
        },
    },
]
