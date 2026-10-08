import type { QualityTask } from '../types';

function safeName(name: string): string {
  return name.replace(/[\\/:*?"<>|\s]+/g, '-').replace(/-+/g, '-').slice(0, 48);
}

export function buildMarkdown(task: QualityTask): string {
  const cases = task.testCases
    .map(
      (testCase) =>
        `### ${testCase.caseId} ${testCase.title}

- 优先级：${testCase.priority}
- 维度：${testCase.dimension}
- 状态：${testCase.status}
- 关联规则：${testCase.relatedRuleIds.join(', ') || '无'}
- 前置条件：${testCase.preconditions.join('；')}
- 测试步骤：${testCase.steps.join('；')}
- 预期结果：${testCase.expectedResults.join('；')}`,
    )
    .join('\n\n');

  return `# ${task.name}

## 一、任务信息

- 业务类型：${task.businessType}
- 创建时间：${new Date(task.createdAt).toLocaleString()}
- 更新时间：${new Date(task.updatedAt).toLocaleString()}
- 综合覆盖率：${task.coverage.overall}%

## 二、原始需求

${task.requirement}

## 三、结构化需求规则

${task.rules.map((rule) => `- ${rule.ruleId} [${rule.type}/${rule.riskLevel}] ${rule.description}`).join('\n')}

## 四、分层测试点

${task.testPoints.map((point) => `- ${point.pointId} [${point.category}/${point.dimension}] ${point.name}，覆盖：${point.covered ? '是' : '否'}`).join('\n')}

## 五、覆盖率分析

- 需求规则覆盖率：${task.coverage.ruleCoverage.rate}%
- 功能流程覆盖率：${task.coverage.functionalCoverage.rate}%
- 参数覆盖率：${task.coverage.parameterCoverage.rate}%
- 风险覆盖率：${task.coverage.riskCoverage.rate}%
- 缺口：${task.coverage.missingDimensions.map((gap) => gap.dimension).join('、') || '无'}

## 六、测试用例

${cases || '暂无测试用例'}

## 七、覆盖缺口与建议

${task.coverage.missingDimensions.map((gap) => `- ${gap.dimension}：${gap.risk} 建议：${gap.recommendation}`).join('\n') || '当前没有明显覆盖缺口。'}
`;
}

export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function exportMarkdown(task: QualityTask): void {
  downloadText(`${safeName(task.name)}-${new Date().toISOString().slice(0, 10)}.md`, buildMarkdown(task), 'text/markdown;charset=utf-8');
}

export function exportJson(task: QualityTask): void {
  downloadText(`${safeName(task.name)}-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(task, null, 2), 'application/json;charset=utf-8');
}
