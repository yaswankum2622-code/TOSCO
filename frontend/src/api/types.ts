export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  mode: string;
  fallback_mode: boolean;
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

export interface CustomRunRequest {
  vendor_id: string;
  amount: number;
  currency: string;
  bank_account_last4: string;
  registered_bank_last4: string;
  invoice_text: string;
  bank_owner_matches_vendor: boolean;
  request_domain_age_days: number;
  logistics_confirmed: boolean;
  is_first_payment_to_account: boolean;
  use_vultr?: boolean;
}

export interface RunHandleResponse {
  run_id: string;
}

export interface ProposedActionPayload {
  type: string;
  vendor_id: string;
  amount: number;
  currency: string;
  bank_account_last4: string;
}

export interface ActionIntentPayload {
  intent_id: string;
  agent_id: string;
  workflow: string;
  action: ProposedActionPayload;
  evidence_refs: string[];
  declared_confidence: number;
  requested_mode: string;
}

export interface AgentProposeRequest {
  agent_id: string;
  workflow: string;
  action: ProposedActionPayload;
  evidence_refs: string[];
  declared_confidence: number;
  requested_mode: string;
  scenario: string;
}

export interface AgentProposeResponse {
  intent_id: string;
  accepted: boolean;
}

export interface ToolCallPayload {
  tool_id: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  simulated: boolean;
  latency_ms: number | null;
}

export interface GateResultPayload {
  gate_id: string;
  name: string;
  status: string;
  decision: string;
  reason_code: string;
  human_reason: string;
  evidence_refs: string[];
}

export interface RunSnapshotResponse {
  run_id: string;
  workflow_id: string | null;
  status: string;
  intent: ActionIntentPayload | null;
  evidence_refs: string[];
  extraction_hash: string | null;
  tool_calls: ToolCallPayload[];
  gate_results: GateResultPayload[];
  decision: string | null;
  fallback_mode: boolean;
  clearance_token: string | null;
  error_message: string | null;
}

export interface ContractRunEvent {
  event: string;
  run_id: string;
  ts: string;
  data: Record<string, unknown>;
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
  chain_head?: string | null;
  tampered_field?: string | null;
  verify_now?: boolean | null;
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

export interface ExecutionAttemptRequest {
  run_id: string;
  token: string | null;
  vendor_id: string;
  amount: number;
}

export interface ExecutionAttemptResponse {
  executed: boolean;
  reason: string;
}
