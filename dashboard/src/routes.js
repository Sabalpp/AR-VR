/**
 * ARPT application routes.
 */
import React from 'react'

const Overview = React.lazy(() => import('./views/arpt/Overview'))
const Queue = React.lazy(() => import('./views/arpt/Queue'))
const PatientDetail = React.lazy(() => import('./views/arpt/PatientDetail'))

const routes = [
  { path: '/', exact: true, name: 'Home' },
  { path: '/dashboard', name: 'Overview', element: Overview },
  { path: '/queue', name: 'Triage Queue', element: Queue },
  { path: '/patient/:id', name: 'Patient Report', element: PatientDetail },
]

export { routes }
export default routes
