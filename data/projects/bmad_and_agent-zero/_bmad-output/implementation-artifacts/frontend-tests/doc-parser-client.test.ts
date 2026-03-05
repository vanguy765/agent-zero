import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  mapToParseDocument,
  submitParseJob,
  getJobStatus,
  getJobResults,
  checkHealth,
  type DocParserResult,
  type DocParserConfidence,
  type DocParserResultSummary,
} from './doc-parser-client';

// ============================================================
// Global fetch mock
// ============================================================

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
});

// ============================================================
// Helper: build a minimal DocParserResult
// ============================================================

function makeResult(overrides: Partial<DocParserResult> = {}): DocParserResult {
  return {
    engine: 'hybrid',
    pages: {},
    units: [
      {
        unit_number: '101',
        unit_type: '1BR',
        floor: 1,
        bedrooms: 1,
        bathrooms: 1,
        half_baths: 0,
        area_sf: 750,
        rooms: [],
        doors: [],
        windows: [],
        fixtures: [],
        upgrades: [],
        general_notes: ['Note A'],
        source_page: 1,
      },
    ],
    tables: [],
    footer_sample: null,
    general_notes: ['General note 1'],
    synthesis: null,
    confidence: {
      overall: 0.85,
      room_dimensions: true,
      door_specifications: true,
      window_specifications: false,
      fixture_completeness: true,
      cross_page_synthesis: true,
      baseboard_data: false,
      unit_identification: true,
      per_page: {},
    },
    summary: {
      pages_count: 5,
      floorplans_count: 3,
      tables_count: 1,
      units_count: 2,
      has_footer: false,
      total_doors: 10,
      total_windows: 8,
      total_baseboard_ft: 120,
      trades: ['flooring'],
    },
    ...overrides,
  };
}

// ============================================================
// mapToParseDocument() - Pure function tests
// ============================================================

describe('mapToParseDocument', () => {
  it('maps result with units, general_notes, summary, confidence correctly', () => {
    const result = makeResult();
    const mapped = mapToParseDocument(result, 'doc-123');

    expect(mapped.units).toEqual(result.units);
    expect(mapped.general_notes).toEqual(['General note 1']);
    expect(mapped.summary).toEqual(result.summary);
    expect(mapped.confidence).toEqual(result.confidence);
  });

  it('sets document_id from parameter', () => {
    const result = makeResult();
    const mapped = mapToParseDocument(result, 'my-doc-456');
    expect(mapped.document_id).toBe('my-doc-456');
  });

  it('handles missing/empty units array (defaults to [])', () => {
    const result = makeResult({ units: undefined as any });
    const mapped = mapToParseDocument(result, 'doc-1');
    expect(mapped.units).toEqual([]);
  });

  it('handles missing general_notes (defaults to [])', () => {
    const result = makeResult({ general_notes: undefined as any });
    const mapped = mapToParseDocument(result, 'doc-1');
    expect(mapped.general_notes).toEqual([]);
  });

  it('handles missing summary.total_baseboard_ft (defaults to 0)', () => {
    const result = makeResult({
      summary: { ...makeResult().summary, total_baseboard_ft: undefined as any },
    });
    const mapped = mapToParseDocument(result, 'doc-1');
    expect(mapped.total_baseboard_ft).toBe(0);
  });
});

// ============================================================
// submitParseJob()
// ============================================================

describe('submitParseJob', () => {
  const fakePdf = new ArrayBuffer(10);

  it('calls correct endpoint for hybrid engine (/parse/hybrid)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: 'j1', status: 'queued', engine: 'hybrid', file: 'test.pdf' }),
    });

    await submitParseJob(fakePdf, 'test.pdf', 'hybrid');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/parse/hybrid');
  });

  it('calls correct endpoint for docling engine (/parse/docling)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: 'j2', status: 'queued', engine: 'docling', file: 'test.pdf' }),
    });

    await submitParseJob(fakePdf, 'test.pdf', 'docling');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/parse/docling');
  });

  it('sends FormData with file blob', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: 'j3', status: 'queued', engine: 'hybrid', file: 'test.pdf' }),
    });

    await submitParseJob(fakePdf, 'test.pdf', 'hybrid');

    const callArgs = mockFetch.mock.calls[0];
    const options = callArgs[1] as RequestInit;
    expect(options.method).toBe('POST');
    expect(options.body).toBeInstanceOf(FormData);

    const formData = options.body as FormData;
    expect(formData.get('file')).toBeTruthy();
  });

  it('includes optional provider, tenantName, projectName in FormData', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: 'j4', status: 'queued', engine: 'hybrid', file: 'test.pdf' }),
    });

    await submitParseJob(fakePdf, 'test.pdf', 'hybrid', {
      provider: 'openrouter',
      tenantName: 'acme',
      projectName: 'proj-1',
    });

    const formData = (mockFetch.mock.calls[0][1] as RequestInit).body as FormData;
    expect(formData.get('provider')).toBe('openrouter');
    expect(formData.get('tenant_name')).toBe('acme');
    expect(formData.get('project_name')).toBe('proj-1');
  });

  it('throws on non-ok response with error message', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => 'Internal Server Error',
    });

    await expect(submitParseJob(fakePdf, 'test.pdf', 'hybrid')).rejects.toThrow(
      /Doc-parser submission failed \(500\)/,
    );
  });

  it('returns parsed JSON response on success', async () => {
    const expected = { job_id: 'j5', status: 'queued', engine: 'hybrid', file: 'test.pdf' };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => expected,
    });

    const result = await submitParseJob(fakePdf, 'test.pdf', 'hybrid');
    expect(result).toEqual(expected);
  });
});

// ============================================================
// getJobStatus()
// ============================================================

describe('getJobStatus', () => {
  it('calls /status/{jobId} endpoint', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: 'abc', status: 'processing' }),
    });

    await getJobStatus('abc');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/status/abc');
  });

  it('returns parsed status JSON', async () => {
    const statusData = { job_id: 'abc', status: 'completed', engine: 'hybrid' };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => statusData,
    });

    const result = await getJobStatus('abc');
    expect(result).toEqual(statusData);
  });

  it('throws "not found" error on 404', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    await expect(getJobStatus('missing')).rejects.toThrow(/not found/);
  });

  it('throws generic error on other failures', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
    });

    await expect(getJobStatus('abc')).rejects.toThrow(/Status check failed \(503\)/);
  });
});

// ============================================================
// getJobResults()
// ============================================================

describe('getJobResults', () => {
  it('calls /results/{jobId} for full results', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: 'abc', status: 'completed', result: {} }),
    });

    await getJobResults('abc');

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/results/abc');
    expect(url).not.toContain('summary=true');
  });

  it('calls /results/{jobId}?summary=true when summaryOnly=true', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ job_id: 'abc', status: 'completed', summary: {} }),
    });

    await getJobResults('abc', true);

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain('/results/abc?summary=true');
  });

  it('returns parsed JSON', async () => {
    const data = { job_id: 'abc', status: 'completed', result: { engine: 'hybrid' } };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => data,
    });

    const result = await getJobResults('abc');
    expect(result).toEqual(data);
  });

  it('throws "not found" on 404', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    await expect(getJobResults('missing')).rejects.toThrow(/not found/);
  });

  it('throws generic error on other failures', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(getJobResults('abc')).rejects.toThrow(/Results fetch failed \(500\)/);
  });
});

// ============================================================
// checkHealth()
// ============================================================

describe('checkHealth', () => {
  it('returns health data on success', async () => {
    const healthData = { status: 'healthy', engines: ['hybrid', 'docling'], dependencies: { supabase: true } };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => healthData,
    });

    const result = await checkHealth();
    expect(result).toEqual(healthData);
  });

  it('returns unhealthy status on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
    });

    const result = await checkHealth();
    expect(result.status).toBe('unhealthy');
    expect(result.engines).toEqual([]);
    expect(result.dependencies).toEqual({});
  });

  it('returns unreachable status on fetch error/timeout', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    const result = await checkHealth();
    expect(result.status).toBe('unreachable');
    expect(result.engines).toEqual([]);
    expect(result.dependencies).toEqual({});
  });

  it('uses AbortSignal.timeout(5000)', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', engines: [], dependencies: {} }),
    });

    await checkHealth();

    const callArgs = mockFetch.mock.calls[0];
    const options = callArgs[1] as RequestInit;
    expect(options.signal).toBeDefined();
  });
});
