import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from '@tanstack/react-router'
import './index.css'
import { Providers } from './providers.tsx'
import { router } from './router.tsx'
import { WorkspaceProvider } from './workspace.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <WorkspaceProvider>
        <RouterProvider router={router} />
      </WorkspaceProvider>
    </Providers>
  </StrictMode>,
)
