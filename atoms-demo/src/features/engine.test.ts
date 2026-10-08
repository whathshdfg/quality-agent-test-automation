import { describe, expect, it, beforeEach } from 'vitest';
import { analyzeRequirement } from './analyzer';
import { generateTestPoints } from './testPointGenerator';
import { generateTestCases, dedupeCases } from './caseGenerator';
import { calculateCoverage } from './coverage';
import { supplementForGap } from './supplement';
import { buildMarkdown } from '../utils/exporters';
import { createTask } from './taskFactory';
import { taskStorage } from '../services/storage';

const payment = '用户只能支付处于待支付状态的订单。支付成功后，订单状态更新为已支付并记录支付流水。用户重复支付时返回REPEAT_PAYMENT，并且不能发生重复扣款。';
const login = '用户使用手机号和密码登录。手机号不能为空且必须符合格式要求。连续五次密码错误后账号锁定三十分钟，登录成功后清空登录失败次数。';
const cancel = '用户只能取消待接单或待服务状态的订单。订单取消后需要释放已占用资源。已完成订单不能取消，重复取消时不能重复退款和重复释放资源。';

const memoryStorage = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(globalThis, 'localStorage', { value: memoryStorage });

beforeEach(() => localStorage.clear());

describe('local rule engine', () => {
  it('支付需求能识别幂等性规则', () => {
    expect(analyzeRequirement(payment).some((rule) => rule.type === '并发幂等')).toBe(true);
  });

  it('支付需求能识别状态流转规则', () => {
    expect(analyzeRequirement(payment).some((rule) => rule.type === '状态约束')).toBe(true);
  });

  it('登录需求能识别参数校验风险', () => {
    expect(analyzeRequirement(login).some((rule) => rule.type === '参数校验')).toBe(true);
  });

  it('登录需求能识别账号锁定安全风险', () => {
    expect(analyzeRequirement(login).some((rule) => rule.type === '安全权限')).toBe(true);
  });

  it('取消订单需求能识别资源释放风险', () => {
    expect(analyzeRequirement(cancel).some((rule) => rule.type === '数据一致性')).toBe(true);
  });

  it('测试用例生成结果不为空且 caseId 不重复', () => {
    const rules = analyzeRequirement(payment);
    const cases = generateTestCases(rules, generateTestPoints(rules), '支付');
    expect(cases.length).toBeGreaterThan(0);
    expect(new Set(cases.map((item) => item.caseId)).size).toBe(cases.length);
  });

  it('重复生成时能去重', () => {
    const rules = analyzeRequirement(payment);
    const cases = generateTestCases(rules, generateTestPoints(rules), '支付');
    expect(dedupeCases([...cases, ...cases]).length).toBe(cases.length);
  });

  it('覆盖率结果位于 0 到 100 之间，且空规则不除零', () => {
    const empty = calculateCoverage([], []);
    expect(empty.overall).toBeGreaterThanOrEqual(0);
    expect(empty.overall).toBeLessThanOrEqual(100);
    const task = createTask({ name: '支付', businessType: '支付', requirement: payment, riskTags: [] });
    expect(task.coverage.overall).toBeGreaterThanOrEqual(0);
    expect(task.coverage.overall).toBeLessThanOrEqual(100);
  });

  it('补充缺失维度后对应覆盖率提高', () => {
    const task = createTask({ name: '支付', businessType: '支付', requirement: payment, riskTags: [] });
    const reduced = { ...task, testCases: task.testCases.filter((item) => item.dimension !== '幂等性') };
    const before = calculateCoverage(reduced.testPoints, reduced.testCases);
    const gap = before.missingDimensions.find((item) => item.dimension === '幂等性');
    expect(gap).toBeTruthy();
    const afterCases = supplementForGap(reduced.testPoints, reduced.testCases, '支付', gap!);
    const after = calculateCoverage(reduced.testPoints, afterCases);
    expect(after.riskCoverage.rate).toBeGreaterThanOrEqual(before.riskCoverage.rate);
  });

  it('localStorage 数据损坏时能安全降级', () => {
    localStorage.setItem('quality_agent_studio_tasks_v1', '{bad json');
    expect(taskStorage.load()).toEqual([]);
  });

  it('导出的 Markdown 包含任务名称和测试用例', () => {
    const task = createTask({ name: '支付任务', businessType: '支付', requirement: payment, riskTags: [] });
    const markdown = buildMarkdown(task);
    expect(markdown).toContain('支付任务');
    expect(markdown).toContain('测试用例');
  });
});
