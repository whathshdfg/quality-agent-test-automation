export type RiskLevel = 'high' | 'medium' | 'low';
export type Priority = 'P0' | 'P1' | 'P2';
export type CaseStatus = 'not_run' | 'passed' | 'failed';
export type GenerationSource = 'rule_generated' | 'gap_supplement' | 'manual';

export interface RequirementRule {
  ruleId: string;
  description: string;
  type: string;
  riskLevel: RiskLevel;
  keywords: string[];
}

export interface TestPoint {
  pointId: string;
  name: string;
  category: '功能流程' | '参数校验' | '风险场景';
  dimension: string;
  relatedRuleIds: string[];
  riskLevel: RiskLevel;
  covered: boolean;
}

export interface TestCase {
  caseId: string;
  title: string;
  priority: Priority;
  businessType: string;
  dimension: string;
  preconditions: string[];
  steps: string[];
  expectedResults: string[];
  relatedRuleIds: string[];
  generationSource: GenerationSource;
  status: CaseStatus;
  createdAt: string;
  updatedAt: string;
}

export interface CoverageMetric {
  covered: number;
  total: number;
  rate: number;
}

export interface CoverageGap {
  dimension: string;
  category: TestPoint['category'];
  risk: string;
  recommendation: string;
}

export interface CoverageResult {
  ruleCoverage: CoverageMetric;
  functionalCoverage: CoverageMetric;
  parameterCoverage: CoverageMetric;
  riskCoverage: CoverageMetric;
  overall: number;
  coveredDimensions: string[];
  missingDimensions: CoverageGap[];
}

export interface QualityTask {
  id: string;
  name: string;
  businessType: string;
  requirement: string;
  riskTags: string[];
  rules: RequirementRule[];
  testPoints: TestPoint[];
  testCases: TestCase[];
  coverage: CoverageResult;
  createdAt: string;
  updatedAt: string;
}

export interface TaskDraft {
  name: string;
  businessType: string;
  requirement: string;
  riskTags: string[];
}
