export type EventType =
  | "AGENT_INIT"
  | "LLM_INFERENCE"
  | "TOOL_INVOCATION"
  | "STATE_MUTATION"
  | "CONTEXT_COMPACTED"
  | "VERIFIER_INVARIANT_CHECK"
  | "TERMINATION";

export interface ContextSnapshot {
  systemPrompt: string;
  episodicMemory: string[];
  schemaTables: string[];
  totalTokens: number;
  maxTokenBudget: number;
  compactedTokensPruned?: number;
}

export interface DecisionPayload {
  actionName: string;
  parameters: Record<string, unknown>;
  idempotencyKey: string;
  executionOutput: unknown;
  verifierPassed: boolean;
  verifierDetails?: string;
}

export interface AgentStep {
  seq: number;
  timestamp: string;
  eventType: EventType;
  eventHash: string;
  parentHash: string;
  context: ContextSnapshot;
  decision: DecisionPayload;
  divergedFromBaseline?: boolean;
  divergenceReason?: string;
}

export interface AgentRun {
  runId: string;
  taskTitle: string;
  taskPrompt: string;
  status: "SUCCESS" | "VERIFIER_FAILURE" | "REPLAY_DIVERGED" | "RUNNING";
  baselineRunId?: string;
  forkStepIndex?: number;
  steps: AgentStep[];
  totalLatencyMs: number;
  totalTokens: number;
}

export interface BootstrapStats {
  baselineSuccessRate: number;
  candidateSuccessRate: number;
  deltaMean: number;
  ciLower: number;
  ciUpper: number;
  pValue: number;
  nResamples: number;
  isRegression: boolean;
}

export interface HolmBonferroniTask {
  taskId: string;
  description: string;
  baselinePassRate: number;
  candidatePassRate: number;
  rawPValue: number;
  adjustedPValue: number;
  rejectedNull: boolean;
}
