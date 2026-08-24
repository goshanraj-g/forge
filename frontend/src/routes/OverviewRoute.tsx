import { Box, Flex, Grid, Heading, Text } from '@chakra-ui/react'

import { PageTitle, PanelHeader, Stat, StatusLight } from '../components/primitives'
import { unitsLeft } from '../lib/orders'
import { useWorkspace } from '../workspace-context'

const WINDOW_HOURS = 24
const SOON_HOURS = 4
const GRID_HOURS = [0, 6, 12, 18, 24]

export function OverviewRoute() {
  const { state, machines, orders, openOrders, unavailable, advanceError, resetError } = useWorkspace()

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
    <>
      <PageTitle
        title="Factory overview"
        sub="See line availability, open work, upcoming deadlines, and current cost."
      />

      <section className="deadline-band">
        <Flex className="band-head">
          <Box>
            <Text className="eyebrow">Order deadlines</Text>
            <Heading className="band-title">Next 24 simulated hours</Heading>
          </Box>
          <Text className="band-window">
            hour {state.sim_hour.toFixed(2)} → {(state.sim_hour + WINDOW_HOURS).toFixed(2)}
          </Text>
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
          {overdue.length > 0 && <Text className="overdue">{overdue.length} past due</Text>}
          <Text>
            {inWindow.length === 0
              ? 'Nothing due in this window'
              : `${inWindow.length} due in this window`}
            {later.length > 0 && ` · ${later.length} scheduled beyond it`}
          </Text>
        </Flex>
      </section>

      {advanceError && (
        <Box className="inline-error">
          Could not advance the clock. {advanceError.message}
        </Box>
      )}
      {resetError && (
        <Box className="inline-error">
          Could not reset the simulation. {resetError.message}
        </Box>
      )}

      <Grid className="stat-strip">
        <Stat
          label="Open orders"
          value={String(openOrders.length)}
          note={`${orders.length} total`}
        />
        <Stat
          label="Available lines"
          value={`${machines.length - unavailable.length}/${machines.length}`}
          note={
            unavailable.length
              ? `${unavailable.length} need attention`
              : 'No active incidents'
          }
        />
        <Stat
          label="Current plan"
          value={`v${state.schedule_version}`}
          note={`${Object.keys(state.jobs).length} planned jobs`}
        />
        <Stat
          label="Recorded cost"
          value={`$${totalCost.toLocaleString()}`}
          note={`${state.overtime_hours.toFixed(1)}h overtime`}
        />
      </Grid>

      <Grid className="dashboard-grid">
        <section className="data-panel machine-panel">
          <PanelHeader title="Production lines" meta={`${machines.length} machines`} />
          <Box className="table-header machine-columns">
            <Text>Machine</Text>
            <Text>Throughput</Text>
            <Text>Products supported</Text>
            <Text>Status</Text>
          </Box>
          {machines.map((machine) => (
            <Grid className="table-row machine-columns" key={machine.id}>
              <Box>
                <Text className="primary-cell">{machine.name}</Text>
                <Text className="sub-cell">{machine.id}</Text>
              </Box>
              <Text className="num-cell">{machine.capacity_per_hour}/hr</Text>
              <Text className="num-cell">{machine.supported_products.length} products</Text>
              <StatusLight status={machine.status} />
            </Grid>
          ))}
        </section>

        <section className="data-panel order-panel">
          <PanelHeader title="Order queue" meta={`${openOrders.length} open`} />
          <Box className="table-header order-columns">
            <Text>Order</Text>
            <Text>Units left</Text>
            <Text>Due at hour</Text>
          </Box>
          {openOrders
            .toSorted((a, b) => a.priority - b.priority || a.due_hour - b.due_hour)
            .slice(0, 7)
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
        </section>
      </Grid>
    </>
  )
}
