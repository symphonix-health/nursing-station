// Generated from the Phase 1 OpenAPI contract. Keep aligned with direct API tests.
export type User = {
  id: string
  tenant_id: string
  facility_id: string | null
  email: string
  name: string
  role: string
  ward_id: string | null
}

export type Observation = {
  id: string
  recorded_at: string
  recorded_by: string
  recorded_by_name: string
  respiratory_rate: number
  oxygen_saturation: number
  systolic_bp: number
  pulse: number
  temperature: number
  consciousness: string
  score: number
  escalation_level: string
  source: string
  units_json: Record<string, string>
  warning_profile_version: string
}

export type Task = {
  id: string
  patient_id: string
  patient_name?: string
  bed?: string
  title: string
  description: string
  priority: string
  status: string
  due_at: string
  assigned_to: string | null
  assigned_to_name?: string | null
  created_by: string
  created_by_name?: string
  version: number
}

export type Medication = {
  id: string
  patient_id: string
  medication_name: string
  dose_value: number
  dose_unit: string
  route: string
  schedule: string
  due_at: string
  high_alert: number
  status: string
  source: string
}

export type Assessment = {
  id: string
  assessment_type: string
  risk_level: string
  score: number | null
  findings: string
  actions_json: string[]
  assessed_at: string
  assessed_by_name?: string
}

export type CarePlan = {
  id: string
  problem: string
  goal: string
  interventions_json: string[]
  status: string
  owner_id: string
  owner_name?: string
  created_by_name?: string
  evaluation: string | null
  updated_at: string
  version: number
}

export type Nurse = { id: string; name: string; role: string }

export type RiskSnapshot = {
  flags: string[]
  allergies: Array<{ substance: string; reaction: string; severity: string }>
  isolation_status: string
  code_status: string
  latest_observation: { score: number; escalation_level: string; recorded_at: string } | null
  high_risk_assessments: Array<{
    assessment_type: string
    risk_level: string
    findings: string
    assessed_at: string
  }>
  captured_at: string
}

export type HandoverRecord = {
  id: string
  patient_id: string
  patient_name: string
  bed: string
  sender_id: string
  receiver_id: string
  sender_name: string
  receiver_name: string
  status: string
  situation: string
  recommendation: string
  unresolved_tasks_json: Array<{
    id: string
    title: string
    priority: string
    due_at: string
    status: string
  }>
  current_risks_json: RiskSnapshot
  version: number
}

export type Patient = {
  id: string
  ward_id: string
  facility_id: string
  mrn: string
  national_id_last4: string
  name: string
  date_of_birth: string
  sex: string
  bed: string
  admission_reason: string
  admitted_at: string
  allergies_json: Array<{ substance: string; reaction: string; severity: string }>
  code_status: string
  isolation_status: string
  flags_json: string[]
  photo_status: string
  accountable_nurse_id: string | null
  accountable_nurse_name?: string | null
  data_class: string
  seed_manifest_id: string
  external_nhs_number: string | null
  source_patient_id: string | null
  latest_score: number | null
  observation_time: string | null
  open_tasks: number
  overdue_tasks: number
  observations?: Observation[]
  tasks?: Task[]
  medications?: Medication[]
  assessments?: Assessment[]
  care_plans?: CarePlan[]
}

export type IntegrationAttempt = {
  correlation_id: string
  attempted_at: string
  completed_at: string | null
  status: string
  error_code: string | null
  error_detail: string | null
  hub_audit_event_id: string | null
}

export type IntegrationSnapshot = {
  source_system: string
  resource_type: string
  content_hash: string
  source_updated_at: string | null
  fetched_at: string
  status: string
  reconciliation_status: string
  correlation_id: string
  version: number
  data: Record<string, unknown>
}

export type IntegrationSource = {
  source_system: string
  resource_type: string
  semantics: string[]
  state: string
  last_attempt: IntegrationAttempt | null
  snapshot: IntegrationSnapshot | null
}

export type PatientIntegrations = {
  patient_id: string
  linked: boolean
  identity: { external_nhs_number: string | null; source_patient_id: string | null }
  sources: IntegrationSource[]
}

export type ClinicalAlert = {
  id: string
  patient_id: string
  patient_name: string
  bed: string
  mrn: string
  event_id: string
  source_system: string
  source_resource_id: string
  alert_type: string
  severity: string
  title: string
  summary: string
  observed_at: string
  received_at: string
  status: string
  correlation_id: string
  version: number
}

export type ClinicalAlertFeed = {
  alerts: ClinicalAlert[]
  generated_at: string
  refresh_seconds: number
}

export type WardBoard = {
  ward: { id: string; facility_id: string; name: string; code: string; specialty: string }
  patients: Patient[]
  generated_at: string
  source: string
}

export type SeedGovernance = {
  id: string
  seed_manifest_id: string
  seeder_name: string
  metadata_pack_id: string
  generated_at: string
  data_class: string
  record_counts: Record<string, number>
  declaration: {
    contains_real_patient_data: boolean
    contains_real_person_data: boolean
    contains_pseudonymised_real_data: boolean
    source_is_live_clinical_system: boolean
    approved_for_use_case: string[]
    limitations: string[]
  }
}

// ---------------------------------------------------------------------------
// National-capability surfaces (FR-NS-090..170)
// ---------------------------------------------------------------------------
export type CountryPackResponse = {
  active: {
    jurisdiction: string
    jurisdiction_name: string
    pack_version: string
    effective_from: string
    adoption_status: string
    adoption_note: string
    languages: string[]
    early_warning_profile_id: string
    safe_staffing_framework_id: string
    quality_measure_ids: string[]
    discharge_criterion_ids: string[]
    sources: Array<{ source_id: string; publisher: string; title: string; effective_from: string; document_type?: string }>
  }
  available_jurisdictions: string[]
  local_adoption: { decision: string; scope: string; adopted_by: string; adopted_at: string; pack_version: string; note: string } | null
  locally_adopted: boolean
  publication_gaps: Array<{ kind: string; gap: string }>
  early_warning: { profile_id: string; thresholds: { review: number; escalate: number; critical: number }; response_minutes: Record<string, number>; responder_minimum_role: Record<string, string> }
}

export type WorkQueueEntry = Task & {
  patient_name: string
  bed: string
  assigned_to_name: string | null
  required_competency: string | null
  rank_score: number
  rank_factors: Record<string, number>
  delegable: boolean
  missing_competency: string | null
  overdue_minutes: number
  unresumed_interruptions: number
  open_interruptions: Array<{ id: string; task_id: string; reason: string; reason_category: string; interrupted_at: string; recorded_by: string }>
}

export type WorkQueue = {
  ward_id: string
  generated_at: string
  jurisdiction: string
  ranking_weights: Record<string, number | Record<string, number>>
  ranking_note: string
  entries: WorkQueueEntry[]
}

export type EscalationRow = {
  id: string
  patient_id: string
  patient_name: string
  bed: string
  recorded_at: string
  score: number
  escalation_level: string
  oxygen_scale: string | null
  response_due_at: string | null
  warning_profile_version: string | null
  jurisdiction: string | null
  response_id: string | null
  responded_at: string | null
  responder_id: string | null
  within_required_interval: number | null
  answered: boolean
  overdue: boolean
}

export type EscalationFeed = {
  ward_id: string
  profile_id: string
  jurisdiction: string
  pack_version: string
  response_minutes: Record<string, number>
  responder_minimum_role: Record<string, string>
  escalations: EscalationRow[]
}

export type HarmIncident = {
  id: string
  patient_id: string
  patient_name: string
  bed: string
  incident_type: string
  occurred_at: string
  discovered_at: string
  reported_by: string
  reported_by_name: string
  reported_at: string
  classification: string | null
  body_site: string | null
  present_on_admission: number
  harm_level: string
  description: string
  externally_reportable: number
  review_required: number
  status: string
  review_id: string | null
  avoidability: string | null
  reviewed_at: string | null
  reviewed_by: string | null
}

export type HarmIncidentFeed = { ward_id: string; incidents: HarmIncident[] }

export type StaffingPositionResponse = {
  position: {
    ward_id: string
    shift_date: string
    shift: string
    shift_hours: number
    jurisdiction: string
    pack_version: string
    framework_id: string
    policy_status: string
    occupied_beds: number
    acuity_distribution: Record<string, number>
    high_acuity_patients: number
    required_nursing_hours: number | null
    required_registered_hours: number | null
    required_registered_nurses: number | null
    max_patients_per_registered_nurse: number | null
    roster_state: string
    roster_source: string
    actual_registered_hours: number | null
    actual_total_hours: number | null
    actual_registered_headcount: number | null
    actual_skill_mix_percent: number | null
    patients_per_registered_nurse: number | null
    unregistered_practitioners: string[]
  }
  roster_contract: { connector: string; resource_type: string; owner: string; note: string }
  declaration_policy: Record<string, unknown>
}

export type StaffingDeclaration = {
  id: string
  declaration_id: string
  scope_unit: string
  declared_by: string
  reason: string
  starts_at: string
  expires_at: string
  revoked: number
  revoked_by: string | null
  revoked_at: string | null
  active: boolean
  created_at: string
}

export type StaffingDeclarationList = { ward_id: string; declarations: StaffingDeclaration[] }

export type QualityMeasure = {
  measure_id: string
  title: string
  measure_type: string
  numerator: number | null
  denominator: number | null
  value: number | null
  unit: string | null
  status: string
  source_id: string
}

export type QualityDataset = {
  ward_id: string
  period_start: string
  period_end: string
  jurisdiction: string
  pack_version: string
  definitions_source: string
  inputs: Record<string, unknown>
  measures: QualityMeasure[]
  unavailable: string[]
}

export type PublicationQueue = {
  publications: Array<{
    id: string
    kind: string
    connector: string
    resource_type: string
    operation: string
    resource_id: string
    correlation_id: string
    status: string
    error_code: string | null
    error_detail: string | null
    attempts: number
    created_by: string
    created_at: string
    completed_at: string | null
  }>
  contracts: Array<{ kind: string; connector: string; resource_type: string; operation: string; route_status: string; gap: string | null }>
}

export type DischargeCriterion = {
  id: string
  readiness_id: string
  criterion_id: string
  title: string
  owner_role: string
  evidence_source: string
  mandatory: number
  status: string
  evidence_reference: string | null
  correlation_id: string | null
  confirmed_by: string | null
  confirmed_at: string | null
  note: string | null
}

export type DischargeReadiness = {
  id: string
  patient_id: string
  status: string
  jurisdiction: string
  pack_version: string
  target_date: string | null
  created_by: string
  created_at: string
  completed_by: string | null
  completed_at: string | null
  criteria: DischargeCriterion[]
  outstanding_mandatory: string[]
  ready_for_discharge: boolean
  coordination?: Array<{ criterion_id: string; status: string; error_code?: string; message?: string; evidence_reference?: string; correlation_id: string }>
}
