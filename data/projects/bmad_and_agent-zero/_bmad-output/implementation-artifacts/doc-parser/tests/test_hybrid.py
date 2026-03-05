"""Tests for hybrid.py - hybrid pipeline + output assembly."""
import os
import sys
import json
import asyncio
import tempfile
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image

# Ensure source dir is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hybrid import assemble_hybrid_output
from models import JobStatus, ProcessingPhase
from job_manager import JobManager, InMemoryJobStore


# ============================================================
# Helpers
# ============================================================

def make_extraction(page_no, success=True, unit_number="101", rooms=None, doors=None,
                    windows=None, fixtures=None, upgrades=None, general_notes=None):
    """Create a mock extraction result."""
    if success:
        return {
            "page_no": page_no,
            "success": True,
            "data": {
                "unit_number": unit_number,
                "unit_type": "2BR",
                "floor": 1,
                "bedrooms": 2,
                "bathrooms": 1,
                "total_area_sf": 850.0,
                "rooms": rooms or [{"name": "Living Room", "area_sf": 200, "baseboard_length_ft": 45}],
                "doors": doors or [{"location": "Entry", "type": "exterior"}],
                "windows": windows or [{"location": "Living Room", "type": "double-hung"}],
                "fixtures": fixtures or [{"name": "Toilet", "room": "Bathroom", "type": "plumbing"}],
                "upgrades": upgrades or [{"description": "Replace flooring", "trade": "flooring"}],
                "general_notes": general_notes or ["All work per code"],
            },
        }
    return {"page_no": page_no, "success": False, "error": "LLM failed"}


def make_pdf_pages(n=2):
    """Create a list of mock PIL images."""
    return [Image.new("RGB", (800, 600), "white") for _ in range(n)]


def make_floorplan_candidates(pages):
    """Create floorplan candidates list: (page_no, pil_img, b64)."""
    return [(i + 1, img, "base64data") for i, img in enumerate(pages)]


def _make_llm_response(data):
    """Create a mock litellm completion response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps(data)
    return mock_resp


async def _fake_to_thread(func, *args, **kwargs):
    """Replace asyncio.to_thread with direct sync call."""
    return func(*args, **kwargs)


# ============================================================
# Test: assemble_hybrid_output
# ============================================================

class TestAssembleHybridOutput:
    """Tests for assemble_hybrid_output pure function."""

    def test_empty_inputs(self):
        """Empty inputs produce empty units, pages, tables."""
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=[], synthesis=None,
        )
        assert result["units"] == []
        assert result["pages"] == {}
        assert result["tables"] == []

    def test_single_successful_extraction(self):
        """Single successful extraction appears in both pages and units."""
        pages = make_pdf_pages(1)
        ext = make_extraction(1)
        result = assemble_hybrid_output(
            unit_extractions=[ext], table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert len(result["units"]) == 1
        assert result["units"][0]["unit_number"] == "101"
        assert 1 in result["pages"]
        assert len(result["pages"][1]["floorplans"]) == 1

    def test_multiple_successful_extractions_different_pages(self):
        """Multiple extractions across different pages."""
        pages = make_pdf_pages(3)
        exts = [
            make_extraction(1, unit_number="101"),
            make_extraction(2, unit_number="102"),
            make_extraction(3, unit_number="103"),
        ]
        result = assemble_hybrid_output(
            unit_extractions=exts, table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert len(result["units"]) == 3
        unit_numbers = [u["unit_number"] for u in result["units"]]
        assert "101" in unit_numbers
        assert "102" in unit_numbers
        assert "103" in unit_numbers

    def test_failed_extraction_error_in_pages_not_in_units(self):
        """Failed extraction: error recorded in pages, NOT added to units."""
        pages = make_pdf_pages(1)
        ext = make_extraction(1, success=False)
        result = assemble_hybrid_output(
            unit_extractions=[ext], table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert len(result["units"]) == 0
        assert len(result["pages"][1]["floorplans"]) == 1
        assert "error" in result["pages"][1]["floorplans"][0]

    def test_mixed_success_failure(self):
        """Only successful extractions appear in units."""
        pages = make_pdf_pages(3)
        exts = [
            make_extraction(1, unit_number="101"),
            make_extraction(2, success=False),
            make_extraction(3, unit_number="103"),
        ]
        result = assemble_hybrid_output(
            unit_extractions=exts, table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert len(result["units"]) == 2
        unit_numbers = [u["unit_number"] for u in result["units"]]
        assert "101" in unit_numbers
        assert "103" in unit_numbers

    def test_table_data_in_tables_and_pages(self):
        """Table data appears in tables array and correct page."""
        pages = make_pdf_pages(2)
        table_data = [(1, "| Col1 | Col2 |\n| --- | --- |\n| A | B |")]
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=table_data, footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis=None,
        )
        assert len(result["tables"]) == 1
        assert result["tables"][0]["page_no"] == 1
        assert len(result["pages"][1]["tables"]) == 1

    def test_footer_sample_included_when_present(self):
        """Footer sample included when present."""
        pages = make_pdf_pages(1)
        footer = {"markdown": "footer text", "page_no": 1}
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=footer,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis=None,
        )
        assert result["footer_sample"] == footer
        assert result["summary"]["has_footer"] is True

    def test_footer_sample_none_when_absent(self):
        """Footer sample is None when absent."""
        pages = make_pdf_pages(1)
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis=None,
        )
        assert result["footer_sample"] is None
        assert result["summary"]["has_footer"] is False

    def test_site_photos_classification(self):
        """Site photos get correct page classification."""
        pages = make_pdf_pages(2)
        site_photos = [(2, pages[1])]
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=site_photos, diagrams=[],
            pdf_pages=pages, synthesis=None,
        )
        assert result["pages"][2]["classification"] == "site_photo"

    def test_diagrams_classification(self):
        """Diagrams get correct page classification."""
        pages = make_pdf_pages(2)
        diagrams = [(1, pages[0])]
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=diagrams,
            pdf_pages=pages, synthesis=None,
        )
        assert result["pages"][1]["classification"] == "diagram"

    def test_summary_counts(self):
        """Summary has correct counts for units, doors, windows, baseboard, trades."""
        pages = make_pdf_pages(2)
        exts = [
            make_extraction(
                1, unit_number="101",
                doors=[{"location": "A", "type": "ext"}, {"location": "B", "type": "int"}],
                windows=[{"location": "LR", "type": "dh"}],
            ),
            make_extraction(
                2, unit_number="102",
                doors=[{"location": "C", "type": "ext"}],
                windows=[{"location": "BR", "type": "sl"}, {"location": "K", "type": "cs"}],
            ),
        ]
        result = assemble_hybrid_output(
            unit_extractions=exts, table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert result["summary"]["units_count"] == 2
        assert result["summary"]["total_doors"] == 3
        assert result["summary"]["total_windows"] == 3
        assert result["summary"]["total_baseboard_ft"] == 90  # 45 * 2
        assert "flooring" in result["summary"]["trades"]

    def test_summary_extraction_errors_count(self):
        """Summary extraction_errors counts failures."""
        pages = make_pdf_pages(3)
        exts = [
            make_extraction(1),
            make_extraction(2, success=False),
            make_extraction(3, success=False),
        ]
        result = assemble_hybrid_output(
            unit_extractions=exts, table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert result["summary"]["extraction_errors"] == 2

    def test_summary_has_synthesis_true(self):
        """Summary has_synthesis is True when synthesis present without error."""
        pages = make_pdf_pages(1)
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis={"common_notes": ["test"]},
        )
        assert result["summary"]["has_synthesis"] is True

    def test_summary_has_synthesis_false_on_error(self):
        """Summary has_synthesis is False when synthesis has error."""
        pages = make_pdf_pages(1)
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis={"error": "failed"},
        )
        assert result["summary"]["has_synthesis"] is False

    def test_unit_fields_mapping(self):
        """total_area_sf maps to area_sf, source_page set."""
        pages = make_pdf_pages(1)
        ext = make_extraction(1)
        result = assemble_hybrid_output(
            unit_extractions=[ext], table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        unit = result["units"][0]
        assert unit["area_sf"] == 850.0
        assert unit["source_page"] == 1

    def test_unit_number_defaults_to_page_n(self):
        """unit_number defaults to page_N when not in data."""
        pages = make_pdf_pages(1)
        ext = {
            "page_no": 1,
            "success": True,
            "data": {
                "unit_type": "1BR", "floor": 1, "bedrooms": 1, "bathrooms": 1,
                "total_area_sf": 500.0, "rooms": [], "doors": [], "windows": [],
                "fixtures": [], "upgrades": [], "general_notes": [],
            },
        }
        result = assemble_hybrid_output(
            unit_extractions=[ext], table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert result["units"][0]["unit_number"] == "page_1"

    def test_general_notes_deduplicated(self):
        """General notes are deduplicated across units."""
        pages = make_pdf_pages(2)
        exts = [
            make_extraction(1, unit_number="101", general_notes=["Note A", "Note B"]),
            make_extraction(2, unit_number="102", general_notes=["Note B", "Note C"]),
        ]
        result = assemble_hybrid_output(
            unit_extractions=exts, table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert len(result["general_notes"]) == 3
        assert "Note A" in result["general_notes"]
        assert "Note B" in result["general_notes"]
        assert "Note C" in result["general_notes"]

    def test_page_classification_defaults_unknown(self):
        """Pages without specific content default to unknown classification."""
        pages = make_pdf_pages(2)
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis=None,
        )
        assert result["pages"][1]["classification"] == "unknown"
        assert result["pages"][2]["classification"] == "unknown"

    def test_floorplan_page_classification(self):
        """Floorplan pages marked as floorplan."""
        pages = make_pdf_pages(1)
        ext = make_extraction(1)
        result = assemble_hybrid_output(
            unit_extractions=[ext], table_data=[], footer_sample=None,
            floorplan_candidates=make_floorplan_candidates(pages),
            site_photos=[], diagrams=[], pdf_pages=pages, synthesis=None,
        )
        assert result["pages"][1]["classification"] == "floorplan"

    def test_table_page_classification(self):
        """Table pages marked as table when no other classification."""
        pages = make_pdf_pages(1)
        table_data = [(1, "| A |\n| - |\n| 1 |")]
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=table_data, footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis=None,
        )
        assert result["pages"][1]["classification"] == "table"

    def test_synthesis_data_passed_through(self):
        """Synthesis data is passed through to output."""
        pages = make_pdf_pages(1)
        synth = {"common_notes": ["All units similar"], "conflicts": []}
        result = assemble_hybrid_output(
            unit_extractions=[], table_data=[], footer_sample=None,
            floorplan_candidates=[], site_photos=[], diagrams=[],
            pdf_pages=pages, synthesis=synth,
        )
        assert result["synthesis"] == synth


# ============================================================
# Test: run_llm_extraction / run_text_llm
# ============================================================

class TestRunLlmExtraction:
    """Tests for run_llm_extraction async function."""

    @pytest.mark.asyncio
    async def test_returns_response_content(self):
        """Returns the content from litellm response."""
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _make_llm_response({"unit": "101"})
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            from hybrid import run_llm_extraction
            result = await run_llm_extraction("openai/gpt-4", "Extract data", "base64img")
        assert json.loads(result) == {"unit": "101"}

    @pytest.mark.asyncio
    async def test_message_format_has_image_url(self):
        """Verify message format includes image_url for extraction."""
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _make_llm_response({"test": True})
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            from hybrid import run_llm_extraction
            await run_llm_extraction("openai/gpt-4", "prompt", "b64data")
        call_args = mock_litellm.completion.call_args
        messages = call_args[1].get("messages", call_args[0][1] if len(call_args[0]) > 1 else [])
        user_msg = [m for m in messages if m["role"] == "user"][0]
        content_types = [c["type"] for c in user_msg["content"]]
        assert "image_url" in content_types

    @pytest.mark.asyncio
    async def test_passes_temperature_and_max_tokens(self):
        """Verify temperature=0.1 and max_tokens passed correctly."""
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _make_llm_response({"test": True})
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            from hybrid import run_llm_extraction
            await run_llm_extraction("openai/gpt-4", "prompt", "b64")
        call_kwargs = mock_litellm.completion.call_args[1]
        assert call_kwargs["temperature"] == 0.1
        assert "max_tokens" in call_kwargs

    @pytest.mark.asyncio
    async def test_raises_on_litellm_failure(self):
        """Raises on litellm failure."""
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = Exception("API error")
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            from hybrid import run_llm_extraction
            with pytest.raises(Exception, match="API error"):
                await run_llm_extraction("openai/gpt-4", "prompt", "b64")


class TestRunTextLlm:
    """Tests for run_text_llm async function."""

    @pytest.mark.asyncio
    async def test_returns_response_content(self):
        """Returns the content from litellm response."""
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _make_llm_response({"synthesis": True})
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            from hybrid import run_text_llm
            result = await run_text_llm("openai/gpt-4", "Synthesize", "context data")
        assert json.loads(result) == {"synthesis": True}

    @pytest.mark.asyncio
    async def test_message_format_is_text_only(self):
        """Verify message format is text only (no image_url)."""
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _make_llm_response({"test": True})
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            from hybrid import run_text_llm
            await run_text_llm("openai/gpt-4", "prompt", "context")
        call_args = mock_litellm.completion.call_args
        messages = call_args[1].get("messages", call_args[0][1] if len(call_args[0]) > 1 else [])
        user_msg = [m for m in messages if m["role"] == "user"][0]
        # Text LLM should have string content, not list with image_url
        assert isinstance(user_msg["content"], str)

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        """Raises on litellm failure."""
        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = RuntimeError("timeout")
        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            from hybrid import run_text_llm
            with pytest.raises(RuntimeError, match="timeout"):
                await run_text_llm("openai/gpt-4", "prompt", "ctx")


# ============================================================
# Test: process_hybrid
# ============================================================

def _setup_docling_mocks(num_tables=0, num_pictures=1, table_md="| A |\n| - |\n| 1 |",
                          footer_table=False):
    """Create mock docling modules and install them in sys.modules.

    Returns dict of mock modules and key objects for assertions.
    """
    # Create mock pictures
    mock_pictures = []
    for i in range(num_pictures):
        pic = MagicMock()
        pic.image.pil_image = Image.new("RGB", (800, 600), "white")
        prov = MagicMock()
        prov.page_no = i + 1
        pic.prov = [prov]
        mock_pictures.append(pic)

    # Create mock tables
    mock_tables = []
    for i in range(num_tables):
        tbl = MagicMock()
        if footer_table and i == 0:
            tbl.export_to_markdown.return_value = "project name drawing number revision date scale"
        else:
            tbl.export_to_markdown.return_value = table_md
        prov = MagicMock()
        prov.page_no = i + 1
        tbl.prov = [prov]
        mock_tables.append(tbl)

    # Mock document
    mock_doc = MagicMock()
    mock_doc.tables = mock_tables
    mock_doc.pictures = mock_pictures

    # Mock converter result wrapper
    mock_wrapper = MagicMock()
    mock_wrapper.document = mock_doc

    # Mock converter class
    mock_converter_cls = MagicMock()
    mock_converter_instance = MagicMock()
    mock_converter_instance.convert.return_value = mock_wrapper
    mock_converter_cls.return_value = mock_converter_instance

    # Create mock modules for lazy imports
    mock_dc_module = MagicMock()
    mock_dc_module.DocumentConverter = mock_converter_cls
    mock_dc_module.PdfFormatOption = MagicMock()

    mock_base_module = MagicMock()
    mock_base_module.InputFormat = MagicMock()

    mock_pipeline_module = MagicMock()
    mock_pipeline_module.PdfPipelineOptions = MagicMock(return_value=MagicMock())

    mock_pdf2image = MagicMock()
    mock_pdf2image.convert_from_path.return_value = make_pdf_pages(2)

    modules = {
        "docling": MagicMock(),
        "docling.document_converter": mock_dc_module,
        "docling.datamodel": MagicMock(),
        "docling.datamodel.base_models": mock_base_module,
        "docling.datamodel.pipeline_options": mock_pipeline_module,
        "pdf2image": mock_pdf2image,
    }

    return modules, mock_converter_instance


@pytest.fixture
def hybrid_job_manager():
    """Create a fresh JobManager with InMemoryJobStore."""
    return JobManager(InMemoryJobStore())


@pytest.fixture
def temp_pdf_file():
    """Create a temporary file simulating a PDF upload."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.write(fd, b"%PDF-1.4 fake content")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


class TestProcessHybrid:
    """Tests for process_hybrid async function."""

    def _build_context(self, num_tables=0, num_pictures=1, llm_data=None,
                       footer_table=False):
        """Build all mocks needed for process_hybrid."""
        if llm_data is None:
            llm_data = {
                "unit_number": "101", "unit_type": "2BR", "floor": 1,
                "bedrooms": 2, "bathrooms": 1, "total_area_sf": 850.0,
                "rooms": [{"name": "LR", "area_sf": 200, "baseboard_length_ft": 40}],
                "doors": [{"location": "Entry", "type": "exterior"}],
                "windows": [{"location": "LR", "type": "dh"}],
                "fixtures": [], "upgrades": [], "general_notes": [],
            }

        docling_modules, mock_converter = _setup_docling_mocks(
            num_tables=num_tables, num_pictures=num_pictures,
            footer_table=footer_table,
        )

        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = _make_llm_response(llm_data)
        docling_modules["litellm"] = mock_litellm

        return docling_modules, mock_litellm, mock_converter

    def _start_patches(self, docling_modules, classify_result="floorplan",
                       is_arch=False, has_arch_text=False):
        """Start all patches and return list for cleanup."""
        patches = [
            patch.dict("sys.modules", docling_modules),
            patch("hybrid.classify_image", return_value=classify_result),
            patch("hybrid.image_to_base64", return_value="base64data"),
            patch("hybrid.is_architectural_drawing", return_value=is_arch),
            patch("hybrid.has_architectural_text", return_value=has_arch_text),
            patch("hybrid.calculate_confidence", return_value=MagicMock(
                model_dump=MagicMock(return_value={"overall": 0.85})
            )),
            patch("hybrid.asyncio.to_thread", side_effect=_fake_to_thread),
        ]
        for p in patches:
            p.start()
        return patches

    def _stop_patches(self, patches):
        """Stop all patches."""
        for p in patches:
            p.stop()

    @pytest.mark.asyncio
    async def test_job_transitions_to_completed(self, hybrid_job_manager, temp_pdf_file):
        """Verify job transitions: QUEUED -> PROCESSING -> COMPLETED."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        modules, _, _ = self._build_context()
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        status = await hybrid_job_manager.get_status(job.job_id)
        assert status.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_progress_updates_phases(self, hybrid_job_manager, temp_pdf_file):
        """Verify progress updates at each phase."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        progress_phases = []
        original_update = hybrid_job_manager.update_progress

        async def tracking_update(job_id, **kwargs):
            if "phase" in kwargs:
                progress_phases.append(kwargs["phase"])
            await original_update(job_id, **kwargs)

        hybrid_job_manager.update_progress = tracking_update
        modules, _, _ = self._build_context()
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        assert ProcessingPhase.DOCLING_CONVERSION in progress_phases
        assert ProcessingPhase.CLASSIFICATION in progress_phases
        assert ProcessingPhase.IMAGE_EXTRACTION in progress_phases
        assert ProcessingPhase.LLM_ANALYSIS in progress_phases
        assert ProcessingPhase.UPLOADING in progress_phases

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_success(self, hybrid_job_manager, temp_pdf_file):
        """Verify temp file cleanup on success."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        assert os.path.exists(temp_pdf_file)
        modules, _, _ = self._build_context()
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        assert not os.path.exists(temp_pdf_file)

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_failure(self, hybrid_job_manager, temp_pdf_file):
        """Verify temp file cleanup on failure."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        modules, _, mock_converter = self._build_context()
        mock_converter.convert.side_effect = Exception("docling crash")
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        assert not os.path.exists(temp_pdf_file)

    @pytest.mark.asyncio
    async def test_failure_handling_sets_failed_status(self, hybrid_job_manager, temp_pdf_file):
        """Verify failure handling: Exception -> fail_job."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        modules, _, mock_converter = self._build_context()
        mock_converter.convert.side_effect = Exception("boom")
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        status = await hybrid_job_manager.get_status(job.job_id)
        assert status.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_timeout_handling(self, hybrid_job_manager, temp_pdf_file):
        """Verify timeout handling: CancelledError -> timeout_job."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        modules, _, mock_converter = self._build_context()
        mock_converter.convert.side_effect = asyncio.CancelledError()
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            with pytest.raises(asyncio.CancelledError):
                await process_hybrid(
                    job_id=job.job_id, temp_path=temp_pdf_file,
                    provider="test-provider", job_manager=hybrid_job_manager,
                )
        finally:
            self._stop_patches(patches)

        status = await hybrid_job_manager.get_status(job.job_id)
        assert status.status == JobStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_confidence_scoring_included(self, hybrid_job_manager, temp_pdf_file):
        """Verify confidence scoring is calculated and included in result."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        modules, _, _ = self._build_context()
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        result = await hybrid_job_manager.get_result(job.job_id)
        assert "confidence" in result
        assert result["confidence"]["overall"] == 0.85

    @pytest.mark.asyncio
    async def test_synthesis_triggered_multiple_floorplans(self, hybrid_job_manager, temp_pdf_file):
        """Verify synthesis is triggered when multiple floorplans found."""
        llm_data = {
            "unit_number": "101", "unit_type": "1BR", "floor": 1,
            "bedrooms": 1, "bathrooms": 1, "total_area_sf": 500.0,
            "rooms": [], "doors": [], "windows": [],
            "fixtures": [], "upgrades": [], "general_notes": [],
        }
        synthesis_data = {"common_notes": ["All units similar"]}

        modules, mock_litellm, _ = self._build_context(num_pictures=2, llm_data=llm_data)
        mock_litellm.completion.side_effect = [
            _make_llm_response(llm_data),
            _make_llm_response(llm_data),
            _make_llm_response(synthesis_data),
        ]
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        # Synthesis was called (3 litellm calls: 2 extraction + 1 synthesis)
        assert mock_litellm.completion.call_count == 3

    @pytest.mark.asyncio
    async def test_synthesis_skipped_single_floorplan_no_tables(self, hybrid_job_manager, temp_pdf_file):
        """Verify synthesis is skipped when only one floorplan and no tables."""
        modules, mock_litellm, _ = self._build_context(num_pictures=1, num_tables=0)
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        # Only 1 extraction call, no synthesis
        assert mock_litellm.completion.call_count == 1

    @pytest.mark.asyncio
    async def test_table_context_appended_to_prompt(self, hybrid_job_manager, temp_pdf_file):
        """Verify table context is appended to enriched prompt."""
        modules, mock_litellm, _ = self._build_context(num_tables=1, num_pictures=1)
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        # The extraction call should have the enriched prompt with table context
        call_args = mock_litellm.completion.call_args_list[0]
        messages = call_args[1].get("messages", [])
        user_msg = [m for m in messages if m["role"] == "user"][0]
        prompt_text = str(user_msg["content"])
        assert "ADDITIONAL CONTEXT" in prompt_text

    @pytest.mark.asyncio
    async def test_json_cleaning_removes_code_fences(self, hybrid_job_manager, temp_pdf_file):
        """Verify JSON cleaning removes markdown code fences."""
        modules, mock_litellm, _ = self._build_context()
        fenced_json = (
            '```json\n'
            '{"unit_number": "101", "unit_type": "1BR", "floor": 1, '
            '"bedrooms": 1, "bathrooms": 1, "total_area_sf": 500, '
            '"rooms": [], "doors": [], "windows": [], '
            '"fixtures": [], "upgrades": [], "general_notes": []}\n'
            '```'
        )
        fenced_response = MagicMock()
        fenced_response.choices = [MagicMock()]
        fenced_response.choices[0].message.content = fenced_json
        mock_litellm.completion.return_value = fenced_response

        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        status = await hybrid_job_manager.get_status(job.job_id)
        assert status.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failed_llm_extraction_continues(self, hybrid_job_manager, temp_pdf_file):
        """Verify failed LLM extraction does not crash pipeline."""
        modules, mock_litellm, _ = self._build_context(num_pictures=2)
        good_data = {
            "unit_number": "102", "unit_type": "1BR", "floor": 1,
            "bedrooms": 1, "bathrooms": 1, "total_area_sf": 500.0,
            "rooms": [], "doors": [], "windows": [],
            "fixtures": [], "upgrades": [], "general_notes": [],
        }
        mock_litellm.completion.side_effect = [
            Exception("LLM timeout"),
            _make_llm_response(good_data),
        ]

        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        status = await hybrid_job_manager.get_status(job.job_id)
        assert status.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_full_page_fallback_detection(self, hybrid_job_manager, temp_pdf_file):
        """Verify full-page fallback detection for pages not found by Docling."""
        modules, mock_litellm, _ = self._build_context(num_pictures=0)
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        patches = self._start_patches(modules, is_arch=True, has_arch_text=True)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        # LLM should have been called for the fallback-detected floorplans
        assert mock_litellm.completion.call_count >= 1

    @pytest.mark.asyncio
    async def test_result_has_correct_engine(self, hybrid_job_manager, temp_pdf_file):
        """Verify result has engine=hybrid."""
        job = await hybrid_job_manager.create_job(file_name="test.pdf", engine="hybrid")
        modules, _, _ = self._build_context()
        patches = self._start_patches(modules)
        try:
            from hybrid import process_hybrid
            await process_hybrid(
                job_id=job.job_id, temp_path=temp_pdf_file,
                provider="test-provider", job_manager=hybrid_job_manager,
            )
        finally:
            self._stop_patches(patches)

        result = await hybrid_job_manager.get_result(job.job_id)
        assert result["engine"] == "hybrid"
