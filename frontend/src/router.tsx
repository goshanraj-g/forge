import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'

import App from './App'

const rootRoute = createRootRoute({ component: Outlet })
const paths = ['/', '/schedule', '/incidents', '/evaluations'] as const
const routeTree = rootRoute.addChildren(
  paths.map((path) =>
    createRoute({
      getParentRoute: () => rootRoute,
      path,
      component: App,
    }),
  ),
)

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
