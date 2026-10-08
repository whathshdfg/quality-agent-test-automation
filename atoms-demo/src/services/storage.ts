import type { QualityTask } from '../types';

const STORAGE_KEY = 'quality_agent_studio_tasks_v1';

function normalizeTask(task: Partial<QualityTask>): QualityTask | null {
  if (!task.id || !task.name || !task.requirement) return null;
  return {
    id: task.id,
    name: task.name,
    businessType: task.businessType ?? '通用业务',
    requirement: task.requirement,
    riskTags: task.riskTags ?? [],
    rules: task.rules ?? [],
    testPoints: task.testPoints ?? [],
    testCases: task.testCases ?? [],
    coverage: task.coverage ?? {
      ruleCoverage: { covered: 0, total: 0, rate: 100 },
      functionalCoverage: { covered: 0, total: 0, rate: 100 },
      parameterCoverage: { covered: 0, total: 0, rate: 100 },
      riskCoverage: { covered: 0, total: 0, rate: 100 },
      overall: 100,
      coveredDimensions: [],
      missingDimensions: [],
    },
    createdAt: task.createdAt ?? new Date().toISOString(),
    updatedAt: task.updatedAt ?? new Date().toISOString(),
  };
}

export const taskStorage = {
  load(): QualityTask[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw) as unknown;
      if (!Array.isArray(parsed)) return [];
      return parsed.map((item) => normalizeTask(item as Partial<QualityTask>)).filter((item): item is QualityTask => Boolean(item));
    } catch {
      return [];
    }
  },
  save(tasks: QualityTask[]): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  },
  upsert(task: QualityTask): QualityTask[] {
    const tasks = this.load();
    const next = [task, ...tasks.filter((item) => item.id !== task.id)];
    this.save(next);
    return next;
  },
  remove(taskId: string): QualityTask[] {
    const next = this.load().filter((task) => task.id !== taskId);
    this.save(next);
    return next;
  },
};
