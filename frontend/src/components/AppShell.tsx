import { Box, Button, Flex, Grid, Text } from '@chakra-ui/react'
import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import {
  CalendarRange,
  CircleGauge,
  Factory,
  FlaskConical,
  Play,
  RefreshCw,
  RotateCcw,
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
  const { state, refetch, refreshing, advance, advancing, reset, resetting } =
    useWorkspace()

  const confirmReset = () => {
    if (window.confirm('Reset the simulation to its initial state?')) {
      reset()
    }
  }

  return (
    <Grid className="app-layout">
      <Flex as="aside" className="sidebar">
        <Flex className="wordmark">
          <Box className="logo-mark">F</Box>
          <Text>ForgeOps</Text>
        </Flex>

        <Box as="nav" className="nav-list" aria-label="Main navigation">
          {navigation.map(({ label, icon: Icon, to }) => (
            <Link
              className={`nav-item${pathname === to ? ' active' : ''}`}
              key={label}
              to={to}
              aria-current={pathname === to ? 'page' : undefined}
            >
              <Icon size={16} strokeWidth={1.8} />
              <Text>{label}</Text>
            </Link>
          ))}
        </Box>

        <Box className="sidebar-footer">
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
          <Flex className="factory-context">
            <Factory size={16} />
            <Box>
              <Text className="eyebrow">Factory</Text>
              <Text className="factory-name">{FACTORY_NAME.replace('_', ' ')}</Text>
            </Box>
          </Flex>
          <Flex className="header-actions">
            <Flex className="header-clock">
              <Text className="eyebrow">Simulation hour</Text>
              <Text className="header-clock-value">H{state.sim_hour.toFixed(2)}</Text>
            </Flex>
            <Button
              className="advance-button header-advance"
              size="sm"
              loading={advancing}
              disabled={resetting}
              onClick={advance}
            >
              <Play size={12} fill="currentColor" /> Advance 15 min
            </Button>
            <Button
              className="header-icon-button"
              variant="ghost"
              size="sm"
              loading={resetting}
              disabled={advancing}
              onClick={confirmReset}
              aria-label="Reset simulation"
              title="Reset simulation"
            >
              <RotateCcw size={14} />
              <span className="header-secondary-label">Reset</span>
            </Button>
            <Button
              className="header-icon-button"
              variant="ghost"
              size="sm"
              aria-label="Refresh factory data"
              title="Refresh factory data"
              loading={refreshing}
              disabled={advancing || resetting}
              onClick={refetch}
            >
              <RefreshCw size={15} />
              <span className="header-secondary-label">Refresh</span>
            </Button>
          </Flex>
        </Flex>

        <Box as="nav" className="mobile-nav" aria-label="Main navigation">
          {navigation.map(({ label, icon: Icon, to }) => (
            <Link
              className={`mobile-nav-item${pathname === to ? ' active' : ''}`}
              key={label}
              to={to}
              aria-current={pathname === to ? 'page' : undefined}
            >
              <Icon size={16} strokeWidth={1.8} />
              <Text>{label}</Text>
            </Link>
          ))}
        </Box>

        <Box as="main" className="page-content">
          <Outlet />
        </Box>
      </Box>
    </Grid>
  )
}
