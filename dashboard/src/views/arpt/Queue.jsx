/**
 * ARPT Triage Queue — urgency-sorted worklist of patient reports.
 */
import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CCard,
  CCardHeader,
  CCardBody,
  CTable,
  CTableHead,
  CTableBody,
  CTableRow,
  CTableHeaderCell,
  CTableDataCell,
  CBadge,
  CSpinner,
  CButton,
  CAlert,
} from '@coreui/react'
import { getQueue, urgencyColor, statusColor } from '../../api/arpt'

const Queue = () => {
  const navigate = useNavigate()
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  const load = () => {
    setError(null)
    getQueue()
      .then(setRows)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [])

  if (error) {
    return (
      <CAlert color="danger" className="d-flex justify-content-between align-items-center">
        <span>Couldn’t load the queue: {error}</span>
        <CButton size="sm" color="danger" variant="outline" onClick={load}>
          Retry
        </CButton>
      </CAlert>
    )
  }

  if (!rows) return <CSpinner color="primary" />

  return (
    <CCard className="mb-4">
      <CCardHeader className="d-flex justify-content-between align-items-center">
        <strong>Triage Queue</strong>
        <span className="text-body-secondary small">
          {rows.filter((r) => r.status === 'pending').length} pending · {rows.length} total
        </span>
      </CCardHeader>
      <CCardBody>
        <CTable hover align="middle" responsive>
          <CTableHead>
            <CTableRow>
              <CTableHeaderCell>Urgency</CTableHeaderCell>
              <CTableHeaderCell>Patient</CTableHeaderCell>
              <CTableHeaderCell>Test</CTableHeaderCell>
              <CTableHeaderCell>Top finding</CTableHeaderCell>
              <CTableHeaderCell>Confidence</CTableHeaderCell>
              <CTableHeaderCell>Status</CTableHeaderCell>
              <CTableHeaderCell>Date</CTableHeaderCell>
              <CTableHeaderCell></CTableHeaderCell>
            </CTableRow>
          </CTableHead>
          <CTableBody>
            {rows.map((r) => (
              <CTableRow
                key={r.report_id}
                role="button"
                onClick={() => navigate(`/patient/${r.report_id}`)}
              >
                <CTableDataCell>
                  <CBadge color={urgencyColor(r.urgency)}>{r.urgency}</CBadge>
                </CTableDataCell>
                <CTableDataCell className="fw-semibold">{r.patient_id}</CTableDataCell>
                <CTableDataCell className="text-body-secondary">{r.test_name}</CTableDataCell>
                <CTableDataCell>{r.top_ailment || '—'}</CTableDataCell>
                <CTableDataCell>
                  {r.top_confidence != null ? `${Math.round(r.top_confidence * 100)}%` : '—'}
                </CTableDataCell>
                <CTableDataCell>
                  <CBadge color={statusColor(r.status)}>{r.status}</CBadge>
                </CTableDataCell>
                <CTableDataCell className="text-body-secondary small">
                  {new Date(r.timestamp_utc).toLocaleDateString()}
                </CTableDataCell>
                <CTableDataCell>
                  <CButton
                    size="sm"
                    color="primary"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/patient/${r.report_id}`)
                    }}
                  >
                    Review
                  </CButton>
                </CTableDataCell>
              </CTableRow>
            ))}
            {rows.length === 0 && (
              <CTableRow>
                <CTableDataCell colSpan={8} className="text-center text-body-secondary">
                  No reports yet. Run a session to generate one.
                </CTableDataCell>
              </CTableRow>
            )}
          </CTableBody>
        </CTable>
      </CCardBody>
    </CCard>
  )
}

export default Queue
