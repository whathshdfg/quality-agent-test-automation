import type { CoverageMetric, CoverageResult, TestCase, TestPoint } from '../types';

function metric(covered: number, total: number): CoverageMetric {
  return { covered, total, rate: total === 0 ? 100 : Math.round((covered / total) * 100) };
}

const riskText: Record<string, string> = {
  幂等性: '重复请求可能导致重复扣款、重复退款或重复创建数据。',
  状态流转: '非法状态被放行会造成流程越权或业务记录异常。',
  参数校验: '非法参数进入核心流程会污染数据并降低接口稳定性。',
  权限安全: '认证、锁定或权限边界缺失会带来安全风险。',
  资源释放: '资源未释放会造成库存、司机、资金或额度长期占用。',
  数据一致性: '状态、流水和资源记录不一致会影响对账和用户权益。',
  异常响应: '异常路径缺少覆盖会导致业务码和前端提示不可控。',
};

export function calculateCoverage(points: TestPoint[], cases: TestCase[]): CoverageResult {
  const coveredRuleIds = new Set(cases.flatMap((testCase) => testCase.relatedRuleIds));
  const allRuleIds = new Set(points.flatMap((point) => point.relatedRuleIds));
  const coveredDimensions = new Set(cases.map((testCase) => testCase.dimension));
  const withCoverage = points.map((point) => ({ ...point, covered: coveredDimensions.has(point.dimension) }));

  const byCategory = (category: TestPoint['category']) => {
    const scoped = withCoverage.filter((point) => point.category === category);
    return metric(scoped.filter((point) => point.covered).length, scoped.length);
  };

  const ruleCoverage = metric([...allRuleIds].filter((ruleId) => coveredRuleIds.has(ruleId)).length, allRuleIds.size);
  const functionalCoverage = byCategory('功能流程');
  const parameterCoverage = byCategory('参数校验');
  const riskCoverage = byCategory('风险场景');
  const overall = Math.round((ruleCoverage.rate + functionalCoverage.rate + parameterCoverage.rate + riskCoverage.rate) / 4);
  const missingDimensions = withCoverage
    .filter((point) => !point.covered)
    .map((point) => ({
      dimension: point.dimension,
      category: point.category,
      risk: riskText[point.dimension] ?? '该检查点尚无直接用例覆盖，回归时可能遗漏关键行为。',
      recommendation: `补充${point.dimension}场景，关联规则 ${point.relatedRuleIds.join(', ')}。`,
    }))
    .filter((gap, index, gaps) => gaps.findIndex((item) => item.dimension === gap.dimension) === index);

  return {
    ruleCoverage,
    functionalCoverage,
    parameterCoverage,
    riskCoverage,
    overall,
    coveredDimensions: [...coveredDimensions],
    missingDimensions,
  };
}
