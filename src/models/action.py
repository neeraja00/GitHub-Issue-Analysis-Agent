"""Structured models for Suggested Actions and Drafted Responses."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Categorized response or remediation action."""
    REQUEST_REPRODUCTION = "request_reproduction"
    CLOSE_AS_DUPLICATE = "close_as_duplicate"
    CLOSE_AS_SPAM = "close_as_spam"
    LABEL_AND_TRIAGE = "label_and_triage"
    ANSWER_QUESTION = "answer_question"
    ESCALATE_CRITICAL = "escalate_critical"
    INVITE_CONTRIBUTION = "invite_contribution"


class DraftedAction(BaseModel):
    """Action plan and drafted response for an issue."""
    issue_number: int = Field(description="The issue number")
    action_type: ActionType = Field(description="Primary action category")
    headline: str = Field(description="Short summary of recommended action (e.g. 'Ask for reproduction steps on Windows')")
    reasoning: str = Field(description="Why this specific action is recommended")
    draft_comment: Optional[str] = Field(
        default=None,
        description="Polite, professional markdown comment drafted for the issue author"
    )
    labels_to_add: List[str] = Field(default_factory=list, description="Labels proposed to be added")
    labels_to_remove: List[str] = Field(default_factory=list, description="Labels proposed to be removed")
    should_close: bool = Field(default=False, description="Whether the agent recommends closing this issue")
    close_reason: Optional[str] = Field(default=None, description="GitHub close reason ('completed' or 'not_planned')")
