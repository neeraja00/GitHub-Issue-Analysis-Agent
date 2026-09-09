"""Integration tests for FastAPI endpoints."""

import pytest
import httpx
from src.api.server import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "default_llm_provider" in data


@pytest.mark.asyncio
async def test_trigger_and_query_analysis():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Trigger run
        post_resp = await client.post(
            "/api/analyze",
            json={
                "repo": "mock/demo-repo",
                "goal": "Test API pipeline run",
                "limit": 5,
                "dry_run": True,
                "provider": "mock",
            },
        )
        assert post_resp.status_code == 200
        post_data = post_resp.json()
        assert "run_id" in post_data
        run_id = post_data["run_id"]

        # Check run details
        get_resp = await client.get(f"/api/runs/{run_id}")
        assert get_resp.status_code == 200
        run_data = get_resp.json()
        assert run_data["run_id"] == run_id
        assert run_data["repo"] == "mock/demo-repo"

        # List runs
        list_resp = await client.get("/api/runs")
        assert list_resp.status_code == 200
        runs = list_resp.json()
        assert any(r["run_id"] == run_id for r in runs)
