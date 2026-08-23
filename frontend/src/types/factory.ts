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
  jobs: Record<string, unknown>
  overtime_hours: number
  changeover_hours: number
  production_cost: number
  late_penalty_cost: number
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
