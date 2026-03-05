"""Unit tests for doc-parser confidence.py.

Covers calculate_confidence() scoring logic and confidence_summary_text() output.
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from confidence import calculate_confidence, confidence_summary_text
from models import ConfidenceScore


# ============================================================
# calculate_confidence Tests
# ============================================================

class TestCalculateConfidenceEmpty:
    """Tests for calculate_confidence with empty or missing data."""

    def test_empty_units_returns_zero(self):
        """Empty units list returns overall=0.0."""
        result = calculate_confidence(units=[], tables=[])
        assert result.overall == 0.0
        assert result.per_page == {"note": "No units extracted"}

    def test_empty_units_all_flags_false(self):
        """Empty units list has all boolean flags False."""
        result = calculate_confidence(units=[], tables=[])
        assert result.room_dimensions is False
        assert result.door_specifications is False
        assert result.window_specifications is False
        assert result.fixture_completeness is False
        assert result.baseboard_data is False
        assert result.unit_identification is False
        assert result.cross_page_synthesis is False


class TestCalculateConfidenceComplete:
    """Tests for calculate_confidence with complete data."""

    def test_single_complete_unit_high_confidence(self, sample_unit_dict_complete):
        """Single complete unit returns high confidence (>0.7)."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
            synthesis={"units": [], "totals": {}},
        )
        assert result.overall > 0.7

    def test_single_sparse_unit_low_confidence(self, sample_unit_dict_sparse):
        """Single sparse unit (only room names, no dimensions) returns low confidence (<0.3)."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert result.overall < 0.3

    def test_overall_score_between_zero_and_one(self, sample_unit_dict_complete):
        """Overall score is always between 0.0 and 1.0."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
            synthesis={"units": []},
        )
        assert 0.0 <= result.overall <= 1.0

    def test_overall_score_between_zero_and_one_sparse(self, sample_unit_dict_sparse):
        """Overall score is between 0.0 and 1.0 even for sparse data."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert 0.0 <= result.overall <= 1.0


class TestCalculateConfidenceRoomDimensions:
    """Tests for room_dimensions scoring."""

    def test_rooms_with_area_and_dimensions(self, sample_unit_dict_complete):
        """Units with rooms having area and length/width: room_dimensions is True."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
        )
        assert result.room_dimensions is True

    def test_rooms_with_area_but_no_length_width(self):
        """Units with rooms having area but no length/width: partial score."""
        unit = {
            "unit_number": "200",
            "unit_type": "1BR",
            "rooms": [
                {"name": "Bedroom", "area_sf": 150.0},
                {"name": "Kitchen", "area_sf": 100.0},
            ],
            "doors": [],
            "windows": [],
            "fixtures": [],
        }
        result = calculate_confidence(units=[unit], tables=[])
        # area contributes but no length/width, so score = 2/(2*2) = 0.5
        # threshold is > 0.5 for True, so exactly 0.5 is False
        assert result.room_dimensions is False

    def test_rooms_with_no_area_no_dimensions(self, sample_unit_dict_sparse):
        """Sparse rooms with no area or dimensions: room_dimensions is False."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert result.room_dimensions is False


class TestCalculateConfidenceDoors:
    """Tests for door_specifications scoring."""

    def test_doors_with_type_size_hardware(self, sample_unit_dict_complete):
        """Units with doors having type, size, and hardware: door_specifications is True."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
        )
        assert result.door_specifications is True

    def test_no_doors_but_rooms_exist(self, sample_unit_dict_sparse):
        """No doors but rooms exist: door score is 0.0."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert result.door_specifications is False

    def test_doors_with_type_and_size_no_hardware(self):
        """Doors with type and size but no hardware: still passes threshold."""
        unit = {
            "unit_number": "300",
            "unit_type": "1BR",
            "rooms": [{"name": "Room"}],
            "doors": [
                {"type": "interior", "width_in": 36.0},
                {"type": "closet", "width_in": 30.0},
            ],
            "windows": [],
            "fixtures": [],
        }
        result = calculate_confidence(units=[unit], tables=[])
        # type: 2/2 * 0.4 = 0.4, size: 2/2 * 0.4 = 0.4, hardware: 0/2 * 0.2 = 0.0
        # total = 0.8, threshold > 0.4 => True
        assert result.door_specifications is True


class TestCalculateConfidenceWindows:
    """Tests for window_specifications scoring."""

    def test_windows_with_type_and_size(self, sample_unit_dict_complete):
        """Units with windows having type and size: window_specifications is True."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
        )
        assert result.window_specifications is True

    def test_no_windows(self, sample_unit_dict_sparse):
        """No windows: window_specifications is False."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert result.window_specifications is False


class TestCalculateConfidenceFixtures:
    """Tests for fixture_completeness scoring."""

    def test_fixtures_with_specs(self, sample_unit_dict_complete):
        """Units with fixtures having specs: fixture_completeness is True."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
        )
        assert result.fixture_completeness is True

    def test_no_fixtures(self, sample_unit_dict_sparse):
        """No fixtures: fixture_completeness is False."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert result.fixture_completeness is False


class TestCalculateConfidenceBaseboard:
    """Tests for baseboard_data scoring."""

    def test_rooms_with_baseboard_data(self, sample_unit_dict_complete):
        """Units with baseboard data: baseboard_data is True."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
        )
        assert result.baseboard_data is True

    def test_rooms_without_baseboard_data(self, sample_unit_dict_sparse):
        """Sparse rooms without baseboard data: baseboard_data is False."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert result.baseboard_data is False


class TestCalculateConfidenceUnitIdentification:
    """Tests for unit_identification scoring."""

    def test_proper_unit_number(self, sample_unit_dict_complete):
        """Unit with proper unit_number (not 'unknown', not 'page_*'): unit_identification is True."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
        )
        assert result.unit_identification is True

    def test_unknown_unit_number(self, sample_unit_dict_sparse):
        """Unit with 'unknown' unit_number: unit_identification is False."""
        result = calculate_confidence(
            units=[sample_unit_dict_sparse],
            tables=[],
        )
        assert result.unit_identification is False

    def test_page_prefix_unit_number(self):
        """Unit with 'page_*' unit_number: unit_identification is False."""
        unit = {
            "unit_number": "page_3",
            "unit_type": "unknown",
            "rooms": [{"name": "Room"}],
            "doors": [],
            "windows": [],
            "fixtures": [],
        }
        result = calculate_confidence(units=[unit], tables=[])
        assert result.unit_identification is False


class TestCalculateConfidenceSynthesis:
    """Tests for cross_page_synthesis scoring."""

    def test_with_synthesis_dict(self, sample_unit_dict_complete):
        """With synthesis dict: cross_page_synthesis is True."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
            synthesis={"units": [], "totals": {}},
        )
        assert result.cross_page_synthesis is True

    def test_without_synthesis(self, sample_unit_dict_complete):
        """Without synthesis: cross_page_synthesis is False."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
            synthesis=None,
        )
        assert result.cross_page_synthesis is False

    def test_empty_synthesis_dict(self, sample_unit_dict_complete):
        """Empty synthesis dict: cross_page_synthesis is False."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
            synthesis={},
        )
        assert result.cross_page_synthesis is False


class TestCalculateConfidencePerPage:
    """Tests for per_page breakdown in confidence results."""

    def test_per_page_contains_correct_keys(self, sample_unit_dict_complete):
        """per_page breakdown contains correct keys for each unit."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
        )
        page_key = f"page_{sample_unit_dict_complete['source_page']}"
        assert page_key in result.per_page
        page_data = result.per_page[page_key]
        assert "fields_populated" in page_data
        assert "fields_total" in page_data
        assert "completeness" in page_data
        assert "rooms_count" in page_data
        assert "doors_count" in page_data
        assert "windows_count" in page_data
        assert "fixtures_count" in page_data
        assert "has_dimensions" in page_data
        assert "has_baseboard" in page_data

    def test_per_page_coverage_metrics(self, sample_unit_dict_complete):
        """per_page coverage metrics when total_pages and floorplans_found provided."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
            total_pages=10,
            floorplans_found=3,
        )
        assert "coverage" in result.per_page
        coverage = result.per_page["coverage"]
        assert coverage["total_pages"] == 10
        assert coverage["floorplans_detected"] == 3
        assert coverage["coverage_ratio"] == 0.3

    def test_no_coverage_when_zero_pages(self, sample_unit_dict_complete):
        """No coverage key when total_pages is 0."""
        result = calculate_confidence(
            units=[sample_unit_dict_complete],
            tables=[],
            total_pages=0,
            floorplans_found=0,
        )
        assert "coverage" not in result.per_page


class TestCalculateConfidenceWeights:
    """Tests for overall score weighting."""

    def test_weights_sum_to_one(self):
        """The dimension weights sum to 1.0 (25+20+15+10+15+10+5 = 100%)."""
        weights = [0.25, 0.20, 0.15, 0.10, 0.15, 0.10, 0.05]
        assert sum(weights) == pytest.approx(1.0)

    def test_multiple_units_aggregate(self):
        """Multiple units: scores aggregate correctly."""
        unit1 = {
            "unit_number": "101",
            "unit_type": "1BR",
            "source_page": 1,
            "rooms": [
                {"name": "Bedroom", "area_sf": 150.0, "length_ft": 12.0, "width_ft": 12.5},
            ],
            "doors": [{"type": "interior", "width_in": 36.0, "hardware": "lever"}],
            "windows": [{"type": "double-hung", "width_in": 36.0}],
            "fixtures": [{"type": "plumbing", "specifications": "standard"}],
        }
        unit2 = {
            "unit_number": "102",
            "unit_type": "2BR",
            "source_page": 2,
            "rooms": [
                {"name": "Living", "area_sf": 200.0, "length_ft": 16.0, "width_ft": 12.5},
            ],
            "doors": [{"type": "exterior", "width_in": 36.0, "hardware": "deadbolt"}],
            "windows": [{"type": "casement", "width_in": 30.0}],
            "fixtures": [{"type": "electrical", "specifications": "LED"}],
        }
        result = calculate_confidence(units=[unit1, unit2], tables=[])
        assert 0.0 <= result.overall <= 1.0
        # Both units have good data, should be reasonably high
        assert result.overall > 0.4
        # Both page keys should exist
        assert "page_1" in result.per_page
        assert "page_2" in result.per_page


# ============================================================
# confidence_summary_text Tests
# ============================================================

class TestConfidenceSummaryText:
    """Tests for confidence_summary_text() output formatting."""

    def test_returns_string_with_overall(self):
        """Returns string containing 'Overall Confidence:'."""
        score = ConfidenceScore(overall=0.75)
        text = confidence_summary_text(score)
        assert isinstance(text, str)
        assert "Overall Confidence:" in text

    def test_contains_checkmark_for_true(self):
        """Contains checkmark for true dimensions."""
        score = ConfidenceScore(
            overall=0.8,
            room_dimensions=True,
            door_specifications=False,
        )
        text = confidence_summary_text(score)
        assert "\u2705" in text  # ✅

    def test_contains_cross_for_false(self):
        """Contains cross mark for false dimensions."""
        score = ConfidenceScore(
            overall=0.3,
            room_dimensions=False,
        )
        text = confidence_summary_text(score)
        assert "\u274c" in text  # ❌

    @pytest.mark.parametrize("label", [
        "Room Dimensions",
        "Door Specifications",
        "Window Specifications",
        "Fixture Completeness",
        "Baseboard Data",
        "Unit Identification",
        "Cross-Page Synthesis",
    ])
    def test_all_dimension_labels_present(self, label):
        """All 7 dimension labels are present in output."""
        score = ConfidenceScore(overall=0.5)
        text = confidence_summary_text(score)
        assert label in text

    def test_full_confidence_all_checkmarks(self):
        """100% confidence shows all checkmarks."""
        score = ConfidenceScore(
            overall=1.0,
            room_dimensions=True,
            door_specifications=True,
            window_specifications=True,
            fixture_completeness=True,
            baseboard_data=True,
            unit_identification=True,
            cross_page_synthesis=True,
        )
        text = confidence_summary_text(score)
        assert text.count("\u2705") == 7
        assert "\u274c" not in text

    def test_zero_confidence_all_crosses(self):
        """0% confidence shows all crosses."""
        score = ConfidenceScore(overall=0.0)
        text = confidence_summary_text(score)
        assert text.count("\u274c") == 7
        assert "\u2705" not in text
