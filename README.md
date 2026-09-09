# 🛡️ GitHub Issue Analysis Agent

> An autonomous, multi-step AI Automation Agent system for fetching, classifying, prioritizing, deduplicating, drafting actionable responses for, and reporting on GitHub repository issues.

![Agent Architecture](https://img.shields.io/badge/Architecture-Multi--Step%20Agentic-blue?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi)
![Pydantic](https://img.shields.io/badge/Validation-Pydantic%20v2-e92063?style=for-the-badge)
![Safety](https://img.shields.io/badge/Safety-Default%20Dry--Run-10b981?style=for-the-badge)

---

## 🌟 Key Capabilities & Architectural Checklist

| Architectural Requirement | Implementation Details | Status |
| :--- | :--- | :---: |
| **Prompt Engineering** | System prompts defining maintainer constraints, few-shot examples for classification and priority scoring rubric, isolated per-subtask prompt templates. | ✅ |
| **Native Function Calling** | 6 explicit tools (`list_issues`, `get_issue_detail`, `search_similar_issues`, `label_issue`, `post_comment`, `close_issue`) with complete docstrings and JSON schemas. | ✅ |
| **Multi-Step Workflows** | Orchestrated pipeline: *Init → Fetch → Classify → Prioritize → Deduplicate → Draft Action → Critique → Report → (Optional) Apply*. | ✅ |
| **Context Management** | `SessionState` tracking repository metadata and processed issues, with context window compression to prevent prompt bloat. | ✅ |
| **Resilient Error Handling** | GitHub API rate limiting with `X-RateLimit-Remaining` inspection & exponential backoff; per-issue fault isolation (one malformed issue will never crash the batch). | ✅ |
| **Structured Outputs** | Strict Pydantic models for `IssueClassification`, `PriorityScore`, `DeduplicationResult`, `DraftedAction`, and `TriageRunReport`. | ✅ |
| **Structured Logging** | Every tool call, LLM call (tokens & latency), decision, and retry logged to `logs/run_<id>.jsonl`. | ✅ |
| **Dual Reporting** | Writes machine-readable `reports/<repo>_<timestamp>.json` and rich human-readable `reports/<repo>_<timestamp>.md`. | ✅ |
| **Safety by Default** | Runs in `--dry-run` simulation mode by default; explicit `--apply` required to write back to GitHub. | ✅ |
| **Flexible LLM Provider** | Out-of-the-box support for Google Gemini (`google-genai`), OpenAI, Anthropic Claude, and high-fidelity Deterministic Mock engine for offline evaluation. | ✅ |
| **Modern Web Dashboard** | Dark-mode SPA served directly by FastAPI with real-time SSE progress streaming, filterable issue tables, duplicate visualizer, and log terminal. | ✅ |

---

## 🏗️ Architecture & Pipeline Flow

```mermaid
flowchart TD
    A["User Goal & Target Repo"] --> B["Agent Pipeline Initialization"]
    B --> C["Fetch Open Issues (Tools Layer)"]
    C --> D["Classify Issue (Few-shot LLM)"]
    D --> E["Score Priority & SLA Matrix"]
    E --> F["Semantic Deduplication Search"]
    F --> G["Draft Action & Polite Response"]
    G --> H["Critic & Alignment Review"]
    H --> I{"Apply Mode Enabled?"}
    I -- No (Default Dry-Run) --> J["Simulate Label/Comment/Close"]
    I -- Yes (--apply) --> K["Write Actions to GitHub API"]
    J --> L["Generate JSON & Markdown Reports"]
    K --> L
    L --> M["Output to Disk, CLI & Web Dashboard"]
```

---

## 🚀 Quickstart Guide

### 1. Installation

Ensure Python 3.10+ is installed. Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to configure your keys:

```dotenv
# Optional: GitHub token for 5,000 req/hr rate limit (unauthenticated limit is 60 req/hr)
GITHUB_TOKEN=your_github_personal_access_token

# Choose LLM Provider: "mock", "gemini", "openai", or "anthropic"
DEFAULT_LLM_PROVIDER=mock

# Required if using cloud LLM providers:
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

> **Note:** The system includes a deterministic mock reasoning engine (`mock`), allowing you to test the entire multi-step pipeline immediately without setting up external API keys!

---

## 💻 CLI Usage

The agent includes a Rich terminal interface with real-time progress bars, KPI tables, and color-coded triage registers.

### Run on Mock Repository (Instant Offline Demo)

```bash
python -m src.cli --mock --limit 8
```

### Run on Any Public GitHub Repository (Dry-Run Mode)

```bash
python -m src.cli --repo fastapi/fastapi --goal "Triage open issues from the last 7 days" --limit 10
```

### Run with Google Gemini Provider

```bash
python -m src.cli --repo owner/repo --provider gemini --model gemini-2.5-flash
```

### Apply Mode (Write Back to GitHub)

```bash
python -m src.cli --repo owner/repo --apply
```

---

## 🌐 FastAPI & Modern Web Dashboard

Start the FastAPI application:

```bash
uvicorn src.api.server:app --reload --port 8000
```

Now open **[http://localhost:8000](http://localhost:8000)** in your browser to access the Web UI:

- **Launch Triage Runs:** Configure repo, goal, issue limits, and provider.
- **Live Pipeline Tracker:** Watch the agent progress live across all 8 pipeline steps with real-time Server-Sent Events (SSE).
- **Interactive Triage Table:** Filter by category (`bug`, `feature_request`, `question`, `documentation`, `duplicate`, `spam`), priority (`critical`, `high`, `medium`, `low`), or keyword search.
- **Duplicate Cluster Visualizer:** View semantic matching pairs with similarity percentages and rationale.
- **Side Inspection Drawer:** Inspect drafted maintainer comments, proposed labels, and LLM reasoning.
- **Markdown & JSON Reports:** Live formatted Markdown preview with 1-click download.
- **Agent Telemetry Terminal:** Live stream of JSONL logs showing tool calls, token usage, and latencies.

### REST API Endpoints

- `POST /api/analyze`: Trigger analysis run in background.
- `GET /api/runs`: List historical runs with statistics.
- `GET /api/runs/{run_id}`: Get status, step, and structured results.
- `GET /api/runs/{run_id}/events`: Server-Sent Events (SSE) stream for live updates.
- `GET /api/runs/{run_id}/logs`: Retrieve JSONL log records.
- `GET /api/reports/{run_id}`: Retrieve JSON data and rendered Markdown report.
- `GET /api/health`: Check service status and configured providers.

---

## 🧪 Automated Testing

Run the full automated test suite covering models, tools, prompts, deduplication, error isolation, and FastAPI routes:

```bash
python -m pytest -v
```

All 18 unit and integration tests execute with 100% pass rate.

---

## 📂 Project Structure

```
Week3/
├── src/
│   ├── models/                # Pydantic schemas (GitHub, Classification, Priority, Dedup, Action, Report)
│   ├── github/                # GitHub API client (rate limits, backoff) & explicit LLM tools
│   ├── llm/                   # Unified LLM provider adapters (Gemini, Claude, OpenAI, Mock)
│   ├── prompts/               # System prompt, few-shot classification, priority rubric, action drafting
│   ├── agent/                 # Orchestration pipeline, session state, structured logger, report generator
│   ├── api/                   # FastAPI server, SSE streaming, and modern web dashboard static assets
│   ├── config.py              # Pydantic-settings configuration
│   └── cli.py                 # Rich CLI entrypoint
├── tests/                     # Test suite (18 automated tests)
├── logs/                      # Structured JSONL run logs (run_<id>.jsonl)
├── reports/                   # Machine-readable JSON and rendered Markdown reports
├── .env.example               # Environment variables template
├── pyproject.toml             # Project metadata and pytest configuration
└── requirements.txt           # Pinned dependencies
```
