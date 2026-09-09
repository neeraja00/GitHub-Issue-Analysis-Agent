"""Action recommendation and response drafting prompts."""

DRAFT_ACTION_SYSTEM_PROMPT = """You are an experienced open-source maintainer determining the appropriate next action for a GitHub issue.
Choose one action_type from:
- `request_reproduction`: When a bug report is vague, missing logs, OS details, or reproducible steps.
- `close_as_duplicate`: When an issue is confirmed duplicate of another existing issue.
- `close_as_spam`: When an issue is unsolicited advertising, scam, or offensive spam.
- `label_and_triage`: When an issue is well-formed and simply needs categorization labels and assignment.
- `answer_question`: When the question can be resolved directly or pointed to specific documentation.
- `escalate_critical`: When an issue is severe (crash/data loss) requiring urgent maintainer attention.
- `invite_contribution`: When an issue is well-scoped and suitable for community contributors (e.g. docs, small fixes).

Produce a courteous, professional maintainer comment in Markdown if communication with the user is required.
"""


def build_draft_action_prompt(
    issue_number: int,
    title: str,
    body: str,
    category: str,
    priority: str,
    duplicate_of: int | None = None,
) -> str:
    """Format prompt for response drafting and action proposal."""
    dup_context = f"Detected duplicate of Issue #{duplicate_of}." if duplicate_of else "Not a duplicate."

    return f"""{DRAFT_ACTION_SYSTEM_PROMPT}

### Issue Context:
Issue Number: #{issue_number}
Title: {title}
Category: {category}
Priority: {priority}
Deduplication Status: {dup_context}
Body:
{body if body.strip() else "(Empty description)"}

Return the recommended action adhering strictly to DraftedAction JSON schema.
"""
