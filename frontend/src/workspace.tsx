import { Button, Flex, Heading, Spinner, Text } from '@chakra-ui/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { TriangleAlert } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { DecisionDialog } from './components/DecisionDialog'
import { IncidentDialog } from './components/IncidentDialog'
import { ScheduleDialog } from './components/ScheduleDialog'
import { getFactory, investigateEvent, resetFactory, tickFactory } from './lib/api'
import type { AgentDecisionRecord, FactoryEvent, FactoryState } from './types/factory'
import {
  FACTORY_NAME,
  STEP_HOURS,
  WorkspaceContext,
  type WorkspaceValue,
} from './workspace-context'

const ACTIVITY_LIMIT = 30

/**
 * Owns everything shared across routes. Lives above the router outlet so the
 * activity log and open dialogs survive navigation between pages.
 */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [incidentOpen, setIncidentOpen] = useState(false)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [events, setEvents] = useState<FactoryEvent[]>([])
  const [investigationEvent, setInvestigationEvent] = useState<FactoryEvent | null>(null)
  const [decisions, setDecisions] = useState<Record<string, AgentDecisionRecord>>({})

  const factoryQuery = useQuery({
    queryKey: ['factory', FACTORY_NAME],
    queryFn: () => getFactory(FACTORY_NAME),
  })
  const tickMutation = useMutation({
    mutationFn: (stepHours: number) => tickFactory(FACTORY_NAME, stepHours),
    onSuccess: ({ state, events: ticked }) => {
      queryClient.setQueryData<FactoryState>(['factory', FACTORY_NAME], state)
      if (ticked.length) {
        setEvents((current) =>
          [...ticked.toReversed(), ...current].slice(0, ACTIVITY_LIMIT),
        )
      }
    },
  })
  const resetMutation = useMutation({
    mutationFn: () => resetFactory(FACTORY_NAME),
    onSuccess: (resetState) => {
      queryClient.setQueryData<FactoryState>(['factory', FACTORY_NAME], resetState)
      tickMutation.reset()
      investigationMutation.reset()
      setEvents([])
      setDecisions({})
      setInvestigationEvent(null)
      setIncidentOpen(false)
      setScheduleOpen(false)
      setNotice('Simulation reset to its initial state')
    },
  })
  const investigationMutation = useMutation({
    mutationFn: (eventId: string) => investigateEvent(FACTORY_NAME, eventId),
    onSuccess: (record, eventId) => {
      setDecisions((current) => ({ ...current, [eventId]: record }))
    },
  })

  const state = factoryQuery.data
  const value = ((): WorkspaceValue | null => {
    if (!state) {
      return null
    }
    const machines = Object.values(state.machines)
    const orders = Object.values(state.orders)
    return {
      state,
      machines,
      orders,
      openOrders: orders.filter(
        (order) => order.status === 'pending' || order.status === 'in_progress',
      ),
      unavailable: machines.filter(
        (machine) => machine.status === 'down' || machine.status === 'maintenance',
      ),
      events,
      notice,
      advance: () => tickMutation.mutate(STEP_HOURS),
      advancing: tickMutation.isPending,
      advanceError: tickMutation.error,
      reset: () => resetMutation.mutate(),
      resetting: resetMutation.isPending,
      resetError: resetMutation.error,
      refetch: () => void factoryQuery.refetch(),
      refreshing: factoryQuery.isFetching,
      openSchedule: () => setScheduleOpen(true),
      openIncident: () => setIncidentOpen(true),
      investigate: (event) => {
        setInvestigationEvent(event)
        // A decision is tied to the state hash it was made against, so re-running
        // it would produce a different record. Reopen the one we already have.
        if (decisions[event.id] || investigationMutation.isPending) {
          return
        }
        investigationMutation.reset()
        investigationMutation.mutate(event.id)
      },
      decisions,
    }
  })()

  if (factoryQuery.isPending) {
    return (
      <Flex className="center-state">
        <Spinner size="md" />
        <Text>Connecting to factory…</Text>
      </Flex>
    )
  }

  if (factoryQuery.isError || value === null) {
    return (
      <Flex className="center-state error-state">
        <TriangleAlert size={22} />
        <Heading className="page-title">Could not load factory</Heading>
        <Text>{factoryQuery.error?.message ?? 'Factory state was unavailable.'}</Text>
        <Button size="sm" onClick={() => void factoryQuery.refetch()}>
          Try again
        </Button>
      </Flex>
    )
  }

  return (
    <WorkspaceContext value={value}>
      {children}
      {incidentOpen && (
        <IncidentDialog
          factoryName={FACTORY_NAME}
          machines={value.machines}
          currentHour={value.state.sim_hour}
          onClose={() => setIncidentOpen(false)}
          onScheduled={(result) => {
            setIncidentOpen(false)
            setNotice(
              `${result.event.machine_id} failure scheduled for hour ${result.event.sim_hour.toFixed(2)} · ${result.pending_event_count} pending event${result.pending_event_count === 1 ? '' : 's'}`,
            )
          }}
        />
      )}
      {scheduleOpen && (
        <ScheduleDialog
          factoryName={FACTORY_NAME}
          state={value.state}
          onClose={() => setScheduleOpen(false)}
          onCommitted={(committedState) => {
            queryClient.setQueryData<FactoryState>(
              ['factory', FACTORY_NAME],
              committedState,
            )
            setScheduleOpen(false)
            setNotice(
              `Schedule v${committedState.schedule_version} committed with ${Object.keys(committedState.jobs).length} jobs`,
            )
          }}
        />
      )}
      {investigationEvent && (
        <DecisionDialog
          event={investigationEvent}
          result={decisions[investigationEvent.id]}
          loading={
            investigationMutation.isPending && !decisions[investigationEvent.id]
          }
          error={
            decisions[investigationEvent.id]
              ? undefined
              : (investigationMutation.error ?? undefined)
          }
          onRetry={() => {
            investigationMutation.reset()
            investigationMutation.mutate(investigationEvent.id)
          }}
          onClose={() => setInvestigationEvent(null)}
          onReplan={() => {
            setInvestigationEvent(null)
            setScheduleOpen(true)
          }}
        />
      )}
    </WorkspaceContext>
  )
}
