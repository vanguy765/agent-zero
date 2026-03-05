"""Tests for server.py - FastAPI endpoints."""
import os
import sys
import io
import json
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

# Ensure source dir is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import JobStatus, ProcessingPhase
from job_manager import JobManager, InMemoryJobStore


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def test_job_manager():
    """Create a fresh JobManager with InMemoryJobStore."""
    return JobManager(InMemoryJobStore())


@pytest_asyncio.fixture
async def client(test_job_manager):
    """Create an httpx AsyncClient with the FastAPI app.

    Patches server.job_manager to use our test instance.
    """
    import server as server_module
    server_module.job_manager = test_job_manager

    transport = ASGITransport(app=server_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_upload_file(filename="test.pdf", content=b"%PDF-1.4 fake"):
    """Create file data for multipart upload."""
    return {"file": (filename, io.BytesIO(content), "application/pdf")}


# ============================================================
# GET /health
# ============================================================

class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_returns_200_with_healthy_status(self, client):
        """Returns 200 with status healthy."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_contains_version_and_engines(self, client):
        """Contains version, engines list, dependencies dict."""
        resp = await client.get("/health")
        data = resp.json()
        assert "version" in data
        assert "engines" in data
        assert isinstance(data["engines"], list)
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)

    @pytest.mark.asyncio
    async def test_jobs_counts_reflect_state(self, client, test_job_manager):
        """Jobs counts reflect actual job_manager state."""
        # Create a job to have non-zero counts
        await test_job_manager.create_job(file_name="a.pdf", engine="hybrid")
        resp = await client.get("/health")
        data = resp.json()
        assert data["jobs"]["total"] >= 1


# ============================================================
# POST /parse/docling
# ============================================================

class TestParseDoclingEndpoint:
    """Tests for POST /parse/docling."""

    @pytest.mark.asyncio
    async def test_returns_200_with_job_info(self, client):
        """Returns 200 with job_id, status=queued, engine=docling."""
        resp = await client.post(
            "/parse/docling",
            files=_make_upload_file(),
            data={"provider": "test-provider"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["engine"] == "docling"

    @pytest.mark.asyncio
    async def test_file_upload_processed(self, client):
        """File upload is processed and job created."""
        resp = await client.post(
            "/parse/docling",
            files=_make_upload_file("myfile.pdf"),
            data={"provider": "test-provider"},
        )
        data = resp.json()
        assert data["file"] == "myfile.pdf"

    @pytest.mark.asyncio
    async def test_background_task_registered(self, client, test_job_manager):
        """Background task is registered (job exists after request)."""
        resp = await client.post(
            "/parse/docling",
            files=_make_upload_file(),
            data={"provider": "test-provider"},
        )
        job_id = resp.json()["job_id"]
        status = await test_job_manager.get_status(job_id)
        assert status is not None

    @pytest.mark.asyncio
    async def test_custom_provider_accepted(self, client):
        """Custom provider form field is accepted."""
        resp = await client.post(
            "/parse/docling",
            files=_make_upload_file(),
            data={"provider": "openai/gpt-4o"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_file_returns_422(self, client):
        """Missing file returns 422."""
        resp = await client.post("/parse/docling", data={"provider": "test"})
        assert resp.status_code == 422


# ============================================================
# POST /parse/hybrid
# ============================================================

class TestParseHybridEndpoint:
    """Tests for POST /parse/hybrid."""

    @pytest.mark.asyncio
    async def test_returns_200_with_job_info(self, client):
        """Returns 200 with job_id, status=queued, engine=hybrid."""
        resp = await client.post(
            "/parse/hybrid",
            files=_make_upload_file(),
            data={"provider": "test-provider"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["engine"] == "hybrid"

    @pytest.mark.asyncio
    async def test_background_task_registered(self, client, test_job_manager):
        """Background task is registered (job exists after request)."""
        resp = await client.post(
            "/parse/hybrid",
            files=_make_upload_file(),
            data={"provider": "test-provider"},
        )
        job_id = resp.json()["job_id"]
        status = await test_job_manager.get_status(job_id)
        assert status is not None

    @pytest.mark.asyncio
    async def test_custom_provider_and_supabase_accepted(self, client):
        """Custom provider and supabase credentials accepted."""
        resp = await client.post(
            "/parse/hybrid",
            files=_make_upload_file(),
            data={
                "provider": "openai/gpt-4o",
                "supabase_url": "https://example.supabase.co",
                "supabase_key": "test-key",
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_file_returns_422(self, client):
        """Missing file returns 422."""
        resp = await client.post("/parse/hybrid", data={"provider": "test"})
        assert resp.status_code == 422


# ============================================================
# GET /status/{job_id}
# ============================================================

class TestStatusEndpoint:
    """Tests for GET /status/{job_id}."""

    @pytest.mark.asyncio
    async def test_returns_status_for_existing_job(self, client, test_job_manager):
        """Returns status for existing job."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        resp = await client.get(f"/status/{job.job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_job(self, client):
        """Returns 404 for unknown job_id."""
        resp = await client.get("/status/nonexistent-job-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_response_matches_status_schema(self, client, test_job_manager):
        """Response matches StatusResponse schema (no result data)."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        resp = await client.get(f"/status/{job.job_id}")
        data = resp.json()
        assert "status" in data
        assert "job_id" in data
        # Should NOT contain full result data
        assert "result" not in data

    @pytest.mark.asyncio
    async def test_progress_fields_included(self, client, test_job_manager):
        """Progress fields included."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        await test_job_manager.update_progress(
            job.job_id,
            phase=ProcessingPhase.DOCLING_CONVERSION,
            current_step="converting",
        )
        resp = await client.get(f"/status/{job.job_id}")
        data = resp.json()
        assert "progress" in data

    @pytest.mark.asyncio
    async def test_error_field_for_failed_jobs(self, client, test_job_manager):
        """Error field included for failed jobs."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        await test_job_manager.fail_job(job.job_id, "Something went wrong")
        resp = await client.get(f"/status/{job.job_id}")
        data = resp.json()
        assert data["status"] == "failed"
        assert "error" in data
        assert data["error"] == "Something went wrong"


# ============================================================
# GET /results/{job_id}
# ============================================================

class TestResultsEndpoint:
    """Tests for GET /results/{job_id}."""

    @pytest.mark.asyncio
    async def test_returns_full_result_for_completed_job(self, client, test_job_manager):
        """Returns full result for completed job."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        result_data = {"engine": "hybrid", "units": [{"unit_number": "101"}]}
        await test_job_manager.complete_job(job.job_id, result_data)

        resp = await client.get(f"/results/{job.job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "result" in data
        assert data["result"]["engine"] == "hybrid"

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_job(self, client):
        """Returns 404 for unknown job_id."""
        resp = await client.get("/results/nonexistent-job-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_processing_message_for_queued(self, client, test_job_manager):
        """Returns processing message for QUEUED jobs."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        resp = await client.get(f"/results/{job.job_id}")
        data = resp.json()
        assert data["status"] == "queued"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_returns_processing_message_for_processing(self, client, test_job_manager):
        """Returns processing message for PROCESSING jobs."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        resp = await client.get(f"/results/{job.job_id}")
        data = resp.json()
        assert data["status"] == "processing"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_returns_error_for_failed_jobs(self, client, test_job_manager):
        """Returns error for FAILED jobs."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        await test_job_manager.fail_job(job.job_id, "Parse error")
        resp = await client.get(f"/results/{job.job_id}")
        data = resp.json()
        assert data["status"] == "failed"
        assert "error" in data

    @pytest.mark.asyncio
    async def test_returns_error_for_timeout_jobs(self, client, test_job_manager):
        """Returns error for TIMEOUT jobs."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        await test_job_manager.timeout_job(job.job_id)
        resp = await client.get(f"/results/{job.job_id}")
        data = resp.json()
        assert data["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_summary_query_param(self, client, test_job_manager):
        """?summary=true returns lightweight summary."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        result_data = {
            "engine": "hybrid",
            "units": [{"unit_number": "101", "rooms": [], "doors": [], "windows": []}],
            "tables": [],
            "summary": {"units_count": 1},
        }
        await test_job_manager.complete_job(job.job_id, result_data)

        resp = await client.get(f"/results/{job.job_id}?summary=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_returns_404_when_no_result_data(self, client, test_job_manager):
        """Returns 404 when completed but no data (edge case)."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        # Complete with None result to simulate missing data
        await test_job_manager.complete_job(job.job_id, None)

        resp = await client.get(f"/results/{job.job_id}")
        # Should return 404 since result is None
        assert resp.status_code == 404


# ============================================================
# GET /jobs
# ============================================================

class TestJobsEndpoint:
    """Tests for GET /jobs."""

    @pytest.mark.asyncio
    async def test_returns_list_of_all_jobs(self, client, test_job_manager):
        """Returns list of all jobs."""
        await test_job_manager.create_job(file_name="a.pdf", engine="hybrid")
        await test_job_manager.create_job(file_name="b.pdf", engine="docling")
        resp = await client.get("/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["jobs"]) == 2

    @pytest.mark.asyncio
    async def test_status_filter_works(self, client, test_job_manager):
        """Status filter works."""
        job1 = await test_job_manager.create_job(file_name="a.pdf", engine="hybrid")
        job2 = await test_job_manager.create_job(file_name="b.pdf", engine="hybrid")
        await test_job_manager.start_processing(job1.job_id)

        resp = await client.get("/jobs?status=processing")
        data = resp.json()
        assert data["total"] == 1
        assert data["jobs"][0]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_empty_list_when_no_jobs(self, client):
        """Empty list when no jobs."""
        resp = await client.get("/jobs")
        data = resp.json()
        assert data["total"] == 0
        assert data["jobs"] == []


# ============================================================
# DELETE /jobs/{job_id}
# ============================================================

class TestDeleteJobEndpoint:
    """Tests for DELETE /jobs/{job_id}."""

    @pytest.mark.asyncio
    async def test_returns_deleted_confirmation(self, client, test_job_manager):
        """Returns deleted confirmation for idle job."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        resp = await client.delete(f"/jobs/{job.job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == job.job_id

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_job(self, client):
        """Returns 404 for unknown job."""
        resp = await client.delete("/jobs/nonexistent-job-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_409_for_running_job(self, client, test_job_manager):
        """Returns 409 for running job (cannot delete)."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        resp = await client.delete(f"/jobs/{job.job_id}")
        assert resp.status_code == 409


# ============================================================
# GET /result/{job_id} - Legacy
# ============================================================

class TestLegacyResultEndpoint:
    """Tests for GET /result/{job_id} legacy endpoint."""

    @pytest.mark.asyncio
    async def test_delegates_to_results_endpoint(self, client, test_job_manager):
        """Legacy endpoint delegates to /results endpoint."""
        job = await test_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        await test_job_manager.start_processing(job.job_id)
        result_data = {"engine": "hybrid", "units": []}
        await test_job_manager.complete_job(job.job_id, result_data)

        resp = await client.get(f"/result/{job.job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "result" in data
