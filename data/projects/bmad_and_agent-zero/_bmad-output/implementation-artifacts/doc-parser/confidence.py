"""Confidence scoring for doc-parser extraction results.

Priority 6: Transparency over hidden gaps.
Calculates completeness metrics so users can decide whether
to re-run with a different engine if confidence is insufficient.
"""
from typing import Dict, Any, List, Optional
from models import ConfidenceScore, UnitExtraction


def calculate_confidence(
    units: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
    synthesis: Optional[Dict[str, Any]] = None,
    total_pages: int = 0,
    floorplans_found: int = 0,
) -> ConfidenceScore:
    """Calculate confidence score for extraction results.

    Evaluates completeness across multiple dimensions:
    - Room dimensions (area, length, width)
    - Door specifications (type, size, hardware)
    - Window specifications (type, size)
    - Fixture completeness
    - Baseboard data
    - Unit identification
    - Cross-page synthesis

    Args:
        units: List of unit extraction dicts
        tables: List of table extraction dicts
        synthesis: Cross-page synthesis result (if available)
        total_pages: Total pages in the document
        floorplans_found: Number of floorplan pages detected

    Returns:
        ConfidenceScore with overall score and per-dimension flags
    """
    if not units:
        return ConfidenceScore(
            overall=0.0,
            per_page={"note": "No units extracted"}
        )

    scores = []
    per_page = {}

    # ---- Room Dimensions ----
    rooms_with_area = 0
    rooms_with_dimensions = 0
    total_rooms = 0

    for unit in units:
        rooms = unit.get("rooms", [])
        total_rooms += len(rooms)
        for room in rooms:
            if room.get("area_sf", 0) > 0:
                rooms_with_area += 1
            if room.get("length_ft", 0) > 0 and room.get("width_ft", 0) > 0:
                rooms_with_dimensions += 1

    room_dim_score = 0.0
    if total_rooms > 0:
        room_dim_score = (rooms_with_area + rooms_with_dimensions) / (total_rooms * 2)
    has_room_dimensions = room_dim_score > 0.5
    scores.append((room_dim_score, 0.25))  # 25% weight

    # ---- Door Specifications ----
    doors_with_type = 0
    doors_with_size = 0
    doors_with_hardware = 0
    total_doors = 0

    for unit in units:
        doors = unit.get("doors", [])
        total_doors += len(doors)
        for door in doors:
            if door.get("type"):
                doors_with_type += 1
            if door.get("width_in", 0) > 0:
                doors_with_size += 1
            if door.get("hardware"):
                doors_with_hardware += 1

    door_score = 0.0
    if total_doors > 0:
        door_score = (
            (doors_with_type / total_doors) * 0.4 +
            (doors_with_size / total_doors) * 0.4 +
            (doors_with_hardware / total_doors) * 0.2
        )
    elif total_rooms > 0:
        # No doors found but rooms exist - likely missing data
        door_score = 0.0
    has_door_specs = door_score > 0.4
    scores.append((door_score, 0.20))  # 20% weight

    # ---- Window Specifications ----
    windows_with_type = 0
    windows_with_size = 0
    total_windows = 0

    for unit in units:
        windows = unit.get("windows", [])
        total_windows += len(windows)
        for window in windows:
            if window.get("type"):
                windows_with_type += 1
            if window.get("width_in", 0) > 0:
                windows_with_size += 1

    window_score = 0.0
    if total_windows > 0:
        window_score = (
            (windows_with_type / total_windows) * 0.5 +
            (windows_with_size / total_windows) * 0.5
        )
    elif total_rooms > 0:
        window_score = 0.0
    has_window_specs = window_score > 0.4
    scores.append((window_score, 0.15))  # 15% weight

    # ---- Fixture Completeness ----
    total_fixtures = 0
    fixtures_with_specs = 0

    for unit in units:
        fixtures = unit.get("fixtures", [])
        total_fixtures += len(fixtures)
        for fixture in fixtures:
            if fixture.get("specifications") or fixture.get("type"):
                fixtures_with_specs += 1

    fixture_score = 0.0
    if total_fixtures > 0:
        fixture_score = fixtures_with_specs / total_fixtures
    has_fixtures = fixture_score > 0.3
    scores.append((fixture_score, 0.10))  # 10% weight

    # ---- Baseboard Data ----
    rooms_with_baseboard = 0
    rooms_with_exclusions = 0

    for unit in units:
        for room in unit.get("rooms", []):
            if room.get("baseboard_length_ft", 0) > 0:
                rooms_with_baseboard += 1
            if room.get("baseboard_exclusions"):
                rooms_with_exclusions += 1

    baseboard_score = 0.0
    if total_rooms > 0:
        baseboard_score = (
            (rooms_with_baseboard / total_rooms) * 0.6 +
            (rooms_with_exclusions / total_rooms) * 0.4
        )
    has_baseboard = baseboard_score > 0.3
    scores.append((baseboard_score, 0.15))  # 15% weight

    # ---- Unit Identification ----
    units_with_number = sum(
        1 for u in units
        if u.get("unit_number") and u["unit_number"] != "unknown"
        and not u["unit_number"].startswith("page_")
    )
    units_with_type = sum(
        1 for u in units
        if u.get("unit_type") and u["unit_type"] != "unknown"
    )

    unit_id_score = 0.0
    if len(units) > 0:
        unit_id_score = (
            (units_with_number / len(units)) * 0.6 +
            (units_with_type / len(units)) * 0.4
        )
    has_unit_id = unit_id_score > 0.5
    scores.append((unit_id_score, 0.10))  # 10% weight

    # ---- Cross-Page Synthesis ----
    has_synthesis = synthesis is not None and bool(synthesis)
    synthesis_score = 1.0 if has_synthesis else 0.0
    scores.append((synthesis_score, 0.05))  # 5% weight

    # ---- Calculate Overall Score ----
    overall = sum(score * weight for score, weight in scores)
    overall = round(min(1.0, max(0.0, overall)), 2)

    # ---- Per-Page Breakdown ----
    for unit in units:
        page = unit.get("source_page", 0)
        page_key = f"page_{page}"
        rooms = unit.get("rooms", [])
        doors = unit.get("doors", [])
        windows = unit.get("windows", [])
        fixtures = unit.get("fixtures", [])

        fields_populated = 0
        fields_total = 6  # rooms, doors, windows, fixtures, unit_number, area

        if rooms:
            fields_populated += 1
        if doors:
            fields_populated += 1
        if windows:
            fields_populated += 1
        if fixtures:
            fields_populated += 1
        if unit.get("unit_number") and not str(unit["unit_number"]).startswith("page_"):
            fields_populated += 1
        if unit.get("area_sf", 0) > 0:
            fields_populated += 1

        per_page[page_key] = {
            "fields_populated": fields_populated,
            "fields_total": fields_total,
            "completeness": round(fields_populated / fields_total, 2),
            "rooms_count": len(rooms),
            "doors_count": len(doors),
            "windows_count": len(windows),
            "fixtures_count": len(fixtures),
            "has_dimensions": any(r.get("area_sf", 0) > 0 for r in rooms),
            "has_baseboard": any(r.get("baseboard_length_ft", 0) > 0 for r in rooms),
        }

    # ---- Coverage Metrics ----
    if total_pages > 0 and floorplans_found > 0:
        per_page["coverage"] = {
            "total_pages": total_pages,
            "floorplans_detected": floorplans_found,
            "coverage_ratio": round(floorplans_found / total_pages, 2),
        }

    return ConfidenceScore(
        overall=overall,
        room_dimensions=has_room_dimensions,
        door_specifications=has_door_specs,
        window_specifications=has_window_specs,
        fixture_completeness=has_fixtures,
        cross_page_synthesis=has_synthesis,
        baseboard_data=has_baseboard,
        unit_identification=has_unit_id,
        per_page=per_page,
    )


def confidence_summary_text(score: ConfidenceScore) -> str:
    """Generate human-readable confidence summary."""
    lines = [f"Overall Confidence: {score.overall:.0%}"]

    checks = [
        ("Room Dimensions", score.room_dimensions),
        ("Door Specifications", score.door_specifications),
        ("Window Specifications", score.window_specifications),
        ("Fixture Completeness", score.fixture_completeness),
        ("Baseboard Data", score.baseboard_data),
        ("Unit Identification", score.unit_identification),
        ("Cross-Page Synthesis", score.cross_page_synthesis),
    ]

    for label, present in checks:
        icon = "✅" if present else "❌"
        lines.append(f"  {icon} {label}")

    return "\n".join(lines)
