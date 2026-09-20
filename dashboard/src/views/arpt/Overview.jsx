/**
 * Meta Care · Clinician Overview.
 * Doctor-first: leads with what needs review, then screening analytics.
 */
import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CRow,
  CCol,
  CWidgetStatsA,
  CCard,
  CCardBody,
  CCardHeader,
  CProgress,
  CListGroup,
  CListGroupItem,
  CBadge,
  CSpinner,
  CButton,
  CAlert,
} from '@coreui/react'
import { getOverview, getQueue, urgencyColor } from '../../api/arpt'

const Overview = () => {
  const navigate = useNavigate()
  const [o, setO] = useState(null)
  const [queue, setQueue] = useState([])
  const [error, setError] = useState(null)

  const load = () => {
    setError(null)
    Promise.all([getOverview(), getQueue()])
      .then(([ov, q]) => {
        setO(ov)
        setQueue(q)
      })
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [])

  if (error) {
    return (
      <CAlert color="danger" className="d-flex justify-content-between align-items-center">
        <span>Couldn’t load the dashboard: {error}</span>
        <CButton size="sm" color="danger" variant="outline" onClick={load}>
          Retry
        </CButton>
      </CAlert>
    )
  }

  if (!o) return <CSpinner color="primary" />

  const regions = Object.entries(o.by_region || {})
  const ailments = Object.entries(o.top_ailments || {})
  const maxR = Math.max(1, ...regions.map((x) => x[1]))
  const maxA = Math.max(1, ...ailments.map((x) => x[1]))
  const pending = queue.filter((r) => r.status === 'pending')

  return (
    <>
      {/* Greeting */}
      <div className="mb-4">
        <h3 className="mb-1" style={{ color: 'var(--mc-navy)' }}>
          Good day, Doctor
        </h3>
        <p className="text-body-secondary mb-0">
          {o.pending > 0
            ? `${o.pending} home-screening ${o.pending === 1 ? 'report' : 'reports'} awaiting your review`
            : 'All home-screening reports have been reviewed'}
          {o.urgent_pending > 0 && (
            <span className="text-danger fw-semibold"> · {o.urgent_pending} marked urgent</span>
          )}
          .
        </p>
      </div>

      {/* Key numbers */}
      <CRow className="mb-2">
        <CCol sm={6} lg={3}>
          <CWidgetStatsA
            color="primary"
            className="mb-4"
            value={String(o.total ?? 0)}
            title="Patients screened"
          />
        </CCol>
        <CCol sm={6} lg={3}>
          <CWidgetStatsA
            color="warning"
            className="mb-4"
            value={String(o.pending ?? 0)}
            title="Awaiting review"
          />
        </CCol>
        <CCol sm={6} lg={3}>
          <CWidgetStatsA
            color="danger"
            className="mb-4"
            value={String(o.urgent_pending ?? 0)}
            title="Urgent · pending"
          />
        </CCol>
        <CCol sm={6} lg={3}>
          <CWidgetStatsA
            color="success"
            className="mb-4"
            value={o.ai_agreement_pct != null ? `${o.ai_agreement_pct}%` : '—'}
            title="You agreed with AI"
          />
        </CCol>
      </CRow>

      {/* Needs your review — the doctor's primary action */}
      <CCard className="mb-4">
        <CCardHeader className="d-flex justify-content-between align-items-center">
          <span>Needs your review</span>
          <CButton size="sm" color="primary" variant="ghost" onClick={() => navigate('/queue')}>
            Open full queue →
          </CButton>
        </CCardHeader>
        <CCardBody className="p-0">
          <CListGroup flush>
            {pending.slice(0, 6).map((r) => (
              <CListGroupItem
                key={r.report_id}
                component="button"
                onClick={() => navigate(`/patient/${r.report_id}`)}
                className="d-flex justify-content-between align-items-center py-3"
              >
                <span className="d-flex align-items-center gap-2">
                  <CBadge color={urgencyColor(r.urgency)} className="text-uppercase">
                    {r.urgency}
                  </CBadge>
                  <span className="fw-semibold">{r.patient_id}</span>
                  <span className="text-body-secondary small">· {r.test_name}</span>
                </span>
                <span className="text-body-secondary">
                  {r.top_ailment || '—'}
                  {r.top_confidence != null && (
                    <span className="ms-2 fw-semibold" style={{ color: 'var(--mc-blue)' }}>
                      {Math.round(r.top_confidence * 100)}%
                    </span>
                  )}
                </span>
              </CListGroupItem>
            ))}
            {pending.length === 0 && (
              <CListGroupItem className="text-body-secondary py-3">
                Nothing waiting — all reports reviewed. 🎉
              </CListGroupItem>
            )}
          </CListGroup>
        </CCardBody>
      </CCard>

      {/* Analytics */}
      <CRow>
        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>Affected regions</CCardHeader>
            <CCardBody>
              {regions.length === 0 && <span className="text-body-secondary">No data yet.</span>}
              {regions.map(([k, v]) => (
                <div className="mb-3" key={k}>
                  <div className="d-flex justify-content-between">
                    <span className="text-capitalize">{k}</span>
                    <span>{v}</span>
                  </div>
                  <CProgress thin value={(v / maxR) * 100} />
                </div>
              ))}
            </CCardBody>
          </CCard>
        </CCol>
        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>Most common findings</CCardHeader>
            <CCardBody>
              {ailments.length === 0 && <span className="text-body-secondary">No data yet.</span>}
              {ailments.map(([k, v]) => (
                <div className="mb-3" key={k}>
                  <div className="d-flex justify-content-between">
                    <span>{k}</span>
                    <span>{v}</span>
                  </div>
                  <CProgress thin value={(v / maxA) * 100} />
                </div>
              ))}
            </CCardBody>
          </CCard>
        </CCol>

        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>Urgency mix</CCardHeader>
            <CCardBody>
              <CRow className="text-center">
                {['urgent', 'soon', 'routine'].map((u) => (
                  <CCol key={u}>
                    <div className={`fs-3 fw-bold text-${urgencyColor(u)}`}>
                      {o.by_urgency?.[u] || 0}
                    </div>
                    <div className="text-body-secondary text-uppercase small">{u}</div>
                  </CCol>
                ))}
              </CRow>
            </CCardBody>
          </CCard>
        </CCol>
        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>Review status</CCardHeader>
            <CCardBody>
              <CRow className="text-center">
                <CCol>
                  <div className="fs-3 fw-bold text-success">{o.by_status?.confirmed || 0}</div>
                  <div className="text-body-secondary text-uppercase small">Confirmed</div>
                </CCol>
                <CCol>
                  <div className="fs-3 fw-bold text-danger">{o.by_status?.revised || 0}</div>
                  <div className="text-body-secondary text-uppercase small">Revised</div>
                </CCol>
                <CCol>
                  <div className="fs-3 fw-bold text-warning">{o.by_status?.pending || 0}</div>
                  <div className="text-body-secondary text-uppercase small">Pending</div>
                </CCol>
              </CRow>
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>
    </>
  )
}

export default Overview
