import type { RequirementRule, RiskLevel } from '../types';
import { hashText } from '../utils/id';

type RulePattern = {
  type: string;
  keywords: string[];
  riskLevel: RiskLevel;
  fallback: string;
};

const patterns: RulePattern[] = [
  { type: '前置条件', keywords: ['只能', '必须', '仅当', '处于', '待支付', '待接单', '待服务'], riskLevel: 'medium', fallback: '业务操作需要满足明确的前置状态或条件。' },
  { type: '核心行为', keywords: ['创建', '支付', '取消', '登录', '提交', '成功'], riskLevel: 'medium', fallback: '系统需要完成主要业务动作并返回明确结果。' },
  { type: '状态约束', keywords: ['成功后', '更新为', '变更为', '状态', '锁定', '清空'], riskLevel: 'high', fallback: '业务完成后状态需要按预期流转并可验证。' },
  { type: '异常处理', keywords: ['返回', '不能', '错误', '失败', 'REPEAT_PAYMENT', '已完成'], riskLevel: 'high', fallback: '异常输入或非法状态需要返回明确业务响应。' },
  { type: '参数校验', keywords: ['不能为空', '为空', '格式', '长度', '最小', '最大', '不能早于', '手机号', '密码', '起点', '终点'], riskLevel: 'medium', fallback: '关键参数需要校验必填、格式和边界条件。' },
  { type: '数据一致性', keywords: ['流水', '扣款', '退款', '释放', '记录', '一致', '只能生成一个'], riskLevel: 'high', fallback: '资金、流水、资源或数据记录需要保持一致。' },
  { type: '安全权限', keywords: ['锁定', '权限', '认证', '登录失败', '账号'], riskLevel: 'high', fallback: '认证失败、账号锁定或权限边界需要被验证。' },
  { type: '并发幂等', keywords: ['重复', '幂等', '并发', '同时提交', '重试'], riskLevel: 'high', fallback: '重复请求、并发请求和超时重试不能造成重复副作用。' },
];

function splitSentences(requirement: string): string[] {
  return requirement
    .split(/[。；;.!?\n]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function analyzeRequirement(requirement: string, selectedRisks: string[] = []): RequirementRule[] {
  const sentences = splitSentences(requirement);
  const rules: RequirementRule[] = [];
  const seen = new Set<string>();

  patterns.forEach((pattern) => {
    const hits = pattern.keywords.filter((keyword) => requirement.includes(keyword));
    const riskHit = selectedRisks.some((risk) => pattern.keywords.some((keyword) => risk.includes(keyword) || keyword.includes(risk.slice(0, 2))));
    if (hits.length === 0 && !riskHit) return;

    const sourceSentence = sentences.find((sentence) => hits.some((keyword) => sentence.includes(keyword)));
    const description = sourceSentence ?? pattern.fallback;
    const key = `${pattern.type}:${description}`;
    if (seen.has(key)) return;
    seen.add(key);
    rules.push({
      ruleId: `R-${rules.length + 1}-${hashText(key).slice(0, 4)}`,
      description,
      type: pattern.type,
      riskLevel: pattern.riskLevel,
      keywords: hits.length > 0 ? hits : selectedRisks,
    });
  });

  if (rules.length === 0 && requirement.trim()) {
    rules.push({
      ruleId: `R-1-${hashText(requirement).slice(0, 4)}`,
      description: requirement.trim().slice(0, 90),
      type: '核心行为',
      riskLevel: 'medium',
      keywords: ['业务需求'],
    });
  }

  return rules;
}
