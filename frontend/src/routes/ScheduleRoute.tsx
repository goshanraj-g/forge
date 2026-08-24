import { Box, Grid, Text } from '@chakra-ui/react'

import { PageTitle, PanelHeader, Stat } from '../components/primitives'
import { ScheduleTimeline } from '../components/ScheduleTimeline'
import { unitsLeft } from '../lib/orders'
import { useWorkspace } from '../workspace-context'

export function ScheduleRoute() {
  const { state, machines, openOrders, notice, openSchedule } = useWorkspace()

  const jobs = Object.values(state.jobs)
  const scheduledOrders = new Set(jobs.map((job) => job.order_id))
  // Committed jobs outlive the orders they belong to, so counting order ids
  // straight off `jobs` would include completed work and read as 12/7.
  const unscheduled = openOrders.filter((order) => !scheduledOrders.has(order.id))
  const covered = openOrders.length - unscheduled.length
  const lastEnd = jobs.reduce((latest, job) => Math.max(latest, job.end_hour), 0)

  return (
    <>
      <PageTitle
        title="Schedule"
        sub="See when each line will run and which open orders still need a slot."
      />

      <Grid className="stat-strip">
        <Stat
          label="Current plan"
          value={`v${state.schedule_version}`}
          note={`${jobs.length} jobs planned`}
        />
        <Stat
          label="Orders in plan"
          value={`${covered}/${openOrders.length}`}
          note={unscheduled.length ? `${unscheduled.length} uncovered` : 'All open orders'}
        />
        <Stat
          label="Plan ends at"
          value={jobs.length ? `H${lastEnd.toFixed(1)}` : '—'}
          note={`Current time: H${state.sim_hour.toFixed(2)}`}
        />
        <Stat
          label="Changeover"
          value={`${state.changeover_hours.toFixed(1)}h`}
          note={`${state.overtime_hours.toFixed(1)}h overtime`}
        />
      </Grid>

      {notice && <Text className="event-notice">{notice}</Text>}

      <ScheduleTimeline state={state} machines={machines} onOptimize={openSchedule} />

      <section className="data-panel">
        <PanelHeader
          title="Uncovered orders"
          meta={unscheduled.length ? `${unscheduled.length} open` : 'none'}
        />
        {unscheduled.length === 0 ? (
          <Box className="empty-panel">
            Every open order has production time in schedule v{state.schedule_version}.
          </Box>
        ) : (
          <>
            <Box className="table-header order-columns">
              <Text>Order</Text>
              <Text>Units left</Text>
              <Text>Due at hour</Text>
            </Box>
            {unscheduled
              .toSorted((a, b) => a.due_hour - b.due_hour)
              .map((order) => (
                <Grid className="table-row order-columns" key={order.id}>
                  <Box>
                    <Text className="primary-cell">{order.id}</Text>
                    <Text className="sub-cell">
                      {order.product_id} · P{order.priority}
                    </Text>
                  </Box>
                  <Text className="num-cell">{unitsLeft(order)}</Text>
                  <Text className="num-cell">H{order.due_hour}</Text>
                </Grid>
              ))}
          </>
        )}
      </section>
    </>
  )
}
