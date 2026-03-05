"""Unit tests for doc-parser models.py.

Covers enums, job tracking models, extraction data models,
API response models, confidence scoring models, and output models.
"""
import sys
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import (
    JobStatus, ProcessingPhase, EngineType,
    JobProgress, JobRecord,
    Room, DoorSpec, WindowSpec, Fixture, Upgrade, UnitExtraction,
    StatusResponse, ResultSummary,
    ConfidenceScore, HybridOutput, PageData,
)


# ============================================================
# Enum Tests
# ============================================================

class TestJobStatus:
    """Tests for JobStatus enum values."""

    @pytest.mark.parametrize("member,value", [
        ("QUEUED", "queued"),
        ("PROCESSING", "processing"),
        ("COMPLETED", "completed"),
        ("FAILED", "failed"),
        ("TIMEOUT", "timeout"),
        ("CANCELLED", "cancelled"),
    ])
    def test_job_status_values(self, member, value):
        """Each JobStatus member has the expected string value."""
        assert JobStatus[member].value == value

    def test_job_status_is_str(self):
        """JobStatus members are strings."""
        for status in JobStatus:
            assert isinstance(status, str)
            assert isinstance(status.value, str)

    def test_job_status_count(self):
        """JobStatus has exactly 6 members."""
        assert len(JobStatus) == 6


class TestProcessingPhase:
    """Tests for ProcessingPhase enum values."""

    @pytest.mark.parametrize("member,value", [
        ("QUEUED", "queued"),
        ("DOCLING_CONVERSION", "docling_conversion"),
        ("CLASSIFICATION", "classification"),
        ("IMAGE_EXTRACTION", "image_extraction"),
        ("LLM_ANALYSIS", "llm_analysis"),
        ("SYNTHESIS", "synthesis"),
        ("UPLOADING", "uploading"),
        ("COMPLETE", "complete"),
    ])
    def test_processing_phase_values(self, member, value):
        """Each ProcessingPhase member has the expected string value."""
        assert ProcessingPhase[member].value == value

    def test_processing_phase_is_str(self):
        """ProcessingPhase members are strings."""
        for phase in ProcessingPhase:
            assert isinstance(phase, str)

    def test_processing_phase_count(self):
        """ProcessingPhase has exactly 8 members."""
        assert len(ProcessingPhase) == 8


class TestEngineType:
    """Tests for EngineType enum values."""

    @pytest.mark.parametrize("member,value", [
        ("DOCLING", "docling"),
        ("HYBRID", "hybrid"),
    ])
    def test_engine_type_values(self, member, value):
        """Each EngineType member has the expected value."""
        assert EngineType[member].value == value

    def test_engine_type_count(self):
        """EngineType has exactly 2 members."""
        assert len(EngineType) == 2


# ============================================================
# JobProgress Tests
# ============================================================

class TestJobProgress:
    """Tests for JobProgress model and update_percent logic."""

    def test_default_values(self, sample_job_progress):
        """JobProgress defaults are correct."""
        p = sample_job_progress
        assert p.current_phase == ProcessingPhase.QUEUED
        assert p.current_page == 0
        assert p.total_pages == 0
        assert p.current_step == "initializing"
        assert p.floorplans_found == 0
        assert p.tables_found == 0
        assert p.percent_complete == 0.0

    def test_default_phases_list(self):
        """Default phases list contains the expected phase names."""
        p = JobProgress()
        expected = [
            "docling_conversion", "classification", "image_extraction",
            "llm_analysis", "synthesis", "uploading",
        ]
        assert p.phases == expected

    @pytest.mark.parametrize("phase,expected_pct", [
        (ProcessingPhase.QUEUED, 0.0),
        (ProcessingPhase.DOCLING_CONVERSION, 15.0),
        (ProcessingPhase.CLASSIFICATION, 25.0),
        (ProcessingPhase.IMAGE_EXTRACTION, 40.0),
        (ProcessingPhase.LLM_ANALYSIS, 70.0),
        (ProcessingPhase.SYNTHESIS, 85.0),
        (ProcessingPhase.UPLOADING, 95.0),
        (ProcessingPhase.COMPLETE, 100.0),
    ])
    def test_update_percent_per_phase(self, phase, expected_pct):
        """update_percent returns correct percentage for each phase."""
        p = JobProgress(current_phase=phase)
        p.update_percent()
        assert p.percent_complete == expected_pct

    def test_update_percent_llm_analysis_page_interpolation(self):
        """During LLM_ANALYSIS, page progress interpolates between 40% and 70%."""
        p = JobProgress(
            current_phase=ProcessingPhase.LLM_ANALYSIS,
            current_page=3,
            total_pages=10,
        )
        p.update_percent()
        # LLM_ANALYSIS base = 0.70, SYNTHESIS = 0.85
        # page_progress = 3/10 = 0.3
        # phase_range = 0.85 - 0.70 = 0.15
        # base = 0.70 + (0.3 * 0.15) = 0.745
        # percent = 74.5
        assert p.percent_complete == 74.5
        assert 40.0 < p.percent_complete < 85.0

    def test_update_percent_llm_analysis_midpoint(self):
        """LLM_ANALYSIS at page 5/10 gives midpoint interpolation."""
        p = JobProgress(
            current_phase=ProcessingPhase.LLM_ANALYSIS,
            current_page=5,
            total_pages=10,
        )
        p.update_percent()
        # page_progress = 0.5, base = 0.70 + (0.5 * 0.15) = 0.775
        assert p.percent_complete == 77.5

    def test_update_percent_llm_analysis_zero_total_pages(self):
        """LLM_ANALYSIS with total_pages=0 doesn't divide by zero."""
        p = JobProgress(
            current_phase=ProcessingPhase.LLM_ANALYSIS,
            current_page=0,
            total_pages=0,
        )
        p.update_percent()
        # Falls through to base weight since total_pages == 0
        assert p.percent_complete == 70.0


# ============================================================
# JobRecord Tests
# ============================================================

class TestJobRecord:
    """Tests for JobRecord model."""

    def test_default_job_id_is_valid_uuid(self, sample_job_record):
        """Default job_id is a valid UUID string."""
        parsed = uuid.UUID(sample_job_record.job_id)
        assert str(parsed) == sample_job_record.job_id

    def test_default_status_is_queued(self, sample_job_record):
        """Default status is QUEUED."""
        assert sample_job_record.status == JobStatus.QUEUED

    def test_touch_updates_updated_at(self, sample_job_record):
        """touch() updates the updated_at timestamp."""
        original = sample_job_record.updated_at
        sample_job_record.touch()
        assert sample_job_record.updated_at >= original

    def test_expires_at_approximately_two_hours(self, sample_job_record):
        """expires_at is approximately 2 hours after created_at."""
        diff = sample_job_record.expires_at - sample_job_record.created_at
        # Allow 5 seconds tolerance for test execution time
        assert timedelta(hours=1, minutes=59, seconds=55) < diff < timedelta(hours=2, seconds=5)

    def test_two_records_have_different_uuids(self):
        """Two JobRecords have different UUIDs."""
        r1 = JobRecord(file_name="a.pdf")
        r2 = JobRecord(file_name="b.pdf")
        assert r1.job_id != r2.job_id

    def test_default_engine(self, sample_job_record):
        """Default engine is DOCLING."""
        assert sample_job_record.engine == EngineType.DOCLING


# ============================================================
# Pydantic Extraction Model Tests
# ============================================================

class TestRoom:
    """Tests for Room model."""

    def test_default_values(self):
        """Room defaults are all zero/empty."""
        r = Room()
        assert r.name == ""
        assert r.area_sf == 0.0
        assert r.length_ft == 0.0
        assert r.width_ft == 0.0
        assert r.ceiling_height_ft == 0.0
        assert r.baseboard_length_ft == 0.0
        assert r.baseboard_exclusions == []
        assert r.baseboard_exclusion_reasoning == ""
        assert r.fixtures == []
        assert r.flooring_type == ""
        assert r.notes == ""

    def test_full_construction(self, sample_room):
        """Room with all fields populated."""
        assert sample_room.name == "Master Bedroom"
        assert sample_room.area_sf == 180.0
        assert sample_room.length_ft == 15.0
        assert sample_room.width_ft == 12.0
        assert sample_room.baseboard_length_ft == 42.0
        assert len(sample_room.baseboard_exclusions) == 2
        assert len(sample_room.fixtures) == 2
        assert sample_room.flooring_type == "hardwood"

    def test_serialization_to_dict(self, sample_room):
        """Room serializes to dict correctly."""
        d = sample_room.model_dump()
        assert isinstance(d, dict)
        assert d["name"] == "Master Bedroom"
        assert d["area_sf"] == 180.0
        assert isinstance(d["baseboard_exclusions"], list)

    def test_list_fields_not_shared(self):
        """List fields default to independent empty lists."""
        r1 = Room()
        r2 = Room()
        r1.baseboard_exclusions.append("test")
        assert r2.baseboard_exclusions == []
        assert r1.baseboard_exclusions == ["test"]


class TestDoorSpec:
    """Tests for DoorSpec model."""

    def test_default_values(self):
        """DoorSpec defaults are all empty/zero."""
        d = DoorSpec()
        assert d.location == ""
        assert d.room == ""
        assert d.type == ""
        assert d.width_in == 0.0
        assert d.height_in == 0.0
        assert d.hardware == ""
        assert d.action == ""
        assert d.swing_direction == ""
        assert d.material == ""
        assert d.notes == ""

    def test_full_construction(self, sample_door):
        """DoorSpec with all fields populated."""
        assert sample_door.location == "Master Bedroom to Hallway"
        assert sample_door.type == "interior"
        assert sample_door.width_in == 36.0
        assert sample_door.hardware == "lever"

    def test_serialization_to_dict(self, sample_door):
        """DoorSpec serializes to dict."""
        d = sample_door.model_dump()
        assert isinstance(d, dict)
        assert d["type"] == "interior"


class TestWindowSpec:
    """Tests for WindowSpec model."""

    def test_default_values(self):
        """WindowSpec defaults are correct."""
        w = WindowSpec()
        assert w.location == ""
        assert w.room == ""
        assert w.type == ""
        assert w.width_in == 0.0
        assert w.height_in == 0.0
        assert w.sill_height_in == 0.0
        assert w.count == 1
        assert w.glazing == ""
        assert w.operable is True
        assert w.notes == ""

    def test_full_construction(self, sample_window):
        """WindowSpec with all fields populated."""
        assert sample_window.type == "double-hung"
        assert sample_window.width_in == 36.0
        assert sample_window.count == 2
        assert sample_window.glazing == "double"

    def test_serialization_to_dict(self, sample_window):
        """WindowSpec serializes to dict."""
        d = sample_window.model_dump()
        assert isinstance(d, dict)
        assert d["count"] == 2


class TestFixture:
    """Tests for Fixture model."""

    def test_default_values(self):
        """Fixture defaults are correct."""
        f = Fixture()
        assert f.name == ""
        assert f.room == ""
        assert f.type == ""
        assert f.specifications == ""
        assert f.count == 1

    def test_full_construction(self, sample_fixture):
        """Fixture with all fields populated."""
        assert sample_fixture.name == "Toilet"
        assert sample_fixture.type == "plumbing"
        assert sample_fixture.specifications == "Kohler Wellworth, elongated, 1.28 GPF"

    def test_serialization_to_dict(self, sample_fixture):
        """Fixture serializes to dict."""
        d = sample_fixture.model_dump()
        assert isinstance(d, dict)
        assert d["name"] == "Toilet"


class TestUpgrade:
    """Tests for Upgrade model."""

    def test_default_values(self):
        """Upgrade defaults are correct."""
        u = Upgrade()
        assert u.description == ""
        assert u.trade == ""
        assert u.location == ""
        assert u.specifications == ""
        assert u.estimated_hours == 0.0

    def test_full_construction(self):
        """Upgrade with all fields populated."""
        u = Upgrade(
            description="Install GFCI outlets",
            trade="electrical",
            location="Kitchen",
            specifications="20A GFCI",
            estimated_hours=2.5,
        )
        assert u.trade == "electrical"
        assert u.estimated_hours == 2.5


class TestUnitExtraction:
    """Tests for UnitExtraction model."""

    def test_default_values(self):
        """UnitExtraction defaults are correct."""
        u = UnitExtraction()
        assert u.unit_number == ""
        assert u.unit_type == "unknown"
        assert u.floor == 0
        assert u.bedrooms == 0
        assert u.bathrooms == 0
        assert u.half_baths == 0
        assert u.area_sf == 0.0
        assert u.rooms == []
        assert u.doors == []
        assert u.windows == []
        assert u.fixtures == []
        assert u.upgrades == []
        assert u.general_notes == []
        assert u.source_page == 0

    def test_full_construction(self, sample_unit_complete):
        """UnitExtraction with all nested data."""
        u = sample_unit_complete
        assert u.unit_number == "101"
        assert u.unit_type == "2BR"
        assert len(u.rooms) == 2
        assert len(u.doors) == 1
        assert len(u.windows) == 1
        assert len(u.fixtures) == 1
        assert len(u.upgrades) == 1
        assert len(u.general_notes) == 1

    def test_serialization_to_dict(self, sample_unit_complete):
        """UnitExtraction serializes to dict with nested models."""
        d = sample_unit_complete.model_dump()
        assert isinstance(d, dict)
        assert isinstance(d["rooms"], list)
        assert isinstance(d["rooms"][0], dict)
        assert d["rooms"][0]["name"] == "Master Bedroom"

    def test_list_fields_not_shared(self):
        """List fields default to independent empty lists."""
        u1 = UnitExtraction()
        u2 = UnitExtraction()
        u1.rooms.append(Room(name="test"))
        assert u2.rooms == []


# ============================================================
# API Response Model Tests
# ============================================================

class TestStatusResponse:
    """Tests for StatusResponse model."""

    def test_construction_with_required_fields(self):
        """StatusResponse can be constructed with required fields."""
        now = datetime.now(timezone.utc)
        sr = StatusResponse(
            job_id="abc-123",
            status=JobStatus.PROCESSING,
            engine="hybrid",
            file_name="test.pdf",
            progress=JobProgress(),
            created_at=now,
            updated_at=now,
        )
        assert sr.job_id == "abc-123"
        assert sr.status == JobStatus.PROCESSING
        assert sr.engine == "hybrid"

    def test_optional_error_defaults_none(self):
        """Optional error field defaults to None."""
        now = datetime.now(timezone.utc)
        sr = StatusResponse(
            job_id="abc",
            status=JobStatus.QUEUED,
            engine="docling",
            file_name="f.pdf",
            progress=JobProgress(),
            created_at=now,
            updated_at=now,
        )
        assert sr.error is None


class TestResultSummary:
    """Tests for ResultSummary model."""

    def test_default_values(self):
        """ResultSummary defaults are all zero/empty."""
        rs = ResultSummary()
        assert rs.pages_count == 0
        assert rs.floorplans_count == 0
        assert rs.tables_count == 0
        assert rs.units_count == 0
        assert rs.has_footer is False
        assert rs.total_doors == 0
        assert rs.total_windows == 0
        assert rs.total_baseboard_ft == 0.0
        assert rs.trades == []

    def test_construction_with_data(self):
        """ResultSummary with populated fields."""
        rs = ResultSummary(
            pages_count=10,
            floorplans_count=3,
            units_count=2,
            total_doors=15,
            trades=["electrical", "plumbing"],
        )
        assert rs.pages_count == 10
        assert len(rs.trades) == 2


# ============================================================
# ConfidenceScore Tests
# ============================================================

class TestConfidenceScore:
    """Tests for ConfidenceScore model."""

    def test_default_overall_is_zero(self):
        """Default overall is 0.0."""
        cs = ConfidenceScore()
        assert cs.overall == 0.0

    def test_all_boolean_flags_default_false(self):
        """All boolean flags default to False."""
        cs = ConfidenceScore()
        assert cs.room_dimensions is False
        assert cs.door_specifications is False
        assert cs.window_specifications is False
        assert cs.fixture_completeness is False
        assert cs.cross_page_synthesis is False
        assert cs.baseboard_data is False
        assert cs.unit_identification is False

    def test_per_page_defaults_empty_dict(self):
        """per_page defaults to empty dict."""
        cs = ConfidenceScore()
        assert cs.per_page == {}


# ============================================================
# HybridOutput Tests
# ============================================================

class TestHybridOutput:
    """Tests for HybridOutput model."""

    def test_default_engine_is_hybrid(self):
        """Default engine is 'hybrid'."""
        ho = HybridOutput()
        assert ho.engine == "hybrid"

    def test_all_collection_fields_default_empty(self):
        """All collection fields default to empty."""
        ho = HybridOutput()
        assert ho.pages == {}
        assert ho.units == []
        assert ho.tables == []
        assert ho.general_notes == []
        assert ho.footer_sample is None
        assert ho.synthesis is None
        assert ho.confidence is None
        assert ho.summary is None

    def test_full_construction_with_nested_data(self):
        """HybridOutput with nested data."""
        ho = HybridOutput(
            engine="hybrid",
            pages={1: {"classification": "floorplan"}},
            units=[UnitExtraction(unit_number="101")],
            tables=[{"table_type": "door_schedule"}],
            general_notes=["Note 1"],
            confidence=ConfidenceScore(overall=0.85),
            summary=ResultSummary(pages_count=5),
        )
        assert len(ho.units) == 1
        assert ho.units[0].unit_number == "101"
        assert ho.confidence.overall == 0.85
        assert ho.summary.pages_count == 5


# ============================================================
# PageData Tests
# ============================================================

class TestPageData:
    """Tests for PageData model."""

    def test_default_classification_is_unknown(self):
        """Default classification is 'unknown'."""
        pd = PageData()
        assert pd.classification == "unknown"

    def test_list_fields_default_empty(self):
        """List fields default to empty."""
        pd = PageData()
        assert pd.floorplans == []
        assert pd.tables == []
        assert pd.site_photos == []
        assert pd.diagrams == []

    def test_default_page_number(self):
        """Default page_number is 0."""
        pd = PageData()
        assert pd.page_number == 0

    def test_full_page_image_default_none(self):
        """full_page_image defaults to None."""
        pd = PageData()
        assert pd.full_page_image is None
