"""Classification prompt templates and few-shot calibration examples."""

CLASSIFY_SYSTEM_PROMPT = """You are a GitHub issue classification model.
Classify the given GitHub issue into exactly ONE of the following primary categories:
- `bug`: An unexpected failure, error, crash, malfunction, regression, or deviation from expected behavior.
- `feature_request`: A proposal for new capability, enhancement, optimization, or aesthetic customization.
- `question`: An inquiry regarding how to configure, use, or troubleshoot existing functionality.
- `documentation`: A report of missing, broken, outdated, or confusing documentation or examples.
- `duplicate`: An issue that describes an identical problem or proposal previously logged.
- `spam`: Unrelated commercial promotion, phishing, casino/crypto shilling, or automated nonsense.

You must also supply:
- `confidence`: Float between 0.0 and 1.0 representing certainty.
- `reasoning`: Concise 1-2 sentence rationale citing specific textual evidence.
- `tags`: List of 1-3 specific technical sub-tags (e.g. ["windows", "crash", "dll"], ["ui", "dark-mode"]).
- `suggested_labels`: Recommended GitHub labels (e.g. ["bug", "os:windows"], ["enhancement"]).
"""

CLASSIFY_FEW_SHOT_EXAMPLES = """
--- Example 1 ---
Title: Crash on launch with AccessViolationException in auth_module.so on Linux
Body: Running v1.2.0 on Ubuntu 22.04 results in immediate crash:
Thread 1 "app" received signal SIGSEGV, Segmentation fault.
Labels: []

Response:
{
  "issue_number": 42,
  "category": "bug",
  "confidence": 0.98,
  "reasoning": "Explicit SIGSEGV / AccessViolation crash traceback reported during standard launch.",
  "tags": ["crash", "linux", "segfault"],
  "suggested_labels": ["bug", "crash", "os:linux"]
}

--- Example 2 ---
Title: Please add true black OLED theme for mobile view
Body: The current dark theme uses dark grey #222. An AMOLED pure black #000 would save battery and looks cleaner.
Labels: ["ui"]

Response:
{
  "issue_number": 88,
  "category": "feature_request",
  "confidence": 0.95,
  "reasoning": "User is proposing a visual enhancement and feature addition (AMOLED black theme).",
  "tags": ["ui", "dark-mode", "theme"],
  "suggested_labels": ["enhancement", "ui"]
}

--- Example 3 ---
Title: Where do I put the JWT public certificate in Docker?
Body: I am deploying via docker-compose and want to know which directory the runner looks for the JWT public key in.
Labels: []

Response:
{
  "issue_number": 93,
  "category": "question",
  "confidence": 0.92,
  "reasoning": "User is asking for configuration guidance and container deployment instructions.",
  "tags": ["docker", "jwt", "configuration"],
  "suggested_labels": ["question", "docker"]
}

--- Example 4 ---
Title: Best Online Casino Bonuses 2026! Free 100 USDT!
Body: Claim your deposit bonus now at http://scam-site.biz with code FREE2026.
Labels: []

Response:
{
  "issue_number": 99,
  "category": "spam",
  "confidence": 1.0,
  "reasoning": "Irrelevant commercial gambling promotion with external affiliate links.",
  "tags": ["spam", "commercial"],
  "suggested_labels": ["spam"]
}
"""


def build_classify_prompt(issue_number: int, title: str, body: str, labels: list) -> str:
    """Build formatted prompt for issue classification."""
    return f"""{CLASSIFY_SYSTEM_PROMPT}

### Calibration Examples:
{CLASSIFY_FEW_SHOT_EXAMPLES}

### Target Issue to Classify:
Issue Number: {issue_number}
Title: {title}
Body:
{body if body.strip() else "(No issue description provided)"}
Existing Labels: {labels}

Return the classification strictly adhering to the JSON schema for IssueClassification.
"""
