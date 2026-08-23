import type { FactoryState, SimulationResponse } from '../types/factory'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

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
    const message =
      typeof body?.detail === 'string'
        ? body.detail
        : `Request failed with status ${response.status}`
    throw new Error(message)
  }

  return response.json() as Promise<T>
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
