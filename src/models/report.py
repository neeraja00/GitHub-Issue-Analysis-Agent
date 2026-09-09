"""Structured models for Final Triage Reports and Run Summaries."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from src.models.github import GitHubIssue
from src.models.classification import IssueClassification
from src.models.priority import PriorityScore
from src.models.deduplication import DeduplicationResult
from src.models.action import DraftedAction


class AppliedActionResult(BaseModel):
    """Result of applying a proposed action to GitHub."""
    issue_number: int
    labels_added: List[str] = Field(default_factory=list)
    comment_posted: bool = False
    comment_url: Optional[str] = None
    issue_closed: bool = False
    dry_run: bool = True
    status: str = "simulated"
    error: Optional[str] = None


class TriageIssueRecord(BaseModel):
    """Aggregated triage assessment for a single issue."""
    issue: GitHubIssue
    classification: Optional[IssueClassification] = None
    priority: Optional[PriorityScore] = None
    deduplication: Optional[DeduplicationResult] = None
    action: Optional[DraftedAction] = None
    execution: Optional[AppliedActionResult] = None
    processing_error: Optional[str] = None


class TriageSummaryStats(BaseModel):
    """Summary statistics across the triage run."""
    total_issues_analyzed: int = 0
    categories_breakdown: Dict[str, int] = Field(default_factory=dict)
    priorities_breakdown: Dict[str, int] = Field(default_factory=dict)
    duplicates_detected: int = 0
    recommended_closes: int = 0
    actions_drafted: int = 0
    total_tokens_used: int = 0
    execution_time_seconds: float = 0.0


class TriageRunReport(BaseModel):
    """Full structured report output of a triage execution."""
    run_id: str
    repository: str
    goal: str
    started_at: datetime
    completed_at: datetime
    dry_run: bool = True
    applied: bool = False
    llm_provider: str
    executive_summary: str
    actionable_takeaways: List[str] = Field(default_factory=list)
    stats: TriageSummaryStats
    issues: List[TriageIssueRecord] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
