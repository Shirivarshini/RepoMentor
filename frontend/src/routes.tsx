import { createBrowserRouter } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import LandingPage from './pages/LandingPage'
import NotFoundPage from './pages/NotFoundPage'
import RepositoryPage from './pages/RepositoryPage'

/** Repository routes (overview, architecture, ...) are added with the dashboard in Phase 8. */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: 'repositories/:repositoryId/:section?', element: <RepositoryPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
