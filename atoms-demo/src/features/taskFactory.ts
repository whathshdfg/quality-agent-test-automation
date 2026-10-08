import type { QualityTask, TaskDraft } from '../types';
import { makeId } from '../utils/id';
import { analyzeRequirement } from './analyzer';
import { generateTestPoints } from './testPointGenerator';
import { generateTestCases } from './caseGenerator';
import { calculateCoverage } from './coverage';

export function createTask(draft: TaskDraft): QualityTask {
  const now = new Date().toISOString();
  const rules = analyzeRequirement(draft.requirement, draft.riskTags);
  const testPoints = generateTestPoints(rules);
  const testCases = generateTestCases(rules, testPoints, draft.businessType === '自动识别' ? inferBusinessType(draft.requirement) : draft.businessType);
  const coverage = calculateCoverage(testPoints, testCases);
  return {
    id: makeId('TASK'),
    name: draft.name.trim(),
    businessType: draft.businessType === '自动识别' ? inferBusinessType(draft.requirement) : draft.businessType,
    requirement: draft.requirement.trim(),
    riskTags: draft.riskTags,
    rules,
    testPoints: testPoints.map((point) => ({ ...point, covered: coverage.coveredDimensions.includes(point.dimension) })),
    testCases,
    coverage,
    createdAt: now,
    updatedAt: now,
  };
}

export function refreshTask(task: QualityTask): QualityTask {
  const coverage = calculateCoverage(task.testPoints, task.testCases);
  return {
    ...task,
    testPoints: task.testPoints.map((point) => ({ ...point, covered: coverage.coveredDimensions.includes(point.dimension) })),
    coverage,
    updatedAt: new Date().toISOString(),
  };
}

function inferBusinessType(requirement: string): string {
  if (requirement.includes('支付') || requirement.includes('扣款')) return '支付';
  if (requirement.includes('取消') || requirement.includes('退款')) return '订单取消';
  if (requirement.includes('登录') || requirement.includes('账号')) return '用户登录';
  if (requirement.includes('创建') || requirement.includes('预约')) return '订单创建';
  return '通用业务';
}
