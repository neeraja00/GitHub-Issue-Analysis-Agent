"""Multi-step Agent Orchestrator for GitHub Issue Triage."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.agent.logger import StructuredRunLogger
from src.agent.reporter import ReportGenerator
from src.agent.state import SessionState
from src.config import settings
from src.github.client import GitHubClient
from src.github.tools import GitHubTools
from src.llm import get_llm_provider
from src.llm.provider import LLMProvider
from src.models import (
    ActionType,
    AppliedActionResult,
    DeduplicationResult,
    DraftedAction,
    GitHubIssue,
    IssueCategory,
    IssueClassification,
    PriorityLevel,
    PriorityScore,
    TriageRunReport,
)
from src.prompts import (
    build_classify_prompt,
    build_deduplicate_prompt,
    build_draft_action_prompt,
    build_prioritize_prompt,
)

logger = logging.getLogger("agent_pipeline")


class TriagePipeline:
    """End-to-end multi-step agent orchestrator executing the triage pipeline."""

    def __init__(
        self,
        repo: str,
        goal: str = "Triage open issues",
        dry_run: bool = True,
        apply_actions: bool = False,
        limit: int = 30,
        provider: Optional[LLMProvider] = None,
        github_client: Optional[GitHubClient] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.repo = repo.strip()
        self.goal = goal.strip()
        # Explicit apply flag overrides dry_run
        self.dry_run = False if apply_actions else dry_run
        self.apply_actions = apply_actions
        self.limit = limit

        self.run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.run_logger = StructuredRunLogger(run_id=self.run_id)
        self.state = SessionState(
            run_id=self.run_id,
            repository=self.repo,
            goal=self.goal,
            dry_run=self.dry_run,
            applied=self.apply_actions,
        )

        self.llm = provider or get_llm_provider()
        self.client = github_client or GitHubClient(force_mock=(repo.startswith("mock/") or settings.default_llm_provider == "mock"))
        self.tools = GitHubTools(client=self.client, dry_run=self.dry_run)
        self.reporter = ReportGenerator()
        self.progress_callback = progress_callback

    def _notify_progress(self, step: str, message: str, percent: int, current_issue: Optional[int] = None) -> None:
        """Emit real-time progress update for CLI spinners or Web SSE."""
        payload = {
            "run_id": self.run_id,
            "step": step,
            "message": message,
            "percent": percent,
            "current_issue": current_issue,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.progress_callback:
            try:
                self.progress_callback(payload)
            except Exception as e:
                logger.debug(f"Progress callback error: {e}")

    async def execute(self) -> TriageRunReport:
        """Run the full multi-step triage workflow."""
        self.run_logger.log_event(
            "start",
            "initialize",
            f"Starting triage run for repository '{self.repo}' (dry_run={self.dry_run})",
            {"goal": self.goal, "limit": self.limit, "llm": self.llm.provider_name},
        )
        self._notify_progress("initialize", "Initializing repository metadata...", 5)

        try:
            # Step 1: Repository Metadata
            await self._step_init_repo()

            # Step 2: Fetch Issues
            await self._step_fetch_issues()

            if not self.state.raw_issues:
                self.run_logger.log_event("info", "fetch", "No open issues found to triage.")
                return await self._step_generate_reports()

            # Step 3: Classify Issues (isolated per-issue)
            await self._step_classify_issues()

            # Step 4: Prioritize Issues
            await self._step_prioritize_issues()

            # Step 5: Semantic Deduplication
            await self._step_deduplicate_issues()

            # Step 6: Draft Actions & Responses
            await self._step_draft_actions()

            # Step 7: Critique & Re-plan
            await self._step_critique_and_align()

            # Step 8: Apply Actions (if enabled)
            if self.apply_actions:
                await self._step_apply_actions()

            # Step 9: Final Report Generation
            report = await self._step_generate_reports()

            self.state.status = "completed"
            self.state.completed_at = datetime.now(timezone.utc)
            self.run_logger.log_event("finish", "complete", "Triage pipeline execution completed successfully.")
            self._notify_progress("complete", "Triage complete. Reports generated.", 100)
            return report

        except Exception as exc:
            self.state.status = "failed"
            self.run_logger.log_error("pipeline", f"Fatal pipeline error: {exc}", str(exc), recoverable=False)
            self._notify_progress("error", f"Pipeline failed: {exc}", 100)
            raise

    async def _step_init_repo(self) -> None:
        """Fetch repo metadata."""
        self.state.current_step = "metadata"
        try:
            meta = await self.client.get_repository_metadata(self.repo)
            self.state.repo_metadata = meta
            self.run_logger.log_event(
                "info", "metadata", f"Loaded metadata for {meta.full_name} ({meta.open_issues_count} open issues)"
            )
        except Exception as e:
            self.run_logger.log_error("metadata", "Could not fetch repository metadata", str(e), recoverable=True)

    async def _step_fetch_issues(self) -> None:
        """Fetch issues via GitHub tools."""
        self.state.current_step = "fetch"
        self._notify_progress("fetch", f"Fetching issues from {self.repo}...", 15)

        issues = await self.client.list_issues(self.repo, limit=self.limit)
        for issue in issues:
            self.state.raw_issues[issue.number] = issue

        self.state.add_telemetry(is_tool=True)
        self.run_logger.log_tool_call(
            step="fetch",
            tool_name="list_issues",
            arguments={"repo": self.repo, "limit": self.limit},
            result=f"Fetched {len(issues)} issues",
        )

    async def _step_classify_issues(self) -> None:
        """Classify each issue with per-issue error isolation."""
        self.state.current_step = "classify"
        total = len(self.state.raw_issues)
        self._notify_progress("classify", f"Classifying {total} issues...", 25)

        for idx, (number, issue) in enumerate(self.state.raw_issues.items(), start=1):
            pct = 25 + int((idx / total) * 15)
            self._notify_progress("classify", f"Classifying issue #{number}: {issue.title[:30]}...", pct, number)
            prompt = build_classify_prompt(issue.number, issue.title, issue.body, issue.labels)

            try:
                classification, telem = await self.llm.generate_structured(prompt, IssueClassification)
                self.state.classifications[number] = classification
                self.state.add_telemetry(tokens=telem.get("tokens_prompt", 0) + telem.get("tokens_completion", 0), is_llm=True)
                self.run_logger.log_llm_call(
                    step="classify",
                    model=telem.get("model", "unknown"),
                    task=f"classify #{number}",
                    tokens_prompt=telem.get("tokens_prompt", 0),
                    tokens_completion=telem.get("tokens_completion", 0),
                    latency_ms=telem.get("latency_ms", 0),
                    issue_number=number,
                )
                self.run_logger.log_decision(
                    step="classify",
                    issue_number=number,
                    decision_type="classification",
                    summary=classification.category.value,
                    reasoning=classification.reasoning,
                    confidence=classification.confidence,
                )
            except Exception as exc:
                self.run_logger.log_error("classify", f"Failed to classify issue #{number}", str(exc), issue_number=number)
                self.state.record_issue_error(number, f"Classification failed: {exc}")
                # Fallback classification to allow run to proceed
                self.state.classifications[number] = IssueClassification(
                    issue_number=number,
                    category=IssueCategory.BUG,
                    confidence=0.5,
                    reasoning=f"Fallback classification due to inference error: {exc}",
                )

    async def _step_prioritize_issues(self) -> None:
        """Assign priority scores and SLA categories."""
        self.state.current_step = "prioritize"
        total = len(self.state.raw_issues)
        now = datetime.now(timezone.utc)

        for idx, (number, issue) in enumerate(self.state.raw_issues.items(), start=1):
            pct = 40 + int((idx / total) * 15)
            self._notify_progress("prioritize", f"Scoring priority for #{number}...", pct, number)

            cls = self.state.classifications.get(number)
            cat_name = cls.category.value if cls else "bug"
            age_days = (now - issue.created_at).total_seconds() / 86400.0

            prompt = build_prioritize_prompt(
                issue_number=number,
                title=issue.title,
                body=issue.body,
                labels=issue.labels,
                comments_count=issue.comments_count,
                age_days=age_days,
                classification_category=cat_name,
            )

            try:
                priority, telem = await self.llm.generate_structured(prompt, PriorityScore)
                self.state.priorities[number] = priority
                self.state.add_telemetry(tokens=telem.get("tokens_prompt", 0) + telem.get("tokens_completion", 0), is_llm=True)
                self.run_logger.log_llm_call(
                    step="prioritize",
                    model=telem.get("model", "unknown"),
                    task=f"prioritize #{number}",
                    tokens_prompt=telem.get("tokens_prompt", 0),
                    tokens_completion=telem.get("tokens_completion", 0),
                    latency_ms=telem.get("latency_ms", 0),
                    issue_number=number,
                )
                self.run_logger.log_decision(
                    step="prioritize",
                    issue_number=number,
                    decision_type="priority",
                    summary=f"{priority.level.value.upper()} ({priority.numerical_score}/100)",
                    reasoning=priority.justification,
                )
            except Exception as exc:
                self.run_logger.log_error("prioritize", f"Failed to score priority for #{number}", str(exc), issue_number=number)
                self.state.record_issue_error(number, f"Priority scoring failed: {exc}")
                self.state.priorities[number] = PriorityScore(
                    issue_number=number,
                    level=PriorityLevel.MEDIUM,
                    numerical_score=50,
                    factors={"content_severity": 0.5, "age_factor": 0.5, "activity_factor": 0.5, "label_modifier": 0.5},
                    justification="Fallback default priority due to scoring error.",
                )

    async def _step_deduplicate_issues(self) -> None:
        """Detect duplicate issues through semantic search and LLM analysis."""
        self.state.current_step = "deduplicate"
        total = len(self.state.raw_issues)

        for idx, (number, issue) in enumerate(self.state.raw_issues.items(), start=1):
            pct = 55 + int((idx / total) * 15)
            self._notify_progress("deduplicate", f"Checking duplicates for #{number}...", pct, number)

            # Tool search for similar candidates
            candidates = await self.tools.search_similar_issues(
                repo=self.repo,
                query=f"{issue.title} {issue.body[:100]}",
                exclude_number=number,
                limit=3,
            )

            if candidates:
                prompt = build_deduplicate_prompt(
                    target_issue_number=number,
                    target_title=issue.title,
                    target_body=issue.body,
                    candidate_issues=candidates,
                )
                try:
                    dedup_res, telem = await self.llm.generate_structured(prompt, DeduplicationResult)
                    # Defensive safeguard: an issue cannot be duplicate of itself
                    if dedup_res.is_duplicate and dedup_res.best_match:
                        if dedup_res.best_match.target_issue_number == number:
                            dedup_res.is_duplicate = False
                            dedup_res.best_match = None

                    self.state.deduplications[number] = dedup_res
                    self.state.add_telemetry(tokens=telem.get("tokens_prompt", 0) + telem.get("tokens_completion", 0), is_llm=True)
                    if dedup_res.is_duplicate and dedup_res.best_match:
                        self.run_logger.log_decision(
                            step="deduplicate",
                            issue_number=number,
                            decision_type="duplicate_detected",
                            summary=f"Duplicate of #{dedup_res.best_match.target_issue_number}",
                            reasoning=dedup_res.best_match.rationale,
                            confidence=dedup_res.confidence,
                        )
                except Exception as exc:
                    self.run_logger.log_error("deduplicate", f"Deduplication failed for #{number}", str(exc), issue_number=number)
                    self.state.deduplications[number] = DeduplicationResult(issue_number=number, is_duplicate=False)
            else:
                self.state.deduplications[number] = DeduplicationResult(issue_number=number, is_duplicate=False)

    async def _step_draft_actions(self) -> None:
        """Draft tailored responses, labels, and closure suggestions."""
        self.state.current_step = "draft_action"
        total = len(self.state.raw_issues)

        for idx, (number, issue) in enumerate(self.state.raw_issues.items(), start=1):
            pct = 70 + int((idx / total) * 15)
            self._notify_progress("draft_action", f"Drafting action for #{number}...", pct, number)

            cls = self.state.classifications.get(number)
            prio = self.state.priorities.get(number)
            dedup = self.state.deduplications.get(number)

            cat_str = cls.category.value if cls else "bug"
            prio_str = prio.level.value if prio else "medium"
            dup_target = dedup.best_match.target_issue_number if (dedup and dedup.is_duplicate and dedup.best_match) else None

            prompt = build_draft_action_prompt(
                issue_number=number,
                title=issue.title,
                body=issue.body,
                category=cat_str,
                priority=prio_str,
                duplicate_of=dup_target,
            )

            try:
                action, telem = await self.llm.generate_structured(prompt, DraftedAction)
                self.state.actions[number] = action
                self.state.add_telemetry(tokens=telem.get("tokens_prompt", 0) + telem.get("tokens_completion", 0), is_llm=True)
                self.run_logger.log_decision(
                    step="draft_action",
                    issue_number=number,
                    decision_type="action_proposal",
                    summary=action.headline,
                    reasoning=action.reasoning,
                )
            except Exception as exc:
                self.run_logger.log_error("draft_action", f"Failed drafting action for #{number}", str(exc), issue_number=number)
                self.state.actions[number] = DraftedAction(
                    issue_number=number,
                    action_type=ActionType.LABEL_AND_TRIAGE,
                    headline="Standard triage review",
                    reasoning="Default action due to drafting error.",
                    labels_to_add=["needs-triage"],
                )

    async def _step_critique_and_align(self) -> None:
        """Critic step: re-aligns any conflicting decisions across steps."""
        self.state.current_step = "critique"
        self._notify_progress("critique", "Validating consistency across decisions...", 88)

        for number, action in list(self.state.actions.items()):
            dedup = self.state.deduplications.get(number)
            cls = self.state.classifications.get(number)

            # Alignment Rule 1: If detected duplicate, enforce close_as_duplicate action
            if dedup and dedup.is_duplicate and action.action_type != ActionType.CLOSE_AS_DUPLICATE:
                target_num = dedup.best_match.target_issue_number if dedup.best_match else 0
                self.run_logger.log_event(
                    "replan",
                    "critique",
                    f"Critique aligned action for #{number}: changed {action.action_type} to close_as_duplicate",
                    {"issue_number": number, "target_duplicate": target_num},
                )
                action.action_type = ActionType.CLOSE_AS_DUPLICATE
                action.should_close = True
                action.close_reason = "not_planned"
                if "duplicate" not in action.labels_to_add:
                    action.labels_to_add.append("duplicate")

            # Alignment Rule 2: If classified as spam, enforce close_as_spam action
            if cls and cls.category == IssueCategory.SPAM and not action.should_close:
                self.run_logger.log_event(
                    "replan",
                    "critique",
                    f"Critique aligned spam action for #{number}: marking for closure",
                    {"issue_number": number},
                )
                action.action_type = ActionType.CLOSE_AS_SPAM
                action.should_close = True
                action.close_reason = "not_planned"
                if "spam" not in action.labels_to_add:
                    action.labels_to_add.append("spam")

    async def _step_apply_actions(self) -> None:
        """Apply actions to GitHub when apply_actions=True."""
        self.state.current_step = "apply"
        self._notify_progress("apply", "Applying actions to GitHub repository...", 92)

        for number, action in self.state.actions.items():
            result = AppliedActionResult(
                issue_number=number,
                dry_run=self.dry_run,
                status="applied" if not self.dry_run else "simulated",
            )

            # Apply labels
            if action.labels_to_add:
                lbl_res = await self.tools.label_issue(self.repo, number, action.labels_to_add)
                result.labels_added = action.labels_to_add
                self.run_logger.log_tool_call("apply", "label_issue", {"number": number, "labels": action.labels_to_add}, lbl_res)

            # Post comment
            if action.draft_comment:
                cmt_res = await self.tools.post_comment(self.repo, number, action.draft_comment)
                result.comment_posted = True
                result.comment_url = cmt_res.get("html_url")
                self.run_logger.log_tool_call("apply", "post_comment", {"number": number}, cmt_res)

            # Close issue if recommended
            if action.should_close:
                close_res = await self.tools.close_issue(self.repo, number, action.close_reason)
                result.issue_closed = True
                self.run_logger.log_tool_call("apply", "close_issue", {"number": number, "reason": action.close_reason}, close_res)

            self.state.execution_results[number] = result

    async def _step_generate_reports(self) -> TriageRunReport:
        """Assemble and write final JSON and Markdown reports."""
        self.state.current_step = "report"
        self._notify_progress("report", "Generating final reports...", 96)

        report = self.reporter.build_report_data(self.state)
        paths = self.reporter.save_reports(report)

        self.run_logger.log_event(
            "report_generated",
            "report",
            f"Triage reports written to {paths['json']} and {paths['md']}",
            {"json_path": str(paths["json"]), "md_path": str(paths["md"])},
        )
        return report
