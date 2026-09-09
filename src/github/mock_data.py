"""Deterministic mock fixture repository data for offline development and testing."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List
from src.models.github import GitHubComment, GitHubIssue, RepositoryMetadata

NOW = datetime.now(timezone.utc)

MOCK_REPO_METADATA = RepositoryMetadata(
    owner="acme-org",
    repo="web-platform",
    full_name="acme-org/web-platform",
    description="Next-generation web framework and developer platform",
    open_issues_count=8,
    stargazers_count=1420,
    default_branch="main",
    html_url="https://github.com/acme-org/web-platform",
)

MOCK_ISSUES: List[GitHubIssue] = [
    GitHubIssue(
        number=101,
        title="Crash on startup: AccessViolationException on Windows 11",
        body=(
            "### Problem Description\n"
            "When launching the application on Windows 11 23H2 with antivirus enabled, "
            "the app crashes instantly before rendering the main window.\n\n"
            "### Stack Trace\n"
            "```\n"
            "Fatal error: AccessViolationException at 0x7FFF89A2310 in native_core.dll\n"
            "   at CoreEngine.Initialize(ConfigOptions options)\n"
            "   at MainApp.Bootstrap()\n"
            "```\n"
            "### Environment\n"
            "- OS: Windows 11 Build 22631\n"
            "- App Version: 2.4.0\n"
        ),
        state="open",
        author="dev_marcus",
        labels=["bug", "crash", "os:windows"],
        comments_count=4,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(hours=3),
        html_url="https://github.com/acme-org/web-platform/issues/101",
        comments=[
            GitHubComment(
                id=1001,
                author="sara_qa",
                body="Confirmed on three different Windows 11 machines. Completely blocking our test suite.",
                created_at=NOW - timedelta(days=1),
            ),
            GitHubComment(
                id=1002,
                author="alex_maintainer",
                body="Looking into the native_core DLL binding right now.",
                created_at=NOW - timedelta(hours=5),
            ),
        ],
    ),
    GitHubIssue(
        number=102,
        title="Feature Request: Add OLED True Dark theme support",
        body=(
            "Could we add a pure black (#000000) dark theme option for OLED screens? "
            "The current dark gray (#1a1a1a) is good, but pure black saves battery on mobile and laptops."
        ),
        state="open",
        author="night_owl99",
        labels=["enhancement", "ui"],
        comments_count=2,
        created_at=NOW - timedelta(days=15),
        updated_at=NOW - timedelta(days=10),
        html_url="https://github.com/acme-org/web-platform/issues/102",
    ),
    GitHubIssue(
        number=103,
        title="App fails to boot on Win11 - native_core.dll AccessViolation",
        body=(
            "Hello, after updating to 2.4.0 today, the app won't start on my Win 11 PC.\n"
            "Event viewer logs an AccessViolationException in native_core.dll at 0x7FFF89A2310. "
            "Seems like a critical regression."
        ),
        state="open",
        author="jordan_codes",
        labels=["bug"],
        comments_count=1,
        created_at=NOW - timedelta(hours=14),
        updated_at=NOW - timedelta(hours=14),
        html_url="https://github.com/acme-org/web-platform/issues/103",
    ),
    GitHubIssue(
        number=104,
        title="How do I configure custom webhook signature headers in config.yml?",
        body=(
            "I am setting up a custom webhook endpoint and need to verify the HMAC SHA256 header. "
            "Where in config.yml should I provide the secret token? I looked through docs but could not find an example."
        ),
        state="open",
        author="integrator_dan",
        labels=["question"],
        comments_count=0,
        created_at=NOW - timedelta(days=4),
        updated_at=NOW - timedelta(days=4),
        html_url="https://github.com/acme-org/web-platform/issues/104",
    ),
    GitHubIssue(
        number=105,
        title="Docs: 404 broken link in Step 3 of Quickstart Guide",
        body=(
            "In `docs/getting-started/quickstart.md`, the link pointing to "
            "`https://docs.acme-org.com/security/credentials` returns a 404 Not Found page. "
            "The new link seems to be `/security/authentication`."
        ),
        state="open",
        author="doc_fixer",
        labels=["documentation"],
        comments_count=0,
        created_at=NOW - timedelta(days=7),
        updated_at=NOW - timedelta(days=7),
        html_url="https://github.com/acme-org/web-platform/issues/105",
    ),
    GitHubIssue(
        number=106,
        title="Best Online Casino Bonuses 2026! Free Spins No Deposit!",
        body=(
            "Get 500 free spins today at our premium casino! Visit http://scam-casino-link.biz/bonus "
            "and sign up with code BONUS2026. Instant payout with Bitcoin, Ethereum and USDT!"
        ),
        state="open",
        author="promo_bot_91",
        labels=[],
        comments_count=0,
        created_at=NOW - timedelta(hours=2),
        updated_at=NOW - timedelta(hours=2),
        html_url="https://github.com/acme-org/web-platform/issues/106",
    ),
    GitHubIssue(
        number=107,
        title="Something broke and it stopped working",
        body=(
            "It doesn't work anymore. Please fix it immediately."
        ),
        state="open",
        author="frustrated_user",
        labels=["bug"],
        comments_count=0,
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
        html_url="https://github.com/acme-org/web-platform/issues/107",
    ),
    GitHubIssue(
        number=108,
        title="High memory consumption / leak when importing large CSV (>100MB)",
        body=(
            "When importing a CSV dataset of roughly 120MB, the memory usage spikes from 150MB to 2.8GB "
            "and does not get garbage collected after the import completes. "
            "Repeated imports eventually result in an OutOfMemory crash."
        ),
        state="open",
        author="big_data_dave",
        labels=["bug", "performance"],
        comments_count=3,
        created_at=NOW - timedelta(days=6),
        updated_at=NOW - timedelta(days=2),
        html_url="https://github.com/acme-org/web-platform/issues/108",
    ),
]


def get_mock_repository(repo_name: str = "acme-org/web-platform") -> RepositoryMetadata:
    """Return mock repository metadata."""
    return MOCK_REPO_METADATA


def get_mock_issues(repo_name: str = "acme-org/web-platform", limit: int = 30) -> List[GitHubIssue]:
    """Return mock issues list."""
    return MOCK_ISSUES[:limit]


def get_mock_issue_detail(issue_number: int) -> GitHubIssue:
    """Return details for a specific mock issue."""
    for issue in MOCK_ISSUES:
        if issue.number == issue_number:
            return issue
    raise KeyError(f"Issue #{issue_number} not found in mock repository.")
