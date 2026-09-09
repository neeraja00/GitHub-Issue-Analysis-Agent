"""FastAPI server exposing REST endpoints, Server-Sent Events (SSE), and static UI."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agent.pipeline import TriagePipeline
from src.agent.state import SessionState
from src.config import settings
from src.llm import get_llm_provider
from src.models import TriageRunReport

logger = logging.getLogger("api_server")

app = FastAPI(
    title="GitHub Issue Analysis Agent API",
    description="Autonomous multi-step AI system for GitHub issue analysis, classification, and triage.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active runs and SSE queues
ACTIVE_RUNS: Dict[str, Dict[str, Any]] = {}
RUN_QUEUES: Dict[str, List[asyncio.Queue]] = {}


class AnalyzeRequest(BaseModel):
    """Payload to trigger an issue analysis run."""
    repo: str = Field(default="mock/demo-repo", description="GitHub repository 'owner/repo'")
    goal: str = Field(
        default="Triage open issues from the last 30 days and detect duplicates",
        description="High-level triage objective",
    )
    limit: int = Field(default=30, ge=1, le=100, description="Max issues to analyze")
    dry_run: bool = Field(default=True, description="Whether to simulate actions safely")
    apply: bool = Field(default=False, description="Whether to write back to GitHub (labels/comments/closes)")
    provider: Optional[str] = Field(default=None, description="LLM provider override (mock, gemini, openai)")
    model: Optional[str] = Field(default=None, description="Model name override")


class RunSummary(BaseModel):
    """Summary record for a triage run."""
    run_id: str
    repo: str
    goal: str
    status: str
    dry_run: bool
    started_at: str
    completed_at: Optional[str] = None
    total_issues: int = 0
    critical_count: int = 0
    duplicates_count: int = 0


async def _run_pipeline_background(
    run_id: str,
    request: AnalyzeRequest,
) -> None:
    """Execute pipeline in background and publish events to active SSE listeners."""
    run_entry = ACTIVE_RUNS[run_id]

    def on_progress(p: Dict[str, Any]) -> None:
        run_entry["current_step"] = p.get("step", "running")
        run_entry["percent"] = p.get("percent", 0)
        run_entry["message"] = p.get("message", "")
        # Broadcast to SSE queues
        queues = RUN_QUEUES.get(run_id, [])
        for q in queues:
            try:
                q.put_nowait(p)
            except asyncio.QueueFull:
                pass

    llm = get_llm_provider(request.provider, model=request.model)
    pipeline = TriagePipeline(
        repo=request.repo,
        goal=request.goal,
        dry_run=request.dry_run and not request.apply,
        apply_actions=request.apply,
        limit=request.limit,
        provider=llm,
        progress_callback=on_progress,
    )
    # Align run IDs
    pipeline.run_id = run_id
    pipeline.run_logger.run_id = run_id
    pipeline.state.run_id = run_id
    run_entry["pipeline"] = pipeline

    try:
        report = await pipeline.execute()
        run_entry["status"] = "completed"
        run_entry["report"] = report
        run_entry["completed_at"] = datetime.now(timezone.utc).isoformat()
        on_progress({"run_id": run_id, "step": "complete", "message": "Pipeline complete", "percent": 100})
    except Exception as exc:
        run_entry["status"] = "failed"
        run_entry["error"] = str(exc)
        on_progress({"run_id": run_id, "step": "error", "message": f"Run failed: {exc}", "percent": 100})
        logger.error(f"Background run {run_id} failed: {exc}", exc_info=True)


@app.post("/api/analyze", response_model=Dict[str, Any])
async def trigger_analysis(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Trigger an autonomous issue analysis run."""
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{Path(__file__).stem[:2]}"
    run_id = f"{run_id}_{abs(hash(req.repo)) % 10000:04d}"

    ACTIVE_RUNS[run_id] = {
        "run_id": run_id,
        "repo": req.repo,
        "goal": req.goal,
        "dry_run": req.dry_run and not req.apply,
        "apply": req.apply,
        "status": "running",
        "current_step": "initialize",
        "percent": 0,
        "message": "Queued for execution",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "report": None,
    }
    RUN_QUEUES[run_id] = []

    background_tasks.add_task(_run_pipeline_background, run_id, req)
    return {
        "run_id": run_id,
        "status": "running",
        "message": "Analysis started successfully.",
        "repo": req.repo,
    }


@app.get("/api/runs")
async def list_runs() -> List[Dict[str, Any]]:
    """List all tracked analysis runs."""
    results = []
    # From in-memory active runs
    for run_id, item in ACTIVE_RUNS.items():
        rep = item.get("report")
        results.append({
            "run_id": run_id,
            "repo": item["repo"],
            "goal": item["goal"],
            "status": item["status"],
            "dry_run": item["dry_run"],
            "started_at": item["started_at"],
            "completed_at": item.get("completed_at"),
            "percent": item.get("percent", 0),
            "total_issues": rep.stats.total_issues_analyzed if rep else 0,
            "critical_count": rep.stats.priorities_breakdown.get("critical", 0) if rep else 0,
            "duplicates_count": rep.stats.duplicates_detected if rep else 0,
        })

    # Also inspect reports directory for historical completed runs
    for json_file in settings.reports_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                r_id = data.get("run_id")
                if r_id and not any(r["run_id"] == r_id for r in results):
                    stats = data.get("stats", {})
                    results.append({
                        "run_id": r_id,
                        "repo": data.get("repository", ""),
                        "goal": data.get("goal", ""),
                        "status": "completed",
                        "dry_run": data.get("dry_run", True),
                        "started_at": data.get("started_at", ""),
                        "completed_at": data.get("completed_at", ""),
                        "percent": 100,
                        "total_issues": stats.get("total_issues_analyzed", 0),
                        "critical_count": stats.get("priorities_breakdown", {}).get("critical", 0),
                        "duplicates_count": stats.get("duplicates_detected", 0),
                    })
        except Exception:
            pass

    results.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return results


@app.get("/api/runs/{run_id}")
async def get_run_details(run_id: str):
    """Retrieve detailed state and report for a run."""
    if run_id in ACTIVE_RUNS:
        item = ACTIVE_RUNS[run_id]
        rep = item.get("report")
        return {
            "run_id": run_id,
            "repo": item["repo"],
            "goal": item["goal"],
            "status": item["status"],
            "dry_run": item["dry_run"],
            "current_step": item.get("current_step", ""),
            "percent": item.get("percent", 0),
            "message": item.get("message", ""),
            "started_at": item["started_at"],
            "completed_at": item.get("completed_at"),
            "report": rep.model_dump() if rep else None,
        }

    # Search in reports directory
    for json_file in settings.reports_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("run_id") == run_id:
                    return {
                        "run_id": run_id,
                        "repo": data.get("repository"),
                        "goal": data.get("goal"),
                        "status": "completed",
                        "dry_run": data.get("dry_run", True),
                        "percent": 100,
                        "started_at": data.get("started_at"),
                        "completed_at": data.get("completed_at"),
                        "report": data,
                    }
        except Exception:
            pass

    raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str):
    """Server-Sent Events (SSE) endpoint streaming real-time run progress."""
    queue = asyncio.Queue(maxsize=100)
    if run_id not in RUN_QUEUES:
        RUN_QUEUES[run_id] = []
    RUN_QUEUES[run_id].append(queue)

    async def event_generator():
        # Yield current state first
        if run_id in ACTIVE_RUNS:
            curr = ACTIVE_RUNS[run_id]
            yield f"data: {json.dumps({'step': curr.get('current_step'), 'message': curr.get('message'), 'percent': curr.get('percent', 0)})}\n\n"

        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("step") in ("complete", "error"):
                    break
        finally:
            if run_id in RUN_QUEUES and queue in RUN_QUEUES[run_id]:
                RUN_QUEUES[run_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/api/runs/{run_id}/logs")
async def get_run_logs(run_id: str) -> List[Dict[str, Any]]:
    """Retrieve raw JSONL structured event log records."""
    log_path = settings.logs_dir / f"run_{run_id}.jsonl"
    if not log_path.exists():
        # Try finding in active runs
        if run_id in ACTIVE_RUNS and "pipeline" in ACTIVE_RUNS[run_id]:
            return ACTIVE_RUNS[run_id]["pipeline"].run_logger.events
        return []

    events = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
    return events


@app.get("/api/reports/{run_id}")
async def get_report_content(run_id: str):
    """Retrieve both JSON model and rendered Markdown report text."""
    # Find matching report files
    md_content = None
    json_data = None

    for md_file in settings.reports_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
            if f"Run ID: `{run_id}`" in text:
                md_content = text
                break
        except Exception:
            pass

    for json_file in settings.reports_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("run_id") == run_id:
                    json_data = data
                    break
        except Exception:
            pass

    if not json_data and not md_content:
        raise HTTPException(status_code=404, detail=f"No reports found for run '{run_id}'")

    return {
        "run_id": run_id,
        "json": json_data,
        "markdown": md_content,
    }


@app.get("/api/health")
async def health_check():
    """Service health and environment configuration status."""
    return {
        "status": "healthy",
        "service": "GitHub Issue Analysis Agent",
        "version": "0.1.0",
        "github_token_configured": bool(settings.github_token),
        "default_llm_provider": settings.default_llm_provider,
        "gemini_api_key_configured": bool(settings.gemini_api_key),
        "anthropic_api_key_configured": bool(settings.anthropic_api_key),
        "openai_api_key_configured": bool(settings.openai_api_key),
    }


# Mount static assets
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the single page application dashboard."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Dashboard static files initializing...</h2>")
