# Doc-Parser Integration — Component Test Plan

> **Goal**: Validate each component in isolation before wiring them together.  
> **Approach**: Unit tests first, integration tests second, E2E last.  
> **Date**: 2026-03-02

---

## Component Inventory

| # | Component | Language | Type | Isolation Difficulty | Dependencies |
|---|-----------|----------|------|---------------------|--------------|
| 1 | `models.py` | Python | Pydantic schemas | ⬤ Easy | None |
| 2 | `detection.py` | Python | Image processing | ⬤⬤ Medium | numpy, cv2, pytesseract, PIL |
| 3 | `prompts.py` | Python | String constants | ⬤ Trivial | None |
| 4 | `confidence.py` | Python | Scoring logic | ⬤ Easy | models.py |
| 5 | `job_manager.py` | Python | Async state machine | ⬤⬤ Medium | models.py, asyncio |
| 6 | `hybrid.py` | Python | Pipeline orchestrator | ⬤⬤⬤ Hard | All Python modules + LLM + Docling |
| 7 | `server.py` | Python | FastAPI endpoints | ⬤⬤ Medium | job_manager, hybrid, detection |
| 8 | `doc-parser-client.ts` | TypeScript | HTTP client | ⬤⬤ Medium | fetch (mock) |
| 9 | `DocParserPanel.tsx` | TSX/SolidJS | UI component | ⬤⬤ Medium | SolidJS, fetch (mock) |
| 10 | `doc-parser-routes.ts` | TypeScript | Hono routes | ⬤⬤ Medium | doc-parser-client.ts |

---

## 1. `models.py` — Pydantic Data Models

**What it does**: Defines all shared types — job states, progress tracking, extraction schemas, API responses.  
**Test framework**: `pytest`  
**Mocks needed**: None  

### Test Cases

#### 1.1 Enum Completeness
```
test_job_status_values:
  - Assert JobStatus has: queued, processing, completed, failed, timeout, cancelled
  - Assert all values are strings (str, Enum)

test_processing_phase_values:
  - Assert ProcessingPhase has all 8 phases
  - Assert ordering: queued < docling_conversion < ... < complete

test_engine_type_values:
  - Assert EngineType has: docling, hybrid
```

#### 1.2 JobProgress Percent Calculation
```
test_progress_percent_queued:
  - Create JobProgress(current_phase=QUEUED)
  - Call update_percent()
  - Assert percent_complete == 0.0

test_progress_percent_complete:
  - Create JobProgress(current_phase=COMPLETE)
  - Call update_percent()
  - Assert percent_complete == 100.0

test_progress_percent_llm_analysis_page_granularity:
  - Create JobProgress(current_phase=LLM_ANALYSIS, current_page=3, total_pages=6)
  - Call update_percent()
  - Assert percent_complete is between 40.0 and 70.0 (interpolated)
  - Verify: higher current_page → higher percent

test_progress_percent_llm_analysis_zero_pages:
  - Create JobProgress(current_phase=LLM_ANALYSIS, total_pages=0)
  - Call update_percent()
  - Assert no division by zero, returns base phase weight (70.0)

test_progress_percent_monotonic:
  - For each phase in order, create JobProgress and update_percent()
  - Assert each subsequent phase has >= percent than previous
```

#### 1.3 JobRecord Defaults & Touch
```
test_job_record_defaults:
  - Create JobRecord() with no args
  - Assert job_id is valid UUID string
  - Assert status == QUEUED
  - Assert expires_at is ~2 hours from now

test_job_record_touch:
  - Create JobRecord()
  - Save original updated_at
  - Sleep briefly or mock time
  - Call touch()
  - Assert updated_at changed
```

#### 1.4 Extraction Model Validation
```
test_room_defaults:
  - Create Room() with no args
  - Assert all numeric fields are 0, lists are empty

test_door_spec_full:
  - Create DoorSpec with all fields populated
  - Assert model_dump() round-trips correctly

test_unit_extraction_nested:
  - Create UnitExtraction with rooms, doors, windows, fixtures, upgrades
  - Assert all nested lists serialize/deserialize correctly

test_confidence_score_defaults:
  - Create ConfidenceScore()
  - Assert overall == 0.0, all booleans False
```

#### 1.5 API Response Models
```
test_status_response_excludes_result:
  - Create StatusResponse with all fields
  - Assert model has NO result/data field
  - Assert serialized size is small (< 1KB)

test_result_summary_aggregation:
  - Create ResultSummary with known values
  - Assert all fields serialize correctly
```

**Run command**: `cd doc-parser && python -m pytest tests/test_models.py -v`

---

## 2. `detection.py` — Floorplan Detection

**What it does**: Canny edge detection, architectural text recognition, image classification.  
**Test framework**: `pytest`  
**Mocks needed**: Test images (synthetic), optional pytesseract mock  
**Test fixtures**: Generate synthetic test images programmatically  

### Test Cases

#### 2.1 `is_architectural_drawing()`
```
test_blank_white_image:
  - Create 500x500 white PIL Image
  - Assert returns False (no edges)

test_synthetic_floorplan:
  - Create 800x600 image with:
    - Multiple horizontal/vertical lines (walls)
    - Quarter-circle arcs (door swings)
    - At least 20 line segments
  - Assert returns True

test_photograph_rejection:
  - Create image with random color noise (simulating photo)
  - High color variance, smooth gradients
  - Assert returns False

test_small_image_rejection:
  - Create 50x50 image with lines
  - Assert returns False (< 100px threshold)

test_edge_threshold_sensitivity:
  - Create image with moderate line work
  - Test with threshold=0.02 (permissive) → True
  - Test with threshold=0.10 (strict) → False

test_fallback_without_cv2:
  - Temporarily mock HAS_CV2 = False
  - Assert falls back to _legacy_bw_check()
  - Assert B&W drawing returns True
  - Assert color photo returns True (relaxed threshold 15.0)
```

#### 2.2 `has_architectural_text()`
```
test_with_dimension_text:
  - Create image with OCR-readable text: "12'-6\" x 10'-0\""
  - Assert returns True (dimension pattern match)
  - NOTE: Requires Tesseract installed; skip if unavailable

test_with_room_labels:
  - Create image with text: "BEDROOM  KITCHEN  BATHROOM"
  - Assert returns True (≥2 architectural labels)

test_with_no_text:
  - Create blank image
  - Assert returns False

test_without_tesseract:
  - Mock HAS_TESSERACT = False
  - Assert returns True (permissive fallback)

test_score_threshold:
  - Image with only 1 room label, no dimensions → score < 3 → False
  - Image with 2 labels + dimensions → score ≥ 3 → True
```

#### 2.3 `classify_image()`
```
test_classify_floorplan:
  - Synthetic floorplan image (lines + text)
  - Assert returns "floorplan"

test_classify_photo:
  - Random color noise image
  - Assert returns "site_photo"

test_classify_table:
  - Image with regular grid pattern (horizontal + vertical lines)
  - Assert returns "table"

test_classify_diagram:
  - Image with lines but no architectural text
  - Assert returns "diagram"

test_classify_unknown:
  - Ambiguous image (low edges, no text)
  - Assert returns "unknown"
```

#### 2.4 `extract_floorplan_candidates()`
```
test_multiple_candidates:
  - Provide 5 images: 2 floorplans, 1 photo, 1 table, 1 diagram
  - Assert returns exactly 2 candidates
  - Assert page numbers preserved correctly

test_failure_includes_candidate:
  - Mock classify_image to raise Exception for one image
  - Assert that image is INCLUDED (not dropped) — prevents data loss

test_empty_input:
  - Provide empty list
  - Assert returns empty list, no errors
```

#### 2.5 Helper Functions
```
test_has_photo_characteristics_color_image:
  - High std deviation across RGB channels
  - Assert returns True

test_has_photo_characteristics_bw_drawing:
  - Low color variance
  - Assert returns False

test_has_table_structure:
  - Image with grid lines
  - Assert returns True

test_image_to_base64:
  - Convert known image to base64
  - Decode and verify dimensions match
```

**Run command**: `cd doc-parser && python -m pytest tests/test_detection.py -v`  
**Prerequisites**: `pip install numpy opencv-python-headless Pillow`  
**Note**: Tests requiring Tesseract should use `@pytest.mark.skipif(not HAS_TESSERACT)`

---

## 3. `prompts.py` — LLM Prompt Templates

**What it does**: Defines prompt strings for floorplan extraction, synthesis, and table analysis.  
**Test framework**: `pytest`  
**Mocks needed**: None  

### Test Cases

```
test_floorplan_prompt_rich_contains_required_fields:
  - Assert FLOORPLAN_PROMPT_RICH contains: "unit_number", "rooms", "doors",
    "windows", "fixtures", "upgrades", "baseboard_length_ft",
    "baseboard_exclusions", "general_notes"
  - Assert contains JSON template structure

test_floorplan_prompt_rich_instructions:
  - Assert contains "EVERY door" (exhaustive extraction)
  - Assert contains "EVERY window"
  - Assert contains "baseboard" calculation instructions
  - Assert contains "Return ONLY the JSON object"

test_synthesis_prompt_contains_correlation_tasks:
  - Assert SYNTHESIS_PROMPT contains: "CORRELATE", "DEDUPLICATE",
    "VALIDATE COUNTS", "COMPUTE TOTALS"
  - Assert contains output JSON template

test_table_analysis_prompt_types:
  - Assert TABLE_ANALYSIS_PROMPT contains all schedule types:
    "door_schedule", "window_schedule", "finish_schedule"

test_backward_compat_prompt_exists:
  - Assert FLOORPLAN_PROMPT is defined and non-empty
  - Assert it's simpler than FLOORPLAN_PROMPT_RICH

test_prompts_are_strings:
  - Assert all three prompts are type str
  - Assert none are empty
  - Assert FLOORPLAN_PROMPT_RICH length > FLOORPLAN_PROMPT length
```

**Run command**: `cd doc-parser && python -m pytest tests/test_prompts.py -v`

---

## 4. `confidence.py` — Confidence Scoring

**What it does**: Calculates completeness metrics across 7 dimensions with weighted scoring.  
**Test framework**: `pytest`  
**Mocks needed**: None (pure logic)  

### Test Cases

#### 4.1 `calculate_confidence()`
```
test_empty_units:
  - Pass units=[], tables=[]
  - Assert overall == 0.0
  - Assert per_page contains "No units extracted" note

test_perfect_extraction:
  - Create unit with:
    - 3 rooms (all with area_sf, length_ft, width_ft, baseboard_length_ft, baseboard_exclusions)
    - 4 doors (all with type, width_in, hardware)
    - 3 windows (all with type, width_in)
    - 2 fixtures (all with type or specifications)
    - unit_number="101", unit_type="2BR"
  - Pass synthesis={"some": "data"}
  - Assert overall > 0.8
  - Assert all boolean flags are True

test_rooms_only:
  - Unit with rooms but no doors/windows/fixtures
  - Assert room_dimensions == True
  - Assert door_specifications == False
  - Assert window_specifications == False
  - Assert overall is moderate (0.2-0.4 range)

test_weight_distribution:
  - Verify weights sum to 1.0:
    rooms(0.25) + doors(0.20) + windows(0.15) + fixtures(0.10) +
    baseboard(0.15) + unit_id(0.10) + synthesis(0.05) = 1.00

test_per_page_breakdown:
  - Create 2 units from different pages
  - Assert per_page has entries for both pages
  - Assert each entry has fields_populated, completeness, counts

test_coverage_metrics:
  - Pass total_pages=10, floorplans_found=3
  - Assert per_page["coverage"]["coverage_ratio"] == 0.3

test_unit_identification_scoring:
  - Unit with unit_number="page_1" → should NOT count as identified
  - Unit with unit_number="101" → should count
  - Assert unit_identification flag reflects this

test_baseboard_scoring:
  - Rooms with baseboard_length_ft > 0 and baseboard_exclusions populated
  - Assert baseboard_data == True
  - Rooms without baseboard data → baseboard_data == False

test_synthesis_flag:
  - With synthesis=None → cross_page_synthesis == False
  - With synthesis={"data": "present"} → cross_page_synthesis == True
```

#### 4.2 `confidence_summary_text()`
```
test_summary_format:
  - Create ConfidenceScore with known values
  - Assert output contains "Overall Confidence:"
  - Assert ✅ for True flags, ❌ for False flags
  - Assert all 7 dimension labels present
```

**Run command**: `cd doc-parser && python -m pytest tests/test_confidence.py -v`

---

## 5. `job_manager.py` — Job Lifecycle Management

**What it does**: Manages job state machine, progress tracking, TTL cleanup, status/result separation.  
**Test framework**: `pytest` + `pytest-asyncio`  
**Mocks needed**: None for InMemoryJobStore; Supabase mock for SupabaseJobStore  

### Test Cases

#### 5.1 InMemoryJobStore
```
test_create_and_get_job:
  - Create job via store.create_job()
  - Retrieve via store.get_job()
  - Assert all fields match

test_update_job:
  - Create job, update status to PROCESSING
  - Assert get_job returns updated status
  - Assert updated_at changed (touch() called)

test_store_and_get_result:
  - Store result dict for a job_id
  - Retrieve via get_result()
  - Assert data matches exactly

test_delete_expired:
  - Create 3 jobs: 1 expired+completed, 1 expired+failed, 1 not expired
  - Call delete_expired()
  - Assert returns 2 (deleted count)
  - Assert non-expired job still exists

test_delete_expired_skips_processing:
  - Create expired job with status=PROCESSING
  - Call delete_expired()
  - Assert returns 0 (processing jobs never auto-deleted)

test_list_jobs_filter:
  - Create jobs with different statuses
  - list_jobs(status="completed") returns only completed
  - list_jobs(status=None) returns all
```

#### 5.2 JobManager Lifecycle
```
test_create_job_returns_queued:
  - Call job_manager.create_job("test.pdf", "docling")
  - Assert job.status == QUEUED (NOT processing — Priority 4c)

test_start_processing_transition:
  - Create job → start_processing()
  - Assert status transitions to PROCESSING

test_update_progress_percent_calculation:
  - Create job → start_processing()
  - update_progress(phase=LLM_ANALYSIS, current_page=2, total_pages=4)
  - Get status → assert percent_complete is reasonable (40-70%)

test_complete_job_stores_result_separately:
  - Create job → complete_job(job_id, {"units": [...]})
  - get_status() → assert status=COMPLETED, NO result data in response
  - get_result() → assert full result data returned

test_fail_job:
  - Create job → fail_job(job_id, "Something broke")
  - Assert status == FAILED
  - Assert error message preserved

test_timeout_job:
  - Create job → timeout_job(job_id)
  - Assert status == TIMEOUT
  - Assert error contains timeout message

test_get_status_is_lightweight:
  - Complete a job with large result (1MB+)
  - Call get_status()
  - Assert response does NOT contain result data
  - Assert response is StatusResponse type

test_get_result_summary:
  - Complete job with known result data
  - Call get_result_summary()
  - Assert counts match (pages, doors, windows, baseboard_ft)
```

#### 5.3 Cleanup Loop
```
test_cleanup_loop_starts:
  - Call start_cleanup_loop(interval_minutes=0.01)
  - Wait briefly
  - Assert cleanup task is running
  - Call stop_cleanup_loop()

test_cleanup_removes_expired:
  - Create expired completed job
  - Start cleanup loop with short interval
  - Wait for one cycle
  - Assert job is deleted
```

#### 5.4 Factory
```
test_create_job_manager_memory:
  - create_job_manager(backend="memory")
  - Assert returns JobManager with InMemoryJobStore

test_create_job_manager_supabase_fallback:
  - create_job_manager(backend="supabase") without credentials
  - Assert falls back to InMemoryJobStore with warning
```

**Run command**: `cd doc-parser && python -m pytest tests/test_job_manager.py -v`  
**Prerequisites**: `pip install pytest-asyncio`

---

## 6. `hybrid.py` — Hybrid Pipeline

**What it does**: Orchestrates Docling → Classification → Claude → Synthesis → Output.  
**Test framework**: `pytest` + `pytest-asyncio`  
**Mocks needed**: `litellm`, `docling`, `pdf2image`, `JobManager`  
**Strategy**: Test helper functions directly; mock external services for pipeline tests  

### Test Cases

#### 6.1 `run_llm_extraction()` (mocked)
```
test_llm_extraction_success:
  - Mock litellm.completion to return valid JSON response
  - Call run_llm_extraction()
  - Assert returns response text

test_llm_extraction_failure:
  - Mock litellm.completion to raise Exception
  - Assert run_llm_extraction raises Exception
```

#### 6.2 `run_text_llm()` (mocked)
```
test_text_llm_formats_prompt:
  - Mock litellm.completion, capture messages arg
  - Call run_text_llm(provider, prompt, context)
  - Assert message contains both prompt and context separated by "--- DATA ---"
```

#### 6.3 `assemble_hybrid_output()` — CRITICAL (no mocks needed)
```
test_assemble_basic_output:
  - Provide 2 successful unit_extractions, 1 table, 1 footer
  - Call assemble_hybrid_output()
  - Assert output["engine"] == "hybrid"
  - Assert len(output["units"]) == 2
  - Assert output["tables"] has 1 entry
  - Assert output["footer_sample"] is not None

test_assemble_failed_extraction_recorded:
  - Provide 1 successful + 1 failed extraction
  - Assert output["units"] has 1 entry (successful only)
  - Assert failed page has error in pages dict

test_assemble_unit_number_fallback:
  - Extraction without unit_number field
  - Assert unit_number defaults to "page_{N}"

test_assemble_page_classification:
  - Provide floorplans, photos, diagrams, tables
  - Assert each page classified correctly in output["pages"]

test_assemble_summary_totals:
  - Known data: 3 doors, 2 windows, 50ft baseboard
  - Assert summary["total_doors"] == 3
  - Assert summary["total_windows"] == 2
  - Assert summary["total_baseboard_ft"] == 50.0

test_assemble_general_notes_deduplication:
  - Two extractions with overlapping general_notes
  - Assert output["general_notes"] has no duplicates

test_assemble_synthesis_included:
  - Pass synthesis dict
  - Assert output["synthesis"] matches
  - Assert summary["has_synthesis"] == True

test_assemble_extraction_error_count:
  - 3 extractions: 2 success, 1 failure
  - Assert summary["extraction_errors"] == 1
```

#### 6.4 `process_hybrid()` — Integration (heavily mocked)
```
test_hybrid_pipeline_happy_path:
  - Mock: Docling converter, pdf2image, litellm, JobManager
  - Provide small synthetic PDF path
  - Assert job transitions: queued → processing → completed
  - Assert job_manager.complete_job called with result containing units

test_hybrid_pipeline_timeout:
  - Mock LLM to sleep longer than timeout
  - Assert job_manager.timeout_job called

test_hybrid_pipeline_failure:
  - Mock Docling to raise ImportError
  - Assert job_manager.fail_job called with error message

test_hybrid_pipeline_cleanup:
  - After completion (success or failure)
  - Assert temp file is deleted

test_hybrid_progress_updates:
  - Mock all externals, capture job_manager.update_progress calls
  - Assert phases progress in order: DOCLING_CONVERSION → CLASSIFICATION →
    IMAGE_EXTRACTION → LLM_ANALYSIS → SYNTHESIS → UPLOADING
```

**Run command**: `cd doc-parser && python -m pytest tests/test_hybrid.py -v`  
**Note**: Most tests require extensive mocking. `assemble_hybrid_output()` is the highest-value target for pure unit tests.

---

## 7. `server.py` — FastAPI Endpoints

**What it does**: HTTP API layer — parse endpoints, status/results separation, health, jobs CRUD.  
**Test framework**: `pytest` + `httpx` (FastAPI TestClient)  
**Mocks needed**: `job_manager` (inject mock), background tasks  

### Test Cases

#### 7.1 POST `/parse/docling`
```
test_parse_docling_returns_queued:
  - Upload a small PDF file
  - Assert response status 200
  - Assert response["status"] == "queued" (NOT "processing")
  - Assert response has job_id, engine="docling", file name

test_parse_docling_creates_job:
  - Upload PDF
  - Assert job_manager.create_job was called with engine="docling"
```

#### 7.2 POST `/parse/hybrid`
```
test_parse_hybrid_returns_queued:
  - Upload PDF with engine=hybrid
  - Assert response["status"] == "queued"
  - Assert response["engine"] == "hybrid"

test_parse_hybrid_accepts_optional_params:
  - Upload with provider, tenant_name, project_name
  - Assert no errors, job created
```

#### 7.3 GET `/status/{job_id}`
```
test_status_found:
  - Create job, then GET /status/{job_id}
  - Assert 200, contains progress, status, engine
  - Assert NO result data in response

test_status_not_found:
  - GET /status/nonexistent-id
  - Assert 404

test_status_polling_safe:
  - Complete a job with large result
  - GET /status/{job_id}
  - Assert response payload is small (no result data)
```

#### 7.4 GET `/results/{job_id}`
```
test_results_completed:
  - Complete a job with known result
  - GET /results/{job_id}
  - Assert 200, contains full result data

test_results_still_processing:
  - Create job (status=processing)
  - GET /results/{job_id}
  - Assert response contains "still processing" message
  - Assert NO error status code (graceful)

test_results_failed:
  - Fail a job
  - GET /results/{job_id}
  - Assert response contains error message

test_results_summary_mode:
  - Complete job
  - GET /results/{job_id}?summary=true
  - Assert response contains summary but NOT full result
  - Assert summary has counts (pages, doors, windows, etc.)

test_results_not_found:
  - GET /results/nonexistent-id
  - Assert 404
```

#### 7.5 GET `/health`
```
test_health_returns_status:
  - GET /health
  - Assert 200
  - Assert response has: status, version, engines, dependencies, jobs, config

test_health_reports_dependencies:
  - Assert dependencies dict has: docling, tesseract, litellm
  - Values are booleans

test_health_reports_job_counts:
  - Create some jobs in various states
  - Assert jobs.running, jobs.queued, jobs.total are accurate
```

#### 7.6 GET `/jobs`
```
test_list_all_jobs:
  - Create 3 jobs
  - GET /jobs
  - Assert total == 3, jobs array has 3 entries

test_list_jobs_filter:
  - Create jobs with different statuses
  - GET /jobs?status=completed
  - Assert only completed jobs returned
```

#### 7.7 DELETE `/jobs/{job_id}`
```
test_delete_idle_job:
  - Create completed job
  - DELETE /jobs/{job_id}
  - Assert 200, deleted confirmation

test_delete_running_job_rejected:
  - Create processing job
  - DELETE /jobs/{job_id}
  - Assert 409 Conflict

test_delete_not_found:
  - DELETE /jobs/nonexistent
  - Assert 404
```

#### 7.8 Legacy Endpoint
```
test_legacy_result_endpoint:
  - GET /result/{job_id} (singular)
  - Assert same behavior as /results/{job_id}
```

**Run command**: `cd doc-parser && python -m pytest tests/test_server.py -v`  
**Prerequisites**: `pip install httpx pytest-asyncio`

---

## 8. `doc-parser-client.ts` — Hono API Client

**What it does**: TypeScript HTTP client wrapping doc-parser REST API.  
**Test framework**: `vitest`  
**Mocks needed**: `global.fetch` mock  

### Test Cases

```
test_submitParseJob_docling:
  - Mock fetch to return { job_id, status: "queued", engine: "docling" }
  - Call submitParseJob(buffer, "test.pdf", "docling")
  - Assert fetch called with POST to /parse/docling
  - Assert FormData contains file blob and provider

test_submitParseJob_hybrid:
  - Same as above but engine="hybrid"
  - Assert endpoint is /parse/hybrid

test_submitParseJob_with_options:
  - Pass all optional params (provider, tenantName, etc.)
  - Assert all appended to FormData

test_submitParseJob_error:
  - Mock fetch to return 500
  - Assert throws Error with status code

test_getJobStatus_success:
  - Mock fetch to return DocParserStatus
  - Assert returns parsed status object

test_getJobStatus_404:
  - Mock fetch to return 404
  - Assert throws "not found" error

test_getJobResults_full:
  - Mock fetch to return full result
  - Call getJobResults(jobId, false)
  - Assert fetch URL has no ?summary param

test_getJobResults_summary:
  - Call getJobResults(jobId, true)
  - Assert fetch URL includes ?summary=true

test_checkHealth_success:
  - Mock fetch to return health response
  - Assert returns status, engines, dependencies

test_checkHealth_unreachable:
  - Mock fetch to throw network error
  - Assert returns { status: "unreachable" } (no throw)

test_checkHealth_timeout:
  - Mock fetch to hang
  - Assert AbortSignal.timeout(5000) triggers
  - Assert returns { status: "unreachable" }

test_mapToParseDocument:
  - Create DocParserResult with known units, confidence, summary
  - Call mapToParseDocument(result, "doc-123")
  - Assert document_id set correctly
  - Assert units array passed through
  - Assert confidence and summary included

test_mapToParseDocument_empty:
  - Result with no units
  - Assert returns empty units array, no crash
```

**Run command**: `cd apps/api && npx vitest run src/services/doc-parser-client.test.ts`

---

## 9. `DocParserPanel.tsx` — SolidJS Frontend Component

**What it does**: Engine selection UI, progress visualization, confidence display.  
**Test framework**: `vitest` + `@solidjs/testing-library`  
**Mocks needed**: `fetch` mock for API calls  

### Test Cases

#### 9.1 Engine Selection
```
test_renders_engine_selector:
  - Render DocParserPanel
  - Assert two engine options visible: "Claude Direct" and "Hybrid"
  - Assert default selection is "claude-direct"

test_engine_selection_changes:
  - Click "Hybrid" option
  - Assert selection state updates
```

#### 9.2 Job Submission
```
test_submit_triggers_api_call:
  - Mock fetch for POST /api/doc-parser/parse
  - Select hybrid engine, trigger parse
  - Assert fetch called with correct engine parameter

test_submit_shows_progress:
  - After successful submission
  - Assert progress panel becomes visible
  - Assert polling starts (setInterval called)
```

#### 9.3 Progress Display
```
test_progress_bar_updates:
  - Mock status endpoint to return 45% complete
  - Assert progress bar width reflects percentage

test_phase_labels_display:
  - Mock status with phase="llm_analysis"
  - Assert displays "Analyzing Floorplans" (human-readable label)

test_page_counter:
  - Mock status with current_page=3, total_pages=8
  - Assert displays "Page 3 of 8" or similar

test_floorplans_found_counter:
  - Mock status with floorplans_found=4
  - Assert displays floorplan count
```

#### 9.4 Completion & Results
```
test_completed_fetches_results:
  - Mock status to return "completed"
  - Assert polling stops
  - Assert results endpoint called

test_confidence_display:
  - Mock results with confidence score
  - Assert overall percentage displayed
  - Assert dimension checkmarks (✅/❌) shown

test_error_display:
  - Mock status to return "failed" with error message
  - Assert error message displayed to user
  - Assert polling stopped

test_timeout_display:
  - Mock status to return "timeout"
  - Assert timeout message displayed
```

#### 9.5 Cleanup
```
test_cleanup_on_unmount:
  - Start polling, then unmount component
  - Assert clearInterval called (no memory leak)
```

**Run command**: `cd apps/work-orders && npx vitest run src/components/doc-parser/DocParserPanel.test.tsx`

---

## 10. `doc-parser-routes.ts` — Hono API Routes (NOT YET CREATED)

**Status**: This file does not exist yet. It will be created during the wiring step.  
**Test plan**: Deferred until after wiring. Will proxy requests from Hono to doc-parser service.

### Anticipated Test Cases
```
test_proxy_parse_docling:
  - POST /api/doc-parser/parse/docling → proxied to doc-parser:5000
test_proxy_parse_hybrid:
  - POST /api/doc-parser/parse/hybrid → proxied
test_proxy_status:
  - GET /api/doc-parser/status/:id → proxied
test_proxy_results:
  - GET /api/doc-parser/results/:id → proxied
test_proxy_health:
  - GET /api/doc-parser/health → proxied
test_service_unavailable:
  - doc-parser down → returns 503 with helpful message
```

---

## Execution Order (Recommended)

```
Phase 1 — Pure Unit Tests (no external deps):
  1. models.py        ← start here, foundation for everything
  2. prompts.py       ← trivial, quick win
  3. confidence.py    ← pure logic, depends only on models

Phase 2 — Logic with Library Deps:
  4. detection.py     ← needs numpy/cv2/PIL, synthetic images
  5. job_manager.py   ← async tests, InMemoryJobStore only

Phase 3 — Integration (mocked externals):
  6. hybrid.py        ← assemble_hybrid_output() first (pure),
                         then process_hybrid() (mocked)
  7. server.py        ← FastAPI TestClient, mock job_manager

Phase 4 — Frontend:
  8. doc-parser-client.ts  ← mock fetch
  9. DocParserPanel.tsx    ← mock fetch + SolidJS testing

Phase 5 — After Wiring:
  10. doc-parser-routes.ts ← proxy tests
  11. End-to-end integration test
```

---

## Test Infrastructure Setup

### Python (doc-parser)
```bash
cd doc-parser
pip install pytest pytest-asyncio httpx Pillow numpy opencv-python-headless
mkdir -p tests
touch tests/__init__.py tests/conftest.py
```

### TypeScript (apps/api + apps/work-orders)
```bash
cd apps/api && npm install -D vitest
cd apps/work-orders && npm install -D vitest @solidjs/testing-library jsdom
```

### conftest.py (shared fixtures)
```python
import pytest
from PIL import Image, ImageDraw
import numpy as np

@pytest.fixture
def blank_image():
    return Image.new("RGB", (500, 500), "white")

@pytest.fixture
def synthetic_floorplan():
    img = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(img)
    # Draw walls
    for y in range(100, 500, 100):
        draw.line([(50, y), (750, y)], fill="black", width=2)
    for x in range(50, 800, 150):
        draw.line([(x, 100), (x, 500)], fill="black", width=2)
    # Draw door arcs
    draw.arc([(200, 200), (260, 260)], 0, 90, fill="black", width=1)
    draw.arc([(400, 300), (460, 360)], 180, 270, fill="black", width=1)
    return img

@pytest.fixture
def photo_image():
    arr = np.random.randint(0, 255, (400, 600, 3), dtype=np.uint8)
    return Image.fromarray(arr)

@pytest.fixture
def sample_unit_dict():
    return {
        "unit_number": "101",
        "unit_type": "2BR",
        "floor": 1,
        "bedrooms": 2,
        "bathrooms": 1,
        "half_baths": 0,
        "area_sf": 850.0,
        "rooms": [
            {"name": "Master Bedroom", "area_sf": 180.0, "length_ft": 15.0,
             "width_ft": 12.0, "baseboard_length_ft": 42.0,
             "baseboard_exclusions": ["closet opening", "doorway"],
             "baseboard_exclusion_reasoning": "2 openings reduce run",
             "fixtures": [], "flooring_type": "carpet", "notes": ""},
            {"name": "Kitchen", "area_sf": 120.0, "length_ft": 12.0,
             "width_ft": 10.0, "baseboard_length_ft": 18.0,
             "baseboard_exclusions": ["kitchen cabinets"],
             "baseboard_exclusion_reasoning": "cabinets cover 2 walls",
             "fixtures": ["range", "refrigerator"], "flooring_type": "tile",
             "notes": ""},
        ],
        "doors": [
            {"location": "Entry", "room": "Hallway", "type": "exterior",
             "width_in": 36.0, "height_in": 80.0, "hardware": "lever",
             "action": "swing", "swing_direction": "in", "material": "solid-core",
             "notes": ""},
        ],
        "windows": [
            {"location": "Living Room - North", "room": "Living Room",
             "type": "double-hung", "width_in": 36.0, "height_in": 48.0,
             "sill_height_in": 36.0, "count": 1, "glazing": "double",
             "operable": True, "notes": ""},
        ],
        "fixtures": [
            {"name": "Toilet", "room": "Bathroom", "type": "plumbing",
             "specifications": "standard", "count": 1},
        ],
        "upgrades": [
            {"description": "Replace flooring", "trade": "flooring",
             "location": "Kitchen", "specifications": "LVP"},
        ],
        "general_notes": ["All work per local code"],
        "source_page": 1,
    }
```
