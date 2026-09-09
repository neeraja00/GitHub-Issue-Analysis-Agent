"""Structured models for Issue Deduplication."""

from typing import List, Optional
from pydantic import BaseModel, Field


class DuplicateCandidate(BaseModel):
    """Potential duplicate issue candidate with matching details."""
    target_issue_number: int = Field(description="Issue number that this is suspected to duplicate")
    similarity_score: float = Field(ge=0.0, le=1.0, description="Semantic or textual similarity score (0.0 - 1.0)")
    matching_aspects: List[str] = Field(
        default_factory=list,
        description="Overlapping factors (e.g. 'same stacktrace', 'identical error message', 'same UI component')"
    )
    rationale: str = Field(description="Explanation of why these two issues refer to the same root problem")


class DeduplicationResult(BaseModel):
    """Result of duplicate analysis for a specific issue."""
    issue_number: int = Field(description="Issue being evaluated")
    is_duplicate: bool = Field(default=False, description="Whether the issue is confirmed or highly suspected duplicate")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence of duplicate assessment")
    best_match: Optional[DuplicateCandidate] = Field(default=None, description="The most prominent duplicate match, if any")
    all_candidates: List[DuplicateCandidate] = Field(default_factory=list, description="All candidates exceeding minimum similarity")
