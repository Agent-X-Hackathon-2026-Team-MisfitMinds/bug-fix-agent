/**
 * Canonical type contracts shared between TypeScript and Python.
 * Keep Python Pydantic models and TS types in sync - same field names and enums.
 */

// Run status contract - must match Python RunStatus enum
export type RunStatus = 
  | 'pending' 
  | 'reproducing' 
  | 'fixing' 
  | 'verifying' 
  | 'completed' 
  | 'failed' 
  | 'could_not_reproduce';

// Confidence level contract - must match Python ConfidenceLevel enum
export type ConfidenceLevel = 'high' | 'medium' | 'low';

// Pipeline step contract - must match Python PipelineStep enum
export type PipelineStep = 
  | 'read' 
  | 'reproduce' 
  | 'diagnose' 
  | 'fix' 
  | 'verify' 
  | 'pr';

// Run state interface - must match Python RunState Pydantic model
export interface RunState {
  run_id: string;
  issue_id: number;
  repo_name: string;
  branch: string;

  status: RunStatus;
  step: PipelineStep;
  confidence: ConfidenceLevel | null;

  issue_title: string | null;
  issue_body: string | null;
  reproduction_steps: string | null;

  before_test_output: string | null;
  before_exit_code: number | null;

  after_test_output: string | null;
  after_exit_code: number | null;

  root_cause: string | null;
  patch: {
    file_path: string;
    old_code: string;
    new_code: string;
    description: string;
  } | null;
  likely_file: string | null;
  likely_line: number | null;

  evidence: string[];
  errors: string[];

  pr_url: string | null;
  branch_name: string | null;

  retry_count: number;
  created_at: string;
  updated_at: string;
}

// Issue summary for the agent
export interface IssueSummary {
  title: string;
  body: string;
  labels: string[];
  repository: string;
}

// Patch representation
export interface Patch {
  file_path: string;
  old_code: string;
  new_code: string;
  description: string;
}

// Error representation
export interface AgentError {
  code: string;
  message: string;
  context?: string;
}

// API response shapes (must match Python Pydantic models)
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: AgentError;
  run?: RunStatus;
}

// Shared constants - keep these in sync with Python enums
export const STATUS_VALUES: ReadonlyArray<RunStatus> = [
  'pending', 
  'reproducing', 
  'fixing', 
  'verifying', 
  'completed', 
  'failed', 
  'could_not_reproduce'
] as const;

export const CONFIDENCE_VALUES: ReadonlyArray<ConfidenceLevel> = [
  'high', 
  'medium', 
  'low'
] as const;

export const STEP_VALUES: ReadonlyArray<PipelineStep> = [
  'read', 
  'reproduce', 
  'diagnose', 
  'fix', 
  'verify', 
  'pr'
] as const;

// Helper type guards
export const isRunStatus = (value: string): value is RunStatus => {
  return STATUS_VALUES.includes(value as RunStatus);
};

export const isConfidenceLevel = (value: string): value is ConfidenceLevel => {
  return CONFIDENCE_VALUES.includes(value as ConfidenceLevel);
};

export const isPipelineStep = (value: string): value is PipelineStep => {
  return STEP_VALUES.includes(value as PipelineStep);
};