"""LLM prompts for doc-parser service.

Priority 1: FLOORPLAN_PROMPT_RICH - Aligned with claudePdfParser granularity
Priority 5: SYNTHESIS_PROMPT - Cross-page data correlation
Backward compat: FLOORPLAN_PROMPT - Original basic prompt
"""

# ============================================================
# Priority 1: Rich Floorplan Extraction Prompt
# Aligned with claudePdfParser.ts extraction granularity
# ============================================================

FLOORPLAN_PROMPT_RICH = """You are an expert architectural document analyst specializing in residential renovation projects. Analyze this floorplan image and extract ALL construction-relevant data with maximum precision.

Return a JSON object with the following structure. Be exhaustive - extract every detail visible in the drawing.

```json
{
  "unit_number": "string - unit/apartment number from title block or drawing label",
  "unit_type": "string - e.g. '1BR', '2BR', 'Studio', '3BR', based on bedroom count",
  "floor": 0,
  "bedrooms": 0,
  "bathrooms": 0,
  "half_baths": 0,
  "total_area_sf": 0.0,

  "rooms": [
    {
      "name": "string - room name as labeled (e.g. 'Master Bedroom', 'Kitchen', 'Living Room')",
      "area_sf": 0.0,
      "length_ft": 0.0,
      "width_ft": 0.0,
      "ceiling_height_ft": 0.0,
      "baseboard_length_ft": 0.0,
      "baseboard_exclusions": ["list of items that interrupt baseboard: 'kitchen cabinets', 'bathtub', 'shower', 'closet opening', 'doorway'"],
      "baseboard_exclusion_reasoning": "string - explain WHY each exclusion reduces baseboard length, with measurements",
      "fixtures": ["list of visible fixtures in this room"],
      "flooring_type": "string - if indicated: 'tile', 'hardwood', 'carpet', 'vinyl', 'concrete'",
      "notes": "string - any additional annotations visible for this room"
    }
  ],

  "doors": [
    {
      "location": "string - e.g. 'Master Bedroom to Hallway', 'Unit Entry'",
      "room": "string - primary room this door serves",
      "type": "string - 'interior', 'exterior', 'closet', 'pocket', 'barn', 'french', 'sliding', 'bifold'",
      "width_in": 0.0,
      "height_in": 0.0,
      "hardware": "string - 'lever', 'knob', 'pull', 'push plate', 'deadbolt' if visible",
      "action": "string - 'swing', 'slide', 'fold', 'pivot'",
      "swing_direction": "string - 'in', 'out', 'left', 'right' based on arc symbol",
      "material": "string - 'hollow-core', 'solid-core', 'glass', 'metal' if determinable",
      "notes": "string - any schedule references or special annotations"
    }
  ],

  "windows": [
    {
      "location": "string - e.g. 'Living Room - North Wall'",
      "room": "string - room containing this window",
      "type": "string - 'single-hung', 'double-hung', 'casement', 'fixed', 'sliding', 'awning'",
      "width_in": 0.0,
      "height_in": 0.0,
      "sill_height_in": 0.0,
      "count": 1,
      "glazing": "string - 'single', 'double', 'triple', 'low-e' if noted",
      "operable": true,
      "notes": "string - schedule references, egress requirements"
    }
  ],

  "fixtures": [
    {
      "name": "string - e.g. 'Toilet', 'Vanity Sink', 'Bathtub', 'Shower', 'Range', 'Refrigerator'",
      "room": "string - room containing this fixture",
      "type": "string - 'plumbing', 'electrical', 'hvac', 'appliance'",
      "specifications": "string - any visible specs, model numbers, sizes",
      "count": 1
    }
  ],

  "upgrades": [
    {
      "description": "string - renovation work item",
      "trade": "string - 'electrical', 'plumbing', 'hvac', 'carpentry', 'painting', 'flooring', 'drywall'",
      "location": "string - where in the unit",
      "specifications": "string - detailed specs if visible"
    }
  ],

  "general_notes": ["list of any general notes, code references, or annotations visible on the drawing"]
}
```

IMPORTANT INSTRUCTIONS:
1. Extract EVERY door visible in the floorplan - count door swing arcs carefully. Include closet doors.
2. Extract EVERY window - look for window symbols on exterior walls.
3. For baseboard calculations: measure the PERIMETER of each room, then SUBTRACT door openings, window sills at floor level, built-in cabinets, bathtubs, showers, and any other items that interrupt the baseboard run. Show your reasoning.
4. If dimensions are shown in the drawing (e.g. 12'-6" x 10'-0"), use them exactly. If not shown, estimate based on scale and standard construction dimensions.
5. Identify the unit number from title blocks, drawing labels, or sheet references.
6. For door types: look at the swing arc symbol - a quarter circle means swing door, parallel lines mean sliding, zigzag means folding.
7. For fixtures: include ALL plumbing fixtures (toilets, sinks, tubs, showers), kitchen appliances (range, refrigerator, dishwasher), and HVAC equipment visible.
8. Return ONLY the JSON object, no markdown formatting, no explanation text.
"""


# ============================================================
# Priority 5: Cross-Page Synthesis Prompt
# Correlates data across multiple pages
# ============================================================

SYNTHESIS_PROMPT = """You are an expert architectural document analyst. You have been given extraction results from multiple pages of an architectural document set. Your task is to SYNTHESIZE and CORRELATE data across pages to produce a unified, deduplicated result.

You will receive:
1. Floorplan extraction data (per-page JSON with rooms, doors, windows, fixtures)
2. Table/schedule data (markdown tables extracted from schedule pages)
3. Total page count

Perform the following synthesis tasks:

1. **CORRELATE SCHEDULES WITH FLOORPLANS**: If door schedules, window schedules, or finish schedules are present in the table data, match each schedule entry to the corresponding item in the floorplan extractions. Update door/window specs with schedule details (hardware, material, fire rating, etc.).

2. **IDENTIFY UNITS**: Determine distinct unit numbers and types from title blocks, drawing labels, and room layouts. If multiple pages show the same unit (e.g., floor plan + enlarged bathroom), merge their data.

3. **APPLY GENERAL NOTES**: If general notes pages are present, determine which notes apply to which units/rooms and attach them.

4. **DEDUPLICATE**: If the same room, door, or window appears on multiple pages (e.g., overview + detail), merge into a single entry keeping the most detailed version.

5. **VALIDATE COUNTS**: Cross-check door counts from schedules vs. floorplans. Flag discrepancies.

6. **COMPUTE TOTALS**: Calculate aggregate metrics:
   - Total baseboard linear feet across all units
   - Total door count by type
   - Total window count by type
   - Total area by unit
   - Trade-specific scope summaries

Return a JSON object:
```json
{
  "units": [
    {
      "unit_number": "string",
      "unit_type": "string",
      "source_pages": [1, 3],
      "merged_data": {
        "rooms": [],
        "doors": [],
        "windows": [],
        "fixtures": [],
        "upgrades": []
      },
      "schedule_correlations": [
        {
          "schedule_type": "door_schedule",
          "schedule_page": 5,
          "items_matched": 8,
          "items_unmatched": 1,
          "discrepancies": ["Door D-09 in schedule not found in floorplan"]
        }
      ]
    }
  ],
  "general_notes_applied": [
    {
      "note": "string",
      "applies_to": ["Unit 101", "Unit 102"],
      "source_page": 1
    }
  ],
  "discrepancies": [
    "Door count mismatch: schedule shows 12 doors, floorplans show 10"
  ],
  "totals": {
    "total_units": 0,
    "total_baseboard_ft": 0.0,
    "total_doors": 0,
    "total_windows": 0,
    "total_area_sf": 0.0,
    "doors_by_type": {},
    "windows_by_type": {},
    "trades_summary": {}
  }
}
```

Return ONLY the JSON object. Be precise with correlations - only match items when confident.
"""


# ============================================================
# Table Extraction Prompt
# For structured table data from schedule pages
# ============================================================

TABLE_ANALYSIS_PROMPT = """Analyze this table/schedule from an architectural document. Determine the table type and extract structured data.

Common table types in architectural documents:
- Door Schedule: lists doors with marks (D-01), sizes, types, hardware, fire ratings
- Window Schedule: lists windows with marks (W-01), sizes, types, glazing
- Finish Schedule: lists rooms with floor, wall, ceiling finishes
- Room Schedule: lists rooms with areas, occupancy, finishes
- Fixture Schedule: lists plumbing/electrical fixtures
- Equipment Schedule: lists mechanical equipment

Return a JSON object:
```json
{
  "table_type": "string - one of: door_schedule, window_schedule, finish_schedule, room_schedule, fixture_schedule, equipment_schedule, general_notes, unknown",
  "entries": [
    {
      "mark": "string - item identifier (e.g. D-01, W-03)",
      "description": "string - item description",
      "specifications": {}
    }
  ],
  "notes": ["any footnotes or general notes from the table"]
}
```

Return ONLY the JSON object.
"""


# ============================================================
# Backward Compatibility: Original Basic Prompt
# ============================================================

FLOORPLAN_PROMPT = """Analyze this architectural floorplan image and extract the following information as JSON:

```json
{
  "rooms": [
    {
      "name": "room name",
      "area_sf": 0.0,
      "dimensions": "LxW"
    }
  ],
  "total_area_sf": 0.0,
  "door_count": 0,
  "window_count": 0,
  "notes": []
}
```

Return ONLY the JSON object.
"""
