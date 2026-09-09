"""Structured models for Issue Priority Scoring."""

from enum import Enum
from pydantic import BaseModel, Field


class PriorityLevel(str, Enum):
    """Priority classifications for triage."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PriorityFactors(BaseModel):
    """Component factors contributing to the final priority score."""
    content_severity: float = Field(ge=0.0, le=1.0, description="Severity based on content: crash, data-loss, security")
    age_factor: float = Field(ge=0.0, le=1.0, description="Impact of issue age (fresh blocker vs stale backlog)")
    activity_factor: float = Field(ge=0.0, le=1.0, description="User reaction and comment momentum")
    label_modifier: float = Field(ge=0.0, le=1.0, description="Influence of existing high-priority labels")


class PriorityScore(BaseModel):
    """Detailed priority assessment for an issue."""
    issue_number: int = Field(description="The GitHub issue number")
    level: PriorityLevel = Field(description="Categorical priority level (critical, high, medium, low)")
    numerical_score: int = Field(ge=0, le=100, description="Weighted composite score between 0 and 100")
    factors: PriorityFactors = Field(description="Breakdown of factors used to calculate score")
    justification: str = Field(description="Detailed justification for the assigned priority level")
    sla_urgency: str = Field(
        default="next sprint",
        description="Suggested turnaround window (e.g. 'immediate', 'within 24h', 'within 48h', 'next sprint', 'backlog')"
    )
