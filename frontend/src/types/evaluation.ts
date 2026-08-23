export interface EvaluationMetrics {
  late_orders: number
  priority_weighted_lateness: number
  unmet_demand_units: number
  penalty_cost: number
  overtime_cost: number
  changeover_cost: number
  /** Penalty + overtime + changeover: the cost a different schedule could avoid. */
  controllable_cost: number
  production_cost: number
  total_cost: number
  overtime_hours: number
  changeover_hours: number
  constraint_violations: number
  replans: number
  model_calls: number
  model_cost: number
}

export interface EvaluationDecisionTrace {
  event_id: string
  event_type: string
  simulation_hour: number
  state_snapshot_hash: string
  replan_requested: boolean
  schedule_committed: boolean
  resulting_schedule_version: number
}

export interface EvaluationResult {
  scenario_id: string
  policy_name: string
  scenario_hash: string
  initial_state_hash: string
  final_state_hash: string
  started_at: string
  metrics: EvaluationMetrics
  decision_event_ids: string[]
  schedule_versions: number[]
  decisions: EvaluationDecisionTrace[]
}

export interface EvaluationScenarioSummary {
  id: string
  description: string
  factory_name: string
  horizon_hour: number
  scenario_hash: string
  event_count: number
}

export interface EvaluationComparison {
  scenarios: EvaluationScenarioSummary[]
  results: EvaluationResult[]
}
