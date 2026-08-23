import { Badge, Box, Button, Flex, Grid, Heading, Spinner, Text } from '@chakra-ui/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock3, Factory, Play, RefreshCw, TriangleAlert } from 'lucide-react'

import { getFactory, tickFactory } from './lib/api'
import type { FactoryState, MachineStatus } from './types/factory'

const FACTORY_NAME = 'factory_01'

const statusPalette: Record<MachineStatus, string> = {
  running: 'green',
  idle: 'gray',
  down: 'red',
  maintenance: 'orange',
}

function metric(label: string, value: string, detail: string) {
  return (
    <Box className="metric-card">
      <Text className="eyebrow">{label}</Text>
      <Text className="metric-value">{value}</Text>
      <Text className="metric-detail">{detail}</Text>
    </Box>
  )
}

function App() {
  const queryClient = useQueryClient()
  const factoryQuery = useQuery({
    queryKey: ['factory', FACTORY_NAME],
    queryFn: () => getFactory(FACTORY_NAME),
  })
  const tickMutation = useMutation({
    mutationFn: (stepHours: number) => tickFactory(FACTORY_NAME, stepHours),
    onSuccess: ({ state }) => {
      queryClient.setQueryData<FactoryState>(['factory', FACTORY_NAME], state)
    },
  })

  if (factoryQuery.isPending) {
    return (
      <Flex className="center-state">
        <Spinner size="lg" />
        <Text>Loading factory state…</Text>
      </Flex>
    )
  }

  if (factoryQuery.isError) {
    return (
      <Flex className="center-state error-state">
        <TriangleAlert size={28} />
        <Heading size="md">Factory unavailable</Heading>
        <Text>{factoryQuery.error.message}</Text>
        <Button onClick={() => factoryQuery.refetch()}>Try again</Button>
      </Flex>
    )
  }

  const state = factoryQuery.data
  const machines = Object.values(state.machines)
  const orders = Object.values(state.orders)
  const openOrders = orders.filter(
    (order) => order.status === 'pending' || order.status === 'in_progress',
  )
  const unavailableMachines = machines.filter(
    (machine) => machine.status === 'down' || machine.status === 'maintenance',
  )
  const totalCost = state.production_cost + state.late_penalty_cost

  return (
    <Box className="app-shell">
      <Flex as="header" className="topbar">
        <Flex align="center" gap="3">
          <Box className="brand-mark"><Factory size={20} /></Box>
          <Box>
            <Text className="brand-name">ForgeOps</Text>
            <Text className="brand-subtitle">Factory control</Text>
          </Box>
        </Flex>
        <Badge colorPalette="green" variant="subtle">Simulator online</Badge>
      </Flex>

      <Box as="main" className="page">
        <Flex className="page-heading">
          <Box>
            <Text className="eyebrow">{state.name.replace('_', ' ')}</Text>
            <Heading size="2xl">Operations overview</Heading>
            <Text className="page-description">
              Current production state, order pressure, and machine availability.
            </Text>
          </Box>

          <Flex className="clock-control">
            <Box>
              <Flex align="center" gap="2" className="clock-label">
                <Clock3 size={15} /> Simulation time
              </Flex>
              <Text className="clock-value">Hour {state.sim_hour.toFixed(2)}</Text>
            </Box>
            <Button
              colorPalette="green"
              loading={tickMutation.isPending}
              onClick={() => tickMutation.mutate(0.25)}
            >
              <Play size={15} /> Advance 15 min
            </Button>
            <Button
              variant="outline"
              aria-label="Refresh factory state"
              onClick={() => factoryQuery.refetch()}
            >
              <RefreshCw size={16} />
            </Button>
          </Flex>
        </Flex>

        {tickMutation.isError && (
          <Box className="inline-error">{tickMutation.error.message}</Box>
        )}

        <Grid className="metrics-grid">
          {metric('Open orders', String(openOrders.length), `${orders.length} total`)}
          {metric(
            'Machines available',
            `${machines.length - unavailableMachines.length}/${machines.length}`,
            unavailableMachines.length
              ? `${unavailableMachines.length} need attention`
              : 'All lines available',
          )}
          {metric(
            'Schedule version',
            `v${state.schedule_version}`,
            `${Object.keys(state.jobs).length} planned jobs`,
          )}
          {metric(
            'Recorded cost',
            `$${totalCost.toLocaleString()}`,
            `${state.overtime_hours.toFixed(1)} overtime hours`,
          )}
        </Grid>

        <Grid className="content-grid">
          <Box className="panel">
            <Flex className="panel-heading">
              <Box>
                <Text className="eyebrow">Production floor</Text>
                <Heading size="lg">Machines</Heading>
              </Box>
              <Text className="panel-count">{machines.length} lines</Text>
            </Flex>
            <Box>
              {machines.map((machine) => (
                <Flex className="machine-row" key={machine.id}>
                  <Box>
                    <Text className="row-title">{machine.name}</Text>
                    <Text className="row-detail">
                      {machine.capacity_per_hour} units/hour ·{' '}
                      {machine.supported_products.length} products
                    </Text>
                  </Box>
                  <Badge colorPalette={statusPalette[machine.status]} variant="subtle">
                    {machine.status}
                  </Badge>
                </Flex>
              ))}
            </Box>
          </Box>

          <Box className="panel">
            <Flex className="panel-heading">
              <Box>
                <Text className="eyebrow">Demand</Text>
                <Heading size="lg">Priority orders</Heading>
              </Box>
              <Text className="panel-count">{openOrders.length} open</Text>
            </Flex>
            <Box>
              {openOrders
                .toSorted((a, b) => a.priority - b.priority || a.due_hour - b.due_hour)
                .slice(0, 6)
                .map((order) => (
                  <Flex className="order-row" key={order.id}>
                    <Box>
                      <Text className="row-title">{order.id}</Text>
                      <Text className="row-detail">
                        {order.product_id} · {order.quantity - order.produced} units left
                      </Text>
                    </Box>
                    <Box textAlign="right">
                      <Text className="due-hour">Due {order.due_hour}h</Text>
                      <Text className="priority">Priority {order.priority}</Text>
                    </Box>
                  </Flex>
                ))}
            </Box>
          </Box>
        </Grid>
      </Box>
    </Box>
  )
}

export default App
