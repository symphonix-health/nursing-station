import { FormEvent, KeyboardEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  BellRing,
  ClipboardCheck,
  ClipboardList,
  FileClock,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  Moon,
  Network,
  RefreshCw,
  ShieldCheck,
  Sun,
  UsersRound,
} from 'lucide-react'
import { NavLink, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { auth, request } from './api/client'
import type {
  CarePlan,
  ClinicalAlertFeed,
  HandoverRecord,
  PatientIntegrations,
  Medication,
  Nurse,
  Patient,
  SeedGovernance,
  Task,
  User,
  WardBoard,
} from './api/types'

const PATIENT_TABS = [
  'overview',
  'observations',
  'tasks',
  'care plan',
  'medications',
  'handover',
  'safety',
  'integrations',
] as const

function ThemeToggle() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') ?? 'system')

  useEffect(() => {
    const applied = theme === 'system'
      ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme
    document.documentElement.dataset.theme = applied
  }, [theme])

  function cycle() {
    const next = theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system'
    setTheme(next)
    localStorage.setItem('theme', next)
  }

  return (
    <button className="btn" onClick={cycle} aria-label={`Theme: ${theme}. Change theme`}>
      {theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
      <span className="header-meta">{theme}</span>
    </button>
  )
}

function Login() {
  const [email, setEmail] = useState('amina.okafor@nursing.test')
  const [password, setPassword] = useState('Nursing2026!')
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const data = await request<{ access_token: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      auth.set(data.access_token)
      window.location.assign('/ward')
    } catch (caught) {
      setError((caught as Error).message)
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="eyebrow">Symphonix Health / Clinical</div>
        <h1>Nursing Station</h1>
        <p>Sign in to your assigned ward. Phase 2 adds governed sibling context for linked fictional patients.</p>
        {error && <div className="alert danger" role="alert">{error}</div>}
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="username" />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" />
        </div>
        <button className="btn btn-primary" type="submit">Sign in</button>
        <p className="sub">Phase 2 / BulletTrain mediated / Governed synthetic patients</p>
      </form>
    </main>
  )
}

function ClinicalAlerts({ privacy }: { privacy: boolean }) {
  const queryClient = useQueryClient()
  const feed = useQuery({
    queryKey: ['clinical-alerts'],
    queryFn: () => request<ClinicalAlertFeed>('/api/alerts'),
    refetchInterval: query => Math.max(1, query.state.data?.refresh_seconds ?? 5) * 1000,
  })
  const acknowledge = useMutation({
    mutationFn: (alertId: string) => request(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clinical-alerts'] }),
  })
  if (feed.error) {
    return <div className="alert danger" role="alert">Live clinical alert feed unavailable: {(feed.error as Error).message}</div>
  }
  if (!feed.data?.alerts.length) return <div className="sr-only" data-testid="clinical-alert-count">0 open clinical alerts</div>
  return (
    <section className="clinical-alert-stack" aria-label="Open clinical alerts" aria-live="polite" data-testid="clinical-alert-feed">
      {feed.data.alerts.map(alert => (
        <article className="clinical-alert" key={alert.id} data-testid={`clinical-alert-${alert.event_id}`}>
          <BellRing size={21} aria-hidden="true" />
          <div>
            <strong>{alert.title}</strong>
            <div>{privacy ? `Patient ${alert.bed}` : `${alert.patient_name} / ${alert.mrn}`} / Bed {alert.bed}</div>
            <div className="sub">{alert.summary} / observed {new Date(alert.observed_at).toLocaleString()} / source {alert.source_system} / correlation {alert.correlation_id}</div>
          </div>
          <button className="btn btn-danger" onClick={() => acknowledge.mutate(alert.id)} disabled={acknowledge.isPending}>
            Acknowledge
          </button>
        </article>
      ))}
    </section>
  )
}

function Layout({ user }: { user: User }) {
  const navigate = useNavigate()
  const [privacy, setPrivacy] = useState(sessionStorage.getItem('nursing-privacy') === 'on')

  function togglePrivacy() {
    setPrivacy(current => {
      const next = !current
      sessionStorage.setItem('nursing-privacy', next ? 'on' : 'off')
      return next
    })
  }

  function logout() {
    auth.clear()
    navigate('/login')
  }

  return (
    <div className="bt-app">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <div className="bt-shell">
        <aside className="bt-sidebar" aria-label="Primary navigation">
          <div className="brand">
            <div className="brand-mark"><HeartPulse size={21} /></div>
            <div className="brand-text">
              <div className="brand-name">Nursing Station</div>
              <div className="brand-sub">SYMPHONIX HEALTH</div>
            </div>
          </div>
          <nav className="nav">
            <NavLink to="/ward"><LayoutDashboard size={18} /><span>Ward board</span></NavLink>
            <NavLink to="/tasks"><ClipboardCheck size={18} /><span>Tasks</span></NavLink>
            <NavLink to="/governance"><ShieldCheck size={18} /><span>Governance</span></NavLink>
          </nav>
          <div className="sidebar-foot">
            <div className="user-text"><strong>{user.name}</strong><br />{user.role.replaceAll('_', ' ')}</div>
          </div>
        </aside>
        <header className="bt-header">
          <div>
            <div className="header-title">Clinical operations</div>
            <div className="header-meta">Phase 2 / durable nursing record / governed sibling context</div>
          </div>
          <div className="header-actions">
            <button className="btn" aria-pressed={privacy} onClick={togglePrivacy}>
              {privacy ? 'Exit privacy mode' : 'Privacy mode'}
            </button>
            <ThemeToggle />
            <button className="btn" onClick={logout} aria-label="Sign out"><LogOut size={16} /></button>
          </div>
        </header>
        <main id="main-content" className="bt-main" tabIndex={-1}>
          {privacy && (
            <div className="alert caution privacy-active" role="status">
              <ShieldCheck size={18} />
              <div><strong>Privacy mode active</strong><div>Direct identifiers are masked across the workspace. Clinical risk remains visible.</div></div>
            </div>
          )}
          <ClinicalAlerts privacy={privacy} />
          <Routes>
            <Route path="/ward" element={<WardPage privacy={privacy} />} />
            <Route path="/patients/:patientId" element={<PatientPage user={user} privacy={privacy} />} />
            <Route path="/tasks" element={<TasksPage privacy={privacy} />} />
            <Route path="/governance" element={<GovernancePage />} />
            <Route path="*" element={<Navigate to="/ward" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

function Status({ kind, label }: { kind: string; label: string }) {
  return <span className={`badge ${kind}`}>{label}</span>
}

function useReference(name: string) {
  return useQuery({
    queryKey: ['reference', name],
    queryFn: () => request<{ name: string; values: string[] }>(`/api/reference/${name}`),
  })
}

const age = (dob: string) => Math.floor((Date.now() - new Date(dob).getTime()) / 31_557_600_000)
const initials = (name: string) => name.split(' ').map(part => part[0]).join('').slice(0, 2)
const displayName = (patient: Pick<Patient, 'name' | 'bed'>, privacy: boolean) => privacy ? `Patient ${patient.bed}` : patient.name

function WardPage({ privacy }: { privacy: boolean }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['ward-board'],
    queryFn: () => request<WardBoard>('/api/ward-board'),
  })
  if (isLoading) return <div className="panel" aria-busy="true">Loading ward board...</div>
  if (error) return <div className="alert danger" role="alert">{(error as Error).message}</div>
  if (!data) return null

  const overdue = data.patients.reduce((sum, patient) => sum + patient.overdue_tasks, 0)
  const high = data.patients.filter(patient => (patient.latest_score ?? 0) >= 5).length
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">{data.ward.code} / {data.ward.specialty}</div>
          <h1>{data.ward.name}</h1>
          <p>Facility {data.ward.facility_id}. Generated {new Date(data.generated_at).toLocaleTimeString()} from {data.source}.</p>
        </div>
        <div className="header-actions">
          <Status kind="info" label="Seeded synthetic" />
          <Status kind="normal" label="Durable source" />
        </div>
      </div>
      <div className="grid grid-3" style={{ marginBottom: 14 }}>
        <div className="metric"><div className="metric-label">Patients</div><div className="metric-value">{data.patients.length}</div></div>
        <div className="metric"><div className="metric-label">Deterioration review</div><div className="metric-value">{high}</div></div>
        <div className="metric"><div className="metric-label">Overdue tasks</div><div className="metric-value">{overdue}</div></div>
      </div>
      <div className="ward-board" role="grid" aria-label={`${data.ward.name} ward board`}>
        <div className="board-row board-head" role="row">
          <div>Bed</div><div>Patient</div><div>Reason</div><div>Score</div><div>Tasks</div><div>Safety context</div><div>Accountable nurse</div>
        </div>
        {data.patients.map(patient => (
          <NavLink
            className="board-row"
            data-testid={`patient-link-${patient.id}`}
            role="row"
            to={`/patients/${patient.id}`}
            key={patient.id}
            aria-label={privacy ? `Open patient in bed ${patient.bed}` : `Open ${patient.name}, bed ${patient.bed}`}
          >
            <div className="bed">{patient.bed}</div>
            <div>
              <div className="patient-name">{displayName(patient, privacy)}</div>
              <div className="sub">{privacy ? 'Identifiers hidden' : `${patient.mrn} / ${age(patient.date_of_birth)}y ${patient.sex}`}</div>
            </div>
            <div>{patient.admission_reason}<div className="sub">Admitted {new Date(patient.admitted_at).toLocaleDateString()}</div></div>
            <div>
              {patient.latest_score == null
                ? <Status kind="info" label="Not recorded" />
                : <Status kind={patient.latest_score >= 7 ? 'danger' : patient.latest_score >= 5 ? 'caution' : 'normal'} label={`Score ${patient.latest_score}`} />}
              <div className="sub">{patient.observation_time ? new Date(patient.observation_time).toLocaleTimeString() : 'No current set'}</div>
            </div>
            <div><span className="num">{patient.open_tasks}</span> open<div className="sub">{patient.overdue_tasks} overdue</div></div>
            <div>{patient.isolation_status !== 'None' && <Status kind="caution" label={patient.isolation_status} />}<div className="sub">{patient.flags_json.join(' / ')}</div></div>
            <div>{patient.accountable_nurse_name ?? 'Unassigned'}</div>
          </NavLink>
        ))}
      </div>
    </>
  )
}

function PatientBanner({ patient, privacy }: { patient: Patient; privacy: boolean }) {
  const allergies = patient.allergies_json.length
    ? patient.allergies_json.map(allergy => `${allergy.substance}: ${allergy.reaction} (${allergy.severity})`).join('; ')
    : 'NKA confirmed'
  return (
    <section className="patient-banner" role="region" aria-label="Patient safety banner">
      <div className="monogram" aria-label="No patient photo available">{privacy ? patient.bed : initials(patient.name)}</div>
      <div>
        <div className="banner-label">Patient / two identifiers</div>
        <div className="banner-value">{displayName(patient, privacy)}</div>
        <div className="sub">{privacy ? 'Direct identifiers hidden' : `${patient.mrn} / DOB ${patient.date_of_birth} / (no photo)`}</div>
      </div>
      <div><div className="banner-label">Allergies</div><div className={patient.allergies_json.length ? 'allergy' : 'banner-value'}>{allergies}</div></div>
      <div><div className="banner-label">Location / isolation</div><div className="banner-value">Bed {patient.bed} / {patient.isolation_status}</div></div>
      <div className="banner-code"><div className="banner-label">Code status</div><div className="banner-value">{patient.code_status}</div></div>
    </section>
  )
}

function PatientPage({ user, privacy }: { user: User; privacy: boolean }) {
  const { patientId = '' } = useParams()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<(typeof PATIENT_TABS)[number]>('overview')
  const { data, error, isLoading } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => request<Patient>(`/api/patients/${patientId}`),
  })
  if (isLoading) return <div aria-busy="true">Loading patient record...</div>
  if (error) return <div className="alert danger" role="alert">{(error as Error).message}</div>
  if (!data) return null
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['patient', patientId] })

  function tabKeyDown(event: KeyboardEvent<HTMLButtonElement>, current: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const target = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? PATIENT_TABS.length - 1
        : (current + (event.key === 'ArrowRight' ? 1 : -1) + PATIENT_TABS.length) % PATIENT_TABS.length
    setTab(PATIENT_TABS[target])
    document.getElementById(`patient-tab-${target}`)?.focus()
  }

  return (
    <>
      <PatientBanner patient={data} privacy={privacy} />
      <div className="page-head">
        <div>
          <div className="eyebrow">Nursing record / Bed {data.bed}</div>
          <h1>{data.admission_reason}</h1>
          <p>
            Accountable nurse: {data.accountable_nurse_name ?? 'unassigned'}. Source manifest: {data.seed_manifest_id}.
          </p>
        </div>
        <Status kind="info" label="Seeded synthetic" />
      </div>
      <div className="tabs" role="tablist" aria-label="Patient record sections">
        {PATIENT_TABS.map((label, index) => (
          <button
            id={`patient-tab-${index}`}
            role="tab"
            aria-selected={tab === label}
            aria-controls="patient-tab-panel"
            tabIndex={tab === label ? 0 : -1}
            className={tab === label ? 'active' : ''}
            data-testid={`patient-tab-${label.replaceAll(' ', '-')}`}
            onClick={() => setTab(label)}
            onKeyDown={event => tabKeyDown(event, index)}
            key={label}
          >
            {label[0].toUpperCase() + label.slice(1)}
          </button>
        ))}
      </div>
      <div id="patient-tab-panel" role="tabpanel" aria-labelledby={`patient-tab-${PATIENT_TABS.indexOf(tab)}`} tabIndex={0}>
        {tab === 'overview' && <Overview patient={data} />}
        {tab === 'observations' && <Observations patient={data} onSaved={refresh} />}
        {tab === 'tasks' && <PatientTasks patient={data} user={user} onSaved={refresh} />}
        {tab === 'care plan' && <CarePlans patient={data} user={user} onSaved={refresh} />}
        {tab === 'medications' && <Medications patient={data} user={user} privacy={privacy} onSaved={refresh} />}
        {tab === 'handover' && <Handover patient={data} user={user} />}
        {tab === 'safety' && <Safety patient={data} onSaved={refresh} />}
        {tab === 'integrations' && <Integrations patient={data} />}
      </div>
    </>
  )
}

function sourceSummary(source: PatientIntegrations['sources'][number]) {
  const data = source.snapshot?.data
  if (!data) return 'No successful snapshot has been recorded.'
  const collectionKeys = ['results', 'orders', 'studies', 'reports', 'medication_requests', 'dispense_events', 'requests', 'issues', 'administrations', 'reactions']
  const counts = collectionKeys
    .filter(key => Array.isArray(data[key]))
    .map(key => `${(data[key] as unknown[]).length} ${key.replaceAll('_', ' ')}`)
  const patient = data.patient as Record<string, unknown> | undefined
  if (patient?.abo_group) counts.unshift(`Blood group ${String(patient.abo_group)} ${String(patient.rhd ?? '')}`.trim())
  return counts.length ? counts.join(' / ') : 'Patient context received; no reportable items.'
}

function Integrations({ patient }: { patient: Patient }) {
  const queryClient = useQueryClient()
  const context = useQuery({
    queryKey: ['patient-integrations', patient.id],
    queryFn: () => request<PatientIntegrations>(`/api/patients/${patient.id}/integrations`),
  })
  const refresh = useMutation({
    mutationFn: () => request<{ all_succeeded: boolean }>(`/api/patients/${patient.id}/integrations/refresh`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patient-integrations', patient.id] }),
  })
  if (context.isLoading) return <div className="panel" aria-busy="true">Loading governed sibling context...</div>
  if (context.error) return <div className="alert danger" role="alert">{(context.error as Error).message}</div>
  if (!context.data) return null
  return (
    <section className="panel integration-panel">
      <div className="panel-head">
        <div><h2>Sibling clinical context</h2><p>Read-only snapshots mediated by the BulletTrain hub. Nursing observations, tasks and handovers remain owned here.</p></div>
        <button data-testid="refresh-integrations" className="btn btn-primary" disabled={!context.data.linked || refresh.isPending} onClick={() => refresh.mutate()}>
          <RefreshCw size={16} aria-hidden="true" /> {refresh.isPending ? 'Refreshing...' : 'Refresh all sources'}
        </button>
      </div>
      {!context.data.linked && <div className="alert caution"><Network size={18} /><div><strong>No governed identity link</strong><div>This patient cannot be queried across sibling systems. No fallback data is shown.</div></div></div>}
      {refresh.error && <div className="alert danger" role="alert">{(refresh.error as Error).message}</div>}
      {refresh.data && !refresh.data.all_succeeded && <div className="alert caution" role="status">One or more sources failed. Existing successful snapshots are marked with their freshness; failed sources remain explicit.</div>}
      <div className="integration-grid">
        {context.data.sources.map(source => {
          const failed = source.state === 'failed'
          const current = source.snapshot?.status === 'current' && !failed
          return (
            <article className="integration-card" key={source.source_system}>
              <div className="panel-head">
                <h3>{source.source_system.replaceAll('-', ' ')}</h3>
                <Status kind={failed ? 'danger' : current ? 'normal' : 'caution'} label={failed ? 'Unavailable' : current ? 'Current' : source.snapshot ? 'Stale' : 'Not refreshed'} />
              </div>
              <p>{sourceSummary(source)}</p>
              <dl className="provenance-list">
                <div><dt>Contract</dt><dd>{source.resource_type}</dd></div>
                <div><dt>Semantics</dt><dd>{source.semantics.join(', ')}</dd></div>
                <div><dt>Source updated</dt><dd>{source.snapshot?.source_updated_at ? new Date(source.snapshot.source_updated_at).toLocaleString() : 'Not supplied'}</dd></div>
                <div><dt>Fetched</dt><dd>{source.snapshot?.fetched_at ? new Date(source.snapshot.fetched_at).toLocaleString() : 'Never'}</dd></div>
                <div><dt>Identity check</dt><dd>{source.snapshot?.reconciliation_status ?? 'Not performed'}</dd></div>
                <div><dt>Correlation</dt><dd className="sub">{source.last_attempt?.correlation_id ?? source.snapshot?.correlation_id ?? 'None'}</dd></div>
              </dl>
              {failed && <div className="alert danger" role="status"><strong>{source.last_attempt?.error_code ?? 'Source failed'}</strong><div>{source.last_attempt?.error_detail ?? 'No further detail returned.'}</div></div>}
            </article>
          )
        })}
      </div>
    </section>
  )
}

function Overview({ patient }: { patient: Patient }) {
  const latest = patient.observations?.[0]
  const activeTasks = patient.tasks?.filter(task => ['open', 'accepted'].includes(task.status)) ?? []
  return (
    <div className="grid grid-2">
      <section className="panel">
        <div className="panel-head">
          <h2>Current state</h2>
          {latest
            ? <Status kind={latest.score >= 7 ? 'danger' : latest.score >= 5 ? 'caution' : 'normal'} label={`Score ${latest.score}`} />
            : <Status kind="info" label="No observation" />}
        </div>
        {latest ? (
          <>
            <div className="grid grid-3">
              <div className="metric"><div className="metric-label">SpO2</div><div className="metric-value">{latest.oxygen_saturation}<small>{latest.units_json.oxygen_saturation}</small></div></div>
              <div className="metric"><div className="metric-label">Blood pressure</div><div className="metric-value">{latest.systolic_bp}<small>{latest.units_json.systolic_bp}</small></div></div>
              <div className="metric"><div className="metric-label">Pulse</div><div className="metric-value">{latest.pulse}<small>{latest.units_json.pulse}</small></div></div>
            </div>
            <p className="sub">Recorded by {latest.recorded_by_name} at {new Date(latest.recorded_at).toLocaleString()} from {latest.source}. Profile {latest.warning_profile_version}.</p>
          </>
        ) : <div className="empty">No structured observation has been recorded.</div>}
      </section>
      <section className="panel">
        <div className="panel-head"><h2>Owned actions</h2><Status kind="info" label={`${activeTasks.length} active`} /></div>
        <div className="task-list">
          {activeTasks.slice(0, 4).map(task => (
            <div className={`task ${new Date(task.due_at) < new Date() ? 'overdue' : ''}`} key={task.id}>
              <Status kind={task.priority === 'stat' ? 'danger' : task.priority === 'high' ? 'caution' : 'info'} label={task.priority} />
              <div><strong>{task.title}</strong><div className="sub">Owner {task.assigned_to_name ?? 'unassigned'} / due {new Date(task.due_at).toLocaleString()} / {task.status}</div></div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function Observations({ patient, onSaved }: { patient: Patient; onSaved: () => void }) {
  const consciousness = useReference('consciousness')
  const [form, setForm] = useState({
    respiratory_rate: '18', oxygen_saturation: '97', supplemental_oxygen: false,
    systolic_bp: '124', pulse: '78', temperature: '36.8', consciousness: 'alert',
    source: 'manual bedside observation',
  })
  const [message, setMessage] = useState('')
  const mutation = useMutation({
    mutationFn: () => request<{ score: number; escalation_level: string; warning_profile: string }>(`/api/patients/${patient.id}/observations`, {
      method: 'POST',
      body: JSON.stringify({
        ...form,
        respiratory_rate: +form.respiratory_rate,
        oxygen_saturation: +form.oxygen_saturation,
        systolic_bp: +form.systolic_bp,
        pulse: +form.pulse,
        temperature: +form.temperature,
      }),
    }),
    onSuccess: result => {
      setMessage(`Observation confirmed. Warning score ${result.score}; ${result.escalation_level} response using ${result.warning_profile}.`)
      onSaved()
    },
  })
  const measures = [
    ['respiratory_rate', 'Respiratory rate /min'],
    ['oxygen_saturation', 'SpO2 %'],
    ['systolic_bp', 'Systolic BP mmHg'],
    ['pulse', 'Pulse /min'],
    ['temperature', 'Temperature Cel'],
  ] as const
  return (
    <div className="grid grid-2">
      <form className="panel" onSubmit={event => { event.preventDefault(); mutation.mutate() }}>
        <div className="panel-head"><h2>Record observations</h2><Status kind="info" label="Manual / measured" /></div>
        {mutation.error && <div className="alert danger" role="alert">{(mutation.error as Error).message}</div>}
        {message && <div className="alert normal" aria-live="polite">{message}</div>}
        <div className="form-grid">
          {measures.map(([key, label]) => (
            <div className="field" key={key}>
              <label htmlFor={key}>{label}</label>
              <input id={key} inputMode="decimal" value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })} />
            </div>
          ))}
          <div className="field">
            <label htmlFor="consciousness">Consciousness</label>
            <select id="consciousness" value={form.consciousness} onChange={event => setForm({ ...form, consciousness: event.target.value })}>
              {(consciousness.data?.values ?? []).map(value => <option value={value} key={value}>{value.replaceAll('-', ' ')}</option>)}
            </select>
          </div>
        </div>
        <label className="check-field"><input type="checkbox" checked={form.supplemental_oxygen} onChange={event => setForm({ ...form, supplemental_oxygen: event.target.checked })} /> Supplemental oxygen</label>
        <button className="btn btn-primary" disabled={mutation.isPending || consciousness.isLoading}>{mutation.isPending ? 'Saving...' : 'Confirm observation'}</button>
      </form>
      <section className="panel">
        <h2>Observation history</h2>
        <div className="table-scroll">
          <table className="table">
            <thead><tr><th>Time and author</th><th>Score</th><th>SpO2</th><th>BP</th><th>Pulse</th><th>Source</th></tr></thead>
            <tbody>{patient.observations?.map(observation => (
              <tr key={observation.id}>
                <td>{new Date(observation.recorded_at).toLocaleString()}<div className="sub">{observation.recorded_by_name}</div></td>
                <td><Status kind={observation.score >= 7 ? 'danger' : observation.score >= 5 ? 'caution' : 'normal'} label={`${observation.score}`} /><div className="sub">{observation.warning_profile_version}</div></td>
                <td>{observation.oxygen_saturation} {observation.units_json.oxygen_saturation}</td>
                <td>{observation.systolic_bp} {observation.units_json.systolic_bp}</td>
                <td>{observation.pulse} {observation.units_json.pulse}</td>
                <td>{observation.source}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function PatientTasks({ patient, user, onSaved }: { patient: Patient; user: User; onSaved: () => void }) {
  const queryClient = useQueryClient()
  const priorities = useReference('task-priorities')
  const { data: nurses = [] } = useQuery({ queryKey: ['ward-nurses', patient.ward_id], queryFn: () => request<Nurse[]>(`/api/wards/${patient.ward_id}/nurses`) })
  const [form, setForm] = useState({ title: '', description: '', priority: 'normal', due_at: '', assigned_to: user.id })
  const refresh = () => {
    onSaved()
    queryClient.invalidateQueries({ queryKey: ['tasks'] })
  }
  const create = useMutation({
    mutationFn: () => request(`/api/patients/${patient.id}/tasks`, {
      method: 'POST',
      body: JSON.stringify({ ...form, due_at: new Date(form.due_at).toISOString() }),
    }),
    onSuccess: () => {
      setForm(current => ({ ...current, title: '', description: '', due_at: '' }))
      refresh()
    },
  })
  const transition = useMutation({
    mutationFn: ({ task, action }: { task: Task; action: string }) => request(`/api/tasks/${task.id}/transition`, {
      method: 'POST',
      body: JSON.stringify({ action, version: task.version, note: action === 'complete' ? 'Care action completed and documented' : action === 'cancel' ? 'Task cancelled after nursing review' : '' }),
    }),
    onSuccess: refresh,
  })
  return (
    <div className="grid grid-2">
      <section className="panel">
        <div className="panel-head"><h2>Nursing tasks</h2><span className="sub">Server-confirmed actions with version guards.</span></div>
        {transition.error && <div className="alert danger" role="alert">{(transition.error as Error).message}</div>}
        <div className="task-list">{patient.tasks?.map(task => {
          const overdue = new Date(task.due_at).getTime() < Date.now() && !['completed', 'cancelled'].includes(task.status)
          return (
            <div className={`task ${overdue ? 'overdue' : ''}`} key={task.id}>
              <Status kind={task.priority === 'stat' ? 'danger' : task.priority === 'high' ? 'caution' : 'info'} label={task.priority} />
              <div>
                <strong>{task.title}</strong><div>{task.description}</div>
                <div className="sub">Owner {task.assigned_to_name ?? 'unassigned'} / created by {task.created_by_name} / due {new Date(task.due_at).toLocaleString()} / {task.status} / version {task.version}</div>
              </div>
              <div className="stack-actions">
                {task.status === 'open' && <button className="btn" onClick={() => transition.mutate({ task, action: 'accept' })}>Accept</button>}
                {task.status === 'open' && <button className="btn" onClick={() => transition.mutate({ task, action: 'cancel' })}>Cancel</button>}
                {task.status === 'accepted' && <button className="btn btn-primary" onClick={() => transition.mutate({ task, action: 'complete' })}>Complete</button>}
              </div>
            </div>
          )
        })}</div>
      </section>
      <form className="panel" onSubmit={event => { event.preventDefault(); create.mutate() }}>
        <h2>Create and assign task</h2>
        {create.error && <div className="alert danger" role="alert">{(create.error as Error).message}</div>}
        <div className="field"><label htmlFor="task-title">Task</label><input id="task-title" required value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} /></div>
        <div className="field"><label htmlFor="task-description">Instructions</label><textarea id="task-description" required value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} /></div>
        <div className="field"><label htmlFor="task-priority">Priority</label><select id="task-priority" value={form.priority} onChange={event => setForm({ ...form, priority: event.target.value })}>{(priorities.data?.values ?? []).map(value => <option key={value}>{value}</option>)}</select></div>
        <div className="field"><label htmlFor="task-due">Due time</label><input id="task-due" type="datetime-local" required value={form.due_at} onChange={event => setForm({ ...form, due_at: event.target.value })} /></div>
        <div className="field"><label htmlFor="task-owner">Assigned nurse</label><select id="task-owner" value={form.assigned_to} onChange={event => setForm({ ...form, assigned_to: event.target.value })}>{nurses.map(nurse => <option value={nurse.id} key={nurse.id}>{nurse.name}, {nurse.role.replaceAll('_', ' ')}</option>)}</select></div>
        <button className="btn btn-primary" disabled={create.isPending || priorities.isLoading}>Create task</button>
      </form>
    </div>
  )
}

function CarePlans({ patient, user, onSaved }: { patient: Patient; user: User; onSaved: () => void }) {
  const { data: nurses = [] } = useQuery({ queryKey: ['ward-nurses', patient.ward_id], queryFn: () => request<Nurse[]>(`/api/wards/${patient.ward_id}/nurses`) })
  const [problem, setProblem] = useState('')
  const [goal, setGoal] = useState('')
  const [intervention, setIntervention] = useState('')
  const [owner, setOwner] = useState(user.id)
  const create = useMutation({
    mutationFn: () => request(`/api/patients/${patient.id}/care-plans`, { method: 'POST', body: JSON.stringify({ problem, goal, interventions: [intervention], owner_id: owner }) }),
    onSuccess: () => { setProblem(''); setGoal(''); setIntervention(''); onSaved() },
  })
  const evaluate = useMutation({
    mutationFn: ({ plan, status }: { plan: CarePlan; status: string }) => request(`/api/care-plans/${plan.id}/evaluate`, {
      method: 'POST',
      body: JSON.stringify({ status, evaluation: status === 'achieved' ? 'Goal achieved following nursing evaluation' : 'Care plan discontinued following nursing review', version: plan.version }),
    }),
    onSuccess: onSaved,
  })
  return (
    <div className="grid grid-2">
      <section className="panel">
        <h2>Nursing care plans</h2>
        {patient.care_plans?.length ? patient.care_plans.map(plan => (
          <div className="task" key={plan.id}>
            <Status kind={plan.status === 'active' ? 'info' : 'normal'} label={plan.status} />
            <div>
              <strong>{plan.problem}</strong><div>Goal: {plan.goal}</div>
              <div className="sub">Owner {plan.owner_name} / created by {plan.created_by_name} / {plan.interventions_json.join('; ')} / version {plan.version}</div>
              {plan.evaluation && <div>Evaluation: {plan.evaluation}</div>}
            </div>
            {plan.status === 'active' && <div className="stack-actions"><button className="btn" onClick={() => evaluate.mutate({ plan, status: 'achieved' })}>Record goal achieved</button><button className="btn" onClick={() => evaluate.mutate({ plan, status: 'discontinued' })}>Discontinue</button></div>}
          </div>
        )) : <div className="empty">No care plan is recorded.</div>}
      </section>
      <form className="panel" onSubmit={event => { event.preventDefault(); create.mutate() }}>
        <h2>Add care plan problem</h2>
        {(create.error || evaluate.error) && <div className="alert danger" role="alert">{((create.error || evaluate.error) as Error).message}</div>}
        <div className="field"><label htmlFor="problem">Nursing problem</label><input id="problem" required value={problem} onChange={event => setProblem(event.target.value)} /></div>
        <div className="field"><label htmlFor="goal">Measurable goal</label><textarea id="goal" required value={goal} onChange={event => setGoal(event.target.value)} /></div>
        <div className="field"><label htmlFor="intervention">Owned intervention</label><textarea id="intervention" required value={intervention} onChange={event => setIntervention(event.target.value)} /></div>
        <div className="field"><label htmlFor="care-owner">Accountable nurse</label><select id="care-owner" value={owner} onChange={event => setOwner(event.target.value)}>{nurses.map(nurse => <option value={nurse.id} key={nurse.id}>{nurse.name}, {nurse.role.replaceAll('_', ' ')}</option>)}</select></div>
        <button className="btn btn-primary" disabled={create.isPending}>Add to care plan</button>
      </form>
    </div>
  )
}

function Medications({ patient, user, privacy, onSaved }: { patient: Patient; user: User; privacy: boolean; onSaved: () => void }) {
  const outcomes = useReference('medication-outcomes')
  const { data: nurses = [] } = useQuery({ queryKey: ['ward-nurses', patient.ward_id], queryFn: () => request<Nurse[]>(`/api/wards/${patient.ward_id}/nurses`) })
  const [selected, setSelected] = useState<Medication | null>(null)
  const [outcome, setOutcome] = useState('administered')
  const [reason, setReason] = useState('')
  const eligible = nurses.filter(nurse => nurse.id !== user.id)
  const [cosigner, setCosigner] = useState('')
  const mutation = useMutation({
    mutationFn: () => request(`/api/medication-orders/${selected!.id}/administrations`, {
      method: 'POST',
      body: JSON.stringify({ outcome, reason: reason || null, mrn_verified: patient.mrn, date_of_birth_verified: patient.date_of_birth, cosigner_id: selected!.high_alert ? (cosigner || eligible[0]?.id) : null }),
    }),
    onSuccess: () => { setSelected(null); setReason(''); onSaved() },
  })
  return (
    <div className="grid grid-2">
      <section className="panel">
        <div className="panel-head"><h2>Medication administration record</h2><Status kind="caution" label="Two identifiers required" /></div>
        {privacy && <div className="alert caution" role="alert">Exit privacy mode before beginning medication verification.</div>}
        <div className="task-list">{patient.medications?.map(medication => (
          <button className={`task ${medication.high_alert ? 'med-high' : ''}`} key={medication.id} onClick={() => setSelected(medication)} disabled={privacy}>
            <Status kind={medication.high_alert ? 'danger' : 'info'} label={medication.high_alert ? 'High alert' : 'Active'} />
            <div className="align-left"><strong>{medication.medication_name}</strong><div className="num">{medication.dose_value} {medication.dose_unit} / {medication.route}</div><div className="sub">{medication.schedule} / due {new Date(medication.due_at).toLocaleString()} / source {medication.source}</div></div>
            <ClipboardList size={18} />
          </button>
        ))}</div>
      </section>
      <section className="panel">
        {selected ? (
          <form onSubmit={event => { event.preventDefault(); mutation.mutate() }}>
            <div className="panel-head"><h2>Verify and record</h2><Status kind="normal" label="Patient matched" /></div>
            <div className="alert info"><UsersRound size={18} /><div><strong>Two identifiers verified</strong><div>{patient.mrn} / DOB {patient.date_of_birth}</div></div></div>
            <p><strong>{selected.medication_name}</strong><br /><span className="num">{selected.dose_value} {selected.dose_unit} / {selected.route}</span></p>
            {selected.high_alert === 1 && <div className="alert danger" role="alert"><ShieldCheck size={18} /><div><strong>HIGH-ALERT medication</strong><div>An independent eligible nurse must co-sign.</div></div></div>}
            {mutation.error && <div className="alert danger" role="alert">{(mutation.error as Error).message}</div>}
            <div className="field"><label htmlFor="outcome">Outcome</label><select id="outcome" value={outcome} onChange={event => setOutcome(event.target.value)}>{(outcomes.data?.values ?? []).map(value => <option key={value}>{value}</option>)}</select></div>
            {outcome !== 'administered' && <div className="field"><label htmlFor="reason">Reason</label><textarea id="reason" required value={reason} onChange={event => setReason(event.target.value)} /></div>}
            {selected.high_alert === 1 && <div className="field"><label htmlFor="cosigner">Independent co-signer</label><select id="cosigner" value={cosigner || eligible[0]?.id || ''} onChange={event => setCosigner(event.target.value)}>{eligible.map(nurse => <option value={nurse.id} key={nurse.id}>{nurse.name}, {nurse.role.replaceAll('_', ' ')}</option>)}</select></div>}
            <button className="btn btn-primary" disabled={mutation.isPending || outcomes.isLoading}>{mutation.isPending ? 'Confirming...' : 'Confirm administration record'}</button>
          </form>
        ) : <div className="empty">Select a medication to begin the verification workflow.</div>}
      </section>
    </div>
  )
}

function Handover({ patient, user }: { patient: Patient; user: User }) {
  const queryClient = useQueryClient()
  const { data: nurses = [] } = useQuery({ queryKey: ['ward-nurses', patient.ward_id], queryFn: () => request<Nurse[]>(`/api/wards/${patient.ward_id}/nurses`) })
  const { data: pending = [] } = useQuery({ queryKey: ['handovers', 'pending'], queryFn: () => request<HandoverRecord[]>('/api/handovers?status=pending') })
  const eligible = nurses.filter(nurse => nurse.id !== user.id)
  const [form, setForm] = useState({
    receiver_id: '',
    situation: `${patient.admission_reason}; current nursing priorities require review.`,
    background: `Admitted to bed ${patient.bed}. Allergies and flags are visible in the persistent banner.`,
    assessment: `Active tasks: ${patient.tasks?.filter(task => ['open', 'accepted'].includes(task.status)).length ?? 0}. Review current observations and safety assessments.`,
    recommendation: 'Review outstanding actions, confirm observation frequency, and accept accountability.',
  })
  const mutation = useMutation({
    mutationFn: () => request(`/api/patients/${patient.id}/handovers`, { method: 'POST', body: JSON.stringify({ ...form, receiver_id: form.receiver_id || eligible[0]?.id }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['handovers'] }),
  })
  const accept = useMutation({
    mutationFn: (handover: HandoverRecord) => request(`/api/handovers/${handover.id}/accept`, { method: 'POST', body: JSON.stringify({ version: handover.version }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['handovers'] }),
  })
  const patientPending = pending.filter(handover => handover.patient_id === patient.id)
  return (
    <div className="grid grid-2">
      <form className="panel" onSubmit={event => { event.preventDefault(); mutation.mutate() }}>
        <div className="panel-head"><h2>Structured SBAR handover</h2><Status kind="caution" label="Explicit acceptance required" /></div>
        {(mutation.error || accept.error) && <div className="alert danger" role="alert">{((mutation.error || accept.error) as Error).message}</div>}
        {Boolean(mutation.data) && <div className="alert normal" aria-live="polite">Handover created. Accountability has not transferred until named acceptance.</div>}
        <div className="grid grid-2">{(['situation', 'background', 'assessment', 'recommendation'] as const).map(key => <div className="field" key={key}><label htmlFor={key}>{key[0].toUpperCase() + key.slice(1)}</label><textarea id={key} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })} /></div>)}</div>
        <div className="field field-narrow"><label htmlFor="receiver">Receiving nurse</label><select id="receiver" value={form.receiver_id || eligible[0]?.id || ''} onChange={event => setForm({ ...form, receiver_id: event.target.value })}>{eligible.map(nurse => <option value={nurse.id} key={nurse.id}>{nurse.name}, {nurse.role.replaceAll('_', ' ')}</option>)}</select></div>
        <button className="btn btn-primary" disabled={mutation.isPending || eligible.length === 0}>{mutation.isPending ? 'Creating...' : 'Create pending handover'}</button>
      </form>
      <section className="panel">
        <h2>Pending accountability and risk snapshot</h2>
        {patientPending.length ? patientPending.map(handover => (
          <div className="handover-card" key={handover.id}>
            <div className="panel-head"><Status kind="caution" label="pending" /><span className="sub">Snapshot {new Date(handover.current_risks_json.captured_at).toLocaleString()} / version {handover.version}</span></div>
            <strong>From {handover.sender_name} to {handover.receiver_name}</strong>
            <p>{handover.situation}</p>
            <div className="sub">{handover.unresolved_tasks_json.length} unresolved tasks / flags: {handover.current_risks_json.flags.join(', ') || 'none'} / isolation: {handover.current_risks_json.isolation_status}</div>
            <div className="sub">Latest score: {handover.current_risks_json.latest_observation?.score ?? 'not recorded'} / high-risk assessments: {handover.current_risks_json.high_risk_assessments.length}</div>
            {handover.receiver_id === user.id && <button className="btn btn-primary" onClick={() => accept.mutate(handover)}>Accept accountability</button>}
          </div>
        )) : <div className="empty">No pending handover for this patient.</div>}
      </section>
    </div>
  )
}

function Safety({ patient, onSaved }: { patient: Patient; onSaved: () => void }) {
  const types = useReference('assessment-types')
  const risks = useReference('risk-levels')
  const [type, setType] = useState('falls')
  const [risk, setRisk] = useState('moderate')
  const [findings, setFindings] = useState('Requires assistance when mobilising.')
  const [action, setAction] = useState('Assist with mobilisation and document tolerance')
  const mutation = useMutation({
    mutationFn: () => request(`/api/patients/${patient.id}/safety-assessments`, { method: 'POST', body: JSON.stringify({ assessment_type: type, risk_level: risk, score: null, findings, actions: [action] }) }),
    onSuccess: onSaved,
  })
  return (
    <div className="grid grid-2">
      <form className="panel" onSubmit={event => { event.preventDefault(); mutation.mutate() }}>
        <h2>Record safety assessment</h2>
        {mutation.error && <div className="alert danger" role="alert">{(mutation.error as Error).message}</div>}
        <div className="field"><label htmlFor="atype">Assessment</label><select id="atype" value={type} onChange={event => setType(event.target.value)}>{(types.data?.values ?? []).map(value => <option key={value}>{value}</option>)}</select></div>
        <div className="field"><label htmlFor="risk">Risk</label><select id="risk" value={risk} onChange={event => setRisk(event.target.value)}>{(risks.data?.values ?? []).map(value => <option key={value}>{value}</option>)}</select></div>
        <div className="field"><label htmlFor="findings">Findings</label><textarea id="findings" value={findings} onChange={event => setFindings(event.target.value)} /></div>
        <div className="field"><label htmlFor="action">Owned action</label><input id="action" value={action} onChange={event => setAction(event.target.value)} /></div>
        <button className="btn btn-primary" disabled={mutation.isPending || types.isLoading || risks.isLoading}>Save and create action</button>
      </form>
      <section className="panel">
        <h2>Assessment history</h2>
        {patient.assessments?.length ? patient.assessments.map(assessment => (
          <div className="task" key={assessment.id}>
            <Status kind={assessment.risk_level === 'critical' ? 'danger' : assessment.risk_level === 'high' ? 'caution' : 'info'} label={assessment.risk_level} />
            <div><strong>{assessment.assessment_type}</strong><div>{assessment.findings}</div><div className="sub">Recorded by {assessment.assessed_by_name} at {new Date(assessment.assessed_at).toLocaleString()} / actions: {assessment.actions_json.join('; ')}</div></div>
          </div>
        )) : <div className="empty">No assessments recorded.</div>}
      </section>
    </div>
  )
}

function TasksPage({ privacy }: { privacy: boolean }) {
  const { data, error, isLoading } = useQuery({ queryKey: ['tasks'], queryFn: () => request<Task[]>('/api/tasks') })
  return (
    <>
      <div className="page-head"><div><div className="eyebrow">Ward work queue</div><h1>Nursing tasks</h1><p>Priority, ownership, author, and due time in one queue.</p></div></div>
      {isLoading ? <div aria-busy="true">Loading tasks...</div> : error ? <div role="alert" className="alert danger">{(error as Error).message}</div> : (
        <section className="panel"><div className="task-list">{data?.map(task => (
          <NavLink className={`task ${new Date(task.due_at) < new Date() && !['completed', 'cancelled'].includes(task.status) ? 'overdue' : ''}`} to={`/patients/${task.patient_id}`} key={task.id}>
            <Status kind={task.priority === 'stat' ? 'danger' : task.priority === 'high' ? 'caution' : 'info'} label={task.priority} />
            <div><strong>{task.title}</strong><div>{privacy ? `Patient ${task.bed}` : task.patient_name} / Bed {task.bed}</div><div className="sub">Owner {task.assigned_to_name ?? 'unassigned'} / created by {task.created_by_name} / due {new Date(task.due_at).toLocaleString()} / {task.status}</div></div>
            <Activity size={18} />
          </NavLink>
        ))}</div></section>
      )}
    </>
  )
}

function GovernancePage() {
  const { data: health, error } = useQuery({
    queryKey: ['health'],
    queryFn: () => request<{ status: string; audit_chain_valid: boolean; audit_events: number; integrations: string; warning_profile: string }>('/health'),
  })
  const { data: seed, error: seedError } = useQuery({ queryKey: ['seed-governance'], queryFn: () => request<SeedGovernance>('/api/governance/seed') })
  return (
    <>
      <div className="page-head"><div><div className="eyebrow">Clinical governance</div><h1>Evidence and boundaries</h1><p>Direct runtime state, not a readiness claim inferred from documentation.</p></div></div>
      {(error || seedError) ? <div className="alert danger" role="alert">{((error || seedError) as Error).message}</div> : (
        <div className="grid grid-3">
          <div className="metric"><div className="metric-label">Service</div><div className="metric-value compact-value">{health?.status ?? 'Checking'}</div></div>
          <div className="metric"><div className="metric-label">Audit chain</div><div className="metric-value compact-value">{health?.audit_chain_valid ? 'Valid' : 'Checking'}</div><div className="sub">{health?.audit_events ?? 0} events</div></div>
          <div className="metric"><div className="metric-label">Synthetic lineage</div><div className="metric-value compact-value">{seed?.data_class ?? 'Checking'}</div><div className="sub">{seed?.seed_manifest_id}</div></div>
        </div>
      )}
      {seed && (
        <section className="panel governance-panel">
          <div className="panel-head"><h2>Landed synthetic seed</h2><Status kind="normal" label="No live source" /></div>
          <p>Seeder {seed.seeder_name}; metadata pack {seed.metadata_pack_id}; landed {new Date(seed.generated_at).toLocaleString()}.</p>
          <div className="seed-counts">{Object.entries(seed.record_counts).map(([name, count]) => <div className="metric" key={name}><div className="metric-label">{name.replaceAll('_', ' ')}</div><div className="metric-value compact-value">{count}</div></div>)}</div>
          <p className="sub">Real patient data: {String(seed.declaration.contains_real_patient_data)} / real person data: {String(seed.declaration.contains_real_person_data)} / pseudonymised real data: {String(seed.declaration.contains_pseudonymised_real_data)} / live clinical source: {String(seed.declaration.source_is_live_clinical_system)}.</p>
        </section>
      )}
      <div className="panel governance-panel">
        <h2>Phase boundary</h2>
        <p>Phase 2 preserves durable nursing-owned workflows and adds governed BulletTrain context from the real seeded sibling services. Critical LIS results enter the ward alert feed through an authenticated, audited hub event and require explicit nurse acknowledgement.</p>
        <p>Warning profile: {health?.warning_profile ?? 'checking'}. Integration state: {health?.integrations ?? 'checking'}.</p>
        <div className="alert caution"><FileClock size={18} /><div><strong>Clinical deployment is not authorised.</strong><div>Clinical Safety Officer review, local escalation policy, production security, secret management, and master-registry approval remain required.</div></div></div>
      </div>
    </>
  )
}

export default function App() {
  const { data: user, isLoading, error } = useQuery({
    queryKey: ['me', auth.get()],
    queryFn: () => request<User>('/api/auth/me'),
    enabled: Boolean(auth.get()),
    retry: false,
  })
  if (!auth.get()) return <Routes><Route path="*" element={<Login />} /></Routes>
  if (isLoading) return <div className="login-page" aria-busy="true"><div className="login-card">Loading clinical workspace...</div></div>
  if (error) {
    auth.clear()
    return <Routes><Route path="*" element={<Login />} /></Routes>
  }
  return <Layout user={user!} />
}
