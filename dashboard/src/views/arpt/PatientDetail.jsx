/**
 * ARPT Patient Report — full review page for one screening session.
 */
import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  CRow,
  CCol,
  CCard,
  CCardHeader,
  CCardBody,
  CBadge,
  CProgress,
  CProgressBar,
  CTable,
  CTableBody,
  CTableRow,
  CTableDataCell,
  CListGroup,
  CListGroupItem,
  CForm,
  CFormInput,
  CFormTextarea,
  CFormSelect,
  CFormLabel,
  CButton,
  CSpinner,
  CAlert,
} from '@coreui/react'
import {
  getReport,
  submitReview,
  videoUrl,
  riskColor,
  urgencyColor,
  statusColor,
} from '../../api/arpt'

const pct = (x) => (x != null ? Math.round(x * 100) : 0)

const PatientDetail = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const [r, setR] = useState(null)
  const [form, setForm] = useState({
    confirmed_diagnosis: '',
    notes: '',
    reviewed_by: '',
    status: 'confirmed',
  })
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    setError(null)
    return getReport(id)
      .then((data) => {
        setR(data)
        const rev = data.physician_review || {}
        setForm({
          confirmed_diagnosis: rev.confirmed_diagnosis || '',
          notes: rev.notes || '',
          reviewed_by: rev.reviewed_by || '',
          status: rev.status && rev.status !== 'pending' ? rev.status : 'confirmed',
        })
      })
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (error) {
    return (
      <CAlert color="danger" className="d-flex justify-content-between align-items-center">
        <span>Couldn’t load this report: {error}</span>
        <CButton size="sm" color="danger" variant="outline" onClick={load}>
          Retry
        </CButton>
      </CAlert>
    )
  }

  if (!r) return <CSpinner color="primary" />

  const g = r.diagnosis?.gemini || {}
  const ail = g.ailments || []
  const sym = r.objective_metrics?.symmetry || {}
  const rom = r.objective_metrics?.range_of_motion || {}
  const mq = r.motion_quality || {}
  const states = mq.state_distribution || {}
  const rev = r.physician_review || {}
  const mlMap = {}
  ;(r.diagnosis?.ml_model || []).forEach((m) => (mlMap[m.condition_id] = m.confidence))

  const save = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await submitReview(id, { ...form, reviewed_by: form.reviewed_by || 'Dr.' })
      setSaved(true)
      await load()
      setTimeout(() => setSaved(false), 2500)
    } catch (err) {
      setError(`Could not save verification: ${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  const metricRow = (label, value, color) => (
    <CTableRow>
      <CTableDataCell>{label}</CTableDataCell>
      <CTableDataCell className="text-end fw-semibold">
        {color ? <span className={`text-${color}`}>{value}</span> : value}
      </CTableDataCell>
    </CTableRow>
  )

  return (
    <>
      <CButton color="link" className="px-0 mb-2" onClick={() => navigate('/queue')}>
        ← Back to queue
      </CButton>

      <div className="d-flex justify-content-between align-items-start mb-4 flex-wrap gap-2">
        <div>
          <h3 className="mb-1">{r.meta.patient_id}</h3>
          <div className="text-body-secondary">
            Report {r.report_id} · {r.meta.test_name} · {r.meta.frame_count} frames ·{' '}
            {r.meta.duration_s}s
          </div>
        </div>
        <CBadge color={urgencyColor(g.urgency)} className="fs-6 px-3 py-2 text-uppercase">
          {g.urgency || 'routine'}
        </CBadge>
      </div>

      {saved && <CAlert color="success">Verification saved.</CAlert>}

      <CRow>
        <CCol xs={12}>
          <CCard className="mb-4">
            <CCardHeader>Patient complaint</CCardHeader>
            <CCardBody>
              <blockquote className="blockquote fs-6 fst-italic border-start border-3 ps-3 mb-2">
                “{r.patient_report.pain_description}”
              </blockquote>
              <div className="d-flex flex-wrap gap-2">
                {(r.patient_report.triage?.suspected_conditions || []).map((c) => (
                  <CBadge color="secondary" key={c}>
                    {c}
                  </CBadge>
                ))}
              </div>
            </CCardBody>
          </CCard>
        </CCol>

        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>
              AI screening suggestion
              <span className="text-body-secondary fw-normal small ms-2">· for your review</span>
            </CCardHeader>
            <CCardBody>
              {ail.length === 0 && (
                <span className="text-body-secondary">No AI suggestion attached.</span>
              )}
              {ail.map((a, i) => (
                <div className="mb-3" key={i}>
                  <div className="d-flex justify-content-between mb-1">
                    <span className="fw-semibold">
                      {a.name}
                      {mlMap[a.condition_id] != null && (
                        <CBadge color="info" className="ms-2">
                          ML {pct(mlMap[a.condition_id])}%
                        </CBadge>
                      )}
                    </span>
                    <span className="fw-bold">{pct(a.confidence)}%</span>
                  </div>
                  <CProgress height={8}>
                    <CProgressBar value={pct(a.confidence)} />
                  </CProgress>
                  <div className="text-body-secondary small mt-1">
                    {a.affected_side} · {a.severity} — {a.reasoning}
                  </div>
                </div>
              ))}
            </CCardBody>
          </CCard>
        </CCol>

        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>Objective metrics</CCardHeader>
            <CCardBody>
              <CTable small borderless className="mb-0">
                <CTableBody>
                  {metricRow(
                    'Knee asymmetry',
                    `${sym.knee?.asymmetry_pct ?? '—'}%`,
                    riskColor(sym.knee?.asymmetry_pct),
                  )}
                  {metricRow(
                    'Hip asymmetry',
                    `${sym.hip?.asymmetry_pct ?? '—'}%`,
                    riskColor(sym.hip?.asymmetry_pct),
                  )}
                  {metricRow(
                    'Ankle asymmetry',
                    `${sym.ankle?.asymmetry_pct ?? '—'}%`,
                    riskColor(sym.ankle?.asymmetry_pct),
                  )}
                  {metricRow('Left knee ROM', `${rom.left_knee?.range?.toFixed(1) ?? '—'}°`)}
                  {metricRow('Right knee ROM', `${rom.right_knee?.range?.toFixed(1) ?? '—'}°`)}
                  {metricRow(
                    'Pelvic tilt (mean)',
                    `${r.objective_metrics?.pelvic_tilt_mean_mm ?? '—'} mm`,
                  )}
                </CTableBody>
              </CTable>
            </CCardBody>
          </CCard>
        </CCol>

        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>Movement replay</CCardHeader>
            <CCardBody>
              <video
                controls
                style={{ width: '100%', borderRadius: 8, background: '#000' }}
                src={videoUrl(id)}
                onError={(e) => {
                  e.target.outerHTML =
                    '<div class="text-body-secondary">No replay video attached.</div>'
                }}
              />
            </CCardBody>
          </CCard>
        </CCol>

        <CCol md={6}>
          <CCard className="mb-4">
            <CCardHeader>
              Motion quality — {mq.test_id || ''}{' '}
              <CBadge color={mq.accepted ? 'success' : 'warning'}>
                {mq.accepted ? 'accepted' : 'redo flagged'}
              </CBadge>
            </CCardHeader>
            <CCardBody>
              <CRow className="text-center mb-2">
                <CCol>
                  <div className="fs-4 fw-bold text-danger">{states.red ?? 0}%</div>
                  <div className="text-body-secondary small text-uppercase">Not moving</div>
                </CCol>
                <CCol>
                  <div className="fs-4 fw-bold text-warning">{states.yellow ?? 0}%</div>
                  <div className="text-body-secondary small text-uppercase">In motion</div>
                </CCol>
                <CCol>
                  <div className="fs-4 fw-bold text-success">{states.green ?? 0}%</div>
                  <div className="text-body-secondary small text-uppercase">Target</div>
                </CCol>
              </CRow>
              {(mq.violations || []).length > 0 && (
                <div className="text-warning small">Form cues: {mq.violations.join('; ')}</div>
              )}
            </CCardBody>
          </CCard>
        </CCol>

        <CCol xs={12}>
          <CCard className="mb-4">
            <CCardHeader>Key findings</CCardHeader>
            <CCardBody>
              <CListGroup flush className="mb-3">
                {(g.key_findings || []).map((f, i) => (
                  <CListGroupItem key={i}>{f}</CListGroupItem>
                ))}
                {(g.key_findings || []).length === 0 && (
                  <CListGroupItem className="text-body-secondary">—</CListGroupItem>
                )}
              </CListGroup>
              <div>
                <strong>Recommended follow-up:</strong>{' '}
                <span className="text-body-secondary">{g.recommended_followup || '—'}</span>
              </div>
            </CCardBody>
          </CCard>
        </CCol>

        <CCol xs={12}>
          <CCard className="mb-4">
            <CCardHeader>
              Physician verification{' '}
              {rev.status && rev.status !== 'pending' && (
                <CBadge color={statusColor(rev.status)}>{rev.status}</CBadge>
              )}
            </CCardHeader>
            <CCardBody>
              <CForm onSubmit={save}>
                <CFormLabel>Confirmed diagnosis</CFormLabel>
                <CFormInput
                  className="mb-3"
                  value={form.confirmed_diagnosis}
                  placeholder="e.g. Left meniscal tear, confirmed on exam"
                  onChange={(e) => setForm({ ...form, confirmed_diagnosis: e.target.value })}
                />
                <CFormLabel>Clinical notes</CFormLabel>
                <CFormTextarea
                  className="mb-3"
                  rows={3}
                  value={form.notes}
                  placeholder="Exam findings, plan, referrals..."
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
                <CRow>
                  <CCol md={6}>
                    <CFormLabel>Reviewing physician</CFormLabel>
                    <CFormInput
                      className="mb-3"
                      value={form.reviewed_by}
                      placeholder="Dr. Name"
                      onChange={(e) => setForm({ ...form, reviewed_by: e.target.value })}
                    />
                  </CCol>
                  <CCol md={6}>
                    <CFormLabel>Decision</CFormLabel>
                    <CFormSelect
                      className="mb-3"
                      value={form.status}
                      onChange={(e) => setForm({ ...form, status: e.target.value })}
                    >
                      <option value="confirmed">Confirm AI diagnosis</option>
                      <option value="revised">Revise diagnosis</option>
                    </CFormSelect>
                  </CCol>
                </CRow>
                <CButton type="submit" color="primary" disabled={submitting}>
                  {submitting ? 'Saving…' : 'Submit verification'}
                </CButton>
              </CForm>
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>
    </>
  )
}

export default PatientDetail
