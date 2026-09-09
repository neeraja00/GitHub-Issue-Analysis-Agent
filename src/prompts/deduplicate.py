"""Prompts for semantic issue deduplication."""

DEDUPLICATE_SYSTEM_PROMPT = """You are a technical duplicate detection specialist for GitHub repositories.
Analyze whether the target issue is a duplicate of any existing candidate issues.
Two issues are duplicates if:
1. They describe the same underlying defect, bug, or failure mechanism (even if user phrasing differs).
2. They share identical stack traces, error codes, and symptoms.
3. They propose the exact same feature or enhancement.

Do NOT flag as duplicate if:
- Issues merely touch the same subsystem or component but report different defects.
- One issue is a bug and the other is a general question or documentation report.

Return a validated DeduplicationResult schema.
"""


def build_deduplicate_prompt(
    target_issue_number: int,
    target_title: str,
    target_body: str,
    candidate_issues: list,
) -> str:
    """Format prompt comparing target issue with candidate open issues."""
    candidates_text = "\n".join(
        f"Candidate #{c['number']}: {c['title']}\nSnippet: {c.get('body', '')[:250]}\n"
        for c in candidate_issues
    )

    return f"""{DEDUPLICATE_SYSTEM_PROMPT}

### Target Issue:
Issue #{target_issue_number}: {target_title}
Description:
{target_body if target_body.strip() else "(No description provided)"}

### Open Candidates for Comparison:
{candidates_text if candidates_text else "(No candidates found)"}

Determine if Issue #{target_issue_number} duplicates any candidate. Return strictly formatted JSON for DeduplicationResult.
"""
