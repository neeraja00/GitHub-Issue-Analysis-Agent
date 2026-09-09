"""Structured models for Issue Classification."""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class IssueCategory(str, Enum):
    """Permitted categories for classifying GitHub issues."""
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    QUESTION = "question"
    DOCUMENTATION = "documentation"
    DUPLICATE = "duplicate"
    SPAM = "spam"


class IssueClassification(BaseModel):
    """Classification result for a single GitHub issue."""
    issue_number: int = Field(description="The GitHub issue number")
    category: IssueCategory = Field(description="Primary category classification")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Concise rationale explaining the classification decision")
    tags: List[str] = Field(default_factory=list, description="Descriptive sub-tags (e.g. 'ui', 'performance', 'windows')")
    suggested_labels: List[str] = Field(default_factory=list, description="Suggested GitHub labels to apply")
