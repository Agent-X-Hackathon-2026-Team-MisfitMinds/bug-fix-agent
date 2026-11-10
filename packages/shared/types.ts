/**
 * Canonical type contracts shared between TypeScript and Python.
 * Keep Python Pydantic models and TS types in sync - same field names and enums.
 */

// Run state contract
export type RunStatus = 
  | 'pending' 
  | 'reproducing' 
  | 'fixing' 
  | 'verifying' 
  | 'completed' 
  | 'failed' 
  | 'could_not_reproduce';

// Pipeline step
export type PipelineStep = 
  | 'read' 
  | 'reproduce' 
  | 'diagnose' 
  | 'fix' 
  | 'verify' 
  | 'pr';

// Confidence level
export type ConfidenceLevel = 'high' | 'medium' | 'low';

// Run ID format: bugfix-{issueNumber}-{timestamp}
export interface RunId {
  value: string;
  issueNumber: number;
  timestamp: string;
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
  filePath: string;
  oldCode: string;
  newCode: string;
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

// Shared constants
export const STATUS_VALUES: ReadonlyArray<RunStatus> = ['pending', 'reproducing', 'fixing', 'verifying', 'completed', 'failed', 'could_not_reproduce'] as const;
export const CONFIDENCE_VALUES: ReadonlyArray<ConfidenceLevel> = ['high', 'medium', 'low'] as const;
export const STEP_VALUES: ReadonlyArray<PipelineStep> = ['read', 'reproduce', 'diagnose', 'fix', 'verify', 'pr'] as const;