import { createContext, use } from 'react'

import type {
  AgentDecisionRecord,
  FactoryEvent,
  FactoryState,
  Machine,
  Order,
} from './types/factory'

export const FACTORY_NAME = 'factory_01'
export const STEP_HOURS = 0.25

export interface WorkspaceValue {
  state: FactoryState
  machines: Machine[]
  orders: Order[]
  openOrders: Order[]
  unavailable: Machine[]
  events: FactoryEvent[]
  notice: string | null
  advance: () => void
  advancing: boolean
  advanceError: Error | null
  refetch: () => void
  openSchedule: () => void
  openIncident: () => void
  investigate: (event: FactoryEvent) => void
  /** Completed investigations, keyed by event id, kept for the whole session. */
  decisions: Record<string, AgentDecisionRecord>
}

export const WorkspaceContext = createContext<WorkspaceValue | null>(null)

export function useWorkspace(): WorkspaceValue {
  const value = use(WorkspaceContext)
  if (value === null) {
    throw new Error('useWorkspace must be used inside a WorkspaceProvider')
  }
  return value
}
