/**
 * Doc-Parser Proxy Routes for Hono API
 *
 * Integrates doc-parser service into the existing work-orders API.
 * Provides engine selection, status polling, and result retrieval.
 *
 * Routes:
 *   POST /api/documents/:id/parse    - Parse document (engine selection)
 *   GET  /api/doc-parser/status/:jobId  - Lightweight status (poll-safe)
 *   GET  /api/doc-parser/results/:jobId - Full results (fetch-once)
 *   GET  /api/doc-parser/health         - Service health check
 */

import { Hono } from 'hono';
import {
  submitParseJob,
  getJobStatus,
  getJobResults,
  checkHealth,
  mapToParseDocument,
  type DocParserStatus,
  type DocParserResult,
} from './doc-parser-client';

const docParserRoutes = new Hono();

// ============================================================
// POST /api/documents/:id/parse
// Engine selection: 'claude-direct' | 'docling' | 'hybrid'
// ============================================================

docParserRoutes.post('/documents/:id/parse', async (c) => {
  const documentId = c.req.param('id');
  const body = await c.req.json().catch(() => ({}));
  const engine = (body?.engine || 'claude-direct') as string;

  // ---- Claude Direct: existing flow (unchanged) ----
  if (engine === 'claude-direct') {
    // Delegate to existing ClaudePdfParser handler
    // This preserves backward compatibility
    return c.json({
      error: 'claude-direct engine should be handled by existing route handler',
      hint: 'This route only handles docling and hybrid engines',
    }, 400);
  }

  // ---- Docling or Hybrid: proxy to doc-parser service ----
  if (engine !== 'docling' && engine !== 'hybrid') {
    return c.json(
      { error: `Unknown engine: ${engine}. Use 'claude-direct', 'docling', or 'hybrid'.` },
      400,
    );
  }

  try {
    // TODO: Fetch the actual PDF buffer from your document storage
    // This is a placeholder - replace with your actual document retrieval logic
    // const document = await getDocument(documentId);
    // const pdfBuffer = await downloadPdf(document.storage_path);

    // For now, expect the PDF to be sent in the request body
    const formData = await c.req.formData().catch(() => null);
    const pdfFile = formData?.get('file') as File | null;

    if (!pdfFile) {
      return c.json(
        { error: 'PDF file required. Send as multipart form data with key "file".' },
        400,
      );
    }

    const pdfBuffer = await pdfFile.arrayBuffer();

    // Submit to doc-parser
    const jobResponse = await submitParseJob(
      pdfBuffer,
      pdfFile.name || `document-${documentId}.pdf`,
      engine as 'docling' | 'hybrid',
      {
        provider: body?.provider || process.env.DEFAULT_LLM_PROVIDER,
        tenantName: body?.tenant_name || c.get('tenantId'),
        projectName: body?.project_name || documentId,
        supabaseUrl: process.env.SUPABASE_URL,
        supabaseKey: process.env.SUPABASE_SERVICE_KEY,
      },
    );

    // Return job info with polling URLs
    return c.json({
      engine,
      job_id: jobResponse.job_id,
      status: jobResponse.status,
      poll_url: `/api/doc-parser/status/${jobResponse.job_id}`,
      results_url: `/api/doc-parser/results/${jobResponse.job_id}`,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error(`[doc-parser] Parse submission failed: ${message}`);
    return c.json({ error: `Doc-parser submission failed: ${message}` }, 502);
  }
});

// ============================================================
// GET /api/doc-parser/status/:jobId
// Lightweight status for polling (Priority 4a)
// Safe to call every 2-5 seconds. Small payload.
// ============================================================

docParserRoutes.get('/doc-parser/status/:jobId', async (c) => {
  const jobId = c.req.param('jobId');

  try {
    const status: DocParserStatus = await getJobStatus(jobId);

    // Ensure result data is NEVER included in status response
    // (defense-in-depth - server should already exclude it)
    const safeStatus = { ...status };
    delete (safeStatus as any).result;

    return c.json(safeStatus);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    if (message.includes('not found')) {
      return c.json({ error: `Job ${jobId} not found` }, 404);
    }
    return c.json({ error: `Status check failed: ${message}` }, 502);
  }
});

// ============================================================
// GET /api/doc-parser/results/:jobId
// Full results - fetch once after status confirms "completed"
// Heavy payload. Includes ParsedDocument-compatible mapping.
// ============================================================

docParserRoutes.get('/doc-parser/results/:jobId', async (c) => {
  const jobId = c.req.param('jobId');
  const summaryOnly = c.req.query('summary') === 'true';

  try {
    const data = await getJobResults(jobId, summaryOnly);

    // If summary requested, return as-is
    if (summaryOnly) {
      return c.json(data);
    }

    // If hybrid engine with units array, map to ParsedDocument format
    const result = data.result as DocParserResult | undefined;
    if (result?.engine === 'hybrid' && result?.units) {
      return c.json({
        ...data,
        parsed: mapToParseDocument(result, jobId),
      });
    }

    // Docling engine - also map units if available
    if (result?.units) {
      return c.json({
        ...data,
        parsed: mapToParseDocument(result, jobId),
      });
    }

    // Fallback: return raw result
    return c.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    if (message.includes('not found')) {
      return c.json({ error: `Results for job ${jobId} not found` }, 404);
    }
    return c.json({ error: `Results fetch failed: ${message}` }, 502);
  }
});

// ============================================================
// GET /api/doc-parser/health
// Service health check with dependency status
// ============================================================

docParserRoutes.get('/doc-parser/health', async (c) => {
  const health = await checkHealth();
  const statusCode = health.status === 'healthy' ? 200 : 503;
  return c.json(health, statusCode);
});

export { docParserRoutes };
export default docParserRoutes;
