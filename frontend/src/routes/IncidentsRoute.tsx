import { Box, Grid, Text } from '@chakra-ui/react'

import { ActivityLog } from '../components/ActivityLog'
import { PageTitle, PanelHeader, Stat, StatusLight } from '../components/primitives'
import { useWorkspace } from '../workspace-context'

export function IncidentsRoute() {
  const {
    state,
    machines,
    unavailable,
    events,
    notice,
    openIncident,
    openSchedule,
    investigate,
    decisions,
  } = useWorkspace()

  const recovering = unavailable.filter(
    (machine) =>
      machine.down_until_hour !== null && machine.down_until_hour > state.sim_hour,
  )
  const nextRecovery = recovering.reduce(
    (earliest, machine) => Math.min(earliest, machine.down_until_hour ?? Infinity),
    Infinity,
  )

  return (
    <>
      <PageTitle
        title="Incidents"
        sub="Track line outages, recovery times, and the AI agent's recommended response."
      />

      <Grid className="stat-strip">
        <Stat
          label="Lines down"
          value={String(unavailable.length)}
          note={`of ${machines.length} production lines`}
        />
        <Stat
          label="Next line returns"
          value={Number.isFinite(nextRecovery) ? `H${nextRecovery.toFixed(1)}` : '—'}
          note={
            recovering.length
              ? `${recovering.length} recovering`
              : 'Nothing scheduled to return'
          }
        />
        <Stat
          label="Simulation events"
          value={String(events.length)}
          note={`sim hour ${state.sim_hour.toFixed(2)}`}
        />
        <Stat
          label="Cost from late orders"
          value={`$${state.late_penalty_cost.toLocaleString()}`}
          note="recorded so far"
        />
      </Grid>

      {notice && <Text className="event-notice">{notice}</Text>}

      <section className="data-panel">
        <PanelHeader
          title="Lines needing attention"
          meta={unavailable.length ? `${unavailable.length} affected` : 'all healthy'}
        />
        {unavailable.length === 0 ? (
          <Box className="empty-panel">
            Every production line is available. Add a test failure below to see how the
            AI agent responds.
          </Box>
        ) : (
          <>
            <Box className="table-header machine-columns">
              <Text>Machine</Text>
              <Text>Throughput</Text>
              <Text>Returns at hour</Text>
              <Text>Status</Text>
            </Box>
            {unavailable.map((machine) => (
              <Grid className="table-row machine-columns" key={machine.id}>
                <Box>
                  <Text className="primary-cell">{machine.name}</Text>
                  <Text className="sub-cell">{machine.id}</Text>
                </Box>
                <Text className="num-cell">{machine.capacity_per_hour}/hr</Text>
                <Text className="num-cell">
                  {machine.down_until_hour === null
                    ? '—'
                    : `H${machine.down_until_hour.toFixed(1)}`}
                </Text>
                <StatusLight status={machine.status} />
              </Grid>
            ))}
          </>
        )}
      </section>

      <ActivityLog
        events={events}
        investigatedIds={new Set(Object.keys(decisions))}
        onInjectFailure={openIncident}
        onOptimize={openSchedule}
        onInvestigate={investigate}
      />
    </>
  )
}
