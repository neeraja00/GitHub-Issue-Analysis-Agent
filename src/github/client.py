"""GitHub REST API Client with rate limiting, exponential backoff, and dry-run safety."""

import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.config import settings
from src.github.mock_data import (
    get_mock_issues,
    get_mock_issue_detail,
    get_mock_repository,
)
from src.models.github import (
    GitHubComment,
    GitHubIssue,
    GitHubLabel,
    GitHubUser,
    RepositoryMetadata,
)

logger = logging.getLogger("github_client")


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""
    pass


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub rate limits are exhausted."""
    def __init__(self, reset_timestamp: int, message: str):
        self.reset_timestamp = reset_timestamp
        super().__init__(message)


class GitHubClient:
    """Asynchronous client interacting with the GitHub REST API."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        force_mock: bool = False,
    ):
        self.token = token or settings.github_token
        self.base_url = (base_url or settings.github_api_base).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.force_mock = force_mock

        self.rate_limit_remaining: Optional[int] = None
        self.rate_limit_reset: Optional[int] = None
        self.rate_limit_limit: Optional[int] = None

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Issue-Analysis-Agent/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _update_rate_limits(self, response: httpx.Response) -> None:
        """Extract and store GitHub rate limit headers."""
        if "x-ratelimit-remaining" in response.headers:
            try:
                self.rate_limit_remaining = int(response.headers["x-ratelimit-remaining"])
                self.rate_limit_limit = int(response.headers.get("x-ratelimit-limit", 60))
                self.rate_limit_reset = int(response.headers.get("x-ratelimit-reset", 0))
                logger.debug(
                    f"Rate limits: {self.rate_limit_remaining}/{self.rate_limit_limit} remaining "
                    f"(reset: {self.rate_limit_reset})"
                )
            except ValueError:
                pass

    def is_mock_target(self, repo: str) -> bool:
        """Determines if a target repo should use mock fixtures."""
        clean = repo.strip().lower()
        return (
            self.force_mock
            or clean.startswith("mock/")
            or clean in ("acme-org/web-platform", "mock/demo-repo", "demo/repo")
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Execute HTTP request with rate-limit checking and exponential backoff."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._get_headers()

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_data,
                    )

                self._update_rate_limits(response)

                # Rate Limit Handling (HTTP 403 or 429)
                if response.status_code in (403, 429) and (
                    "rate limit exceeded" in response.text.lower()
                    or self.rate_limit_remaining == 0
                ):
                    reset_epoch = self.rate_limit_reset or (int(time.time()) + 60)
                    wait_seconds = max(1, reset_epoch - int(time.time()))
                    logger.warning(
                        f"GitHub Rate limit reached. Reset in {wait_seconds}s. Attempt {attempt}/{self.max_retries}"
                    )
                    if attempt < self.max_retries and wait_seconds <= 15:
                        await asyncio.sleep(wait_seconds + 1)
                        continue
                    raise GitHubRateLimitError(
                        reset_timestamp=reset_epoch,
                        message=f"GitHub rate limit exceeded. Resets at {datetime.fromtimestamp(reset_epoch, tz=timezone.utc).isoformat()}",
                    )

                # Retriable server errors (5xx)
                if response.status_code >= 500:
                    if attempt < self.max_retries:
                        backoff = (2 ** attempt) + random.uniform(0.1, 0.9)
                        logger.warning(f"Server error {response.status_code}. Retrying in {backoff:.2f}s...")
                        await asyncio.sleep(backoff)
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                return response

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt < self.max_retries:
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.9)
                    logger.warning(f"Network error: {exc}. Retrying in {backoff:.2f}s...")
                    await asyncio.sleep(backoff)
                else:
                    raise GitHubAPIError(f"Network error after {self.max_retries} attempts: {exc}") from exc

        raise GitHubAPIError(f"Request to {url} failed after {self.max_retries} attempts.")

    async def get_repository_metadata(self, repo: str) -> RepositoryMetadata:
        """Fetch metadata for a GitHub repository."""
        if self.is_mock_target(repo):
            return get_mock_repository(repo)

        resp = await self._request("GET", f"repos/{repo}")
        data = resp.json()
        return RepositoryMetadata(
            owner=data["owner"]["login"],
            repo=data["name"],
            full_name=data["full_name"],
            description=data.get("description"),
            open_issues_count=data.get("open_issues_count", 0),
            stargazers_count=data.get("stargazers_count", 0),
            default_branch=data.get("default_branch", "main"),
            html_url=data.get("html_url", f"https://github.com/{repo}"),
        )

    async def list_issues(
        self,
        repo: str,
        state: str = "open",
        since: Optional[datetime] = None,
        labels: Optional[List[str]] = None,
        limit: int = 30,
    ) -> List[GitHubIssue]:
        """Fetch repository issues, filtering out pull requests."""
        if self.is_mock_target(repo):
            return get_mock_issues(repo, limit=limit)

        params: Dict[str, Any] = {
            "state": state,
            "per_page": min(limit, 100),
            "sort": "updated",
            "direction": "desc",
        }
        if since:
            params["since"] = since.isoformat()
        if labels:
            params["labels"] = ",".join(labels)

        resp = await self._request("GET", f"repos/{repo}/issues", params=params)
        raw_items = resp.json()

        issues: List[GitHubIssue] = []
        for item in raw_items:
            # GitHub API returns pull requests alongside issues; filter them out
            if "pull_request" in item and item["pull_request"]:
                continue

            parsed_labels = [
                lbl["name"] if isinstance(lbl, dict) else str(lbl)
                for lbl in item.get("labels", [])
            ]

            created_at = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            updated_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
            closed_at = None
            if item.get("closed_at"):
                closed_at = datetime.fromisoformat(item["closed_at"].replace("Z", "+00:00"))

            issues.append(
                GitHubIssue(
                    number=item["number"],
                    title=item.get("title", ""),
                    body=item.get("body") or "",
                    state=item.get("state", "open"),
                    author=item.get("user", {}).get("login", "unknown"),
                    labels=parsed_labels,
                    comments_count=item.get("comments", 0),
                    created_at=created_at,
                    updated_at=updated_at,
                    closed_at=closed_at,
                    html_url=item.get("html_url", ""),
                    is_pull_request=False,
                )
            )
            if len(issues) >= limit:
                break

        return issues

    async def get_issue_detail(self, repo: str, issue_number: int) -> GitHubIssue:
        """Fetch full issue details including latest comments."""
        if self.is_mock_target(repo):
            return get_mock_issue_detail(issue_number)

        resp = await self._request("GET", f"repos/{repo}/issues/{issue_number}")
        item = resp.json()

        comments: List[GitHubComment] = []
        if item.get("comments", 0) > 0:
            try:
                comments_resp = await self._request(
                    "GET", f"repos/{repo}/issues/{issue_number}/comments", params={"per_page": 20}
                )
                for c in comments_resp.json():
                    c_created = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                    c_updated = (
                        datetime.fromisoformat(c["updated_at"].replace("Z", "+00:00"))
                        if c.get("updated_at")
                        else None
                    )
                    comments.append(
                        GitHubComment(
                            id=c["id"],
                            author=c.get("user", {}).get("login", "unknown"),
                            body=c.get("body", ""),
                            created_at=c_created,
                            updated_at=c_updated,
                        )
                    )
            except Exception as e:
                logger.warning(f"Could not fetch comments for issue #{issue_number}: {e}")

        created_at = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
        closed_at = (
            datetime.fromisoformat(item["closed_at"].replace("Z", "+00:00"))
            if item.get("closed_at")
            else None
        )

        return GitHubIssue(
            number=item["number"],
            title=item.get("title", ""),
            body=item.get("body") or "",
            state=item.get("state", "open"),
            author=item.get("user", {}).get("login", "unknown"),
            labels=[lbl["name"] if isinstance(lbl, dict) else str(lbl) for lbl in item.get("labels", [])],
            comments_count=item.get("comments", 0),
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            html_url=item.get("html_url", ""),
            is_pull_request=False,
            comments=comments,
        )

    async def label_issue(
        self,
        repo: str,
        issue_number: int,
        labels: List[str],
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Add labels to an issue. Guaranteed no network modification if dry_run is True."""
        if dry_run or self.is_mock_target(repo):
            logger.info(f"[DRY-RUN] Would add labels {labels} to {repo}#{issue_number}")
            return {
                "dry_run": True,
                "action": "label_issue",
                "issue_number": issue_number,
                "labels_added": labels,
                "status": "simulated",
            }

        resp = await self._request(
            "POST",
            f"repos/{repo}/issues/{issue_number}/labels",
            json_data={"labels": labels},
        )
        return {
            "dry_run": False,
            "action": "label_issue",
            "issue_number": issue_number,
            "labels_added": labels,
            "status": "applied",
            "response": resp.json(),
        }

    async def post_comment(
        self,
        repo: str,
        issue_number: int,
        body: str,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Post a comment to an issue. Guaranteed no network modification if dry_run is True."""
        if dry_run or self.is_mock_target(repo):
            logger.info(f"[DRY-RUN] Would post comment on {repo}#{issue_number}:\n{body}")
            return {
                "dry_run": True,
                "action": "post_comment",
                "issue_number": issue_number,
                "comment_body": body,
                "status": "simulated",
                "html_url": f"https://github.com/{repo}/issues/{issue_number}#simulated-comment",
            }

        resp = await self._request(
            "POST",
            f"repos/{repo}/issues/{issue_number}/comments",
            json_data={"body": body},
        )
        data = resp.json()
        return {
            "dry_run": False,
            "action": "post_comment",
            "issue_number": issue_number,
            "comment_id": data.get("id"),
            "html_url": data.get("html_url"),
            "status": "applied",
        }

    async def close_issue(
        self,
        repo: str,
        issue_number: int,
        reason: Optional[str] = "not_planned",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Close an issue. Guaranteed no network modification if dry_run is True."""
        if dry_run or self.is_mock_target(repo):
            logger.info(f"[DRY-RUN] Would close {repo}#{issue_number} with reason '{reason}'")
            return {
                "dry_run": True,
                "action": "close_issue",
                "issue_number": issue_number,
                "reason": reason,
                "status": "simulated",
            }

        payload: Dict[str, Any] = {"state": "closed"}
        if reason:
            payload["state_reason"] = reason

        resp = await self._request(
            "PATCH",
            f"repos/{repo}/issues/{issue_number}",
            json_data=payload,
        )
        return {
            "dry_run": False,
            "action": "close_issue",
            "issue_number": issue_number,
            "status": "applied",
            "response": resp.json(),
        }
