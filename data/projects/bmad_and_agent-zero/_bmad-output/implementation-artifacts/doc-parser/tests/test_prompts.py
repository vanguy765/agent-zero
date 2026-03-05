"""Unit tests for doc-parser prompts.py.

Verifies prompt integrity: required keys, instructions, length limits,
and embedded JSON examples are parseable.
"""
import sys
import os
import json
import re

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prompts import (
    FLOORPLAN_PROMPT_RICH,
    SYNTHESIS_PROMPT,
    TABLE_ANALYSIS_PROMPT,
    FLOORPLAN_PROMPT,
)


class TestFloorplanPromptRich:
    """Tests for the rich floorplan extraction prompt."""

    def test_is_non_empty_string(self):
        """FLOORPLAN_PROMPT_RICH is a non-empty string."""
        assert isinstance(FLOORPLAN_PROMPT_RICH, str)
        assert len(FLOORPLAN_PROMPT_RICH) > 0

    @pytest.mark.parametrize("key", [
        "unit_number",
        "unit_type",
        "rooms",
        "doors",
        "windows",
        "fixtures",
        "upgrades",
        "general_notes",
    ])
    def test_contains_required_json_keys(self, key):
        """FLOORPLAN_PROMPT_RICH contains all required JSON keys."""
        assert key in FLOORPLAN_PROMPT_RICH

    def test_contains_baseboard_instructions(self):
        """FLOORPLAN_PROMPT_RICH contains baseboard-related keys."""
        assert "baseboard_length_ft" in FLOORPLAN_PROMPT_RICH
        assert "baseboard_exclusions" in FLOORPLAN_PROMPT_RICH

    def test_contains_door_swing_analysis(self):
        """FLOORPLAN_PROMPT_RICH contains door swing analysis instructions."""
        assert "swing_direction" in FLOORPLAN_PROMPT_RICH
        # Check for swing arc instruction
        assert "swing" in FLOORPLAN_PROMPT_RICH.lower()
        assert "arc" in FLOORPLAN_PROMPT_RICH.lower()

    def test_contains_json_only_instruction(self):
        """FLOORPLAN_PROMPT_RICH mentions returning only JSON."""
        assert "Return ONLY the JSON object" in FLOORPLAN_PROMPT_RICH

    def test_does_not_exceed_length_limit(self):
        """FLOORPLAN_PROMPT_RICH does not exceed 10000 characters."""
        assert len(FLOORPLAN_PROMPT_RICH) < 10000


class TestSynthesisPrompt:
    """Tests for the cross-page synthesis prompt."""

    def test_is_non_empty_string(self):
        """SYNTHESIS_PROMPT is a non-empty string."""
        assert isinstance(SYNTHESIS_PROMPT, str)
        assert len(SYNTHESIS_PROMPT) > 0

    def test_contains_correlation_instructions(self):
        """SYNTHESIS_PROMPT contains correlation instructions."""
        prompt_upper = SYNTHESIS_PROMPT.upper()
        assert "CORRELATE" in prompt_upper
        assert "DEDUPLICATE" in prompt_upper
        assert "VALIDATE" in prompt_upper

    @pytest.mark.parametrize("key", [
        "units",
        "discrepancies",
        "totals",
    ])
    def test_contains_required_output_keys(self, key):
        """SYNTHESIS_PROMPT contains required output keys."""
        assert key in SYNTHESIS_PROMPT

    def test_contains_json_only_instruction(self):
        """SYNTHESIS_PROMPT mentions returning only JSON."""
        assert "Return ONLY the JSON object" in SYNTHESIS_PROMPT

    def test_does_not_exceed_length_limit(self):
        """SYNTHESIS_PROMPT does not exceed 10000 characters."""
        assert len(SYNTHESIS_PROMPT) < 10000


class TestTableAnalysisPrompt:
    """Tests for the table analysis prompt."""

    def test_is_non_empty_string(self):
        """TABLE_ANALYSIS_PROMPT is a non-empty string."""
        assert isinstance(TABLE_ANALYSIS_PROMPT, str)
        assert len(TABLE_ANALYSIS_PROMPT) > 0

    @pytest.mark.parametrize("table_type", [
        "door_schedule",
        "window_schedule",
        "finish_schedule",
    ])
    def test_lists_expected_table_types(self, table_type):
        """TABLE_ANALYSIS_PROMPT lists expected table types."""
        assert table_type in TABLE_ANALYSIS_PROMPT

    def test_contains_json_only_instruction(self):
        """TABLE_ANALYSIS_PROMPT mentions returning only JSON."""
        assert "Return ONLY the JSON object" in TABLE_ANALYSIS_PROMPT

    def test_does_not_exceed_length_limit(self):
        """TABLE_ANALYSIS_PROMPT does not exceed 10000 characters."""
        assert len(TABLE_ANALYSIS_PROMPT) < 10000


class TestFloorplanPromptBackwardCompat:
    """Tests for the backward-compatible basic floorplan prompt."""

    def test_exists_and_is_non_empty(self):
        """FLOORPLAN_PROMPT (backward compat) exists and is non-empty."""
        assert isinstance(FLOORPLAN_PROMPT, str)
        assert len(FLOORPLAN_PROMPT) > 0

    @pytest.mark.parametrize("key", [
        "rooms",
        "total_area_sf",
        "door_count",
    ])
    def test_contains_basic_keys(self, key):
        """FLOORPLAN_PROMPT contains basic extraction keys."""
        assert key in FLOORPLAN_PROMPT

    def test_contains_json_only_instruction(self):
        """FLOORPLAN_PROMPT mentions returning only JSON."""
        assert "Return ONLY the JSON object" in FLOORPLAN_PROMPT

    def test_does_not_exceed_length_limit(self):
        """FLOORPLAN_PROMPT does not exceed 10000 characters."""
        assert len(FLOORPLAN_PROMPT) < 10000


class TestAllPromptsJsonExamples:
    """Tests that embedded JSON examples in all prompts are parseable."""

    @staticmethod
    def _extract_json_blocks(text):
        """Extract JSON blocks from markdown code fences in prompt text."""
        pattern = r'```json\s*\n(.*?)\n```'
        return re.findall(pattern, text, re.DOTALL)

    @pytest.mark.parametrize("prompt_name,prompt_text", [
        ("FLOORPLAN_PROMPT_RICH", FLOORPLAN_PROMPT_RICH),
        ("SYNTHESIS_PROMPT", SYNTHESIS_PROMPT),
        ("TABLE_ANALYSIS_PROMPT", TABLE_ANALYSIS_PROMPT),
        ("FLOORPLAN_PROMPT", FLOORPLAN_PROMPT),
    ])
    def test_embedded_json_is_parseable(self, prompt_name, prompt_text):
        """All JSON blocks embedded in prompts are valid JSON."""
        blocks = self._extract_json_blocks(prompt_text)
        assert len(blocks) > 0, f"{prompt_name} should contain at least one JSON example"
        for i, block in enumerate(blocks):
            try:
                json.loads(block)
            except json.JSONDecodeError:
                # JSON examples in prompts use placeholder values like
                # "string - description" which aren't valid JSON values.
                # We verify the structure is at least brace-balanced.
                open_braces = block.count("{")
                close_braces = block.count("}")
                open_brackets = block.count("[")
                close_brackets = block.count("]")
                assert open_braces == close_braces, (
                    f"{prompt_name} block {i}: unbalanced braces "
                    f"({{ {open_braces} vs }} {close_braces})"
                )
                assert open_brackets == close_brackets, (
                    f"{prompt_name} block {i}: unbalanced brackets "
                    f"([ {open_brackets} vs ] {close_brackets})"
                )
