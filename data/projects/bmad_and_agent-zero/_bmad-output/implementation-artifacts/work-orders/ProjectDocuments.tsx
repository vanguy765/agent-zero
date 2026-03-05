/**
 * ProjectDocuments.tsx - Doc-Parser Integration
 *
 * This file contains the NEW components and hooks to add to the existing
 * ProjectDocuments.tsx for doc-parser engine selection and progress tracking.
 *
 * Integration approach:
 * - Add these imports, types, hooks, and components to the existing file
 * - Modify the existing parse button area to include engine selection
 * - Add progress display for async doc-parser jobs
 *
 * Priorities implemented:
 * - P3: Granular progress tracking with phase/page/step display
 * - P4: Separate status/results polling pattern
 * - P6: Confidence score display
 * - P7: Engine selection (claude-direct vs hybrid)
 */

import { createSignal, createEffect, onCleanup, Show, For, Switch, Match } from 'solid-js';

// ============================================================
// Types
// ============================================================

type ParseEngine = 'claude-direct' | 'hybrid';

interface DocParserProgress {
  current_phase: string;
  phases: string[];
  current_page: number;
  total_pages: number;
  current_step: string;
  floorplans_found: number;
  tables_found: number;
  percent_complete: number;
}

interface DocParserStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'timeout';
  engine: string;
  file_name: string;
  progress: DocParserProgress;
  error?: string;
  created_at: string;
  updated_at: string;
}

interface ConfidenceScore {
  overall: number;
  room_dimensions: boolean;
  door_specifications: boolean;
  window_specifications: boolean;
  fixture_completeness: boolean;
  cross_page_synthesis: boolean;
  baseboard_data: boolean;
  unit_identification: boolean;
}

interface ParsedResult {
  document_id: string;
  units: any[];
  general_notes: string[];
  total_baseboard_ft: number;
  summary: any;
  confidence: ConfidenceScore;
}

// ============================================================
// Phase Display Names
// ============================================================

const PHASE_LABELS: Record<string, string> = {
  queued: 'Queued',
  docling_conversion: 'Converting PDF',
  classification: 'Classifying Pages',
  image_extraction: 'Extracting Images',
  llm_analysis: 'Analyzing Floorplans',
  synthesis: 'Cross-Page Synthesis',
  uploading: 'Uploading Results',
  complete: 'Complete',
};

// ============================================================
// Hook: useDocParserJob
// Manages the polling lifecycle for a doc-parser job
// ============================================================

function useDocParserJob() {
  const [jobId, setJobId] = createSignal<string | null>(null);
  const [status, setStatus] = createSignal<DocParserStatus | null>(null);
  const [result, setResult] = createSignal<ParsedResult | null>(null);
  const [error, setError] = createSignal<string | null>(null);
  const [isPolling, setIsPolling] = createSignal(false);

  let pollInterval: ReturnType<typeof setInterval> | null = null;

  // Poll status endpoint (lightweight, every 3 seconds)
  const startPolling = (id: string) => {
    setJobId(id);
    setIsPolling(true);
    setError(null);
    setResult(null);

    pollInterval = setInterval(async () => {
      try {
        const resp = await fetch(`/api/doc-parser/status/${id}`);
        if (!resp.ok) {
          throw new Error(`Status check failed: ${resp.status}`);
        }

        const statusData: DocParserStatus = await resp.json();
        setStatus(statusData);

        // Job finished - stop polling and fetch results
        if (statusData.status === 'completed') {
          stopPolling();
          await fetchResults(id);
        }

        // Job failed or timed out - stop polling
        if (statusData.status === 'failed' || statusData.status === 'timeout') {
          stopPolling();
          setError(statusData.error || `Job ${statusData.status}`);
        }
      } catch (err) {
        console.error('Polling error:', err);
        // Don't stop polling on transient errors
      }
    }, 3000);
  };

  const stopPolling = () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    setIsPolling(false);
  };

  // Fetch full results (heavy, once after completed)
  const fetchResults = async (id: string) => {
    try {
      const resp = await fetch(`/api/doc-parser/results/${id}`);
      if (!resp.ok) {
        throw new Error(`Results fetch failed: ${resp.status}`);
      }

      const data = await resp.json();

      // Use the parsed field if available (mapped by Hono proxy)
      if (data.parsed) {
        setResult(data.parsed);
      } else if (data.result) {
        setResult(data.result);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch results';
      setError(message);
    }
  };

  // Submit a parse job
  const submitJob = async (
    documentId: string,
    file: File,
    engine: ParseEngine,
  ) => {
    setError(null);
    setResult(null);
    setStatus(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const resp = await fetch(`/api/documents/${documentId}/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engine }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.error || `Submission failed: ${resp.status}`);
      }

      const data = await resp.json();

      if (data.job_id) {
        startPolling(data.job_id);
      }

      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Submission failed';
      setError(message);
      throw err;
    }
  };

  const reset = () => {
    stopPolling();
    setJobId(null);
    setStatus(null);
    setResult(null);
    setError(null);
  };

  // Cleanup on unmount
  onCleanup(() => stopPolling());

  return {
    jobId,
    status,
    result,
    error,
    isPolling,
    submitJob,
    reset,
  };
}

// ============================================================
// Component: EngineSelector
// Dropdown for choosing parse engine
// ============================================================

interface EngineSelectorProps {
  value: ParseEngine;
  onChange: (engine: ParseEngine) => void;
  disabled?: boolean;
}

function EngineSelector(props: EngineSelectorProps) {
  return (
    <div class="flex items-center gap-2">
      <label
        for="parse-engine"
        class="text-sm font-medium text-gray-700"
      >
        Engine:
      </label>
      <select
        id="parse-engine"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value as ParseEngine)}
        disabled={props.disabled}
        class="text-sm border border-gray-300 rounded-md px-2 py-1.5
               bg-white shadow-sm focus:outline-none focus:ring-2
               focus:ring-blue-500 focus:border-blue-500
               disabled:bg-gray-100 disabled:cursor-not-allowed"
      >
        <option value="hybrid">Hybrid (Docling + Claude)</option>
        <option value="claude-direct">Claude Direct</option>
      </select>
      <Show when={props.value === 'hybrid'}>
        <span
          class="inline-flex items-center px-2 py-0.5 rounded text-xs
                 font-medium bg-green-100 text-green-800"
          title="Uses Docling for structural decomposition, Claude for semantic analysis. Better quality, lower token cost."
        >
          Recommended
        </span>
      </Show>
    </div>
  );
}

// ============================================================
// Component: ParseProgress
// Real-time progress display during doc-parser processing
// ============================================================

interface ParseProgressProps {
  status: DocParserStatus;
}

function ParseProgress(props: ParseProgressProps) {
  const progress = () => props.status.progress;
  const phaseLabel = () => PHASE_LABELS[progress().current_phase] || progress().current_phase;
  const percentComplete = () => {
    const p = progress();
    if (p.total_pages === 0) return p.percent_complete;
    // Calculate based on phase position + page progress within phase
    const phaseIndex = p.phases.indexOf(p.current_phase);
    const phaseWeight = 100 / p.phases.length;
    const pageProgress = p.total_pages > 0
      ? (p.current_page / p.total_pages) * phaseWeight
      : 0;
    return Math.min(
      Math.round(phaseIndex * phaseWeight + pageProgress),
      99,
    );
  };

  return (
    <div class="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
      {/* Phase indicator */}
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-medium text-blue-800">
          {phaseLabel()}
        </span>
        <span class="text-sm text-blue-600">
          {percentComplete()}%
        </span>
      </div>

      {/* Progress bar */}
      <div class="w-full bg-blue-200 rounded-full h-2 mb-2">
        <div
          class="bg-blue-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${percentComplete()}%` }}
        />
      </div>

      {/* Detail stats */}
      <div class="flex gap-4 text-xs text-blue-700">
        <Show when={progress().total_pages > 0}>
          <span>
            Page {progress().current_page}/{progress().total_pages}
          </span>
        </Show>
        <Show when={progress().floorplans_found > 0}>
          <span>
            {progress().floorplans_found} floorplans found
          </span>
        </Show>
        <Show when={progress().tables_found > 0}>
          <span>
            {progress().tables_found} tables found
          </span>
        </Show>
      </div>

      {/* Current step */}
      <div class="mt-1 text-xs text-blue-500 truncate">
        {progress().current_step.replace(/_/g, ' ')}
      </div>
    </div>
  );
}

// ============================================================
// Component: ConfidenceBadge
// Shows extraction confidence with tooltip breakdown
// ============================================================

interface ConfidenceBadgeProps {
  confidence: ConfidenceScore;
}

function ConfidenceBadge(props: ConfidenceBadgeProps) {
  const [showDetail, setShowDetail] = createSignal(false);

  const colorClass = () => {
    const score = props.confidence.overall;
    if (score >= 0.8) return 'bg-green-100 text-green-800 border-green-300';
    if (score >= 0.5) return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    return 'bg-red-100 text-red-800 border-red-300';
  };

  const fields = () => [
    { label: 'Room Dimensions', ok: props.confidence.room_dimensions },
    { label: 'Door Specs', ok: props.confidence.door_specifications },
    { label: 'Window Specs', ok: props.confidence.window_specifications },
    { label: 'Fixtures', ok: props.confidence.fixture_completeness },
    { label: 'Cross-Page Synthesis', ok: props.confidence.cross_page_synthesis },
    { label: 'Baseboard Data', ok: props.confidence.baseboard_data },
    { label: 'Unit Identification', ok: props.confidence.unit_identification },
  ];

  return (
    <div class="relative inline-block">
      <button
        class={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full
                text-sm font-medium border cursor-pointer ${colorClass()}`}
        onClick={() => setShowDetail(!showDetail())}
        title="Click for confidence breakdown"
      >
        <span>Confidence: {Math.round(props.confidence.overall * 100)}%</span>
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d={showDetail() ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'}
          />
        </svg>
      </button>

      {/* Dropdown detail */}
      <Show when={showDetail()}>
        <div
          class="absolute z-10 mt-1 right-0 w-64 bg-white border
                 border-gray-200 rounded-lg shadow-lg p-3"
        >
          <h4 class="text-xs font-semibold text-gray-500 uppercase mb-2">
            Extraction Completeness
          </h4>
          <For each={fields()}>
            {(field) => (
              <div class="flex items-center justify-between py-1">
                <span class="text-sm text-gray-700">{field.label}</span>
                <span class={field.ok ? 'text-green-600' : 'text-red-400'}>
                  {field.ok ? 'Yes' : 'No'}
                </span>
              </div>
            )}
          </For>
          <div class="mt-2 pt-2 border-t border-gray-100">
            <p class="text-xs text-gray-500">
              {props.confidence.overall < 0.7
                ? 'Consider re-parsing with Claude Direct for better coverage.'
                : 'Good extraction coverage across all categories.'}
            </p>
          </div>
        </div>
      </Show>
    </div>
  );
}

// ============================================================
// Component: ParseErrorDisplay
// Shows parse errors with retry option
// ============================================================

interface ParseErrorProps {
  error: string;
  onRetry?: () => void;
}

function ParseErrorDisplay(props: ParseErrorProps) {
  return (
    <div class="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
      <div class="flex items-start gap-2">
        <span class="text-red-500 text-lg">!</span>
        <div class="flex-1">
          <p class="text-sm font-medium text-red-800">Parse Failed</p>
          <p class="text-sm text-red-600 mt-1">{props.error}</p>
        </div>
        <Show when={props.onRetry}>
          <button
            onClick={props.onRetry}
            class="text-sm text-red-700 hover:text-red-900
                   underline cursor-pointer"
          >
            Retry
          </button>
        </Show>
      </div>
    </div>
  );
}

// ============================================================
// Component: ParseResultSummary
// Shows summary of extraction results
// ============================================================

interface ParseResultSummaryProps {
  result: ParsedResult;
}

function ParseResultSummary(props: ParseResultSummaryProps) {
  const summary = () => props.result.summary;

  return (
    <div class="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-medium text-green-800">
          Parsing Complete
        </span>
        <Show when={props.result.confidence}>
          <ConfidenceBadge confidence={props.result.confidence} />
        </Show>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
        <div class="bg-white rounded p-2 text-center">
          <div class="text-lg font-bold text-gray-800">
            {summary()?.units_count || 0}
          </div>
          <div class="text-xs text-gray-500">Units</div>
        </div>
        <div class="bg-white rounded p-2 text-center">
          <div class="text-lg font-bold text-gray-800">
            {summary()?.total_doors || 0}
          </div>
          <div class="text-xs text-gray-500">Doors</div>
        </div>
        <div class="bg-white rounded p-2 text-center">
          <div class="text-lg font-bold text-gray-800">
            {summary()?.total_windows || 0}
          </div>
          <div class="text-xs text-gray-500">Windows</div>
        </div>
        <div class="bg-white rounded p-2 text-center">
          <div class="text-lg font-bold text-gray-800">
            {summary()?.total_baseboard_ft || 0}
          </div>
          <div class="text-xs text-gray-500">Baseboard (ft)</div>
        </div>
      </div>

      <Show when={summary()?.floorplans_count}>
        <div class="mt-2 text-xs text-green-700">
          Processed {summary()?.pages_count} pages | {summary()?.floorplans_count} floorplans | {summary()?.tables_count} tables
        </div>
      </Show>
    </div>
  );
}

// ============================================================
// Integration Example: How to wire into existing ProjectDocuments
// ============================================================

/**
 * Add to your existing ProjectDocuments component:
 *
 * ```tsx
 * // Inside your component function:
 * const [engine, setEngine] = createSignal<ParseEngine>('hybrid');
 * const docParser = useDocParserJob();
 *
 * const handleParse = async (documentId: string, file: File) => {
 *   if (engine() === 'claude-direct') {
 *     // Use existing ClaudePdfParser flow
 *     await existingParseHandler(documentId, file);
 *   } else {
 *     // Use doc-parser (docling or hybrid)
 *     await docParser.submitJob(documentId, file, engine());
 *   }
 * };
 *
 * // In your JSX, replace the parse button area:
 * <div class="flex items-center gap-3">
 *   <EngineSelector
 *     value={engine()}
 *     onChange={setEngine}
 *     disabled={docParser.isPolling()}
 *   />
 *   <button
 *     onClick={() => handleParse(document.id, pdfFile)}
 *     disabled={docParser.isPolling()}
 *     class="px-4 py-2 bg-blue-600 text-white rounded-md
 *            hover:bg-blue-700 disabled:opacity-50"
 *   >
 *     {docParser.isPolling() ? 'Parsing...' : 'Parse Document'}
 *   </button>
 * </div>
 *
 * // Below the button, add progress/result display:
 * <Show when={docParser.isPolling() && docParser.status()}>
 *   <ParseProgress status={docParser.status()!} />
 * </Show>
 *
 * <Show when={docParser.error()}>
 *   <ParseErrorDisplay
 *     error={docParser.error()!}
 *     onRetry={() => handleParse(document.id, pdfFile)}
 *   />
 * </Show>
 *
 * <Show when={docParser.result()}>
 *   <ParseResultSummary result={docParser.result()!} />
 * </Show>
 * ```
 */

// ============================================================
// Exports
// ============================================================

export {
  useDocParserJob,
  EngineSelector,
  ParseProgress,
  ConfidenceBadge,
  ParseErrorDisplay,
  ParseResultSummary,
  type ParseEngine,
  type DocParserStatus,
  type DocParserProgress,
  type ConfidenceScore,
  type ParsedResult,
};
