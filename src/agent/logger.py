"""Structured JSON Lines Logger for agent runs."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings

logger = logging.getLogger("run_logger")


class StructuredRunLogger:
    """Logs detailed agent events, tool invocations, LLM calls, and decisions into a JSONL file."""

    def __init__(self, run_id: str, log_dir: Optional[Path] = None):
        self.run_id = run_id
        self.log_dir = log_dir or settings.logs_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"run_{run_id}.jsonl"
        self.events: List[Dict[str, Any]] = []

    def _append_event(self, event: Dict[str, Any]) -> None:
        """Write event record to memory and JSONL disk file."""
        self.events.append(event)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error(f"Failed writing event to {self.log_file}: {exc}")

    def log_event(
        self,
        event_type: str,
        step: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        issue_number: Optional[int] = None,
        tokens: int = 0,
        latency_ms: int = 0,
    ) -> Dict[str, Any]:
        """Log a generic agent lifecycle event."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": event_type,
            "step": step,
            "issue_number": issue_number,
            "message": message,
            "data": data or {},
            "tokens": tokens,
            "latency_ms": latency_ms,
        }
        self._append_event(event)
        logger.info(f"[{event_type.upper()}][{step}] {message}")
        return event

    def log_tool_call(
        self,
        step: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        latency_ms: int = 0,
    ) -> Dict[str, Any]:
        """Record an explicit tool call."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": "tool_call",
            "step": step,
            "message": f"Invoked tool '{tool_name}'",
            "data": {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
            },
            "tokens": 0,
            "latency_ms": latency_ms,
        }
        self._append_event(event)
        return event

    def log_llm_call(
        self,
        step: str,
        model: str,
        task: str,
        tokens_prompt: int,
        tokens_completion: int,
        latency_ms: int,
        issue_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record an LLM call with token consumption and latency telemetry."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": "llm_call",
            "step": step,
            "issue_number": issue_number,
            "message": f"LLM inference for {task} ({model})",
            "data": {
                "model": model,
                "task": task,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "tokens_total": tokens_prompt + tokens_completion,
            },
            "tokens": tokens_prompt + tokens_completion,
            "latency_ms": latency_ms,
        }
        self._append_event(event)
        return event

    def log_decision(
        self,
        step: str,
        issue_number: int,
        decision_type: str,
        summary: str,
        reasoning: str,
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Record an autonomous triage decision with reasoning trace."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": "decision",
            "step": step,
            "issue_number": issue_number,
            "message": f"Issue #{issue_number}: {decision_type} -> {summary}",
            "data": {
                "decision_type": decision_type,
                "summary": summary,
                "reasoning": reasoning,
                "confidence": confidence,
            },
            "tokens": 0,
            "latency_ms": 0,
        }
        self._append_event(event)
        return event

    def log_error(
        self,
        step: str,
        message: str,
        error: str,
        issue_number: Optional[int] = None,
        recoverable: bool = True,
    ) -> Dict[str, Any]:
        """Record an error or exception during execution."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": "error",
            "step": step,
            "issue_number": issue_number,
            "message": message,
            "data": {
                "error": error,
                "recoverable": recoverable,
            },
            "tokens": 0,
            "latency_ms": 0,
        }
        self._append_event(event)
        logger.warning(f"[ERROR][{step}] {message}: {error} (recoverable={recoverable})")
        return event
