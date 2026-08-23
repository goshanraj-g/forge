import type {
  AgentDecisionRecord,
  EventScheduledResponse,
  FactoryState,
  CommitScheduleResponse,
  ProductionJob,
  ScheduleResult,
  SimulationResponse,
} from '../types/factory'
import type { EvaluationComparison } from '../types/evaluation'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export function getEvaluations(): Promise<EvaluationComparison> {
  return request('/evaluations')
}

export function runAgentEvaluations(): Promise<EvaluationComparison> {
  return request('/evaluations/agent', { method: 'POST' })
}

export function investigateEvent(
  name: string,
  eventId: string,
): Promise<AgentDecisionRecord> {
  return request(`/factories/${name}/investigations`, {
    method: 'POST',
    body: JSON.stringify({ event_id: eventId }),
  })
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: unknown
    } | null
    const detail = body?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail &&
            typeof detail === 'object' &&
            'message' in detail &&
            typeof detail.message === 'string'
          ? detail.message
          : `Request failed with status ${response.status}`
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export function optimizeFactory(name: string): Promise<ScheduleResult> {
  return request(`/factories/${name}/optimize`, {
    method: 'POST',
    body: JSON.stringify({
      horizon_hours: 72,
      bucket_hours: 1,
      time_limit_seconds: 10,
    }),
  })
}

export function commitSchedule(
  name: string,
  expectedVersion: number,
  jobs: ProductionJob[],
): Promise<CommitScheduleResponse> {
  return request(`/factories/${name}/schedules/commit`, {
    method: 'POST',
    body: JSON.stringify({
      expected_version: expectedVersion,
      jobs,
      hard_deadline_orders: [],
    }),
  })
}

export function getFactory(name: string): Promise<FactoryState> {
  return request(`/factories/${name}`)
}

export function tickFactory(
  name: string,
  stepHours: number,
): Promise<SimulationResponse> {
  return request(`/factories/${name}/tick`, {
    method: 'POST',
    body: JSON.stringify({ step_hours: stepHours }),
  })
}

export function scheduleMachineFailure(
  name: string,
  input: {
    machineId: string
    simHour: number
    durationHours: number
  },
): Promise<EventScheduledResponse> {
  return request(`/factories/${name}/events`, {
    method: 'POST',
    body: JSON.stringify({
      type: 'machine_failure',
      sim_hour: input.simHour,
      machine_id: input.machineId,
      duration_hours: input.durationHours,
    }),
  })
}
