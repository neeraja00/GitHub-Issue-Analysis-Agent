"""Priority scoring prompts, factor weights, and rubric calibration."""

PRIORITIZE_SYSTEM_PROMPT = """You are an expert GitHub issue triage scoring engine.
Your task is to compute a balanced priority assessment for a GitHub issue using a 0-100 numerical scale and map it to:
- `critical` (Score 85-100): System crash, data loss, security vulnerability, or complete outage blocking release.
- `high` (Score 65-84): Significant functional impairment, severe performance degradation/memory leak, or blocking core workflow.
- `medium` (Score 40-64): Standard bug with a workaround, notable cosmetic glitch, or popular feature proposal.
- `low` (Score 0-39): Minor documentation fix, simple usage question, trivial cosmetic tweak, or spam.

### Evaluation Factors (0.0 to 1.0 each):
1. `content_severity`: Intrinsic severity (crash/data loss = 0.9-1.0; major bug = 0.7-0.8; annoyance = 0.4-0.6; doc/question = 0.1-0.3).
2. `age_factor`: How urgent given issue age (urgent recent regression = 0.8-1.0; stale backlog item = 0.2-0.4).
3. `activity_factor`: Community buzz, comments, or multiple users reproducing the problem (0.0 for 0 comments up to 1.0 for active threads).
4. `label_modifier`: Influence of existing labels (e.g. 'critical', 'p0', 'security' = 0.9-1.0; none = 0.5).
"""

PRIORITIZE_FEW_SHOT_EXAMPLES = """
--- Example 1 ---
Issue: #101
Title: Crash on startup: AccessViolationException on Windows 11
Body: Immediate segmentation fault before window render on Windows 11 23H2. Multiple users confirmed.
Existing Labels: ["bug", "crash"]
Comments Count: 4
Age in Days: 2

Response:
{
  "issue_number": 101,
  "level": "critical",
  "numerical_score": 94,
  "factors": {
    "content_severity": 0.98,
    "age_factor": 0.90,
    "activity_factor": 0.85,
    "label_modifier": 0.95
  },
  "justification": "Application fails to start completely on latest Windows release, verified by multiple users. Immediate blocker.",
  "sla_urgency": "immediate"
}

--- Example 2 ---
Issue: #105
Title: Docs: 404 broken link in Step 3 of Quickstart Guide
Body: Link to credentials documentation gives 404.
Existing Labels: ["documentation"]
Comments Count: 0
Age in Days: 7

Response:
{
  "issue_number": 105,
  "level": "low",
  "numerical_score": 28,
  "factors": {
    "content_severity": 0.20,
    "age_factor": 0.35,
    "activity_factor": 0.10,
    "label_modifier": 0.30
  },
  "justification": "Broken documentation link is inconvenient but does not impair software functionality.",
  "sla_urgency": "next sprint"
}
"""


def build_prioritize_prompt(
    issue_number: int,
    title: str,
    body: str,
    labels: list,
    comments_count: int,
    age_days: float,
    classification_category: str,
) -> str:
    """Build prompt for priority evaluation."""
    return f"""{PRIORITIZE_SYSTEM_PROMPT}

### Calibration Examples:
{PRIORITIZE_FEW_SHOT_EXAMPLES}

### Target Issue to Score:
Issue Number: {issue_number}
Category: {classification_category}
Title: {title}
Body:
{body if body.strip() else "(No issue description provided)"}
Existing Labels: {labels}
Comments Count: {comments_count}
Age in Days: {age_days:.1f}

Return the priority assessment strictly adhering to the JSON schema for PriorityScore.
"""
