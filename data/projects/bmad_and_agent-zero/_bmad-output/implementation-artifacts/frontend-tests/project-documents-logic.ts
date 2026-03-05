/**
 * Extracted pure logic from ProjectDocuments.tsx for testing.
 * These functions mirror the logic used in the SolidJS components.
 */

export const PHASE_LABELS: Record<string, string> = {
  queued: 'Queued',
  docling_conversion: 'Converting PDF',
  classification: 'Classifying Pages',
  image_extraction: 'Extracting Images',
  llm_analysis: 'Analyzing Floorplans',
  synthesis: 'Cross-Page Synthesis',
  uploading: 'Uploading Results',
  complete: 'Complete',
};

export function getConfidenceColorClass(score: number): string {
  if (score >= 0.8) return 'bg-green-100 text-green-800 border-green-300';
  if (score >= 0.5) return 'bg-yellow-100 text-yellow-800 border-yellow-300';
  return 'bg-red-100 text-red-800 border-red-300';
}

export function calculatePercentComplete(progress: {
  current_phase: string;
  phases: string[];
  current_page: number;
  total_pages: number;
  percent_complete: number;
}): number {
  if (progress.total_pages === 0) return progress.percent_complete;
  const phaseIndex = progress.phases.indexOf(progress.current_phase);
  const phaseWeight = 100 / progress.phases.length;
  const pageProgress = progress.total_pages > 0
    ? (progress.current_page / progress.total_pages) * phaseWeight
    : 0;
  return Math.min(Math.round(phaseIndex * phaseWeight + pageProgress), 99);
}

export function getConfidenceFields(confidence: {
  room_dimensions: boolean;
  door_specifications: boolean;
  window_specifications: boolean;
  fixture_completeness: boolean;
  cross_page_synthesis: boolean;
  baseboard_data: boolean;
  unit_identification: boolean;
}): Array<{ label: string; ok: boolean }> {
  return [
    { label: 'Room Dimensions', ok: confidence.room_dimensions },
    { label: 'Door Specs', ok: confidence.door_specifications },
    { label: 'Window Specs', ok: confidence.window_specifications },
    { label: 'Fixtures', ok: confidence.fixture_completeness },
    { label: 'Cross-Page Synthesis', ok: confidence.cross_page_synthesis },
    { label: 'Baseboard Data', ok: confidence.baseboard_data },
    { label: 'Unit Identification', ok: confidence.unit_identification },
  ];
}

export function getConfidenceAdvice(overall: number): string {
  return overall < 0.7
    ? 'Consider re-parsing with Claude Direct for better coverage.'
    : 'Good extraction coverage across all categories.';
}

export function formatStep(step: string): string {
  return step.replace(/_/g, ' ');
}
