import type { RequirementRule, TestPoint } from '../types';

const categoryForType = (type: string): TestPoint['category'] => {
  if (type.includes('参数')) return '参数校验';
  if (['数据一致性', '安全权限', '并发幂等'].includes(type)) return '风险场景';
  return '功能流程';
};

const dimensionForType = (type: string): string => {
  const map: Record<string, string> = {
    前置条件: '合法前置状态',
    核心行为: '正常业务流程',
    状态约束: '状态流转',
    异常处理: '异常响应',
    参数校验: '参数校验',
    数据一致性: '数据一致性',
    安全权限: '权限安全',
    并发幂等: '幂等性',
  };
  return map[type] ?? '通用业务规则';
};

export function generateTestPoints(rules: RequirementRule[]): TestPoint[] {
  return rules.map((rule, index) => ({
    pointId: `TP-${index + 1}`,
    name: `${dimensionForType(rule.type)}检查：${rule.description.slice(0, 28)}`,
    category: categoryForType(rule.type),
    dimension: dimensionForType(rule.type),
    relatedRuleIds: [rule.ruleId],
    riskLevel: rule.riskLevel,
    covered: false,
  }));
}
