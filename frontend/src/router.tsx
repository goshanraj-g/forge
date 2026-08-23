import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import { AppShell } from './components/AppShell'
import { EvaluationsRoute } from './routes/EvaluationsRoute'
import { IncidentsRoute } from './routes/IncidentsRoute'
import { OverviewRoute } from './routes/OverviewRoute'
import { ScheduleRoute } from './routes/ScheduleRoute'

const rootRoute = createRootRoute({ component: AppShell })

const routeTree = rootRoute.addChildren([
  createRoute({ getParentRoute: () => rootRoute, path: '/', component: OverviewRoute }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/schedule',
    component: ScheduleRoute,
  }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/incidents',
    component: IncidentsRoute,
  }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: '/evaluations',
    component: EvaluationsRoute,
  }),
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
