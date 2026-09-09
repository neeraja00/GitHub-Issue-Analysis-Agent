"""Deterministic Mock LLM Provider for offline development and testing."""

import re
import time
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel

from src.llm.provider import LLMProvider
from src.models.classification import IssueCategory, IssueClassification
from src.models.priority import PriorityFactors, PriorityLevel, PriorityScore
from src.models.deduplication import DeduplicationResult, DuplicateCandidate
from src.models.action import ActionType, DraftedAction

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(LLMProvider):
    """High-fidelity deterministic mock provider that simulates LLM reasoning."""

    provider_name: str = "mock"
    model_name: str = "mock-reasoning-engine"

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
    ) -> Tuple[T, Dict[str, Any]]:
        start_time = time.perf_counter()

        # Extract issue number from prompt if present
        issue_match = re.search(r"Issue\s*(?:Number:?\s*|:\s*)?#?(\d+)", prompt, re.IGNORECASE)
        issue_number = int(issue_match.group(1)) if issue_match else 101

        # Extract target issue section to avoid matching instructions, system prompts, or few-shot examples
        target_section = prompt
        for marker in ("### Target Issue", "### Issue Context", "### Target Issue to Score", "### Target Issue to Classify"):
            if marker in prompt:
                target_section = prompt.split(marker)[-1]
                break
        target_lower = target_section.lower()

        prompt_lower = target_lower
        result: Any = None

        if response_model == IssueClassification:
            if "casino" in prompt_lower or "bonus" in prompt_lower or "free spins" in prompt_lower:
                result = IssueClassification(
                    issue_number=issue_number,
                    category=IssueCategory.SPAM,
                    confidence=0.99,
                    reasoning="Unsolicited gambling and cryptocurrency promotion containing spam links.",
                    tags=["spam", "casino"],
                    suggested_labels=["spam"],
                )
            elif "dark theme" in prompt_lower or "feature request" in prompt_lower or "oled" in prompt_lower:
                result = IssueClassification(
                    issue_number=issue_number,
                    category=IssueCategory.FEATURE_REQUEST,
                    confidence=0.96,
                    reasoning="User proposes an enhancement to support true dark OLED themes.",
                    tags=["ui", "theme", "enhancement"],
                    suggested_labels=["enhancement", "ui"],
                )
            elif "404" in prompt_lower or "docs" in prompt_lower or "quickstart" in prompt_lower:
                result = IssueClassification(
                    issue_number=issue_number,
                    category=IssueCategory.DOCUMENTATION,
                    confidence=0.94,
                    reasoning="Report of broken hyperlink in documentation quickstart guide.",
                    tags=["documentation", "links"],
                    suggested_labels=["documentation", "good-first-issue"],
                )
            elif "how do i" in prompt_lower or "question" in prompt_lower or "webhook signature" in prompt_lower:
                result = IssueClassification(
                    issue_number=issue_number,
                    category=IssueCategory.QUESTION,
                    confidence=0.92,
                    reasoning="User asking how to configure custom webhook secret in config.yml.",
                    tags=["configuration", "webhook"],
                    suggested_labels=["question"],
                )
            elif issue_number == 103 or ("native_core.dll" in prompt_lower and issue_number != 101):
                result = IssueClassification(
                    issue_number=issue_number,
                    category=IssueCategory.DUPLICATE,
                    confidence=0.91,
                    reasoning="Duplicate crash report sharing the exact same native_core.dll AccessViolationException.",
                    tags=["crash", "windows", "duplicate"],
                    suggested_labels=["bug", "duplicate"],
                )
            else:
                result = IssueClassification(
                    issue_number=issue_number,
                    category=IssueCategory.BUG,
                    confidence=0.95,
                    reasoning="Report indicates software error or crash during standard execution.",
                    tags=["bug", "core"],
                    suggested_labels=["bug"],
                )

        elif response_model == PriorityScore:
            if "accessviolation" in prompt_lower or "crash" in prompt_lower:
                result = PriorityScore(
                    issue_number=issue_number,
                    level=PriorityLevel.CRITICAL,
                    numerical_score=94,
                    factors=PriorityFactors(
                        content_severity=0.98,
                        age_factor=0.90,
                        activity_factor=0.85,
                        label_modifier=0.95,
                    ),
                    justification="Fatal startup crash with native exception blocking all users on Windows 11.",
                    sla_urgency="immediate",
                )
            elif "memory" in prompt_lower or "leak" in prompt_lower or "oom" in prompt_lower:
                result = PriorityScore(
                    issue_number=issue_number,
                    level=PriorityLevel.HIGH,
                    numerical_score=78,
                    factors=PriorityFactors(
                        content_severity=0.80,
                        age_factor=0.75,
                        activity_factor=0.70,
                        label_modifier=0.70,
                    ),
                    justification="Unbounded memory consumption leading to OOM crash on large dataset imports.",
                    sla_urgency="within 48 hours",
                )
            elif "spam" in prompt_lower or "casino" in prompt_lower:
                result = PriorityScore(
                    issue_number=issue_number,
                    level=PriorityLevel.LOW,
                    numerical_score=5,
                    factors=PriorityFactors(
                        content_severity=0.05,
                        age_factor=0.10,
                        activity_factor=0.0,
                        label_modifier=0.0,
                    ),
                    justification="Commercial spam, zero product impact.",
                    sla_urgency="backlog",
                )
            elif "oled" in prompt_lower or "feature" in prompt_lower:
                result = PriorityScore(
                    issue_number=issue_number,
                    level=PriorityLevel.MEDIUM,
                    numerical_score=52,
                    factors=PriorityFactors(
                        content_severity=0.45,
                        age_factor=0.50,
                        activity_factor=0.60,
                        label_modifier=0.50,
                    ),
                    justification="Valuable user-requested aesthetic enhancement with positive engagement.",
                    sla_urgency="next sprint",
                )
            else:
                result = PriorityScore(
                    issue_number=issue_number,
                    level=PriorityLevel.LOW,
                    numerical_score=30,
                    factors=PriorityFactors(
                        content_severity=0.30,
                        age_factor=0.30,
                        activity_factor=0.20,
                        label_modifier=0.30,
                    ),
                    justification="Routine question or documentation update with low disruption.",
                    sla_urgency="next sprint",
                )

        elif response_model == DeduplicationResult:
            if issue_number == 103:
                match = DuplicateCandidate(
                    target_issue_number=101,
                    similarity_score=0.92,
                    matching_aspects=[
                        "Identical AccessViolationException at 0x7FFF89A2310",
                        "Same DLL failure: native_core.dll",
                        "Same OS environment: Windows 11",
                    ],
                    rationale="Issue #103 reports the exact same crash address and DLL regression as Issue #101.",
                )
                result = DeduplicationResult(
                    issue_number=issue_number,
                    is_duplicate=True,
                    confidence=0.92,
                    best_match=match,
                    all_candidates=[match],
                )
            else:
                result = DeduplicationResult(
                    issue_number=issue_number,
                    is_duplicate=False,
                    confidence=0.90,
                    best_match=None,
                    all_candidates=[],
                )

        elif response_model == DraftedAction:
            if issue_number == 106 or "category: spam" in prompt_lower:
                result = DraftedAction(
                    issue_number=issue_number,
                    action_type=ActionType.CLOSE_AS_SPAM,
                    headline="Close as spam and lock discussion",
                    reasoning="Unsolicited commercial spam and link farming.",
                    draft_comment="Closing as spam. Unsolicited promotions violate repository guidelines.",
                    labels_to_add=["spam"],
                    should_close=True,
                    close_reason="not_planned",
                )
            elif issue_number == 103 or "duplicate of issue #101" in prompt_lower:
                result = DraftedAction(
                    issue_number=issue_number,
                    action_type=ActionType.CLOSE_AS_DUPLICATE,
                    headline="Close as duplicate of #101",
                    reasoning="Shares identical native_core.dll crash traceback on Windows 11.",
                    draft_comment=(
                        f"Thanks for reporting @{issue_match.group(0) if issue_match else 'contributor'}! "
                        "This appears to be a duplicate of #101, which is actively being investigated. "
                        "Closing this in favor of consolidating updates on #101."
                    ),
                    labels_to_add=["duplicate"],
                    should_close=True,
                    close_reason="not_planned",
                )
            elif issue_number == 107 or "something broke" in prompt_lower:
                result = DraftedAction(
                    issue_number=issue_number,
                    action_type=ActionType.REQUEST_REPRODUCTION,
                    headline="Request reproduction steps, logs, and system details",
                    reasoning="Issue contains zero diagnostic context or actionable reproduction information.",
                    draft_comment=(
                        "Hello! Thank you for reporting. Could you please provide: "
                        "1) Steps to reproduce the issue, 2) Operating system version, and "
                        "3) Any console or crash logs from the application? "
                        "This will help us investigate."
                    ),
                    labels_to_add=["needs-repro", "waiting-for-response"],
                    should_close=False,
                )
            elif "crash on startup" in prompt_lower or issue_number == 101:
                result = DraftedAction(
                    issue_number=issue_number,
                    action_type=ActionType.ESCALATE_CRITICAL,
                    headline="Escalate critical startup crash to core maintainers",
                    reasoning="High impact regression affecting multiple Windows 11 users.",
                    draft_comment=(
                        "Thank you for the detailed traceback! We have reproduced the `native_core.dll` "
                        "fault on Windows 11 and escalated this to P0. A hotfix build will be published shortly."
                    ),
                    labels_to_add=["priority:critical", "in-progress"],
                    should_close=False,
                )
            elif "oled" in prompt_lower or issue_number == 102:
                result = DraftedAction(
                    issue_number=issue_number,
                    action_type=ActionType.LABEL_AND_TRIAGE,
                    headline="Accept feature proposal and queue for next UI sprint",
                    reasoning="Valid UI improvement with clear design proposal.",
                    draft_comment=(
                        "Thanks for the suggestion! True AMOLED black theme is a great enhancement for mobile OLEDs. "
                        "Marking this for discussion in our next UI planning cycle."
                    ),
                    labels_to_add=["enhancement", "ui"],
                    should_close=False,
                )
            elif "404" in prompt_lower or issue_number == 105:
                result = DraftedAction(
                    issue_number=issue_number,
                    action_type=ActionType.INVITE_CONTRIBUTION,
                    headline="Mark as good-first-issue for documentation fix",
                    reasoning="Straightforward 404 documentation link update ideal for community contributors.",
                    draft_comment=(
                        "Great catch! Would you be interested in opening a quick pull request to update "
                        "the link from `/security/credentials` to `/security/authentication`?"
                    ),
                    labels_to_add=["documentation", "good-first-issue"],
                    should_close=False,
                )
            else:
                result = DraftedAction(
                    issue_number=issue_number,
                    action_type=ActionType.LABEL_AND_TRIAGE,
                    headline="Apply standard triage labels",
                    reasoning="Issue triaged and labeled for maintainer review.",
                    draft_comment=None,
                    labels_to_add=["triaged"],
                    should_close=False,
                )

        latency_ms = int((time.perf_counter() - start_time) * 1000) + 15
        telemetry = {
            "model": self.model_name,
            "provider": self.provider_name,
            "tokens_prompt": 380,
            "tokens_completion": 140,
            "latency_ms": latency_ms,
        }

        return result, telemetry

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        start_time = time.perf_counter()
        response_text = (
            "### Executive Summary\n"
            "Autonomous triage analyzed the open issues repository. "
            "A critical regression (#101) was detected along with duplicate reports (#103) "
            "and an unmoderated spam item (#106). Overall health is stable with clear next steps."
        )
        latency_ms = int((time.perf_counter() - start_time) * 1000) + 12
        telemetry = {
            "model": self.model_name,
            "provider": self.provider_name,
            "tokens_prompt": 250,
            "tokens_completion": 80,
            "latency_ms": latency_ms,
        }
        return response_text, telemetry
