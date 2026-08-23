import { Box, Button, Flex, Grid, Heading, Spinner, Text } from '@chakra-ui/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useRouterState } from '@tanstack/react-router'
import {
  CalendarRange,
  ChevronDown,
  CircleGauge,
  Factory,
  FlaskConical,
  Play,
  RefreshCw,
  Settings,
  TriangleAlert,
} from 'lucide-react'
import { useState } from 'react'

import { ActivityLog } from './components/ActivityLog'
import { DecisionDialog } from './components/DecisionDialog'
import { IncidentDialog } from './components/IncidentDialog'
import { ScheduleDialog } from './components/ScheduleDialog'
import { ScheduleTimeline } from './components/ScheduleTimeline'
import { getFactory, investigateEvent, tickFactory } from './lib/api'
import type { FactoryEvent, FactoryState, MachineStatus } from './types/factory'

const FACTORY_NAME = 'factory_01'
const STEP_HOURS = 0.25
const WINDOW_HOURS = 24
const SOON_HOURS = 4
const GRID_HOURS = [0, 6, 12, 18, 24]

const navigation = [
  { label: 'Overview', icon: CircleGauge, to: '/' },
  { label: 'Schedule', icon: CalendarRange, to: '/schedule' },
  { label: 'Incidents', icon: TriangleAlert, to: '/incidents' },
  { label: 'Evaluations', icon: FlaskConical, to: '/evaluations' },
]

function App() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const [incidentOpen, setIncidentOpen] = useState(false)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [eventNotice, setEventNotice] = useState<string | null>(null)
  const [activityEvents, setActivityEvents] = useState<FactoryEvent[]>([])
  const [investigationEvent, setInvestigationEvent] = useState<FactoryEvent | null>(null)
  const queryClient = useQueryClient()
  const factoryQuery = useQuery({
    queryKey: ['factory', FACTORY_NAME],
    queryFn: () => getFactory(FACTORY_NAME),
  })
  const tickMutation = useMutation({
    mutationFn: (stepHours: number) => tickFactory(FACTORY_NAME, stepHours),
    onSuccess: ({ state, events }) => {
      queryClient.setQueryData<FactoryState>(['factory', FACTORY_NAME], state)
      if (events.length) {
        setActivityEvents((current) => [...events.toReversed(), ...current].slice(0, 30))
      }
    },
  })
  const investigationMutation = useMutation({
    mutationFn: (eventId: string) => investigateEvent(FACTORY_NAME, eventId),
  })

  if (factoryQuery.isPending) {
    return (
      <Flex className="center-state">
        <Spinner size="md" />
        <Text>Connecting to factory…</Text>
      </Flex>
    )
  }

  if (factoryQuery.isError) {
    return (
      <Flex className="center-state error-state">
        <TriangleAlert size={22} />
        <Heading className="page-title">Could not load factory</Heading>
        <Text>{factoryQuery.error.message}</Text>
        <Button size="sm" onClick={() => factoryQuery.refetch()}>
          Try again
        </Button>
      </Flex>
    )
  }

  const state = factoryQuery.data
  const machines = Object.values(state.machines)
  const orders = Object.values(state.orders)
  const openOrders = orders.filter(
    (order) => order.status === 'pending' || order.status === 'in_progress',
  )
  const unavailable = machines.filter(
    (machine) => machine.status === 'down' || machine.status === 'maintenance',
  )
  const totalCost = state.production_cost + state.late_penalty_cost

  // Every deadline measured from now, so the band only ever shows work still ahead.
  const deadlines = openOrders.map((order) => ({
    id: order.id,
    hoursOut: order.due_hour - state.sim_hour,
  }))
  const overdue = deadlines.filter((deadline) => deadline.hoursOut < 0)
  const inWindow = deadlines.filter(
    (deadline) => deadline.hoursOut >= 0 && deadline.hoursOut <= WINDOW_HOURS,
  )
  const later = deadlines.filter((deadline) => deadline.hoursOut > WINDOW_HOURS)
  const at = (hours: number) => `${(hours / WINDOW_HOURS) * 100}%`

  return (
    <Grid className="app-layout">
      <Flex as="aside" className="sidebar">
        <Flex className="wordmark">
          <Box className="logo-mark">F</Box>
          <Text>ForgeOps</Text>
        </Flex>

        <Box as="nav" className="nav-list">
          {navigation.map(({ label, icon: Icon, to }) => (
            <Link className={`nav-item${pathname === to ? ' active' : ''}`} key={label} to={to}>
              <Icon size={16} strokeWidth={1.8} />
              <Text>{label}</Text>
            </Link>
          ))}
        </Box>

        <Box className="sidebar-footer">
          <Flex className="nav-item">
            <Settings size={16} strokeWidth={1.8} />
            <Text>Settings</Text>
          </Flex>
          <Flex className="workspace-user">
            <Box className="avatar">GR</Box>
            <Box>
              <Text>Operations</Text>
              <Text>Demo workspace</Text>
            </Box>
          </Flex>
        </Box>
      </Flex>

      <Box className="workspace">
        <Flex as="header" className="workspace-header">
          <Button variant="ghost" size="sm" className="factory-selector">
            <Factory size={15} /> factory_01 <ChevronDown size={14} />
          </Button>
          <Flex align="center" gap="3">
            <Flex className="connection-state">
              <span /> Live
            </Flex>
            <Button
              variant="ghost"
              size="sm"
              aria-label="Refresh factory state"
              onClick={() => factoryQuery.refetch()}
            >
              <RefreshCw size={15} />
            </Button>
          </Flex>
        </Flex>

        <Box as="main" className="page-content">
          <Box className="title-row">
            <Heading className="page-title">Factory overview</Heading>
            <Text className="page-sub">
              Live operating state and the production commitments it still has to meet.
            </Text>
          </Box>

          <section className="deadline-band">
            <Flex className="band-head">
              <Box>
                <Text className="eyebrow">Order deadlines</Text>
                <Heading className="band-title">Next 24 simulated hours</Heading>
              </Box>
              <Flex align="center" gap="5">
                <Box className="clock">
                  <Text className="eyebrow">Sim hour</Text>
                  <Text className="clock-value">{state.sim_hour.toFixed(2)}</Text>
                </Box>
                <Button
                  className="advance-button"
                  loading={tickMutation.isPending}
                  onClick={() => tickMutation.mutate(STEP_HOURS)}
                >
                  <Play size={13} fill="currentColor" /> Advance 15 min
                </Button>
              </Flex>
            </Flex>

            <Box className="band">
              <Box className="band-track">
                {GRID_HOURS.map((hour) => (
                  <i className="grid" key={hour} style={{ left: at(hour) }} />
                ))}
                {inWindow.map((deadline) => (
                  <i
                    className={deadline.hoursOut <= SOON_HOURS ? 'due soon' : 'due'}
                    key={deadline.id}
                    style={{ left: at(deadline.hoursOut) }}
                    title={`${deadline.id} due in ${deadline.hoursOut.toFixed(1)}h`}
                  />
                ))}
              </Box>
              <Box className="band-scale">
                {GRID_HOURS.map((hour) => (
                  <span key={hour} style={{ left: at(hour) }}>
                    {hour === 0 ? 'Now' : `+${hour}h`}
                  </span>
                ))}
              </Box>
            </Box>

            <Flex className="band-note">
              {overdue.length > 0 && (
                <Text className="overdue">{overdue.length} past due</Text>
              )}
              <Text>
                {inWindow.length === 0
                  ? 'Nothing due in this window'
                  : `${inWindow.length} due in this window`}
                {later.length > 0 && ` · ${later.length} scheduled beyond it`}
              </Text>
            </Flex>
          </section>

          {tickMutation.isError && (
            <Box className="inline-error">
              Could not advance the clock. {tickMutation.error.message}
            </Box>
          )}

          <Grid className="stat-strip">
            <Stat label="Open orders" value={String(openOrders.length)} note={`${orders.length} total`} />
            <Stat label="Available lines" value={`${machines.length - unavailable.length}/${machines.length}`} note={unavailable.length ? `${unavailable.length} need attention` : 'No active incidents'} />
            <Stat label="Schedule version" value={`v${state.schedule_version}`} note={`${Object.keys(state.jobs).length} planned jobs`} />
            <Stat label="Recorded cost" value={`$${totalCost.toLocaleString()}`} note={`${state.overtime_hours.toFixed(1)}h overtime`} />
          </Grid>

          <ScheduleTimeline
            state={state}
            machines={machines}
            onOptimize={() => setScheduleOpen(true)}
          />

          <Grid className="dashboard-grid">
            <section className="data-panel machine-panel">
              <PanelHeader title="Production lines" meta={`${machines.length} machines`} />
              <Box className="table-header machine-columns">
                <Text>Machine</Text><Text>Throughput</Text><Text>Workload</Text><Text>Status</Text>
              </Box>
              {machines.map((machine) => (
                <Grid className="table-row machine-columns" key={machine.id}>
                  <Box><Text className="primary-cell">{machine.name}</Text><Text className="sub-cell">{machine.id}</Text></Box>
                  <Text className="num-cell">{machine.capacity_per_hour}/hr</Text>
                  <Text className="num-cell">{machine.supported_products.length} products</Text>
                  <StatusLight status={machine.status} />
                </Grid>
              ))}
            </section>

            <section className="data-panel order-panel">
              <PanelHeader title="Order queue" meta={`${openOrders.length} open`} />
              <Box className="table-header order-columns">
                <Text>Order</Text><Text>Remaining</Text><Text>Due</Text>
              </Box>
              {openOrders
                .toSorted((a, b) => a.priority - b.priority || a.due_hour - b.due_hour)
                .slice(0, 7)
                .map((order) => (
                  <Grid className="table-row order-columns" key={order.id}>
                    <Box><Text className="primary-cell">{order.id}</Text><Text className="sub-cell">{order.product_id} · P{order.priority}</Text></Box>
                    <Text className="num-cell">{order.quantity - order.produced}</Text>
                    <Text className="num-cell">{order.due_hour}h</Text>
                  </Grid>
                ))}
            </section>
          </Grid>

          {eventNotice && <Text className="event-notice">{eventNotice}</Text>}

          <ActivityLog
            events={activityEvents}
            onInjectFailure={() => setIncidentOpen(true)}
            onOptimize={() => setScheduleOpen(true)}
            onInvestigate={(event) => {
              setInvestigationEvent(event)
              investigationMutation.reset()
              investigationMutation.mutate(event.id)
            }}
          />
        </Box>
      </Box>
      {incidentOpen && (
        <IncidentDialog
          factoryName={FACTORY_NAME}
          machines={machines}
          currentHour={state.sim_hour}
          onClose={() => setIncidentOpen(false)}
          onScheduled={(result) => {
            setIncidentOpen(false)
            setEventNotice(
              `${result.event.machine_id} failure scheduled for hour ${result.event.sim_hour.toFixed(2)} · ${result.pending_event_count} pending event${result.pending_event_count === 1 ? '' : 's'}`,
            )
          }}
        />
      )}
      {scheduleOpen && (
        <ScheduleDialog
          factoryName={FACTORY_NAME}
          state={state}
          onClose={() => setScheduleOpen(false)}
          onCommitted={(committedState) => {
            queryClient.setQueryData<FactoryState>(['factory', FACTORY_NAME], committedState)
            setScheduleOpen(false)
            setEventNotice(`Schedule v${committedState.schedule_version} committed with ${Object.keys(committedState.jobs).length} jobs`)
          }}
        />
      )}
      {investigationEvent && (
        <DecisionDialog
          event={investigationEvent}
          result={investigationMutation.data}
          loading={investigationMutation.isPending}
          error={investigationMutation.error ?? undefined}
          onClose={() => setInvestigationEvent(null)}
          onReplan={() => {
            setInvestigationEvent(null)
            setScheduleOpen(true)
          }}
        />
      )}
    </Grid>
  )
}

function StatusLight({ status }: { status: MachineStatus }) {
  return (
    <span className={`status status-${status}`}>
      <i aria-hidden="true" />
      {status}
    </span>
  )
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <Box className="stat">
      <Text className="eyebrow">{label}</Text>
      <Text className="stat-value">{value}</Text>
      <Text className="stat-note">{note}</Text>
    </Box>
  )
}

function PanelHeader({ title, meta }: { title: string; meta: string }) {
  return (
    <Flex className="panel-header">
      <Heading className="panel-title">{title}</Heading>
      <Text className="eyebrow">{meta}</Text>
    </Flex>
  )
}

export default App
