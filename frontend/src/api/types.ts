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
