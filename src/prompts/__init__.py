"""Prompts package."""

from src.prompts.system import SYSTEM_TRIAGE_PROMPT
from src.prompts.classify import build_classify_prompt
from src.prompts.prioritize import build_prioritize_prompt
from src.prompts.deduplicate import build_deduplicate_prompt
from src.prompts.draft_action import build_draft_action_prompt

__all__ = [
    "SYSTEM_TRIAGE_PROMPT",
    "build_classify_prompt",
    "build_prioritize_prompt",
    "build_deduplicate_prompt",
    "build_draft_action_prompt",
]
