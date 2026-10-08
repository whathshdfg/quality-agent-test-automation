import type { GenerationSource, Priority, RequirementRule, TestCase, TestPoint } from '../types';
import { makeId } from '../utils/id';

const priorityByRisk = (risk: string): Priority => (risk === 'high' ? 'P0' : risk === 'medium' ? 'P1' : 'P2');

function titleFor(point: TestPoint, source: GenerationSource): string {
  const prefix = source === 'gap_supplement' ? '补充覆盖' : source === 'manual' ? '手工用例' : '验证';
  return `${prefix}${point.dimension} - ${point.name.replace(/^.*：/, '').slice(0, 26)}`;
}

export function buildCaseFromPoint(point: TestPoint, businessType: string, source: GenerationSource): TestCase {
  const now = new Date().toISOString();
  const steps =
    point.dimension === '幂等性'
      ? ['准备一笔满足条件的业务数据', '连续提交两次相同请求', '检查第二次请求的业务响应和副作用']
      : point.dimension === '参数校验'
        ? ['构造缺失或非法参数的请求', '提交业务操作', '观察校验错误和业务数据变化']
        : point.dimension === '数据一致性'
          ? ['执行目标业务操作', '查询状态、流水和关联资源', '核对多处数据是否一致']
          : ['准备满足前置条件的数据', '执行目标业务操作', '检查状态、响应和关键记录'];
  const expected =
    point.dimension === '幂等性'
      ? ['重复请求不会产生重复扣款、退款、资源释放或重复数据', '系统返回可解释的业务结果']
      : point.dimension === '参数校验'
        ? ['系统拒绝非法参数并给出明确提示', '业务状态和持久化数据不被错误修改']
        : point.dimension === '数据一致性'
          ? ['主状态、流水记录和资源占用结果保持一致']
          : ['业务响应符合需求描述', '相关状态按预期变化'];

  return {
    caseId: makeId('TC'),
    title: titleFor(point, source),
    priority: priorityByRisk(point.riskLevel),
    businessType,
    dimension: point.dimension,
    preconditions: ['使用隔离测试数据', '保留操作前状态快照'],
    steps,
    expectedResults: expected,
    relatedRuleIds: point.relatedRuleIds,
    generationSource: source,
    status: 'not_run',
    createdAt: now,
    updatedAt: now,
  };
}

export function generateTestCases(rules: RequirementRule[], points: TestPoint[], businessType: string): TestCase[] {
  const cases = points.map((point) => buildCaseFromPoint(point, businessType, 'rule_generated'));
  const hasNormal = cases.some((testCase) => testCase.dimension === '正常业务流程');
  if (!hasNormal && rules.length > 0) {
    const now = new Date().toISOString();
    cases.unshift({
      caseId: makeId('TC'),
      title: `${businessType}正常主流程验证`,
      priority: 'P1',
      businessType,
      dimension: '正常业务流程',
      preconditions: ['存在一条满足业务前置条件的数据'],
      steps: ['提交合法业务请求', '查询业务结果', '核对关键状态和记录'],
      expectedResults: ['请求成功', '状态和记录符合需求描述'],
      relatedRuleIds: [rules[0].ruleId],
      generationSource: 'rule_generated',
      status: 'not_run',
      createdAt: now,
      updatedAt: now,
    });
  }
  return dedupeCases(cases);
}

export function dedupeCases(cases: TestCase[]): TestCase[] {
  const seen = new Set<string>();
  return cases.filter((testCase) => {
    const key = `${testCase.title}:${testCase.dimension}:${testCase.expectedResults.join('|')}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
