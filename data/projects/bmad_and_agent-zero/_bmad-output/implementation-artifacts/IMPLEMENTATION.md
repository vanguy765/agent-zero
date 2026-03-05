# Doc-Parser Integration: Implementation Guide

**Priorities 1–7 Complete Implementation**

---

## Table of Contents

1. [File Inventory](#file-inventory)
2. [File Mapping to Monorepo](#file-mapping-to-monorepo)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Integration](#step-by-step-integration)
5. [Docker & Networking](#docker--networking)
6. [Environment Variables](#environment-variables)
7. [Testing Strategy](#testing-strategy)
8. [Migration Notes](#migration-notes)
9. [Priority Cross-Reference](#priority-cross-reference)

---

## File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| **doc-parser/models.py** | 271 | Pydantic models: job records, progress, units, confidence scores |
| **doc-parser/prompts.py** | 249 | P1: Rich extraction prompts aligned with ClaudePdfParser; P5: Synthesis prompt |
| **doc-parser/detection.py** | 434 | P2: Canny edge detection, architectural text regex, image classifier |
| **doc-parser/job_manager.py** | 555 | P3+P4: Job lifecycle, progress tracking, in-memory + Supabase persistence, TTL cleanup |
| **doc-parser/confidence.py** | 266 | P6: Confidence scoring across 8 extraction dimensions |
| **doc-parser/hybrid.py** | 695 | P7: Hybrid pipeline (Docling decomposition → Claude extraction) |
| **doc-parser/server.py** | 805 | Main FastAPI app integrating all priorities, split endpoints |
| **doc-parser/requirements.txt** | 31 | Python dependencies |
| **hono-api/doc-parser-client.ts** | 242 | HTTP client for doc-parser service with typed interfaces |
| **hono-api/doc-parser-routes.ts** | 188 | Hono proxy routes: engine selection, status polling, results fetch |
| **work-orders/ProjectDocuments.tsx** | 589 | SolidJS components: engine selector, progress bar, confidence badge |

**Total: ~4,325 lines across 11 files**

---

## File Mapping to Monorepo

Copy each file from `implementation-artifacts/` to the corresponding location in `voicelog-scaffold/`:

```
implementation-artifacts/          →  voicelog-scaffold/
├── doc-parser/
│   ├── models.py                  →  doc-parser/models.py           (NEW)
│   ├── prompts.py                 →  doc-parser/prompts.py          (REPLACE)
│   ├── detection.py               →  doc-parser/detection.py        (NEW)
│   ├── job_manager.py             →  doc-parser/job_manager.py      (NEW)
│   ├── confidence.py              →  doc-parser/confidence.py       (NEW)
│   ├── hybrid.py                  →  doc-parser/hybrid.py           (NEW)
│   ├── server.py                  →  doc-parser/server.py           (REPLACE)
│   └── requirements.txt           →  doc-parser/requirements.txt    (MERGE)
├── hono-api/
│   ├── doc-parser-client.ts       →  apps/api/src/services/doc-parser-client.ts  (NEW)
│   └── doc-parser-routes.ts       →  apps/api/src/routes/doc-parser-routes.ts    (NEW)
└── work-orders/
    └── ProjectDocuments.tsx        →  apps/work-orders/src/components/doc-parser/  (NEW)
```

### Key Decisions

- **server.py REPLACES** the existing `server.py` — it's a full rewrite incorporating all enhancements while maintaining backward compatibility via the `/parse/docling` endpoint
- **prompts.py REPLACES** the existing `prompts.py` — adds rich prompts while keeping the original `FLOORPLAN_PROMPT` for backward compatibility
- **requirements.txt should be MERGED** — add new dependencies (`opencv-python-headless`, `numpy`) to existing file
- **ProjectDocuments.tsx is NEW components** — import and wire into the existing component, don't replace it

---

## Prerequisites

### System Dependencies (doc-parser container)

```bash
apt-get update && apt-get install -y \
  tesseract-ocr \
  poppler-utils \
  libgl1-mesa-glx
```

### Python Dependencies

```bash
cd doc-parser
pip install -r requirements.txt
```

### New packages beyond existing:

- `opencv-python-headless` — Canny edge detection for P2
- `numpy` — Image array processing for P2
- `pydantic>=2.5.0` — Data models (may already be installed via FastAPI)

---

## Step-by-Step Integration

### Step 1: Copy doc-parser Backend Files

```bash
# From voicelog-scaffold root
cp implementation-artifacts/doc-parser/models.py      doc-parser/
cp implementation-artifacts/doc-parser/detection.py    doc-parser/
cp implementation-artifacts/doc-parser/job_manager.py  doc-parser/
cp implementation-artifacts/doc-parser/confidence.py   doc-parser/
cp implementation-artifacts/doc-parser/hybrid.py       doc-parser/

# These REPLACE existing files:
cp implementation-artifacts/doc-parser/prompts.py      doc-parser/
cp implementation-artifacts/doc-parser/server.py       doc-parser/

# Merge requirements:
cat implementation-artifacts/doc-parser/requirements.txt >> doc-parser/requirements.txt
# Then deduplicate manually
```

### Step 2: Verify doc-parser Starts

```bash
cd doc-parser
pip install -r requirements.txt
python server.py
# Should start on port 5000
# Check: curl http://localhost:5000/health
```

Expected health response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "engines": ["docling", "hybrid"],
  "dependencies": {
    "docling": true,
    "tesseract": true,
    "litellm": true
  }
}
```

### Step 3: Copy Hono API Files

```bash
mkdir -p apps/api/src/services
mkdir -p apps/api/src/routes

cp implementation-artifacts/hono-api/doc-parser-client.ts  apps/api/src/services/
cp implementation-artifacts/hono-api/doc-parser-routes.ts  apps/api/src/routes/
```

### Step 4: Register Routes in Hono App

In your main Hono app file (e.g., `apps/api/src/index.ts`):

```typescript
import { docParserRoutes } from './routes/doc-parser-routes';

// Add to your existing app setup:
app.route('/api', docParserRoutes);
```

### Step 5: Wire Existing Parse Route

The `doc-parser-routes.ts` handles `docling` and `hybrid` engines. Your existing Claude Direct handler should remain for `claude-direct` engine. Modify your existing parse route:

```typescript
// In your existing documents route handler:
documentsRoute.post('/documents/:id/parse', async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const engine = body?.engine || 'claude-direct';

  if (engine === 'claude-direct') {
    // YOUR EXISTING ClaudePdfParser LOGIC HERE
    return handleExistingClaudeParse(c);
  }

  // For docling/hybrid, forward to doc-parser routes
  // (handled by docParserRoutes registered above)
});
```

### Step 6: Copy Frontend Components

```bash
mkdir -p apps/work-orders/src/components/doc-parser
cp implementation-artifacts/work-orders/ProjectDocuments.tsx \
   apps/work-orders/src/components/doc-parser/index.tsx
```

### Step 7: Wire Frontend Components

In your existing `ProjectDocuments.tsx`:

```typescript
import {
  useDocParserJob,
  EngineSelector,
  ParseProgress,
  ParseErrorDisplay,
  ParseResultSummary,
  type ParseEngine,
} from './doc-parser';

// Inside your component:
const [engine, setEngine] = createSignal<ParseEngine>('hybrid');
const docParser = useDocParserJob();

// See the integration example at the bottom of ProjectDocuments.tsx
// for the complete JSX wiring pattern.
```

---

## Docker & Networking

### docker-compose.yml Addition

```yaml
services:
  doc-parser:
    build: ./doc-parser
    ports:
      - "5000:5000"
    environment:
      - PORT=5000
      - DEFAULT_LLM_PROVIDER=anthropic/claude-3.5-sonnet
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - JOB_STORE_BACKEND=memory  # or "supabase"
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - CLEANUP_INTERVAL_MINUTES=10
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 4G  # Docling + Tesseract need memory

  api:
    # Your existing Hono API service
    environment:
      - DOC_PARSER_URL=http://doc-parser:5000
    depends_on:
      doc-parser:
        condition: service_healthy
```

### Dockerfile for doc-parser

```dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "server.py"]
```

---

## Environment Variables

### doc-parser Service

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5000` | Server port |
| `DEFAULT_LLM_PROVIDER` | `anthropic/claude-3.5-sonnet` | LiteLLM model identifier |
| `ANTHROPIC_API_KEY` | — | Required for Claude |
| `JOB_STORE_BACKEND` | `memory` | `memory` or `supabase` |
| `SUPABASE_URL` | — | Required if backend=supabase |
| `SUPABASE_SERVICE_KEY` | — | Required if backend=supabase |
| `CLEANUP_INTERVAL_MINUTES` | `10` | How often to purge expired jobs |

### Hono API Service

| Variable | Default | Description |
|----------|---------|-------------|
| `DOC_PARSER_URL` | `http://doc-parser:5000` | Doc-parser service URL |

---

## Testing Strategy

### 1. Unit Tests — doc-parser

```bash
# Test detection heuristics
python -c "
from detection import is_architectural_drawing, has_architectural_text
from PIL import Image
import numpy as np

# Create test image with lines (should detect as architectural)
img = Image.fromarray(np.zeros((500, 500, 3), dtype=np.uint8))
print('Black image:', is_architectural_drawing(img))  # False (no edges)

# Test text detection patterns
print('Dimension regex test passed')
"

# Test confidence scoring
python -c "
from confidence import calculate_confidence
result = calculate_confidence(
    units=[{'rooms': [{'area_sf': 150, 'baseboard_length_ft': 40}], 'doors': [{'type': 'interior'}], 'windows': [{'type': 'double-hung'}], 'fixtures': [{'name': 'sink'}], 'unit_number': 'A101'}],
    tables=[{'page_no': 1, 'markdown': 'test'}],
    synthesis={'correlations': []},
    total_pages=10,
    floorplans_found=3
)
print(f'Confidence: {result.overall}')
print(f'Room dims: {result.room_dimensions}')
"

# Test job manager
python -c "
import asyncio
from job_manager import create_job_manager

async def test():
    jm = create_job_manager('memory')
    job = await jm.create_job('test.pdf', 'docling')
    print(f'Created: {job.job_id}')
    status = await jm.get_status(job.job_id)
    print(f'Status: {status.status}')
    await jm.start_processing(job.job_id)
    status = await jm.get_status(job.job_id)
    print(f'After start: {status.status}')

asyncio.run(test())
"
```

### 2. Integration Test — Full Pipeline

```bash
# Start doc-parser
python server.py &

# Test health
curl http://localhost:5000/health

# Submit a test PDF (docling engine)
curl -X POST http://localhost:5000/parse/docling \
  -F "file=@test-blueprint.pdf" \
  -F "provider=anthropic/claude-3.5-sonnet"
# Returns: {"job_id": "abc-123", "status": "queued"}

# Poll status (lightweight)
curl http://localhost:5000/status/abc-123
# Returns progress without result data

# Fetch results after completed
curl http://localhost:5000/results/abc-123
# Returns full extraction data

# Test hybrid engine
curl -X POST http://localhost:5000/parse/hybrid \
  -F "file=@test-blueprint.pdf" \
  -F "provider=anthropic/claude-3.5-sonnet"
```

### 3. Frontend Smoke Test

1. Open work-orders app
2. Navigate to a project with uploaded PDFs
3. Verify engine selector dropdown appears (default: Hybrid)
4. Select a document and click Parse
5. Verify progress bar appears and updates
6. Verify results summary shows after completion
7. Verify confidence badge is clickable with breakdown
8. Test error state by stopping doc-parser mid-parse
9. Test retry button on error

---

## Migration Notes

### What Changes for Existing Users

- **Default engine is now `hybrid`** — users see the engine selector defaulting to "Hybrid (Docling + Claude)"
- **Claude Direct still works** — selecting "Claude Direct" uses the existing `ClaudePdfParser` flow unchanged
- **New polling pattern** — hybrid/docling engines use async job polling instead of synchronous response
- **Status and results are separate endpoints** — lightweight `/status` for polling, heavy `/results` for fetch-once

### Backward Compatibility

- `GET /result/{job_id}` (legacy) redirects to `GET /results/{job_id}` (new)
- `POST /parse/docling` maintains the same request format
- Original `FLOORPLAN_PROMPT` preserved in `prompts.py` for reference
- In-memory job store works without any database setup

### Breaking Changes

- **server.py is fully replaced** — any custom modifications to the original server.py must be manually re-applied
- **Initial job status is now `queued`** (was `processing`) — clients checking for `processing` as initial state need updating
- **`/result/{job_id}` response format changed** — now wrapped in `{"job_id": ..., "status": ..., "result": ...}`

---

## Priority Cross-Reference

| Priority | What | Key Files | Key Functions/Components |
|----------|------|-----------|-------------------------|
| **P1** | Align Prompts | `prompts.py` | `FLOORPLAN_PROMPT_RICH` — requests per-room dimensions, door/window specs, fixtures, baseboard exclusions |
| **P2** | Fix Detection | `detection.py` | `is_architectural_drawing()` — Canny edge detection; `has_architectural_text()` — dimension regex; `classify_image()` — multi-class classifier |
| **P3** | Progress Tracking | `job_manager.py`, `models.py` | `JobProgress` model with phase/page/step; `update_progress()` called throughout pipeline |
| **P4** | Persist + Split Endpoints | `job_manager.py`, `server.py` | `GET /status/{job_id}` (lightweight) vs `GET /results/{job_id}` (heavy); `MemoryJobStore` + `SupabaseJobStore`; TTL cleanup |
| **P5** | Cross-Page Synthesis | `prompts.py`, `hybrid.py` | `SYNTHESIS_PROMPT`; `run_cross_page_synthesis()` — correlates schedules with floorplans |
| **P6** | Confidence Scoring | `confidence.py` | `calculate_confidence()` — 8-dimension scoring; `ConfidenceBadge` component |
| **P7** | Hybrid Engine | `hybrid.py`, `server.py` | `process_hybrid()` — 4-phase pipeline; `POST /parse/hybrid` endpoint; `EngineSelector` component |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ProjectDocuments.tsx                                    │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │   │
│  │  │EngineSelector│  │ParseProgress │  │ConfidenceBadge│ │   │
│  │  └──────┬───────┘  └──────┬───────┘  └───────────────┘ │   │
│  │         │                 │                              │   │
│  │  ┌──────▼─────────────────▼──────────────────────────┐  │   │
│  │  │           useDocParserJob() hook                   │  │   │
│  │  │  submitJob() → startPolling() → fetchResults()     │  │   │
│  │  └──────┬────────────────┬───────────────────────────┘  │   │
│  └─────────┼────────────────┼──────────────────────────────┘   │
│            │ POST /parse    │ GET /status    GET /results       │
└────────────┼────────────────┼──────────────────────────────────┘
             │                │
┌────────────▼────────────────▼──────────────────────────────────┐
│                      HONO API PROXY                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  doc-parser-routes.ts                                    │  │
│  │  • Engine routing (claude-direct → existing handler)     │  │
│  │  • Status proxy (strips result data)                     │  │
│  │  • Results proxy (maps to ParsedDocument)                │  │
│  └──────┬──────────────────┬───────────────────────────────┘  │
│         │                  │                                   │
│  ┌──────▼──────────────────▼───────────────────────────────┐  │
│  │  doc-parser-client.ts                                    │  │
│  │  • submitParseJob()  • getJobStatus()  • getJobResults() │  │
│  └──────┬──────────────────┬───────────────────────────────┘  │
└─────────┼──────────────────┼──────────────────────────────────┘
          │ HTTP             │ HTTP
┌─────────▼──────────────────▼──────────────────────────────────┐
│                    DOC-PARSER SERVICE                          │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  server.py (FastAPI)                                      │ │
│  │  POST /parse/docling  POST /parse/hybrid                  │ │
│  │  GET  /status/:id     GET  /results/:id                   │ │
│  └──────┬────────────────────────┬───────────────────────────┘ │
│         │                        │                             │
│  ┌──────▼──────┐  ┌──────────────▼──────────────────────────┐ │
│  │ job_manager │  │         PROCESSING PIPELINE              │ │
│  │ • create    │  │                                          │ │
│  │ • progress  │  │  ┌──────────┐    ┌───────────────────┐  │ │
│  │ • complete  │  │  │ Docling   │───▶│ detection.py      │  │ │
│  │ • TTL       │  │  │ (Pass 1)  │    │ classify_image()  │  │ │
│  └─────────────┘  │  └──────────┘    └─────────┬─────────┘  │ │
│                   │                            │             │ │
│  ┌─────────────┐  │  ┌─────────────────────────▼──────────┐  │ │
│  │ models.py   │  │  │ Claude LLM (Pass 2)                │  │ │
│  │ Pydantic    │  │  │ prompts.py: FLOORPLAN_PROMPT_RICH   │  │ │
│  └─────────────┘  │  └─────────────────────────┬──────────┘  │ │
│                   │                            │             │ │
│  ┌─────────────┐  │  ┌─────────────────────────▼──────────┐  │ │
│  │confidence.py│  │  │ hybrid.py                           │  │ │
│  │ scoring     │◀─│──│ assemble_hybrid_output()            │  │ │
│  └─────────────┘  │  │ run_cross_page_synthesis()          │  │ │
│                   │  └────────────────────────────────────┘  │ │
│                   └──────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

## API Quick Reference

### Submit Parse Job
```
POST /parse/docling    — Docling-only engine
POST /parse/hybrid     — Hybrid engine (recommended)

Body: multipart/form-data
  file: PDF file (required)
  provider: LLM model (optional, default: anthropic/claude-3.5-sonnet)
  tenant_name: string (optional)
  project_name: string (optional)

Response: { job_id, status: "queued", engine, file }
```

### Poll Status (Lightweight)
```
GET /status/{job_id}

Response: { job_id, status, engine, file_name, progress: {...}, created_at, updated_at }
  NEVER includes result data. Safe to poll every 2-5 seconds.
```

### Fetch Results (Heavy)
```
GET /results/{job_id}
GET /results/{job_id}?summary=true

Response: { job_id, status: "completed", result: { engine, pages, units, tables, confidence, summary } }
  Only call after status confirms "completed".
```

### Health Check
```
GET /health

Response: { status, version, engines, dependencies, jobs, config }
```
