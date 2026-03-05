"""Shared data models for doc-parser service.

Provides Pydantic models for job tracking, extraction results,
and API response schemas across all engine modes.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from enum import Enum
from datetime import datetime, timedelta, timezone
import uuid


# ============================================================
# Job State Machine
# ============================================================

class JobStatus(str, Enum):
    """Job lifecycle states: queued -> processing -> completed|failed|timeout."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ProcessingPhase(str, Enum):
    """Granular processing phases for progress tracking."""
    QUEUED = "queued"
    DOCLING_CONVERSION = "docling_conversion"
    CLASSIFICATION = "classification"
    IMAGE_EXTRACTION = "image_extraction"
    LLM_ANALYSIS = "llm_analysis"
    SYNTHESIS = "synthesis"
    UPLOADING = "uploading"
    COMPLETE = "complete"


class EngineType(str, Enum):
    """Available parsing engine modes."""
    DOCLING = "docling"
    HYBRID = "hybrid"


# ============================================================
# Job Tracking Models
# ============================================================

class JobProgress(BaseModel):
    """Real-time progress tracking for background jobs."""
    current_phase: ProcessingPhase = ProcessingPhase.QUEUED
    phases: List[str] = Field(default_factory=lambda: [
        "docling_conversion", "classification", "image_extraction",
        "llm_analysis", "synthesis", "uploading"
    ])
    current_page: int = 0
    total_pages: int = 0
    current_step: str = "initializing"
    floorplans_found: int = 0
    tables_found: int = 0
    percent_complete: float = 0.0

    def update_percent(self):
        """Calculate percent complete based on phase progression."""
        phase_weights = {
            ProcessingPhase.QUEUED: 0.0,
            ProcessingPhase.DOCLING_CONVERSION: 0.15,
            ProcessingPhase.CLASSIFICATION: 0.25,
            ProcessingPhase.IMAGE_EXTRACTION: 0.40,
            ProcessingPhase.LLM_ANALYSIS: 0.70,
            ProcessingPhase.SYNTHESIS: 0.85,
            ProcessingPhase.UPLOADING: 0.95,
            ProcessingPhase.COMPLETE: 1.0,
        }
        base = phase_weights.get(self.current_phase, 0.0)
        # Add page-level granularity within LLM_ANALYSIS phase
        if self.current_phase == ProcessingPhase.LLM_ANALYSIS and self.total_pages > 0:
            page_progress = self.current_page / self.total_pages
            phase_range = phase_weights[ProcessingPhase.SYNTHESIS] - phase_weights[ProcessingPhase.LLM_ANALYSIS]
            base = phase_weights[ProcessingPhase.LLM_ANALYSIS] + (page_progress * phase_range)
        self.percent_complete = round(base * 100, 1)


class JobRecord(BaseModel):
    """Complete job record for persistence."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED
    engine: EngineType = EngineType.DOCLING
    file_name: str = ""
    progress: JobProgress = Field(default_factory=JobProgress)
    result_ref: Optional[str] = None  # Storage path for results (not inline)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=2)
    )

    def touch(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)


# ============================================================
# API Response Models (Priority 4a: Separate Status from Results)
# ============================================================

class StatusResponse(BaseModel):
    """Lightweight status response for polling - NEVER includes result data.

    This is the response for GET /status/{job_id}.
    Safe to poll every 2-5 seconds. Small payload.
    """
    job_id: str
    status: JobStatus
    engine: str
    file_name: str
    progress: JobProgress
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ResultSummary(BaseModel):
    """Lightweight result summary for GET /results/{job_id}?summary=true."""
    pages_count: int = 0
    floorplans_count: int = 0
    tables_count: int = 0
    units_count: int = 0
    has_footer: bool = False
    total_doors: int = 0
    total_windows: int = 0
    total_baseboard_ft: float = 0.0
    trades: List[str] = Field(default_factory=list)


# ============================================================
# Extraction Data Models (Priority 1: Aligned with ParsedDocument)
# ============================================================

class Room(BaseModel):
    """Per-room extraction matching claudePdfParser granularity."""
    name: str = ""
    area_sf: float = 0.0
    length_ft: float = 0.0
    width_ft: float = 0.0
    ceiling_height_ft: float = 0.0
    baseboard_length_ft: float = 0.0
    baseboard_exclusions: List[str] = Field(default_factory=list)
    baseboard_exclusion_reasoning: str = ""
    fixtures: List[str] = Field(default_factory=list)
    flooring_type: str = ""
    notes: str = ""


class DoorSpec(BaseModel):
    """Individual door specification matching claudePdfParser detail."""
    location: str = ""  # "Master Bedroom to Hallway"
    room: str = ""  # Room the door belongs to
    type: str = ""  # "interior", "exterior", "closet", "pocket", "barn", "french"
    width_in: float = 0.0
    height_in: float = 0.0
    hardware: str = ""  # "lever", "knob", "pull", "push plate"
    action: str = ""  # "swing", "slide", "fold", "pivot"
    swing_direction: str = ""  # "in", "out", "left", "right"
    material: str = ""  # "hollow-core", "solid-core", "glass"
    notes: str = ""


class WindowSpec(BaseModel):
    """Individual window specification matching claudePdfParser detail."""
    location: str = ""  # "Living Room - North Wall"
    room: str = ""
    type: str = ""  # "single-hung", "double-hung", "casement", "fixed", "sliding"
    width_in: float = 0.0
    height_in: float = 0.0
    sill_height_in: float = 0.0
    count: int = 1
    glazing: str = ""  # "single", "double", "triple", "low-e"
    operable: bool = True
    notes: str = ""


class Fixture(BaseModel):
    """Fixture specification per room."""
    name: str = ""
    room: str = ""
    type: str = ""  # "plumbing", "electrical", "hvac", "appliance"
    specifications: str = ""
    count: int = 1


class Upgrade(BaseModel):
    """Renovation scope item by trade."""
    description: str = ""
    trade: str = ""  # "electrical", "plumbing", "hvac", "carpentry", "painting"
    location: str = ""
    specifications: str = ""
    estimated_hours: float = 0.0


class UnitExtraction(BaseModel):
    """Unit-oriented extraction compatible with ParsedDocument schema.

    This is the primary output format for the hybrid engine,
    directly consumable by the work-orders frontend.
    """
    unit_number: str = ""
    unit_type: str = "unknown"  # "1BR", "2BR", "studio", etc.
    floor: int = 0
    bedrooms: int = 0
    bathrooms: int = 0
    half_baths: int = 0
    area_sf: float = 0.0
    rooms: List[Room] = Field(default_factory=list)
    doors: List[DoorSpec] = Field(default_factory=list)
    windows: List[WindowSpec] = Field(default_factory=list)
    fixtures: List[Fixture] = Field(default_factory=list)
    upgrades: List[Upgrade] = Field(default_factory=list)
    general_notes: List[str] = Field(default_factory=list)
    source_page: int = 0


# ============================================================
# Confidence Scoring (Priority 6)
# ============================================================

class ConfidenceScore(BaseModel):
    """Completeness and confidence metrics for extraction results."""
    overall: float = 0.0  # 0.0 - 1.0
    room_dimensions: bool = False
    door_specifications: bool = False
    window_specifications: bool = False
    fixture_completeness: bool = False
    cross_page_synthesis: bool = False
    baseboard_data: bool = False
    unit_identification: bool = False
    per_page: Dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Output Models
# ============================================================

class PageData(BaseModel):
    """Per-page extraction data (page-oriented format)."""
    page_number: int = 0
    full_page_image: Optional[str] = None  # URL or base64
    floorplans: List[Dict[str, Any]] = Field(default_factory=list)
    tables: List[str] = Field(default_factory=list)  # Markdown tables
    site_photos: List[str] = Field(default_factory=list)
    diagrams: List[str] = Field(default_factory=list)
    classification: str = "unknown"


class HybridOutput(BaseModel):
    """Complete output from hybrid pipeline.

    Contains BOTH page-oriented and unit-oriented formats:
    - pages: for doc-parser native consumers
    - units: for direct ParsedDocument compatibility (work-orders)
    """
    engine: str = "hybrid"
    pages: Dict[int, Any] = Field(default_factory=dict)
    units: List[UnitExtraction] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)
    footer_sample: Optional[Dict[str, Any]] = None
    general_notes: List[str] = Field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    confidence: Optional[ConfidenceScore] = None
    summary: Optional[ResultSummary] = None
