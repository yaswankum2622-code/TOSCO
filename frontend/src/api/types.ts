export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  mode: string;
}

export interface WorkflowMetadata {
  workflow_id: string;
  workflow_name: string;
  required_evidence_types: string[];
  gates_to_run: string[];
  tools_to_call: string[];
  execution_adapter: string;
}

export interface ScenarioMetadata {
  scenario: string;
  title: string;
  description: string;
  expected_naive_agent_action: string;
  expected_tosco_decision: string;
}

export interface RunSummaryResponse {
  scenario: string;
  run_id: string;
  final_decision: string;
  allow_execution: boolean;
  token_issued: boolean;
  mock_bank_status: string;
  mock_bank_reason_code: string;
  proof_hash: string;
  ledger_entry_hash: string;
  timeline_events_count: number;
}

export interface StartRunRequest {
  scenario: string;
  use_vultr?: boolean;
}

export interface OrchestratorEvent {
  index: number;
  event_type: string;
  run_id: string;
  title: string;
  detail: string;
  payload: Record<string, unknown>;
}

export interface EventTimelineResponse {
  run_id: string;
  events: OrchestratorEvent[];
}

export interface ProofPacketResponse {
  run_id: string;
  proof_packet: Record<string, unknown>;
  proof_hash: string;
  ledger_entry_hash: string;
}

export interface VerifyRunResponse {
  run_id: string;
  ledger_chain_valid: boolean;
  packet_entry_valid: boolean;
  proof_hash: string;
  ledger_entry_hash: string;
  verified: boolean;
}

export interface ResetResponse {
  status: string;
  runs: number;
}

export interface VultrStatusResponse {
  configured: boolean;
  base_url: string;
  model: string;
  mode: string;
  key_present: boolean;
}
