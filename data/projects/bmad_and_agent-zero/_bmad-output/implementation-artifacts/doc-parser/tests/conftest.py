"""Shared pytest fixtures for doc-parser unit tests."""
import sys
import os
import pytest

# Add parent directory to path so we can import doc-parser modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import (
    Room, DoorSpec, WindowSpec, Fixture, Upgrade, UnitExtraction,
    JobRecord, JobProgress, JobStatus, ProcessingPhase, EngineType,
    ConfidenceScore, HybridOutput, PageData, StatusResponse, ResultSummary,
)


@pytest.fixture
def sample_room():
    """Room with full data including area, dimensions, baseboard, fixtures, flooring."""
    return Room(
        name="Master Bedroom",
        area_sf=180.0,
        length_ft=15.0,
        width_ft=12.0,
        ceiling_height_ft=9.0,
        baseboard_length_ft=42.0,
        baseboard_exclusions=["closet opening", "doorway"],
        baseboard_exclusion_reasoning="Closet opening 6ft, doorway 3ft subtracted from perimeter",
        fixtures=["ceiling fan", "recessed lights"],
        flooring_type="hardwood",
        notes="South-facing windows",
    )


@pytest.fixture
def sample_room_minimal():
    """Room with only a name, all other fields at defaults."""
    return Room(name="Closet")


@pytest.fixture
def sample_door():
    """DoorSpec with full data."""
    return DoorSpec(
        location="Master Bedroom to Hallway",
        room="Master Bedroom",
        type="interior",
        width_in=36.0,
        height_in=80.0,
        hardware="lever",
        action="swing",
        swing_direction="in",
        material="solid-core",
        notes="6-panel design",
    )


@pytest.fixture
def sample_window():
    """WindowSpec with full data."""
    return WindowSpec(
        location="Living Room - North Wall",
        room="Living Room",
        type="double-hung",
        width_in=36.0,
        height_in=60.0,
        sill_height_in=30.0,
        count=2,
        glazing="double",
        operable=True,
        notes="Egress compliant",
    )


@pytest.fixture
def sample_fixture():
    """Fixture with full data."""
    return Fixture(
        name="Toilet",
        room="Bathroom",
        type="plumbing",
        specifications="Kohler Wellworth, elongated, 1.28 GPF",
        count=1,
    )


@pytest.fixture
def sample_unit_complete(sample_room, sample_door, sample_window, sample_fixture):
    """UnitExtraction with rooms, doors, windows, fixtures, upgrades."""
    return UnitExtraction(
        unit_number="101",
        unit_type="2BR",
        floor=1,
        bedrooms=2,
        bathrooms=1,
        half_baths=0,
        area_sf=850.0,
        rooms=[sample_room, Room(name="Kitchen", area_sf=120.0, length_ft=10.0, width_ft=12.0)],
        doors=[sample_door],
        windows=[sample_window],
        fixtures=[sample_fixture],
        upgrades=[
            Upgrade(
                description="Replace all outlets",
                trade="electrical",
                location="Throughout unit",
                specifications="20A GFCI in kitchen/bath",
                estimated_hours=4.0,
            )
        ],
        general_notes=["All work per 2024 NEC"],
        source_page=3,
    )


@pytest.fixture
def sample_unit_sparse():
    """UnitExtraction with minimal data."""
    return UnitExtraction(
        unit_number="unknown",
        rooms=[Room(name="Room 1"), Room(name="Room 2")],
    )


@pytest.fixture
def sample_unit_dict_complete():
    """Complete unit as a dict for confidence.py functions."""
    return {
        "unit_number": "101",
        "unit_type": "2BR",
        "floor": 1,
        "area_sf": 850.0,
        "source_page": 3,
        "rooms": [
            {
                "name": "Master Bedroom",
                "area_sf": 180.0,
                "length_ft": 15.0,
                "width_ft": 12.0,
                "baseboard_length_ft": 42.0,
                "baseboard_exclusions": ["closet opening", "doorway"],
            },
            {
                "name": "Kitchen",
                "area_sf": 120.0,
                "length_ft": 10.0,
                "width_ft": 12.0,
                "baseboard_length_ft": 30.0,
                "baseboard_exclusions": ["kitchen cabinets"],
            },
        ],
        "doors": [
            {
                "type": "interior",
                "width_in": 36.0,
                "height_in": 80.0,
                "hardware": "lever",
            },
            {
                "type": "closet",
                "width_in": 30.0,
                "height_in": 80.0,
                "hardware": "knob",
            },
        ],
        "windows": [
            {
                "type": "double-hung",
                "width_in": 36.0,
                "height_in": 60.0,
            },
        ],
        "fixtures": [
            {
                "name": "Toilet",
                "type": "plumbing",
                "specifications": "Kohler 1.28 GPF",
            },
        ],
        "upgrades": [],
        "general_notes": ["All work per 2024 NEC"],
    }


@pytest.fixture
def sample_unit_dict_sparse():
    """Sparse unit as a dict for confidence.py functions."""
    return {
        "unit_number": "unknown",
        "unit_type": "unknown",
        "rooms": [
            {"name": "Room 1"},
            {"name": "Room 2"},
        ],
        "doors": [],
        "windows": [],
        "fixtures": [],
    }


@pytest.fixture
def sample_job_record():
    """JobRecord with defaults."""
    return JobRecord(file_name="test-floorplan.pdf")


@pytest.fixture
def sample_job_progress():
    """JobProgress with defaults."""
    return JobProgress()


# ============================================================
# Phase 2 Fixtures - Detection & Job Manager
# ============================================================

from job_manager import InMemoryJobStore, JobManager


@pytest.fixture
def in_memory_store():
    """Fresh InMemoryJobStore instance."""
    return InMemoryJobStore()


@pytest.fixture
def job_manager():
    """JobManager with InMemoryJobStore."""
    store = InMemoryJobStore()
    return JobManager(store=store)


@pytest.fixture
def sample_result_data():
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


# ============================================================
# Phase 3 Fixtures - Hybrid Pipeline & Server Tests
# ============================================================

from PIL import Image


@pytest.fixture
def mock_pil_image():
    """Simple PIL Image for testing."""
    return Image.new("RGB", (800, 600), "white")


@pytest.fixture
def sample_extraction_success():
    """Successful extraction dict as returned by LLM analysis."""
    return {
        "page_no": 1,
        "success": True,
        "data": {
            "unit_number": "101",
            "unit_type": "2BR",
            "floor": 1,
            "bedrooms": 2,
            "bathrooms": 1,
            "half_baths": 0,
            "total_area_sf": 850.0,
            "rooms": [
                {"name": "Living Room", "area_sf": 200, "baseboard_length_ft": 45},
                {"name": "Kitchen", "area_sf": 120, "baseboard_length_ft": 30},
            ],
            "doors": [
                {"location": "Entry", "type": "exterior"},
                {"location": "Bedroom", "type": "interior"},
            ],
            "windows": [
                {"location": "Living Room", "type": "double-hung"},
            ],
            "fixtures": [
                {"name": "Toilet", "room": "Bathroom", "type": "plumbing"},
            ],
            "upgrades": [
                {"description": "Replace flooring", "trade": "flooring"},
            ],
            "general_notes": ["All work per code"],
        },
    }


@pytest.fixture
def sample_extraction_failure():
    """Failed extraction dict."""
    return {
        "page_no": 2,
        "success": False,
        "error": "LLM failed to parse floorplan",
    }


@pytest.fixture
def sample_table_data():
    """List of (page_no, markdown) tuples for table data."""
    return [
        (3, "| Door | Type | Width |\n|---|---|---|\n| D1 | Interior | 36in |"),
        (4, "| Window | Type | Size |\n|---|---|---|\n| W1 | Double-hung | 36x60 |"),
    ]


# ============================================================
# Phase 3 Fixtures
# ============================================================

@pytest.fixture
def mock_pil_image():
    """Simple PIL Image for testing."""
    from PIL import Image
    return Image.new("RGB", (800, 600), "white")


@pytest.fixture
def sample_extraction_success():
    """Successful extraction dict."""
    return {
        "page_no": 1,
        "success": True,
        "data": {
            "unit_number": "101",
            "unit_type": "2BR",
            "floor": 1,
            "bedrooms": 2,
            "bathrooms": 1,
            "total_area_sf": 850.0,
            "rooms": [{"name": "Living Room", "area_sf": 200, "baseboard_length_ft": 45}],
            "doors": [{"location": "Entry", "type": "exterior"}],
            "windows": [{"location": "Living Room", "type": "double-hung"}],
            "fixtures": [{"name": "Toilet", "room": "Bathroom", "type": "plumbing"}],
            "upgrades": [{"description": "Replace flooring", "trade": "flooring"}],
            "general_notes": ["All work per code"],
        },
    }


@pytest.fixture
def sample_extraction_failure():
    """Failed extraction dict."""
    return {
        "page_no": 2,
        "success": False,
        "error": "LLM failed to parse floorplan",
    }


@pytest.fixture
def sample_table_data():
    """List of (page_no, markdown) tuples."""
    return [
        (1, "| Unit | Type | Area |\n| --- | --- | --- |\n| 101 | 2BR | 850 |"),
        (3, "| Material | Qty |\n| --- | --- |\n| Drywall | 50 |"),
    ]
