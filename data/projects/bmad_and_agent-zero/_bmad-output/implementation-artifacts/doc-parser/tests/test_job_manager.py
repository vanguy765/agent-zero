"""Tests for job_manager.py - Job management system.

Phase 2: Async tests for InMemoryJobStore and JobManager.
All async tests use pytest-asyncio.
"""
import pytest
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from models import (
    JobRecord, JobStatus, JobProgress, ProcessingPhase, EngineType,
    StatusResponse, ResultSummary,
)
from job_manager import (
    InMemoryJobStore,
    JobManager,
    create_job_manager,
    DEFAULT_TTL_HOURS,
    PROCESSING_TIMEOUT_SECONDS,
)


# ============================================================
# InMemoryJobStore Tests
# ============================================================

class TestInMemoryJobStore:
    """Tests for InMemoryJobStore backend."""

    @pytest.fixture
    def store(self):
        return InMemoryJobStore()

    @pytest.fixture
    def sample_job(self):
        return JobRecord(file_name="test.pdf", engine=EngineType.DOCLING)

    @pytest.mark.asyncio
    async def test_create_job_stores_and_returns_id(self, store, sample_job):
        """create_job stores job and returns job_id."""
        job_id = await store.create_job(sample_job)
        assert job_id == sample_job.job_id
        stored = await store.get_job(job_id)
        assert stored is not None
        assert stored.file_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_get_job_returns_stored_job(self, store, sample_job):
        """get_job returns the stored job."""
        await store.create_job(sample_job)
        result = await store.get_job(sample_job.job_id)
        assert result is not None
        assert result.job_id == sample_job.job_id
        assert result.file_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_get_job_returns_none_for_unknown(self, store):
        """get_job returns None for unknown ID."""
        result = await store.get_job("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_job_modifies_fields(self, store, sample_job):
        """update_job modifies fields and calls touch()."""
        await store.create_job(sample_job)
        original_updated = sample_job.updated_at

        # Small delay to ensure timestamp changes
        await asyncio.sleep(0.01)
        await store.update_job(sample_job.job_id, status=JobStatus.PROCESSING)

        updated = await store.get_job(sample_job.job_id)
        assert updated.status == JobStatus.PROCESSING
        assert updated.updated_at >= original_updated

    @pytest.mark.asyncio
    async def test_update_job_unknown_id_no_raise(self, store):
        """update_job on unknown ID doesn't raise."""
        # Should not raise
        await store.update_job("nonexistent-id", status=JobStatus.FAILED)

    @pytest.mark.asyncio
    async def test_store_and_get_result_roundtrip(self, store, sample_job):
        """store_result and get_result round-trip."""
        await store.create_job(sample_job)
        result_data = {"pages": {"1": {"floorplans": []}}, "units": [], "tables": []}
        await store.store_result(sample_job.job_id, result_data)

        retrieved = await store.get_result(sample_job.job_id)
        assert retrieved is not None
        assert retrieved == result_data

    @pytest.mark.asyncio
    async def test_get_result_returns_none_for_unknown(self, store):
        """get_result returns None for unknown ID."""
        result = await store.get_result("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_expired_removes_completed(self, store):
        """delete_expired removes expired completed/failed/timeout jobs."""
        # Create expired completed job
        job1 = JobRecord(
            file_name="expired.pdf",
            status=JobStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.create_job(job1)
        await store.store_result(job1.job_id, {"data": "test"})

        # Create expired failed job
        job2 = JobRecord(
            file_name="failed.pdf",
            status=JobStatus.FAILED,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.create_job(job2)

        # Create expired timeout job
        job3 = JobRecord(
            file_name="timeout.pdf",
            status=JobStatus.TIMEOUT,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.create_job(job3)

        count = await store.delete_expired()
        assert count == 3

        # Verify all removed
        assert await store.get_job(job1.job_id) is None
        assert await store.get_job(job2.job_id) is None
        assert await store.get_job(job3.job_id) is None

    @pytest.mark.asyncio
    async def test_delete_expired_keeps_queued_processing(self, store):
        """delete_expired does NOT remove queued/processing jobs even if expired."""
        job_queued = JobRecord(
            file_name="queued.pdf",
            status=JobStatus.QUEUED,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        job_processing = JobRecord(
            file_name="processing.pdf",
            status=JobStatus.PROCESSING,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.create_job(job_queued)
        await store.create_job(job_processing)

        count = await store.delete_expired()
        assert count == 0

        # Both should still exist
        assert await store.get_job(job_queued.job_id) is not None
        assert await store.get_job(job_processing.job_id) is not None

    @pytest.mark.asyncio
    async def test_delete_expired_removes_associated_results(self, store):
        """delete_expired also removes associated results."""
        job = JobRecord(
            file_name="expired.pdf",
            status=JobStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await store.create_job(job)
        await store.store_result(job.job_id, {"data": "test"})

        await store.delete_expired()
        assert await store.get_result(job.job_id) is None

    @pytest.mark.asyncio
    async def test_list_jobs_returns_all(self, store):
        """list_jobs returns all jobs."""
        job1 = JobRecord(file_name="a.pdf")
        job2 = JobRecord(file_name="b.pdf")
        await store.create_job(job1)
        await store.create_job(job2)

        jobs = await store.list_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, store):
        """list_jobs with status filter works."""
        job1 = JobRecord(file_name="a.pdf", status=JobStatus.QUEUED)
        job2 = JobRecord(file_name="b.pdf", status=JobStatus.COMPLETED)
        job3 = JobRecord(file_name="c.pdf", status=JobStatus.QUEUED)
        await store.create_job(job1)
        await store.create_job(job2)
        await store.create_job(job3)

        queued = await store.list_jobs(status=JobStatus.QUEUED)
        assert len(queued) == 2

        completed = await store.list_jobs(status=JobStatus.COMPLETED)
        assert len(completed) == 1


# ============================================================
# JobManager Tests
# ============================================================

class TestJobManager:
    """Tests for JobManager facade."""

    @pytest.fixture
    def store(self):
        return InMemoryJobStore()

    @pytest.fixture
    def manager(self, store):
        return JobManager(store=store)

    @pytest.fixture
    def sample_result_data(self):
        """Dict matching HybridOutput structure with pages, units, tables."""
        return {
            "engine": "hybrid",
            "pages": {
                "1": {
                    "page_number": 1,
                    "floorplans": [{"image": "base64..."}],
                    "tables": ["| Col1 | Col2 |\n|---|---|\n| A | B |"],
                    "classification": "floorplan",
                },
                "2": {
                    "page_number": 2,
                    "floorplans": [{"image": "base64..."}, {"image": "base64..."}],
                    "tables": [],
                    "classification": "floorplan",
                },
            },
            "units": [
                {
                    "unit_number": "101",
                    "rooms": [
                        {"name": "Bedroom", "baseboard_length_ft": 42.0},
                        {"name": "Kitchen", "baseboard_length_ft": 30.0},
                    ],
                    "doors": [{"type": "interior"}, {"type": "closet"}],
                    "windows": [{"type": "double-hung"}],
                    "upgrades": [
                        {"trade": "electrical", "description": "Replace outlets"},
                        {"trade": "plumbing", "description": "Fix pipes"},
                    ],
                },
                {
                    "unit_number": "102",
                    "rooms": [
                        {"name": "Living Room", "baseboard_length_ft": 55.0},
                    ],
                    "doors": [{"type": "exterior"}],
                    "windows": [{"type": "casement"}, {"type": "fixed"}],
                    "upgrades": [
                        {"trade": "electrical", "description": "New panel"},
                    ],
                },
            ],
            "tables": [{"name": "Schedule A", "data": []}],
            "footer_sample": {"text": "Page footer"},
        }

    # ---- create_job ----

    @pytest.mark.asyncio
    async def test_create_job_returns_queued_status(self, manager):
        """create_job returns JobRecord with QUEUED status (Priority 4c fix)."""
        job = await manager.create_job(file_name="test.pdf")
        assert job.status == JobStatus.QUEUED
        assert job.status != JobStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_create_job_sets_file_name_and_engine(self, manager):
        """create_job sets correct file_name and engine."""
        job = await manager.create_job(file_name="plan.pdf", engine="hybrid")
        assert job.file_name == "plan.pdf"
        assert job.engine == "hybrid"

    @pytest.mark.asyncio
    async def test_create_job_sets_expires_at(self, manager):
        """create_job sets expires_at based on ttl_hours."""
        before = datetime.now(timezone.utc)
        job = await manager.create_job(file_name="test.pdf", ttl_hours=5)
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(hours=5)
        expected_max = after + timedelta(hours=5)
        assert expected_min <= job.expires_at <= expected_max

    @pytest.mark.asyncio
    async def test_create_job_default_ttl(self, manager):
        """create_job uses DEFAULT_TTL_HOURS when not specified."""
        before = datetime.now(timezone.utc)
        job = await manager.create_job(file_name="test.pdf")
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(hours=DEFAULT_TTL_HOURS)
        expected_max = after + timedelta(hours=DEFAULT_TTL_HOURS)
        assert expected_min <= job.expires_at <= expected_max

    # ---- start_processing ----

    @pytest.mark.asyncio
    async def test_start_processing_transitions_status(self, manager):
        """start_processing transitions to PROCESSING."""
        job = await manager.create_job(file_name="test.pdf")
        assert job.status == JobStatus.QUEUED

        await manager.start_processing(job.job_id)
        status = await manager.get_status(job.job_id)
        assert status.status == JobStatus.PROCESSING

    # ---- update_progress ----

    @pytest.mark.asyncio
    async def test_update_progress_updates_fields(self, manager):
        """update_progress updates phase, page, step, floorplans, tables."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.start_processing(job.job_id)

        await manager.update_progress(
            job.job_id,
            phase=ProcessingPhase.LLM_ANALYSIS,
            current_page=3,
            total_pages=10,
            current_step="Analyzing page 3",
            floorplans_found=2,
            tables_found=1,
        )

        status = await manager.get_status(job.job_id)
        assert status.progress.current_phase == ProcessingPhase.LLM_ANALYSIS
        assert status.progress.current_page == 3
        assert status.progress.total_pages == 10
        assert status.progress.current_step == "Analyzing page 3"
        assert status.progress.floorplans_found == 2
        assert status.progress.tables_found == 1

    @pytest.mark.asyncio
    async def test_update_progress_auto_calculates_percent(self, manager):
        """update_progress auto-calculates percent_complete."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.start_processing(job.job_id)

        await manager.update_progress(
            job.job_id,
            phase=ProcessingPhase.CLASSIFICATION,
        )

        status = await manager.get_status(job.job_id)
        # CLASSIFICATION phase weight is 0.25 -> 25.0%
        assert status.progress.percent_complete == 25.0

    @pytest.mark.asyncio
    async def test_update_progress_nonexistent_job_no_raise(self, manager):
        """update_progress on non-existent job doesn't raise."""
        # Should not raise
        await manager.update_progress(
            "nonexistent-id",
            phase=ProcessingPhase.LLM_ANALYSIS,
        )

    # ---- complete_job ----

    @pytest.mark.asyncio
    async def test_complete_job_stores_result(self, manager, sample_result_data):
        """complete_job stores result and sets COMPLETED status."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.start_processing(job.job_id)
        await manager.complete_job(job.job_id, sample_result_data)

        status = await manager.get_status(job.job_id)
        assert status.status == JobStatus.COMPLETED

        result = await manager.get_result(job.job_id)
        assert result is not None
        assert result == sample_result_data

    @pytest.mark.asyncio
    async def test_complete_job_sets_100_percent(self, manager, sample_result_data):
        """complete_job sets progress to 100%."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.complete_job(job.job_id, sample_result_data)

        status = await manager.get_status(job.job_id)
        assert status.progress.percent_complete == 100.0
        assert status.progress.current_phase == ProcessingPhase.COMPLETE

    # ---- fail_job ----

    @pytest.mark.asyncio
    async def test_fail_job_sets_failed_status(self, manager):
        """fail_job sets FAILED status with error message."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.fail_job(job.job_id, "PDF parsing error")

        status = await manager.get_status(job.job_id)
        assert status.status == JobStatus.FAILED
        assert status.error == "PDF parsing error"

    # ---- timeout_job ----

    @pytest.mark.asyncio
    async def test_timeout_job_sets_timeout_status(self, manager):
        """timeout_job sets TIMEOUT status with timeout message."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.timeout_job(job.job_id)

        status = await manager.get_status(job.job_id)
        assert status.status == JobStatus.TIMEOUT
        assert str(PROCESSING_TIMEOUT_SECONDS) in status.error

    # ---- get_status ----

    @pytest.mark.asyncio
    async def test_get_status_returns_status_response(self, manager):
        """get_status returns StatusResponse (never includes result data)."""
        job = await manager.create_job(file_name="test.pdf")
        status = await manager.get_status(job.job_id)

        assert isinstance(status, StatusResponse)
        assert status.job_id == job.job_id
        assert status.status == JobStatus.QUEUED
        assert status.file_name == "test.pdf"
        # StatusResponse has no result field
        assert not hasattr(status, "result") or getattr(status, "result", None) is None

    @pytest.mark.asyncio
    async def test_get_status_returns_none_for_unknown(self, manager):
        """get_status returns None for unknown job."""
        result = await manager.get_status("nonexistent-id")
        assert result is None

    # ---- get_result ----

    @pytest.mark.asyncio
    async def test_get_result_returns_stored_data(self, manager, sample_result_data):
        """get_result returns stored result data."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.complete_job(job.job_id, sample_result_data)

        result = await manager.get_result(job.job_id)
        assert result == sample_result_data

    @pytest.mark.asyncio
    async def test_get_result_returns_none_for_unknown(self, manager):
        """get_result returns None for unknown job."""
        result = await manager.get_result("nonexistent-id")
        assert result is None

    # ---- get_result_summary ----

    @pytest.mark.asyncio
    async def test_get_result_summary_correct_counts(self, manager, sample_result_data):
        """get_result_summary calculates correct counts from result data."""
        job = await manager.create_job(file_name="test.pdf")
        await manager.complete_job(job.job_id, sample_result_data)

        summary = await manager.get_result_summary(job.job_id)
        assert isinstance(summary, ResultSummary)
        assert summary.pages_count == 2  # 2 pages
        assert summary.floorplans_count == 3  # 1 + 2 floorplans
        assert summary.tables_count == 1  # 1 table
        assert summary.units_count == 2  # 2 units
        assert summary.has_footer is True  # footer_sample present
        assert summary.total_doors == 3  # 2 + 1 doors
        assert summary.total_windows == 3  # 1 + 2 windows
        assert summary.total_baseboard_ft == 127.0  # 42 + 30 + 55
        assert set(summary.trades) == {"electrical", "plumbing"}

    @pytest.mark.asyncio
    async def test_get_result_summary_returns_none_when_no_result(self, manager):
        """get_result_summary returns None when no result."""
        job = await manager.create_job(file_name="test.pdf")
        summary = await manager.get_result_summary(job.job_id)
        assert summary is None

    # ---- Full Lifecycle Tests ----

    @pytest.mark.asyncio
    async def test_full_success_lifecycle(self, manager, sample_result_data):
        """Full lifecycle: create -> start -> progress -> complete -> status -> result."""
        # Create
        job = await manager.create_job(file_name="plan.pdf", engine="hybrid")
        assert job.status == JobStatus.QUEUED

        # Start processing
        await manager.start_processing(job.job_id)
        status = await manager.get_status(job.job_id)
        assert status.status == JobStatus.PROCESSING

        # Progress updates
        await manager.update_progress(
            job.job_id,
            phase=ProcessingPhase.DOCLING_CONVERSION,
            total_pages=5,
        )
        status = await manager.get_status(job.job_id)
        assert status.progress.current_phase == ProcessingPhase.DOCLING_CONVERSION
        assert status.progress.total_pages == 5

        await manager.update_progress(
            job.job_id,
            phase=ProcessingPhase.LLM_ANALYSIS,
            current_page=3,
            floorplans_found=2,
        )
        status = await manager.get_status(job.job_id)
        assert status.progress.floorplans_found == 2

        # Complete
        await manager.complete_job(job.job_id, sample_result_data)
        status = await manager.get_status(job.job_id)
        assert status.status == JobStatus.COMPLETED
        assert status.progress.percent_complete == 100.0

        # Get result
        result = await manager.get_result(job.job_id)
        assert result == sample_result_data

    @pytest.mark.asyncio
    async def test_full_failure_lifecycle(self, manager):
        """Full failure lifecycle: create -> start -> fail -> status shows error."""
        job = await manager.create_job(file_name="bad.pdf")
        await manager.start_processing(job.job_id)
        await manager.fail_job(job.job_id, "Corrupt PDF file")

        status = await manager.get_status(job.job_id)
        assert status.status == JobStatus.FAILED
        assert status.error == "Corrupt PDF file"

    # ---- list_jobs ----

    @pytest.mark.asyncio
    async def test_list_jobs(self, manager):
        """list_jobs returns all jobs."""
        await manager.create_job(file_name="a.pdf")
        await manager.create_job(file_name="b.pdf")

        jobs = await manager.list_jobs()
        assert len(jobs) == 2


# ============================================================
# create_job_manager Factory Tests
# ============================================================

class TestCreateJobManager:
    """Tests for create_job_manager factory function."""

    def test_default_creates_memory_store(self):
        """Default creates InMemoryJobStore."""
        manager = create_job_manager()
        assert isinstance(manager._store, InMemoryJobStore)

    def test_memory_backend_creates_memory_store(self):
        """'memory' backend creates InMemoryJobStore."""
        manager = create_job_manager(backend="memory")
        assert isinstance(manager._store, InMemoryJobStore)

    def test_supabase_without_credentials_falls_back(self):
        """'supabase' without credentials falls back to InMemoryJobStore."""
        manager = create_job_manager(backend="supabase")
        assert isinstance(manager._store, InMemoryJobStore)

    def test_supabase_with_partial_credentials_falls_back(self):
        """'supabase' with only URL falls back to InMemoryJobStore."""
        manager = create_job_manager(
            backend="supabase",
            supabase_url="https://example.supabase.co",
        )
        assert isinstance(manager._store, InMemoryJobStore)

    def test_supabase_fallback_logs_warning(self, caplog):
        """'supabase' fallback logs a warning."""
        with caplog.at_level(logging.WARNING):
            create_job_manager(backend="supabase")
        assert "falling back" in caplog.text.lower() or "missing" in caplog.text.lower()
