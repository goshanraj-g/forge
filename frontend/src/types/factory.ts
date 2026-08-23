export type MachineStatus = 'running' | 'idle' | 'down' | 'maintenance'

export interface Machine {
  id: string
  name: string
  capacity_per_hour: number
  supported_products: string[]
  status: MachineStatus
  down_until_hour: number | null
  current_family: string | null
}

export interface Order {
  id: string
  product_id: string
  quantity: number
  due_hour: number
  priority: number
  status: 'pending' | 'in_progress' | 'complete' | 'late'
  produced: number
}

export interface InventoryItem {
  component_id: string
  on_hand: number
  reserved: number
  reorder_point: number
}

export interface FactoryState {
  name: string
  sim_hour: number
  schedule_version: number
  machines: Record<string, Machine>
  orders: Record<string, Order>
  inventory: Record<string, InventoryItem>
  jobs: Record<string, ProductionJob>
  overtime_hours: number
  changeover_hours: number
  production_cost: number
  late_penalty_cost: number
}

export interface ProductionJob {
  id: string
  order_id: string
  machine_id: string
  product_id: string
  start_hour: number
  end_hour: number
  quantity: number
  schedule_version: number
  produced: number
}

export interface ScheduleViolation {
  code: string
  message: string
  job_ids: string[]
  order_ids: string[]
}

export interface ScheduleResult {
  status: 'optimal' | 'feasible' | 'partial' | 'needs_information' | 'infeasible' | 'unknown' | 'error'
  jobs: ProductionJob[]
  unscheduled_orders: Array<{
    order_id: string
    reason_code: string
    explanation: string
    required_action: string | null
  }>
  cost: { late_penalty: number; overtime: number; changeover: number }
  optimality_gap: number | null
  solve_seconds: number
  time_limit_seconds: number
  relaxed_constraints: string[]
  notes: string[]
  validation: { violations: ScheduleViolation[] } | null
}

export interface CommitScheduleResponse {
  state: FactoryState
  validation: { violations: ScheduleViolation[] }
}

export interface FactoryEvent {
  id: string
  sim_hour: number
  type: string
  [key: string]: unknown
}

export interface SimulationResponse {
  state: FactoryState
  events: FactoryEvent[]
}

export interface MachineFailureEvent extends FactoryEvent {
  type: 'machine_failure'
  machine_id: string
  duration_hours: number
}

export interface EventScheduledResponse {
  event: MachineFailureEvent
  pending_event_count: number
}

export interface AgentDecisionRecord {
  factory_name: string
  simulation_hour: number
  schedule_version: number
  state_snapshot_hash: string
  trigger_event_id: string
  trigger_event_type: string
  prompt_version: string
  model_name: string
  decision: {
    status: 'no_action' | 'replan_recommended' | 'needs_information' | 'escalate'
    severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
    summary: string
    explanation: string
    affected_order_ids: string[]
    affected_machine_ids: string[]
    missing_information: string[]
    should_replan: boolean
    requires_human_approval: boolean
  }
}
