import { Box, Button, Flex, Grid, Text } from '@chakra-ui/react'
import { Link, Outlet, useRouterState } from '@tanstack/react-router'
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

import { FACTORY_NAME, useWorkspace } from '../workspace-context'

const navigation = [
  { label: 'Overview', icon: CircleGauge, to: '/' },
  { label: 'Schedule', icon: CalendarRange, to: '/schedule' },
  { label: 'Incidents', icon: TriangleAlert, to: '/incidents' },
  { label: 'Evaluations', icon: FlaskConical, to: '/evaluations' },
] as const

export function AppShell() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const { state, refetch, advance, advancing } = useWorkspace()

  return (
    <Grid className="app-layout">
      <Flex as="aside" className="sidebar">
        <Flex className="wordmark">
          <Box className="logo-mark">F</Box>
          <Text>ForgeOps</Text>
        </Flex>

        <Box as="nav" className="nav-list">
          {navigation.map(({ label, icon: Icon, to }) => (
            <Link
              className={`nav-item${pathname === to ? ' active' : ''}`}
              key={label}
              to={to}
            >
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
            <Factory size={15} /> {FACTORY_NAME} <ChevronDown size={14} />
          </Button>
          <Flex align="center" gap="3">
            <Flex className="header-clock">
              <Text className="eyebrow">Sim hour</Text>
              <Text className="header-clock-value">{state.sim_hour.toFixed(2)}</Text>
            </Flex>
            <Button
              className="advance-button header-advance"
              size="sm"
              loading={advancing}
              onClick={advance}
            >
              <Play size={12} fill="currentColor" /> Advance 15 min
            </Button>
            <Flex className="connection-state">
              <span /> Live
            </Flex>
            <Button
              variant="ghost"
              size="sm"
              aria-label="Refresh factory state"
              onClick={refetch}
            >
              <RefreshCw size={15} />
            </Button>
          </Flex>
        </Flex>

        <Box as="main" className="page-content">
          <Outlet />
        </Box>
      </Box>
    </Grid>
  )
}
