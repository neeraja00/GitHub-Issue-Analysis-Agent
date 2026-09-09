"""Report Generator for Agent Triage Runs (JSON and Rich Markdown)."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from src.config import settings
from src.agent.state import SessionState
from src.models import (
    TriageIssueRecord,
    TriageRunReport,
    TriageSummaryStats,
)

logger = logging.getLogger("reporter")


class ReportGenerator:
    """Generates machine-readable JSON and formatted Markdown reports."""

    def __init__(self, reports_dir: Optional[Path] = None):
        self.reports_dir = reports_dir or settings.reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def build_report_data(self, state: SessionState) -> TriageRunReport:
        """Compile SessionState into a consolidated TriageRunReport model."""
        now = datetime.now(timezone.utc)
        completed_at = state.completed_at or now
        execution_time = (completed_at - state.started_at).total_seconds()

        # Aggregate category counts
        cat_counts: Dict[str, int] = {}
        for cls in state.classifications.values():
            cat = cls.category.value
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        # Aggregate priority counts
        prio_counts: Dict[str, int] = {}
        for prio in state.priorities.values():
            lvl = prio.level.value
            prio_counts[lvl] = prio_counts.get(lvl, 0) + 1

        duplicates_count = sum(1 for d in state.deduplications.values() if d.is_duplicate)
        recommended_closes = sum(1 for a in state.actions.values() if a.should_close)

        stats = TriageSummaryStats(
            total_issues_analyzed=len(state.raw_issues),
            categories_breakdown=cat_counts,
            priorities_breakdown=prio_counts,
            duplicates_detected=duplicates_count,
            recommended_closes=recommended_closes,
            actions_drafted=len(state.actions),
            total_tokens_used=state.total_tokens_used,
            execution_time_seconds=round(execution_time, 2),
        )

        # Build issue records
        records: List[TriageIssueRecord] = []
        for num, issue in state.raw_issues.items():
            records.append(
                TriageIssueRecord(
                    issue=issue,
                    classification=state.classifications.get(num),
                    priority=state.priorities.get(num),
                    deduplication=state.deduplications.get(num),
                    action=state.actions.get(num),
                    execution=state.execution_results.get(num),
                    processing_error=state.isolated_errors.get(num),
                )
            )

        # Sort records by priority: critical -> high -> medium -> low
        priority_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        records.sort(
            key=lambda r: (
                priority_weight.get(r.priority.level.value, 0) if r.priority else 0,
                r.priority.numerical_score if r.priority else 0,
            ),
            reverse=True,
        )

        exec_summary = (
            f"Triage run completed for repository '{state.repository}' under goal: '{state.goal}'. "
            f"Analyzed {len(state.raw_issues)} open issues in {execution_time:.1f}s. "
            f"Discovered {prio_counts.get('critical', 0)} critical blocker(s), "
            f"{duplicates_count} duplicate(s), and drafted {len(state.actions)} actionable responses."
        )

        takeaways = [
            f"Immediately address {prio_counts.get('critical', 0)} critical issue(s) affecting core runtime stability.",
            f"Consolidate {duplicates_count} duplicate discussion(s) into canonical tracking issues to prevent fragmented effort.",
            f"Apply suggested labels and automated reproduction requests to unblock maintainer review.",
        ]

        return TriageRunReport(
            run_id=state.run_id,
            repository=state.repository,
            goal=state.goal,
            started_at=state.started_at,
            completed_at=completed_at,
            dry_run=state.dry_run,
            applied=state.applied,
            llm_provider=settings.default_llm_provider,
            executive_summary=exec_summary,
            actionable_takeaways=takeaways,
            stats=stats,
            issues=records,
            errors=state.general_errors,
        )

    def generate_markdown(self, report: TriageRunReport) -> str:
        """Render a publication-ready GitHub Flavored Markdown report."""
        repo_clean = report.repository
        exec_mode = "APPLIED TO GITHUB" if report.applied else "DRY-RUN (Simulated)"

        md = [
            f"# 🛡️ GitHub Issue Triage Report: `{repo_clean}`",
            "",
            f"**Run ID:** `{report.run_id}` | **Mode:** `{exec_mode}` | **Date:** {report.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Triage Goal:** *\"{report.goal}\"*",
            "",
            "---",
            "",
            "## 📊 Executive Summary",
            "",
            report.executive_summary,
            "",
            "### Key Performance Indicators",
            "",
            "| Analyzed Issues | Critical Blockers | High Priority | Duplicates | Recommended Closes | Execution Time | Tokens Used |",
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            (
                f"| **{report.stats.total_issues_analyzed}** "
                f"| **{report.stats.priorities_breakdown.get('critical', 0)}** "
                f"| **{report.stats.priorities_breakdown.get('high', 0)}** "
                f"| **{report.stats.duplicates_detected}** "
                f"| **{report.stats.recommended_closes}** "
                f"| **{report.stats.execution_time_seconds:.1f}s** "
                f"| **{report.stats.total_tokens_used:,}** |"
            ),
            "",
            "---",
            "",
            "## 🏷️ Category & Priority Distributions",
            "",
            "### Categories",
            "| Category | Count | Percentage |",
            "| :--- | :--- | :--- |",
        ]

        total = max(1, report.stats.total_issues_analyzed)
        for cat, cnt in sorted(report.stats.categories_breakdown.items(), key=lambda x: x[1], reverse=True):
            pct = (cnt / total) * 100
            md.append(f"| `{cat}` | {cnt} | {pct:.1f}% |")

        md.extend([
            "",
            "### Priority Levels",
            "| Priority | Count | Percentage | SLA Target |",
            "| :--- | :--- | :--- | :--- |",
        ])

        sla_targets = {
            "critical": "Immediate (< 24h)",
            "high": "Within 48h",
            "medium": "Next Sprint",
            "low": "Backlog / Community",
        }
        for prio, cnt in sorted(report.stats.priorities_breakdown.items(), key=lambda x: x[1], reverse=True):
            pct = (cnt / total) * 100
            sla = sla_targets.get(prio, "Standard")
            md.append(f"| `{prio.upper()}` | {cnt} | {pct:.1f}% | {sla} |")

        # Duplicate section if any
        duplicates = [r for r in report.issues if r.deduplication and r.deduplication.is_duplicate]
        if duplicates:
            md.extend([
                "",
                "---",
                "",
                "## 👥 Detected Duplicates",
                "",
                "| Issue | Suspected Duplicate Of | Similarity | Reason |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for d in duplicates:
                target_num = d.deduplication.best_match.target_issue_number if d.deduplication.best_match else "N/A"
                sim_pct = f"{d.deduplication.confidence * 100:.0f}%" if d.deduplication else "N/A"
                reason = d.deduplication.best_match.rationale if (d.deduplication and d.deduplication.best_match) else ""
                md.append(f"| #{d.issue.number} `{d.issue.title}` | **#{target_num}** | {sim_pct} | {reason} |")

        # Detailed triage table
        md.extend([
            "",
            "---",
            "",
            "## 📋 Comprehensive Issue Triage Register",
            "",
        ])

        for rec in report.issues:
            issue = rec.issue
            cls = rec.classification
            prio = rec.priority
            act = rec.action

            cat_str = f"`{cls.category.value}`" if cls else "N/A"
            prio_str = f"**`{prio.level.value.upper()}`** ({prio.numerical_score}/100)" if prio else "N/A"
            urgency = prio.sla_urgency if prio else "N/A"

            md.append(f"### [#{issue.number}] {issue.title}")
            md.append(f"- **Author:** @{issue.author} | **Created:** {issue.created_at.strftime('%Y-%m-%d')} | **Comments:** {issue.comments_count}")
            md.append(f"- **Classification:** {cat_str} (Confidence: {cls.confidence * 100:.0f}%) | **Priority:** {prio_str} | **SLA:** {urgency}")
            if cls and cls.reasoning:
                md.append(f"- **Reasoning:** {cls.reasoning}")

            if act:
                close_badge = " *(Recommends Closing)*" if act.should_close else ""
                md.append(f"- **Recommended Action:** `{act.action_type.value}`{close_badge}")
                md.append(f"- **Action Rationale:** {act.reasoning}")
                if act.labels_to_add:
                    labels_formatted = " ".join(f"`{l}`" for l in act.labels_to_add)
                    md.append(f"- **Proposed Labels:** {labels_formatted}")
                if act.draft_comment:
                    md.append("- **Drafted Response for Maintainer:**")
                    md.append("  > " + "\n  > ".join(act.draft_comment.split("\n")))

            if rec.execution:
                md.append(f"- **Execution Status:** `{rec.execution.status}` (Dry run: {rec.execution.dry_run})")

            md.append("")

        # Actionable Takeaways
        md.extend([
            "---",
            "",
            "## 🚀 Actionable Next Steps",
            "",
        ])
        for idx, takeaway in enumerate(report.actionable_takeaways, start=1):
            md.append(f"{idx}. {takeaway}")

        md.append("\n*Report generated autonomously by GitHub Issue Analysis Agent.*")
        return "\n".join(md)

    def save_reports(self, report: TriageRunReport) -> Dict[str, Path]:
        """Save both JSON and Markdown reports to disk."""
        repo_slug = report.repository.replace("/", "_").replace("\\", "_")
        timestamp_slug = report.completed_at.strftime("%Y%m%d_%H%M%S")

        json_filename = f"{repo_slug}_{timestamp_slug}.json"
        md_filename = f"{repo_slug}_{timestamp_slug}.md"

        json_path = self.reports_dir / json_filename
        md_path = self.reports_dir / md_filename

        # Write JSON
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        # Write Markdown
        md_content = self.generate_markdown(report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Saved reports: JSON={json_path}, MD={md_path}")
        return {"json": json_path, "md": md_path}
