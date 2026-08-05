# National capability disposition ledger

**Repository:** nursing-station (ward nursing operations)
**Audit:** `docs/national-capability-audit.md` (wave 3, generated 22 July 2026)
**Implementation session:** 2026-08-05
**Jurisdiction:** Ireland (`IE`), per audit section 5

The audit proposed eight requirement families with a disposition attached to
each. Those dispositions are **claims**. Every family below was graded against
the live code before anything was built, and three of the eight audit
dispositions turned out to be wrong. Line numbers are as of this commit.

## 1. Dispositions

| # | Family (audit alias) | Audit said | Verified disposition | Native ids landed |
|---|---|---|---|---|
| 1 | Ward work orchestration (`REQ-NS-NAT-001`) | RETAIN-AS-OWNER | **partial** — task lifecycle owned; risk ranking, skill gating and interruption all missing | `FR-NS-090`, `FR-NS-091`, `FR-NS-092` |
| 2 | Observation / deterioration (`REQ-NS-NAT-002`) | BUILD-NEW | **partial — substantially already-covered** (audit wrong) | `FR-NS-100`, `FR-NS-101` |
| 3 | eMAR closed loop (`REQ-NS-NAT-003`) | HUB-CONSUME | **partial** — read leg existed, neither the receive-into-eMAR nor the publish-outcome leg did | `FR-NS-110`, `FR-NS-111` |
| 4 | Structured handover (`REQ-NS-NAT-004`) | BUILD-NEW | **already-covered except one leg** (audit wrong) | `FR-NS-120` |
| 5 | Staffing / skill mix (`REQ-NS-NAT-005`) | HUB-CONSUME | **missing here AND unowned estate-wide** | `FR-NS-130`, `FR-NS-131`, `FR-NS-132`, `NFR-NS-028` |
| 6 | Pressure injury / falls / infection (`REQ-NS-NAT-006`) | BUILD-NEW | **partial** — prevention and assessment existed; incident, review and reporting did not | `FR-NS-140`, `FR-NS-141` |
| 7 | Discharge readiness (`REQ-NS-NAT-007`) | HUB-CONSUME | **missing** | `FR-NS-150`, `FR-NS-151` |
| 8 | Nursing quality dataset (`REQ-NS-NAT-008`) | BUILD-NEW | **partial** — the de-identified transport existed; the dataset did not | `FR-NS-160`, `FR-NS-161` |
| — | Country policy (audit section 5) | — | **missing** | `FR-NS-170`, `NFR-NS-027` |
| — | Outbound national obligations | — | **missing** | `NFR-NS-029` |
| — | Human authority over new decisions | — | **missing** | `NFR-NS-030` |

### Alias mapping

The audit's `REQ-NS-NAT-00N` identifiers are provisional intake aliases. They
are **not** requirements of this repository and appear only in this ledger and
in the committed intake copy of the audit. They are deliberately absent from
`docs/REQUIREMENTS.md`, `docs/USE_CASES.md`, `docs/TRACEABILITY.md` and every
catalogue JSON so that no gate scraping those artefacts can turn an alias into
a phantom obligation.

The repository's native scheme is `FR-NS-NNN` / `NFR-NS-NNN`, sourced from
`docs/REQUIREMENTS.md` and rendered into `tests/harness/requirements_matrix.json`,
`requirements_superset.json` and `healthcare_requirements_superset.json` by
`scripts/generate_canonical_matrices.py`. The maxima before this wave were
`FR-NS-082` and `NFR-NS-026`; the catalogue held 58 ids. New ids continue the
existing decade grouping from `FR-NS-090` and `NFR-NS-027`. De-duplicated
against all three catalogue JSONs plus `docs/REQUIREMENTS.md` before allocation.
Catalogue after this wave: **80** requirements, 140 canonical scenarios.

## 2. Per-family evidence

### Family 1 — Ward work orchestration: `partial`

**Already there.** Task create / assign / accept / complete / cancel with
priority, due time, ward-and-role scope and optimistic version guard:
`backend/nursing_station/main.py:1015` (`create_task`),
`main.py:1048` (`transition_task`), listing ordered by priority then due time at
`main.py:1030`. Requirements `FR-NS-020`/`FR-NS-021` already covered this.

**Genuinely missing.** No risk-weighted ordering (the list was priority-then-due
only), no competency model anywhere in the schema, no interruption record.

**Built.** `backend/nursing_station/work_queue.py` (deterministic explainable
ranking); `nurse_competencies` and `task_interruptions` tables at
`database.py:216` and `database.py:221`; `tasks.required_competency` /
`origin_kind` / `origin_id` columns; routes at `national_routes.py:290`
(`/api/ward-board/work-queue`), `:350` (ward competencies), `:373`
(record interruption), `:407` (resume). The competency gate is enforced at both
delegation points, `main.py:973` (`require_competency`) called from
`create_task` and `transition_task`.

### Family 2 — Observation / deterioration: `partial` (audit said BUILD-NEW — WRONG)

**Correction.** The audit called this BUILD-NEW. A full seven-parameter NEWS2
aggregate score, structured observation persistence with units, performer,
provenance and profile version, implausible-value rejection, and automatic
escalation-task creation at threshold were **already implemented and tested**
before this wave: scoring at `main.py:876`, capture at `main.py:889`, covered
by `FR-NS-010`/`FR-NS-011`/`FR-NS-012` and by
`tests/test_api.py::test_observation_records_score_and_creates_escalation`.
Building this family as specified would have duplicated working clinical code.

**Genuinely missing.** (a) Only NEWS2 Scale 1 existed, so a patient prescribed
an 88-92% target range was scored against a 94-98% target and over-escalated;
(b) the escalation created a task but nothing recorded **who responded, when, or
whether the response met the required interval**; (c) thresholds and the profile
identity were service constants, not jurisdictional data.

**Built.** `backend/nursing_station/warning_scores.py` (pack-driven bands
including Scale 2 on-air and on-oxygen tables); `escalation_responses` table at
`database.py:227`; `observations.oxygen_scale` / `jurisdiction` /
`pack_version` / `response_due_at` columns; routes at `national_routes.py:436`
(ward escalation feed) and `:471` (record response, seniority-gated, idempotent).

### Family 3 — eMAR closed loop: `partial`

**Already there.** Six explicit administration outcomes, two-identifier
verification, independent high-alert co-sign, one-terminal-record-per-occurrence
index: `main.py:1329` (`administer`), index at `database.py:98`. Pharmacy
`MedicationRequest` / `MedicationDispense` context is already read through the
hub: `backend/nursing_station/integration.py:31`.

**Genuinely missing.** Both halves of the loop. Orders were seeded locally
(`"Phase 1 seeded order"`) and pharmacy's requests were never turned into eMAR
orders; and no administration outcome was ever sent back to pharmacy — the only
`operation="write"` exchange in the repo was HMIS.

**Built.** `reconcile_medication_orders` at `main.py:407`, called from the
pharmacy branch of the refresh at `main.py:525`; `medication_orders.source_system`
/ `source_order_id` with a partial unique index; `_map_medication_request` at
`main.py:375` refuses a request with no dose unit rather than defaulting one
(FR-NS-043); `queue_medication_outcome` at `main.py:1403` writes the durable
outbox row inside the administration transaction.

### Family 4 — Structured handover: `already-covered` except one leg (audit said BUILD-NEW — WRONG)

**Correction.** The audit called this BUILD-NEW. Full SBAR handover with a named
receiver in the same ward, a snapshot of unresolved tasks **and** current risks
(flags, allergies, isolation, code status, latest observation, high-risk
assessments), receiver-only acceptance with a version guard, and accountability
transfer, were already implemented: `main.py:1110` (`create_handover`) and
`main.py:1166` (`accept_handover`), covered by `FR-NS-030`/`FR-NS-031`.

**Genuinely missing.** Acceptance moved the **patient** but not the **work**:
unresolved tasks kept their previous assignee, so a task could end a shift owned
by a nurse who had gone home. `FR-NS-120` closes exactly that leg, and declines
an action the receiver has no verified competency for rather than transferring
it silently (`main.py:1166`).

### Family 5 — Staffing / skill mix: `missing` here and `owned-by-nobody` estate-wide

**Verified.** No roster, ratio, registration or skill-mix table existed in this
repo. A read-only sweep of BulletTrain confirms the wider position: there is no
`workforce` connector and no `NursingRosterContext` exchange route anywhere in
`BulletTrain/connectors/manifests/`, and no `nursing.*`, `staffing.*`, `ward.*`
or `handover.*` kind in `BulletTrain/connectors/registries/outbound_webhook_events.json`.
BulletTrain's governed role assumption owns `StaffingDeclaration`
(`bullettrain/security/role_assumption.py`) but exposes no declare/revoke HTTP
surface yet.

**Built, and graded honestly.**
- `backend/nursing_station/workforce.py` declares the roster consumption
  contract, computes the position from repo-owned occupancy and acuity against
  the pack norm, and builds the declaration payload.
- `staffing_snapshots` / `staffing_declarations` tables at `database.py:246`
  and `:254`; routes at `national_routes.py:1016`, `:1037`, `:1106`, `:1166`,
  `:1195`.
- The declaration emits **exactly** BulletTrain's six governed fields
  (`declaration_id`, `scope_unit`, `declared_by`, `reason`, `starts_at`,
  `expires_at`). No severity, no role enum, no approval field, no tier — the
  governed model has none of those and inventing one would fork the contract.
  `workforce.build_declaration` raises if a caller adds a field.
- **REMAINING:** the consumption loop has no publisher and the declaration has
  no destination. Both are implemented **to the durable queue**, never reported
  as delivered. This family is NOT closed-loop.

### Family 6 — Pressure injury / falls / infection: `partial`

**Already there.** Falls, pressure-injury, infection, nutrition, hydration, pain
and delirium **assessments** with risk level and automatic generation of owned,
due nursing actions: `main.py:1463` (`assess`), `safety_assessments` table at
`database.py:100`, covered by `FR-NS-050`/`FR-NS-051`.

**Genuinely missing.** Nothing recorded an incident that actually **happened** —
a fall, a pressure injury with a category and a present-on-admission status, an
acquired infection — and nothing reviewed one.

**Built.** `harm_incidents` and `incident_reviews` tables at `database.py:264`
and `:275`; routes at `national_routes.py:553` (report), `:632` (list), `:647`
(review). Reportability is decided by the country pack, not by code
(`national_routes.py:41`, `_externally_reportable`), and a present-on-admission
pressure injury is excluded from this ward's acquired harm. Review requires a
different person from the reporter and produces owned learning tasks.

### Family 7 — Discharge readiness: `missing`

**Verified.** No discharge concept existed anywhere in the repo (the only
matches for "discharge" at HEAD were a test title and a prose line in
`docs/STANDARDS_PROFILE.md`).

**Built.** `discharge_readiness` / `discharge_criteria` tables at
`database.py:283` and `:293`, with a partial unique index preventing two open
records for one patient; routes at `national_routes.py:715` (open), `:781`
(view), `:793` (confirm a repo-owned criterion), `:842` (hub coordination),
`:945` (complete). A criterion owned by another system **cannot** be met by
local assertion, and coordination marks a criterion met only when that system's
own response carries the evidence.

**REMAINING:** only `pharmacy-system` has a usable read route today
(`NursingMedicationContext`). Equipment, community referral, transport and
follow-up have no confirmation route and stay `pending` with
`hub_route_unregistered`.

### Family 8 — Nursing quality dataset: `partial`

**Already there.** A de-identified, hub-mediated, receipt-bearing ward-count
submission to HMIS: `main.py:641` (`submit_hmis_measures`), covered by
`FR-NS-075` and `NFR-NS-014`.

**Genuinely missing.** The payload was six operational counts. There was no
measure **definition** (numerator, denominator, exclusions, unit, citation), no
staffing measure, no missed-care measure, no harm rate, no deterioration-response
measure, and nothing distinguished "we have no data" from "the value is zero".

**Built.** Measure definitions are country-pack data; computation is
`backend/nursing_station/quality.py` with three explicit states (`computed`,
`source-unavailable`, `no-denominator`); read surface at
`national_routes.py:1216`; publication extends the **existing** HMIS
`NursingMeasureReport` envelope with an additive `measures` block, leaving its
six required keys untouched so an HMIS that does not understand `measures`
still accepts the submission it always accepted. Results persist to
`quality_measure_results` (`database.py:301`).

## 3. Country pack

`backend/nursing_station/country_packs/{ie,gb,ke,us}.json`, loaded and validated
by `backend/nursing_station/country_packs.py`. Ireland is the jurisdiction;
Dublin is a location within it, not a pack.

Each pack carries the early-warning profile (including the Scale 2 oxygen band
tables), safe-staffing norms and declaration triggers, harm-incident
classification and external reporting owner, discharge criteria, and quality
measure definitions — every clinically meaningful entry citing a `source_id`
that resolves to a publisher, title, document type and effective date inside the
same pack. Validation refuses a dangling citation.

**Honesty constraints deliberately encoded.**
- Every pack ships `adoption_status: "candidate"`. Nothing promotes it except a
  recorded organisational decision pinned to the exact pack version
  (`NFR-NS-027`, `country_pack_adoptions` at `database.py:310`).
- The Ireland and Kenya and United States early-warning profiles carry the
  transportable NEWS2 parameter bands as a **candidate** and say so in
  `algorithm_note`. This repository does **not** claim to have encoded INEWS V2's
  authoritative parameter table, and does not claim a national aggregate score
  exists for Kenya or the United States.
- The United States pack sets `nursing_hours_per_patient_day: 0` for its federal
  ward norms with a note; the staffing position then reports
  `insufficient-policy` rather than manufacturing a compliance verdict from a
  zero. California appears as an explicitly state-scoped overlay.
- Citations are publisher-level (`citation_scope: "publisher-cited"`). A deep
  document URL was not fabricated where it could not be verified from this
  environment.

## 4. Defects found and fixed

1. **`scripts/generate_canonical_matrices.py` was regenerate-overwrite.**
   Proved by planting a foreign requirement and a foreign matrix row and running
   the builder: both were deleted. Fixed to read-merge-write with union
   recounting; regression test `tests/test_matrix_builder_brownfield.py`, whose
   bite was proved by reverting the merge and watching the test fail.
2. **The legacy matrix rotation was catalogue-coupled.** Adding requirements to
   `REQUIREMENTS` would have reshuffled all 100 legacy rows, rewriting every row
   body and destroying the coverage atoms recorded in
   `matrix-integrity-baseline.json`. Fixed by freezing
   `LEGACY_MATRIX_REQUIREMENT_IDS`; guarded by
   `test_growing_the_catalogue_never_reshuffles_the_legacy_matrix`.
3. **Superseded warning-score configuration.** `NURSING_STATION_WARNING_PROFILE`
   and the three threshold environment variables no longer reach the scorer now
   that the country pack owns them. They were **removed** rather than left in
   place: a threshold variable an operator can set but which never reaches an
   escalation trigger is worse than no variable at all.
4. **Positional `INSERT ... VALUES` statements.** Several seed and route inserts
   relied on column order (`INSERT INTO tasks VALUES (?,...16)`). Adding a
   column would have silently mis-assigned clinical fields. All converted to
   explicit column lists.
5. **FastAPI dependency shape.** Under this module's postponed annotations a
   factory-local `Annotated[..., Depends(ctx.current_user)]` never resolves, so
   FastAPI degraded every new route to a query parameter and returned 422.
   Fixed to the default-value form and recorded at the call site.
6. **Hardcoded single-file scan in the scenario harness and its evidence
   generator.** `tests/harness/test_matrix_scenario_app_harness.py` and
   `scripts/generate_scenario_success_evidence.py` both named
   `nursing_station_phase2_canonical` literally, so the forty new canonical
   scenarios had no executable coverage and no success evidence. `caid
   test-agent` caught it as
   `traceability_failure :: scenario success evidence does not cover every
   matrix scenario`. Both now discover every matrix in their directory, the
   harness executes all nine new domains against the real application, and the
   gate passes with 140 of 140 scenarios covered.

## 5. Observations recorded, not fixed

- **Seed manifest jurisdiction mismatch.** `SEED_MANIFEST_ID` is
  `seed.uk.nursing_station.phase2_v1` and `METADATA_PACK_ID` is
  `uk.0.1.fabricated`, while the tenant is `tenant-st-brigids` with Irish
  patient names and the jurisdiction is now `IE`. Renaming touches the manifest
  id, the two `seed_manifests/uk/*.yaml` files, three database column defaults
  and several test assertions; it was judged out of blast radius for this wave
  and is recorded here instead. `/health` now reports `jurisdiction` beside
  `synthetic_seed` so the mismatch is visible rather than hidden.
- **Hardcoded warning thresholds in the frontend.** `frontend/src/App.tsx:551`
  colours the observation score with literal `>= 7` and `>= 5` comparisons
  rather than reading the pack thresholds. No frontend file was touched in this
  wave, so this is unchanged and unverified by headed evidence.
- **18-column padding blind spot.** The legacy 18-column matrix escapes the
  padding detector only because each row carries a per-row `scenario_index`
  counter; its 14-column twin, which has no such counter, reports 27 duplicate
  bodies. The committed baseline records those 27; this wave did not raise it.

## 6. BulletTrain-side work this repository needs (not landed here)

BulletTrain was read **read-only**. Nothing in that repository was edited.

| Need | Why |
|---|---|
| `pharmacy_system` exchange route `NursingMedicationOutcome` (write) | `FR-NS-111` closes the eMAR loop only when pharmacy can receive the administration/omission outcome. Today the outcome is durable and queued. |
| A declare/revoke surface for `StaffingDeclaration`, and a connector route reaching it | `FR-NS-132` emits the exact governed field set but has no destination. BulletTrain's own `docs/security/governed_role_assumption.md` names this API as the next part of that work. |
| `hmis` exchange route `NursingHarmIncidentReport` (write) | `FR-NS-140` queues externally reportable ward incidents de-identified; there is no incident route on the HMIS connector. |
| A roster publisher and a `workforce` / `NursingRosterContext` read route | `FR-NS-130` declares the consumption contract; nothing in the estate publishes a nursing roster, which is why two quality measures report `source-unavailable`. |
| Discharge confirmation routes for `supply-chain-erp`, `community-nursing` (receipt, not dispatch), `appointment-system`, `ambulance-ems` | `FR-NS-151` meets a criterion only from the owning system's receipt. |
| `nursing_station` registration in `connector_registry_index.json` | The manifest exists and dispatches, but the connector is invisible to `GET /v1/connectors`, so a sibling doing discovery-then-dispatch cannot find it. |
| HMIS acceptance of the additive `measures` block on `NursingMeasureReport` | The six required envelope keys are unchanged, so delivery is unaffected, but HMIS-side handling of `measures` is unproven. |

`tests/test_bt_connector_seam.py` pins every one of these read-only and turns
**red** the day any of them lands, so the gap notes, this ledger and the family
grading cannot rot apart.

## 7. Remaining work, stated plainly

- Families 5 and 7 and the harm-reporting leg of family 6 are **implemented to
  the queue**, not closed-loop. No receipt exists because no receiver exists.
- Two of the seven quality measures (`NSQ-STAFF-01`, `NSQ-STAFF-02`) report
  `source-unavailable` in every period until a roster is published.
- No frontend surface was built for any new capability. The backend is complete
  and the API is exercised, but the ward-facing UI for the work queue,
  escalation response, incident review, discharge readiness, staffing position
  and quality dataset does not exist yet. No frontend file was modified, so no
  headed-SignalBox evidence was produced or required for this wave.
- The CAID NFR-derivation artefacts (`derived_nfrs.json`,
  `nfr_canonical_matrices/`) remain absent, so six shared-suite tests continue to
  skip. This wave did not opt in.
- The Seeding Alignment Gate reports `decision=BLOCKED, rationale=Required
  artefact(s) missing: seed` both before and after this wave — byte-identical
  output on both runs, `rows=140 blocking=0 orphan_seed=0 missing_seed=0
  partial_seeding=0`. The cause is structural: the gate discovers a seeder at
  `backend/<package>/seed.py`, and this repository's seeder lives inside
  `backend/nursing_station/database.py`. Extracting it is a real improvement but
  a separate change with its own blast radius, so it was recorded rather than
  bundled into this wave. The identical before/after output is also the control
  proving the committed audit copy leaked no phantom obligations.
