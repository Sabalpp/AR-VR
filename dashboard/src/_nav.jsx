/**
 * Meta Care sidebar navigation (doctor-facing).
 */
import React from 'react'
import CIcon from '@coreui/icons-react'
import { cilSpeedometer, cilList, cilMedicalCross } from '@coreui/icons'
import { CNavItem, CNavTitle } from '@coreui/react'

const _nav = [
  {
    component: CNavTitle,
    name: 'Clinician',
  },
  {
    component: CNavItem,
    name: 'Overview',
    to: '/dashboard',
    icon: <CIcon icon={cilSpeedometer} customClassName="nav-icon" />,
  },
  {
    component: CNavItem,
    name: 'Patient Queue',
    to: '/queue',
    icon: <CIcon icon={cilList} customClassName="nav-icon" />,
    badge: { color: 'primary', text: 'REVIEW' },
  },
]

export default _nav
