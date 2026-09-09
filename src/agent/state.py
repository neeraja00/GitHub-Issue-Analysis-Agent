"""Agent Session State and Context Compression."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.models import (
    GitHubIssue,
    RepositoryMetadata,
    IssueClassification,
    PriorityScore,
    DeduplicationResult,
    DraftedAction,
    AppliedActionResult,
)


class SessionState(BaseModel):
    """Encapsulates the full state of an agent triage session."""

    run_id: str
    repository: str
    goal: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    dry_run: bool = True
    applied: bool = False
    current_step: str = "initialized"
    status: str = "running"  # running, completed, failed

    # Repository context
    repo_metadata: Optional[RepositoryMetadata] = None

    # Step records keyed by issue_number
    raw_issues: Dict[int, GitHubIssue] = Field(default_factory=dict)
    classifications: Dict[int, IssueClassification] = Field(default_factory=dict)
    priorities: Dict[int, PriorityScore] = Field(default_factory=dict)
    deduplications: Dict[int, DeduplicationResult] = Field(default_factory=dict)
    actions: Dict[int, DraftedAction] = Field(default_factory=dict)
    execution_results: Dict[int, AppliedActionResult] = Field(default_factory=dict)

    # Errors isolated per issue or general
    isolated_errors: Dict[int, str] = Field(default_factory=dict)
    general_errors: List[str] = Field(default_factory=list)

    # Telemetry and metrics
    total_tokens_used: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0

    def add_telemetry(self, tokens: int = 0, is_llm: bool = False, is_tool: bool = False) -> None:
        """Accumulate token and call statistics."""
        self.total_tokens_used += tokens
        if is_llm:
            self.total_llm_calls += 1
        if is_tool:
            self.total_tool_calls += 1

    def record_issue_error(self, issue_number: int, error_msg: str) -> None:
        """Record an isolated error for a specific issue without stopping the run."""
        self.isolated_errors[issue_number] = error_msg

    def get_compressed_context(self, max_recent: int = 5) -> str:
        """Generate a compact summary of issues processed so far to fit inside LLM context limits."""
        if not self.classifications:
            return "No issues triaged yet."

        lines = ["### Previously Triaged Issues:"]
        for num, cls in list(self.classifications.items())[:max_recent]:
            prio = self.priorities.get(num)
            prio_str = prio.level.value.upper() if prio else "UNSCORED"
            dup = self.deduplications.get(num)
            dup_str = f" [DUP of #{dup.best_match.target_issue_number}]" if (dup and dup.is_duplicate and dup.best_match) else ""
            issue = self.raw_issues.get(num)
            title = (issue.title[:40] + "...") if (issue and len(issue.title) > 40) else (issue.title if issue else "")
            lines.append(f"- #{num} ({cls.category.value.upper()}, {prio_str}{dup_str}): {title}")

        if len(self.classifications) > max_recent:
            remaining = len(self.classifications) - max_recent
            lines.append(f"... and {remaining} additional issues triaged.")

        return "\n".join(lines)
