/**
 * Ward-facing surfaces for the national-capability workflows (FR-NS-090..170).
 *
 * Every control here is a named human act against the real API: ranking,
 * computation and import never resolve anything on the nurse's behalf
 * (NFR-NS-030). Thresholds come from the active country pack, not from
 * literals in this file (FR-NS-101).
 */
import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, BellRing, ClipboardList, FileClock, ShieldCheck, UsersRound } from 'lucide-react'
import { request } from './api/client'
import type {
  CountryPackResponse,
  DischargeReadiness,
  EscalationFeed,
  HarmIncidentFeed,
  Patient,
  PublicationQueue,
  QualityDataset,
  StaffingDeclarationList,
  StaffingPositionResponse,
  User,
  WardBoard,
  WorkQueue,
} from './api/types'

const SENIOR_ROLES = ['nurse_in_charge', 'clinical_safety_officer']
const NURSING_ROLES = ['registered_nurse', 'nurse_in_charge']
const isSenior = (user: User) => SENIOR_ROLES.includes(user.role)
const isNursing = (user: User) => NURSING_ROLES.includes(user.role)
const when = (value: string | null | undefined) => (value ? new Date(value).toLocaleString() : 'n/a')

function Status({ kind, label }: { kind: string; label: string }) {
  return <span className={`badge ${kind}`}>{label}</span>
}

function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null
  return <div className="alert danger" role="alert"><AlertTriangle size={18} /><div>{(error as Error).message}</div></div>
}

// ---------------------------------------------------------------------------
// Country pack thresholds (FR-NS-101): the pack decides, the UI reads.
// ---------------------------------------------------------------------------
export type Thresholds = { review: number; escalate: number; critical: number; loaded: boolean }
const FALLBACK: Thresholds = { review: 3, escalate: 5, critical: 7, loaded: false }

export function useCountryPack() {
  return useQuery({ queryKey: ['country-pack'], queryFn: () => request<CountryPackResponse>('/api/country-pack') })
}

export function usePackThresholds(): Thresholds {
  const { data } = useCountryPack()
  const thresholds = data?.early_warning?.thresholds
  return thresholds ? { ...thresholds, loaded: true } : FALLBACK
}

export function scoreKind(score: number | null | undefined, thresholds: Thresholds): string {
  if (score == null) return 'info'
  if (score >= thresholds.critical) return 'danger'
  if (score >= thresholds.escalate) return 'caution'
  return 'normal'
}

function useWard() {
  const board = useQuery({ queryKey: ['ward-board'], queryFn: () => request<WardBoard>('/api/ward-board') })
  return { wardId: board.data?.ward.id ?? null, patients: board.data?.patients ?? [], error: board.error, isLoading: board.isLoading }
}

// ---------------------------------------------------------------------------
// Work queue (FR-NS-090 / 091 / 092)
// ---------------------------------------------------------------------------
const INTERRUPTION_CATEGORIES = ['clinical-emergency', 'patient-request', 'medication-round', 'staffing-reallocation', 'equipment-unavailable', 'communication']

export function WorkQueuePage({ user, privacy }: { user: User; privacy: boolean }) {
  const queryClient = useQueryClient()
  const { data, error, isLoading } = useQuery({ queryKey: ['work-queue'], queryFn: () => request<WorkQueue>('/api/ward-board/work-queue') })
  const [open, setOpen] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [category, setCategory] = useState(INTERRUPTION_CATEGORIES[0])
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ['work-queue'] }); queryClient.invalidateQueries({ queryKey: ['tasks'] }) }
  const interrupt = useMutation({
    mutationFn: (taskId: string) => request(`/api/tasks/${taskId}/interruptions`, { method: 'POST', body: JSON.stringify({ reason, reason_category: category }) }),
    onSuccess: () => { setOpen(null); setReason(''); refresh() },
  })
  const resume = useMutation({
    mutationFn: (interruptionId: string) => request(`/api/task-interruptions/${interruptionId}/resume`, { method: 'POST' }),
    onSuccess: refresh,
  })
  if (isLoading) return <div className="panel" aria-busy="true">Ranking ward work...</div>
  if (error) return <ErrorNote error={error} />
  if (!data) return null
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Ward work / {data.ward_id} / {data.jurisdiction}</div>
          <h1>Risk-ranked work queue</h1>
          <p>{data.ranking_note}</p>
        </div>
        <Status kind="info" label={`Generated ${when(data.generated_at)}`} />
      </div>
      <ErrorNote error={interrupt.error || resume.error} />
      <section className="panel" aria-label="Ranked work">
        <div className="panel-head"><h2>{data.entries.length} open items</h2><span className="sub">Weights: {Object.entries(data.ranking_weights).map(([k, v]) => typeof v === 'number' ? `${k} ${v}` : `${k} (${Object.entries(v).map(([level, weight]) => `${level} ${weight}`).join(', ')})`).join(' / ')}</span></div>
        <div className="task-list">
          {data.entries.map((entry, index) => (
            <div className={`task ${entry.overdue_minutes > 0 ? 'overdue' : ''}`} key={entry.id} data-testid={`work-queue-entry-${entry.id}`}>
              <div>
                <Status kind={entry.priority === 'stat' ? 'danger' : entry.priority === 'high' ? 'caution' : 'info'} label={`#${index + 1} rank ${entry.rank_score}`} />
                <div className="sub">{entry.priority} / due {when(entry.due_at)}</div>
              </div>
              <div>
                <strong>{entry.title}</strong>
                <div>{privacy ? `Patient ${entry.bed}` : entry.patient_name} / Bed {entry.bed} / owner {entry.assigned_to_name ?? 'unassigned'}</div>
                <div className="sub">
                  Factors: {Object.entries(entry.rank_factors).filter(([, v]) => v > 0).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}
                  {entry.overdue_minutes > 0 && ` / overdue ${Math.round(entry.overdue_minutes)} min`}
                  {entry.required_competency && ` / requires ${entry.required_competency}`}
                </div>
                {!entry.delegable && <div className="alert caution" role="status">Not delegable to you: missing competency {entry.missing_competency}</div>}
                {entry.open_interruptions.map(item => (
                  <div className="alert caution" role="status" key={item.id}>
                    <div>
                      Interrupted {when(item.interrupted_at)} ({item.reason_category}): {item.reason}
                      {isNursing(user) && <button className="btn" style={{ marginLeft: 8 }} onClick={() => resume.mutate(item.id)} disabled={resume.isPending} data-testid={`resume-${item.id}`}>Resume</button>}
                    </div>
                  </div>
                ))}
                {open === entry.id && (
                  <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); interrupt.mutate(entry.id) }} aria-label="Record interruption">
                    <div className="field"><label htmlFor={`reason-${entry.id}`}>Reason</label><input id={`reason-${entry.id}`} value={reason} onChange={event => setReason(event.target.value)} required minLength={3} /></div>
                    <div className="field"><label htmlFor={`category-${entry.id}`}>Category</label><select id={`category-${entry.id}`} value={category} onChange={event => setCategory(event.target.value)}>{INTERRUPTION_CATEGORIES.map(value => <option key={value} value={value}>{value}</option>)}</select></div>
                    <div className="field"><label>&nbsp;</label><button className="btn btn-primary" disabled={interrupt.isPending}>Save interruption</button></div>
                  </form>
                )}
              </div>
              <div className="stack-actions">
                {isNursing(user) && open !== entry.id && <button className="btn" onClick={() => setOpen(entry.id)} data-testid={`interrupt-${entry.id}`}>Record interruption</button>}
                {open === entry.id && <button className="btn" onClick={() => setOpen(null)}>Cancel</button>}
              </div>
            </div>
          ))}
          {!data.entries.length && <div className="empty">No open work on this ward.</div>}
        </div>
      </section>
    </>
  )
}

// ---------------------------------------------------------------------------
// Escalations (FR-NS-100 / 101)
// ---------------------------------------------------------------------------
const OUTCOMES = ['reviewed-no-change', 'treatment-changed', 'escalated-to-medical-team', 'transferred']

export function EscalationsPage({ user, privacy }: { user: User; privacy: boolean }) {
  const queryClient = useQueryClient()
  const { wardId, error: wardError } = useWard()
  const feed = useQuery({
    queryKey: ['escalations', wardId],
    queryFn: () => request<EscalationFeed>(`/api/wards/${wardId}/escalations`),
    enabled: Boolean(wardId),
  })
  const [open, setOpen] = useState<string | null>(null)
  const [response, setResponse] = useState('')
  const [outcome, setOutcome] = useState(OUTCOMES[0])
  const respond = useMutation({
    mutationFn: (observationId: string) => request(`/api/observations/${observationId}/escalation-response`, { method: 'POST', body: JSON.stringify({ clinical_response: response, outcome }) }),
    onSuccess: () => { setOpen(null); setResponse(''); queryClient.invalidateQueries({ queryKey: ['escalations'] }) },
  })
  if (wardError) return <ErrorNote error={wardError} />
  if (feed.isLoading || !wardId) return <div className="panel" aria-busy="true">Loading escalations...</div>
  if (feed.error) return <ErrorNote error={feed.error} />
  const data = feed.data
  if (!data) return null
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Deterioration / {data.profile_id} / {data.jurisdiction} pack {data.pack_version}</div>
          <h1>Escalation responses</h1>
          <p>Every escalation carries the pack's response interval ({Object.entries(data.response_minutes).map(([level, minutes]) => `${level} ${minutes} min`).join(', ')}) and minimum responder seniority ({Object.entries(data.responder_minimum_role).map(([level, role]) => `${level}: ${role}`).join(', ')}). Recording a response never completes the escalation task.</p>
        </div>
        <BellRing size={22} aria-hidden="true" />
      </div>
      <ErrorNote error={respond.error} />
      <section className="panel" aria-label="Escalations">
        <div className="task-list">
          {data.escalations.map(row => (
            <div className={`task ${row.overdue ? 'overdue' : ''}`} key={row.id} data-testid={`escalation-${row.id}`}>
              <div>
                <Status kind={row.answered ? 'normal' : row.overdue ? 'danger' : 'caution'} label={row.answered ? 'Answered' : row.overdue ? 'Overdue' : 'Awaiting response'} />
                <div className="sub">Score {row.score} / {row.escalation_level}</div>
              </div>
              <div>
                <strong>{privacy ? `Patient ${row.bed}` : row.patient_name} / Bed {row.bed}</strong>
                <div>Recorded {when(row.recorded_at)}; response due {when(row.response_due_at)}{row.oxygen_scale ? ` / oxygen scale ${row.oxygen_scale}` : ''}</div>
                {row.answered && <div className="sub">Responded {when(row.responded_at)} by {row.responder_id} {row.within_required_interval ? 'within' : 'outside'} the required interval</div>}
                {open === row.id && (
                  <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); respond.mutate(row.id) }} aria-label="Record clinical response">
                    <div className="field"><label htmlFor={`response-${row.id}`}>Clinical response</label><textarea id={`response-${row.id}`} value={response} onChange={event => setResponse(event.target.value)} required minLength={5} /></div>
                    <div className="field"><label htmlFor={`outcome-${row.id}`}>Outcome</label><select id={`outcome-${row.id}`} value={outcome} onChange={event => setOutcome(event.target.value)}>{OUTCOMES.map(value => <option key={value} value={value}>{value}</option>)}</select></div>
                    <div className="field"><label>&nbsp;</label><button className="btn btn-primary" disabled={respond.isPending}>Record response as {user.name}</button></div>
                  </form>
                )}
              </div>
              <div className="stack-actions">
                {!row.answered && isNursing(user) && open !== row.id && <button className="btn" onClick={() => setOpen(row.id)} data-testid={`respond-${row.id}`}>Respond</button>}
                {open === row.id && <button className="btn" onClick={() => setOpen(null)}>Cancel</button>}
              </div>
            </div>
          ))}
          {!data.escalations.length && <div className="empty">No escalations at or above the pack's escalate threshold.</div>}
        </div>
      </section>
    </>
  )
}

// ---------------------------------------------------------------------------
// Harm incidents (FR-NS-140 / 141)
// ---------------------------------------------------------------------------
const INCIDENT_TYPES = ['fall', 'pressure-injury', 'healthcare-associated-infection']
const HARM_LEVELS = ['none', 'low', 'moderate', 'severe', 'death']
const AVOIDABILITY = ['avoidable', 'unavoidable', 'not-determined']
const toIso = (local: string) => (local ? new Date(local).toISOString() : '')
const nowLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
const lines = (text: string) => text.split('\n').map(item => item.trim()).filter(Boolean)

export function IncidentsPage({ user, privacy }: { user: User; privacy: boolean }) {
  const queryClient = useQueryClient()
  const { wardId, patients, error: wardError } = useWard()
  const feed = useQuery({
    queryKey: ['harm-incidents', wardId],
    queryFn: () => request<HarmIncidentFeed>(`/api/wards/${wardId}/harm-incidents`),
    enabled: Boolean(wardId),
  })
  const [form, setForm] = useState({ patient_id: '', incident_type: INCIDENT_TYPES[0], occurred_at: nowLocal(), discovered_at: nowLocal(), harm_level: 'low', description: '', classification: '', body_site: '', present_on_admission: false })
  const [reviewing, setReviewing] = useState<string | null>(null)
  const [review, setReview] = useState({ avoidability: AVOIDABILITY[2], factors: '', actions: '', conclusion: '' })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['harm-incidents'] })
  const report = useMutation({
    mutationFn: () => request(`/api/patients/${form.patient_id || patients[0]?.id}/harm-incidents`, {
      method: 'POST',
      body: JSON.stringify({
        incident_type: form.incident_type, occurred_at: toIso(form.occurred_at), discovered_at: toIso(form.discovered_at),
        harm_level: form.harm_level, description: form.description, classification: form.classification || null,
        body_site: form.body_site || null, present_on_admission: form.present_on_admission,
      }),
    }),
    onSuccess: () => { setForm(current => ({ ...current, description: '', classification: '', body_site: '' })); refresh() },
  })
  const submitReview = useMutation({
    mutationFn: (incidentId: string) => request(`/api/harm-incidents/${incidentId}/review`, {
      method: 'POST',
      body: JSON.stringify({ avoidability: review.avoidability, contributory_factors: lines(review.factors), learning_actions: lines(review.actions), conclusion: review.conclusion }),
    }),
    onSuccess: () => { setReviewing(null); setReview({ avoidability: AVOIDABILITY[2], factors: '', actions: '', conclusion: '' }); refresh(); queryClient.invalidateQueries({ queryKey: ['work-queue'] }) },
  })
  if (wardError) return <ErrorNote error={wardError} />
  if (feed.isLoading || !wardId) return <div className="panel" aria-busy="true">Loading incidents...</div>
  if (feed.error) return <ErrorNote error={feed.error} />
  const incidents = feed.data?.incidents ?? []
  return (
    <>
      <div className="page-head">
        <div><div className="eyebrow">Harm / {wardId}</div><h1>Incidents and review</h1><p>Falls, pressure injuries and healthcare-associated infections, with external reportability decided by the country pack and review by someone other than the reporter.</p></div>
        <AlertTriangle size={22} aria-hidden="true" />
      </div>
      <div className="grid grid-2">
        {isNursing(user) && (
          <form className="panel" onSubmit={(event: FormEvent) => { event.preventDefault(); report.mutate() }} aria-label="Report harm incident">
            <h2>Report an incident</h2>
            <ErrorNote error={report.error} />
            <div className="field"><label htmlFor="inc-patient">Patient</label><select id="inc-patient" value={form.patient_id || patients[0]?.id || ''} onChange={event => setForm({ ...form, patient_id: event.target.value })}>{patients.map(patient => <option key={patient.id} value={patient.id}>{privacy ? `Patient ${patient.bed}` : patient.name} / Bed {patient.bed}</option>)}</select></div>
            <div className="form-grid">
              <div className="field"><label htmlFor="inc-type">Type</label><select id="inc-type" value={form.incident_type} onChange={event => setForm({ ...form, incident_type: event.target.value })}>{INCIDENT_TYPES.map(value => <option key={value} value={value}>{value}</option>)}</select></div>
              <div className="field"><label htmlFor="inc-harm">Harm level</label><select id="inc-harm" value={form.harm_level} onChange={event => setForm({ ...form, harm_level: event.target.value })}>{HARM_LEVELS.map(value => <option key={value} value={value}>{value}</option>)}</select></div>
              <div className="field"><label htmlFor="inc-class">Classification</label><input id="inc-class" value={form.classification} onChange={event => setForm({ ...form, classification: event.target.value })} placeholder="e.g. category 2" /></div>
              <div className="field"><label htmlFor="inc-occurred">Occurred</label><input id="inc-occurred" type="datetime-local" value={form.occurred_at} onChange={event => setForm({ ...form, occurred_at: event.target.value })} required /></div>
              <div className="field"><label htmlFor="inc-discovered">Discovered</label><input id="inc-discovered" type="datetime-local" value={form.discovered_at} onChange={event => setForm({ ...form, discovered_at: event.target.value })} required /></div>
              <div className="field"><label htmlFor="inc-site">Body site</label><input id="inc-site" value={form.body_site} onChange={event => setForm({ ...form, body_site: event.target.value })} /></div>
            </div>
            <div className="field"><label htmlFor="inc-desc">Description</label><textarea id="inc-desc" value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} required minLength={5} /></div>
            <label className="check-field"><input type="checkbox" checked={form.present_on_admission} onChange={event => setForm({ ...form, present_on_admission: event.target.checked })} /> Present on admission (excluded from this ward's acquired harm)</label>
            <button className="btn btn-primary" disabled={report.isPending} data-testid="report-incident">Report as {user.name}</button>
          </form>
        )}
        <section className="panel" aria-label="Incident list">
          <h2>{incidents.length} incident{incidents.length === 1 ? '' : 's'}</h2>
          <ErrorNote error={submitReview.error} />
          <div className="task-list">
            {incidents.map(incident => (
              <div className="task" key={incident.id} data-testid={`incident-${incident.id}`}>
                <div>
                  <Status kind={incident.harm_level === 'none' || incident.harm_level === 'low' ? 'info' : incident.harm_level === 'moderate' ? 'caution' : 'danger'} label={`${incident.incident_type} / ${incident.harm_level}`} />
                  <div className="sub">{incident.review_id ? `Reviewed ${when(incident.reviewed_at)}: ${incident.avoidability}` : incident.status}</div>
                </div>
                <div>
                  <strong>{privacy ? `Patient ${incident.bed}` : incident.patient_name} / Bed {incident.bed}</strong>
                  <div>{incident.description}</div>
                  <div className="sub">Occurred {when(incident.occurred_at)}; reported by {incident.reported_by_name}; {incident.externally_reportable ? 'externally reportable (queued, not claimed delivered)' : 'not externally reportable'}{incident.present_on_admission ? '; present on admission' : ''}</div>
                  {reviewing === incident.id && (
                    <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); submitReview.mutate(incident.id) }} aria-label="Review incident">
                      <div className="field"><label htmlFor={`avoid-${incident.id}`}>Avoidability</label><select id={`avoid-${incident.id}`} value={review.avoidability} onChange={event => setReview({ ...review, avoidability: event.target.value })}>{AVOIDABILITY.map(value => <option key={value} value={value}>{value}</option>)}</select></div>
                      <div className="field"><label htmlFor={`factors-${incident.id}`}>Contributory factors (one per line)</label><textarea id={`factors-${incident.id}`} value={review.factors} onChange={event => setReview({ ...review, factors: event.target.value })} required /></div>
                      <div className="field"><label htmlFor={`actions-${incident.id}`}>Learning actions (one per line)</label><textarea id={`actions-${incident.id}`} value={review.actions} onChange={event => setReview({ ...review, actions: event.target.value })} required /></div>
                      <div className="field"><label htmlFor={`conclusion-${incident.id}`}>Conclusion</label><textarea id={`conclusion-${incident.id}`} value={review.conclusion} onChange={event => setReview({ ...review, conclusion: event.target.value })} required minLength={5} /></div>
                      <div className="field"><label>&nbsp;</label><button className="btn btn-primary" disabled={submitReview.isPending}>Record review as {user.name}</button></div>
                    </form>
                  )}
                </div>
                <div className="stack-actions">
                  {!incident.review_id && isSenior(user) && incident.reported_by !== user.id && reviewing !== incident.id && <button className="btn" onClick={() => setReviewing(incident.id)} data-testid={`review-${incident.id}`}>Review</button>}
                  {reviewing === incident.id && <button className="btn" onClick={() => setReviewing(null)}>Cancel</button>}
                </div>
              </div>
            ))}
            {!incidents.length && <div className="empty">No incidents recorded on this ward.</div>}
          </div>
        </section>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Staffing position and governed declaration (FR-NS-130 / 131 / 132, NFR-NS-028)
// ---------------------------------------------------------------------------
export function StaffingPage({ user }: { user: User }) {
  const queryClient = useQueryClient()
  const { wardId, error: wardError } = useWard()
  const position = useQuery({ queryKey: ['staffing-position', wardId], queryFn: () => request<StaffingPositionResponse>(`/api/wards/${wardId}/staffing-position`), enabled: Boolean(wardId) })
  const declarations = useQuery({ queryKey: ['staffing-declarations', wardId], queryFn: () => request<StaffingDeclarationList>(`/api/wards/${wardId}/staffing-declarations`), enabled: Boolean(wardId) && isSenior(user) })
  const [reason, setReason] = useState('')
  const [windowMinutes, setWindowMinutes] = useState(240)
  const [revokeReason, setRevokeReason] = useState('')
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ['staffing-position'] }); queryClient.invalidateQueries({ queryKey: ['staffing-declarations'] }) }
  const refreshRoster = useMutation({ mutationFn: () => request(`/api/wards/${wardId}/staffing-roster/refresh`, { method: 'POST' }), onSuccess: refresh })
  const declare = useMutation({
    mutationFn: () => request(`/api/wards/${wardId}/staffing-declarations`, { method: 'POST', body: JSON.stringify({ reason, window_minutes: windowMinutes }) }),
    onSuccess: () => { setReason(''); refresh() },
  })
  const revoke = useMutation({
    mutationFn: (declarationId: string) => request(`/api/staffing-declarations/${declarationId}/revoke`, { method: 'POST', body: JSON.stringify({ reason: revokeReason }) }),
    onSuccess: () => { setRevokeReason(''); refresh() },
  })
  if (wardError) return <ErrorNote error={wardError} />
  if (position.isLoading || !wardId) return <div className="panel" aria-busy="true">Computing staffing position...</div>
  if (position.error) return <ErrorNote error={position.error} />
  const pos = position.data?.position
  if (!pos) return null
  const metric = (label: string, value: string | number | null | undefined) => (
    <div className="metric" key={label}><div className="metric-label">{label}</div><div className="metric-value compact-value">{value ?? 'absent'}</div></div>
  )
  return (
    <>
      <div className="page-head">
        <div><div className="eyebrow">Staffing / {pos.ward_id} / {pos.shift_date} {pos.shift}</div><h1>Ward staffing position</h1><p>Repo-owned occupancy and acuity against the {pos.jurisdiction} pack's norm ({pos.framework_id}). Roster state: {pos.roster_state} ({pos.roster_source}). Nursing Station consumes a roster; it never authors one.</p></div>
        <Status kind={pos.policy_status === 'insufficient-policy' ? 'caution' : pos.roster_state === 'absent' ? 'caution' : 'normal'} label={pos.policy_status} />
      </div>
      <ErrorNote error={refreshRoster.error || declare.error || revoke.error} />
      <div className="grid grid-3">
        {metric('Occupied beds', pos.occupied_beds)}
        {metric('High acuity', pos.high_acuity_patients)}
        {metric('Required RN hours', pos.required_nursing_hours)}
        {metric('Required RNs', pos.required_registered_nurses)}
        {metric('Actual RN headcount', pos.actual_registered_headcount)}
        {metric('Patients per RN', pos.patients_per_registered_nurse)}
      </div>
      {isSenior(user) && (
        <section className="panel governance-panel" aria-label="Roster">
          <div className="panel-head"><h2>Roster consumption</h2><button className="btn" onClick={() => refreshRoster.mutate()} disabled={refreshRoster.isPending} data-testid="refresh-roster">Refresh roster through hub</button></div>
          <p className="sub">{position.data?.roster_contract.connector}/{position.data?.roster_contract.resource_type}: {position.data?.roster_contract.note}</p>
        </section>
      )}
      {isSenior(user) && (
        <div className="grid grid-2" style={{ marginTop: 14 }}>
          {user.role === 'nurse_in_charge' && (
            <form className="panel" onSubmit={(event: FormEvent) => { event.preventDefault(); declare.mutate() }} aria-label="Declare staffing shortage">
              <h2>Declare a staffing shortage</h2>
              <p className="sub">A named human act by the nurse in charge. The declaration carries exactly BulletTrain's governed field set and asserts no tier, severity or approval of its own; it is queued, never reported as delivered.</p>
              <div className="field"><label htmlFor="decl-reason">Reason</label><textarea id="decl-reason" value={reason} onChange={event => setReason(event.target.value)} required minLength={10} /></div>
              <div className="field field-narrow"><label htmlFor="decl-window">Window (minutes)</label><input id="decl-window" type="number" min={15} max={1440} value={windowMinutes} onChange={event => setWindowMinutes(Number(event.target.value))} /></div>
              <button className="btn btn-primary" disabled={declare.isPending} data-testid="declare-shortage">Declare as {user.name}</button>
            </form>
          )}
          <section className="panel" aria-label="Declarations">
            <h2>Declarations</h2>
            {declarations.error && <ErrorNote error={declarations.error} />}
            <div className="task-list">
              {(declarations.data?.declarations ?? []).map(row => (
                <div className="task" key={row.id} data-testid={`declaration-${row.declaration_id}`}>
                  <div><Status kind={row.active ? 'danger' : row.revoked ? 'info' : 'normal'} label={row.active ? 'Active' : row.revoked ? 'Revoked' : 'Expired'} /></div>
                  <div><strong>{row.reason}</strong><div className="sub">{row.declaration_id} / {row.scope_unit} / declared by {row.declared_by} / {when(row.starts_at)} to {when(row.expires_at)}{row.revoked ? ` / revoked by ${row.revoked_by} at ${when(row.revoked_at)}` : ''}</div></div>
                  <div className="stack-actions">
                    {row.active && user.role === 'nurse_in_charge' && (
                      <form onSubmit={(event: FormEvent) => { event.preventDefault(); revoke.mutate(row.declaration_id) }} className="field">
                        <label htmlFor={`revoke-${row.id}`}>Revocation reason</label>
                        <input id={`revoke-${row.id}`} value={revokeReason} onChange={event => setRevokeReason(event.target.value)} required minLength={5} />
                        <button className="btn" disabled={revoke.isPending} data-testid={`revoke-${row.declaration_id}`}>Revoke</button>
                      </form>
                    )}
                  </div>
                </div>
              ))}
              {!declarations.data?.declarations.length && <div className="empty">No declarations for this ward.</div>}
            </div>
          </section>
        </div>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Nursing quality dataset (FR-NS-160 / 161)
// ---------------------------------------------------------------------------
export function QualityPage() {
  const { wardId, error: wardError } = useWard()
  const [days, setDays] = useState(7)
  const dataset = useQuery({ queryKey: ['quality-measures', wardId, days], queryFn: () => request<QualityDataset>(`/api/wards/${wardId}/quality-measures?days=${days}`), enabled: Boolean(wardId) })
  if (wardError) return <ErrorNote error={wardError} />
  if (dataset.isLoading || !wardId) return <div className="panel" aria-busy="true">Computing quality measures...</div>
  if (dataset.error) return <ErrorNote error={dataset.error} />
  const data = dataset.data
  if (!data) return null
  const kind = (status: string) => (status === 'computed' ? 'normal' : status === 'no-denominator' ? 'info' : 'caution')
  return (
    <>
      <div className="page-head">
        <div><div className="eyebrow">Quality / {data.ward_id} / {data.jurisdiction} pack {data.pack_version}</div><h1>Nursing quality dataset</h1><p>Definitions are {data.definitions_source} data. An unavailable source is shown as unavailable, a zero as zero, and an absent denominator as no denominator.</p></div>
        <div className="field field-narrow"><label htmlFor="quality-days">Period (days)</label><select id="quality-days" value={days} onChange={event => setDays(Number(event.target.value))}>{[1, 7, 30, 90].map(value => <option key={value} value={value}>{value}</option>)}</select></div>
      </div>
      <p className="sub">{when(data.period_start)} to {when(data.period_end)}. {data.unavailable.length ? `Unavailable: ${data.unavailable.join(', ')}` : 'All sources available.'}</p>
      <div className="table-scroll">
        <table className="table" aria-label="Quality measures">
          <thead><tr><th>Measure</th><th>Type</th><th>Value</th><th>Numerator / denominator</th><th>State</th><th>Source</th></tr></thead>
          <tbody>
            {data.measures.map(measure => (
              <tr key={measure.measure_id} data-testid={`measure-${measure.measure_id}`}>
                <td><strong>{measure.title}</strong><div className="sub">{measure.measure_id}</div></td>
                <td>{measure.measure_type}</td>
                <td className="num">{measure.value == null ? 'n/a' : `${measure.value} ${measure.unit ?? ''}`}</td>
                <td className="num">{measure.numerator ?? 'n/a'} / {measure.denominator ?? 'n/a'}</td>
                <td><Status kind={kind(measure.status)} label={measure.status} /></td>
                <td className="sub">{measure.source_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Country pack and adoption (FR-NS-170 / NFR-NS-027) and the publication queue (NFR-NS-029)
// ---------------------------------------------------------------------------
export function CountryPackPanel({ user }: { user: User }) {
  const queryClient = useQueryClient()
  const pack = useCountryPack()
  const [decision, setDecision] = useState<'adopted' | 'rejected'>('adopted')
  const [scope, setScope] = useState('')
  const [note, setNote] = useState('')
  const adopt = useMutation({
    mutationFn: () => request('/api/country-pack/adoptions', { method: 'POST', body: JSON.stringify({ jurisdiction: pack.data?.active.jurisdiction, pack_version: pack.data?.active.pack_version, decision, scope, note }) }),
    onSuccess: () => { setScope(''); setNote(''); queryClient.invalidateQueries({ queryKey: ['country-pack'] }) },
  })
  if (pack.error) return <ErrorNote error={pack.error} />
  const active = pack.data?.active
  if (!active) return <div className="panel" aria-busy="true">Loading country pack...</div>
  const adoption = pack.data?.local_adoption
  return (
    <section className="panel governance-panel" aria-labelledby="country-pack-heading">
      <div className="panel-head"><h2 id="country-pack-heading">Country pack</h2><Status kind={pack.data?.locally_adopted ? 'normal' : 'caution'} label={pack.data?.locally_adopted ? 'Locally adopted' : `Candidate (${active.adoption_status})`} /></div>
      <p>{active.jurisdiction_name} ({active.jurisdiction}) pack {active.pack_version}, effective {active.effective_from}. Early-warning profile {active.early_warning_profile_id}; staffing framework {active.safe_staffing_framework_id}; thresholds review {pack.data?.early_warning.thresholds.review} / escalate {pack.data?.early_warning.thresholds.escalate} / critical {pack.data?.early_warning.thresholds.critical}. {active.adoption_note}</p>
      {adoption ? <p className="sub">Decision: {adoption.decision} for scope "{adoption.scope}" by {adoption.adopted_by} at {when(adoption.adopted_at)} (pack {adoption.pack_version}).</p> : <p className="sub">No organisational decision is recorded for this exact pack version; nothing in it is treated as locally adopted clinical policy.</p>}
      <div className="table-scroll">
        <table className="table" aria-label="Pack sources">
          <thead><tr><th>Source</th><th>Publisher</th><th>Effective from</th></tr></thead>
          <tbody>{active.sources.map(source => <tr key={source.source_id}><td>{source.title}</td><td>{source.publisher}</td><td className="num">{source.effective_from}</td></tr>)}</tbody>
        </table>
      </div>
      {user.role === 'clinical_safety_officer' && !adoption && (
        <form onSubmit={(event: FormEvent) => { event.preventDefault(); adopt.mutate() }} aria-label="Record adoption decision" style={{ marginTop: 14 }}>
          <h3>Record an adoption decision for pack {active.pack_version}</h3>
          <ErrorNote error={adopt.error} />
          <div className="form-grid">
            <div className="field"><label htmlFor="adopt-decision">Decision</label><select id="adopt-decision" value={decision} onChange={event => setDecision(event.target.value as 'adopted' | 'rejected')}><option value="adopted">adopted</option><option value="rejected">rejected</option></select></div>
            <div className="field"><label htmlFor="adopt-scope">Scope</label><input id="adopt-scope" value={scope} onChange={event => setScope(event.target.value)} required minLength={3} placeholder="e.g. synthetic clinical simulation on ward MED-A" /></div>
            <div className="field"><label htmlFor="adopt-note">Note</label><input id="adopt-note" value={note} onChange={event => setNote(event.target.value)} required minLength={3} /></div>
          </div>
          <button className="btn btn-primary" disabled={adopt.isPending} data-testid="record-adoption">Record decision as {user.name}</button>
        </form>
      )}
    </section>
  )
}

export function PublicationsPanel({ user }: { user: User }) {
  const queue = useQuery({ queryKey: ['publications'], queryFn: () => request<PublicationQueue>('/api/publications'), enabled: isSenior(user) })
  if (!isSenior(user)) return null
  if (queue.error) return <ErrorNote error={queue.error} />
  const data = queue.data
  if (!data) return <div className="panel" aria-busy="true">Loading publication queue...</div>
  return (
    <section className="panel governance-panel" aria-labelledby="publications-heading">
      <div className="panel-head"><h2 id="publications-heading">Outbound national publications</h2><FileClock size={18} aria-hidden="true" /></div>
      <p className="sub">Durable, idempotent by correlation identifier, written before any transport. A publication stays pending until a receipt arrives; a missing BulletTrain route is a named gap, never a delivery.</p>
      <div className="table-scroll">
        <table className="table" aria-label="Publication contracts">
          <thead><tr><th>Kind</th><th>Destination</th><th>Route</th><th>Gap</th></tr></thead>
          <tbody>{data.contracts.map(contract => <tr key={contract.kind}><td>{contract.kind}</td><td className="num">{contract.connector}/{contract.resource_type} ({contract.operation})</td><td><Status kind={contract.route_status === 'registered' ? 'normal' : 'caution'} label={contract.route_status} /></td><td className="sub">{contract.gap ?? ''}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="task-list" style={{ marginTop: 12 }}>
        {data.publications.map(row => (
          <div className="task" key={row.id} data-testid={`publication-${row.id}`}>
            <div><Status kind={row.status === 'delivered' ? 'normal' : row.status === 'failed' ? 'danger' : 'caution'} label={row.status} /></div>
            <div><strong>{row.kind}</strong><div className="sub">{row.connector}/{row.resource_type} {row.operation} / correlation {row.correlation_id} / attempts {row.attempts} / {when(row.created_at)}{row.error_code ? ` / ${row.error_code}: ${row.error_detail}` : ''}</div></div>
            <ShieldCheck size={16} aria-hidden="true" />
          </div>
        ))}
        {!data.publications.length && <div className="empty">Nothing queued.</div>}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Discharge readiness (FR-NS-150 / 151)
// ---------------------------------------------------------------------------
export function DischargeTab({ patient, user }: { patient: Patient; user: User }) {
  const queryClient = useQueryClient()
  const readiness = useQuery({
    queryKey: ['discharge-readiness', patient.id],
    queryFn: () => request<DischargeReadiness>(`/api/patients/${patient.id}/discharge-readiness`),
    retry: false,
  })
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [coordination, setCoordination] = useState<DischargeReadiness['coordination'] | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['discharge-readiness', patient.id] })
  const open = useMutation({ mutationFn: () => request(`/api/patients/${patient.id}/discharge-readiness`, { method: 'POST', body: JSON.stringify({}) }), onSuccess: refresh })
  const confirm = useMutation({
    mutationFn: (criterionId: string) => request(`/api/discharge-readiness/${readiness.data?.id}/criteria/${criterionId}/confirm`, { method: 'POST', body: JSON.stringify({ note: notes[criterionId] ?? '' }) }),
    onSuccess: refresh,
  })
  const coordinate = useMutation({
    mutationFn: () => request<{ readiness: DischargeReadiness; results: NonNullable<DischargeReadiness['coordination']> }>(`/api/discharge-readiness/${readiness.data?.id}/coordinate`, { method: 'POST' }),
    onSuccess: result => { setCoordination(result.results); refresh() },
  })
  const complete = useMutation({ mutationFn: () => request(`/api/discharge-readiness/${readiness.data?.id}/complete`, { method: 'POST' }), onSuccess: refresh })
  const notOpened = readiness.error && (readiness.error as Error).message.includes('No discharge readiness')
  if (readiness.isLoading) return <div className="panel" aria-busy="true">Loading discharge readiness...</div>
  if (notOpened) {
    return (
      <section className="panel">
        <h2>Discharge readiness</h2>
        <p>No readiness record is open for this patient. Opening one loads the active jurisdiction's criteria set with each criterion's owner, evidence source and mandatory status.</p>
        <ErrorNote error={open.error} />
        {isNursing(user) && <button className="btn btn-primary" onClick={() => open.mutate()} disabled={open.isPending} data-testid="open-discharge">Open discharge readiness</button>}
      </section>
    )
  }
  if (readiness.error) return <ErrorNote error={readiness.error} />
  const data = readiness.data
  if (!data) return null
  const shown = coordination ?? data.coordination ?? null
  return (
    <div className="grid grid-2">
      <section className="panel" aria-label="Discharge criteria">
        <div className="panel-head"><h2>Criteria ({data.jurisdiction} pack {data.pack_version})</h2><Status kind={data.status === 'completed' ? 'normal' : data.ready_for_discharge ? 'normal' : 'caution'} label={data.status === 'completed' ? 'Completed' : data.ready_for_discharge ? 'Ready' : `${data.outstanding_mandatory.length} mandatory outstanding`} /></div>
        <ErrorNote error={confirm.error || coordinate.error || complete.error} />
        <div className="task-list">
          {data.criteria.map(criterion => {
            const local = criterion.evidence_source === 'nursing-station'
            return (
              <div className="task" key={criterion.criterion_id} data-testid={`criterion-${criterion.criterion_id}`}>
                <div><Status kind={criterion.status === 'met' ? 'normal' : criterion.mandatory ? 'caution' : 'info'} label={criterion.status} /><div className="sub">{criterion.mandatory ? 'mandatory' : 'optional'}</div></div>
                <div>
                  <strong>{criterion.title}</strong>
                  <div className="sub">Owner {criterion.owner_role}; evidence from {criterion.evidence_source}{criterion.evidence_reference ? `; ${criterion.evidence_reference}` : ''}{criterion.confirmed_by ? `; confirmed by ${criterion.confirmed_by} at ${when(criterion.confirmed_at)}` : ''}</div>
                  {criterion.status !== 'met' && local && isNursing(user) && data.status !== 'completed' && (
                    <form className="field" onSubmit={(event: FormEvent) => { event.preventDefault(); confirm.mutate(criterion.criterion_id) }}>
                      <label htmlFor={`note-${criterion.criterion_id}`}>Confirmation note</label>
                      <input id={`note-${criterion.criterion_id}`} value={notes[criterion.criterion_id] ?? ''} onChange={event => setNotes({ ...notes, [criterion.criterion_id]: event.target.value })} required minLength={3} />
                      <button className="btn" disabled={confirm.isPending} data-testid={`confirm-${criterion.criterion_id}`}>Confirm as {user.name}</button>
                    </form>
                  )}
                  {criterion.status !== 'met' && !local && <div className="sub">Met only from {criterion.evidence_source}'s own receipt through the hub.</div>}
                </div>
                <ClipboardList size={16} aria-hidden="true" />
              </div>
            )
          })}
        </div>
        {data.status !== 'completed' && isNursing(user) && (
          <div className="stack-actions" style={{ marginTop: 12 }}>
            <button className="btn" onClick={() => coordinate.mutate()} disabled={coordinate.isPending} data-testid="coordinate-discharge">Coordinate through hub</button>
            <button className="btn btn-primary" onClick={() => complete.mutate()} disabled={complete.isPending || !data.ready_for_discharge} data-testid="complete-discharge">Complete discharge readiness</button>
          </div>
        )}
      </section>
      <section className="panel" aria-label="Coordination results">
        <h2>Hub coordination</h2>
        <p className="sub">Each criterion owned by another system is met only from that system's receipt. A dispatch, an empty response or a missing route leaves it pending with a typed reason.</p>
        <div className="task-list">
          {(shown ?? []).map(result => (
            <div className="task" key={result.criterion_id}>
              <div><Status kind={result.status === 'met' ? 'normal' : 'caution'} label={result.status} /></div>
              <div><strong>{result.criterion_id}</strong><div className="sub">{result.error_code ? `${result.error_code}: ${result.message}` : result.evidence_reference ?? ''} / correlation {result.correlation_id}</div></div>
              <UsersRound size={16} aria-hidden="true" />
            </div>
          ))}
          {!shown?.length && <div className="empty">No coordination attempted yet.</div>}
        </div>
      </section>
    </div>
  )
}
