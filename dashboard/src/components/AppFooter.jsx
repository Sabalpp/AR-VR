import React from 'react'
import { CFooter } from '@coreui/react'

const AppFooter = () => {
  return (
    <CFooter className="px-4">
      <div>
        <span className="fw-semibold" style={{ color: 'var(--mc-navy)' }}>
          Meta Care
        </span>
        <span className="ms-1 text-body-secondary">
          &copy; {new Date().getFullYear()} — Musculoskeletal screening for remote care
        </span>
      </div>
      <div className="ms-auto text-body-secondary small">
        Clinical decision support — physician review required
      </div>
    </CFooter>
  )
}

export default React.memo(AppFooter)
