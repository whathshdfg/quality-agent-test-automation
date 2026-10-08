import type { CoverageGap, TestCase, TestPoint } from '../types';
import { buildCaseFromPoint, dedupeCases } from './caseGenerator';

export function supplementForGap(points: TestPoint[], cases: TestCase[], businessType: string, gap: CoverageGap): TestCase[] {
  const point = points.find((item) => item.dimension === gap.dimension);
  if (!point) return cases;
  return dedupeCases([...cases, buildCaseFromPoint(point, businessType, 'gap_supplement')]);
}

export function supplementAllGaps(points: TestPoint[], cases: TestCase[], businessType: string, gaps: CoverageGap[]): TestCase[] {
  return gaps.reduce((current, gap) => supplementForGap(points, current, businessType, gap), cases);
}
