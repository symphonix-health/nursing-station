# Standards profile

## Global safety and nursing direction

The Phase 1 control set adopts the WHO Global Patient Safety Action Plan 2021-2030 as its safety frame: visible risk, named accountability, prevention controls, learning evidence, and a local deployment safety case. Medication verification, high-alert co-sign, explicit non-administration outcomes, and handover acceptance implement the medication-administration and transition-of-care concerns in WHO Medication Without Harm.

The workflow supports the service-delivery and nursing-practice direction described by WHO's Global Strategic Directions for Nursing and Midwifery and the 2025 State of the World's Nursing report. These sources do not define one universal nursing-station screen. The repository therefore treats local staffing, scope of practice, escalation, retention, terminology, and consent rules as governed overlays.

WHO SMART Guidelines inform the requirement shape: standards-based, machine-readable, adaptive, requirements-based, and testable. Phase 1 uses explicit requirements, generated contracts, deterministic seed data, canonical matrices, and traceable direct tests. It does not claim that WHO has endorsed this product or that a generic nursing-station Digital Adaptation Kit exists.

## Information and interoperability

- ISO 18104:2023 provides the nursing-practice terminology structure for future coded nursing diagnoses, actions, and nurse-sensitive outcomes.
- HL7 FHIR R4 resource semantics inform the Phase 2 mappings for Observation, Task, CarePlan, Communication, MedicationAdministration, Encounter, Provenance, PractitionerRole, and AuditEvent. Phase 1 does not claim FHIR conformance because no profile or conformance test has yet been implemented.
- ISO 27799:2025 informs health-information security controls. The Phase 1 implementation proves local authentication, ward and role scope, minimisation, version checks, durable storage, and tamper-evident audit; production controls remain deployment work.
- WCAG 2.2 AA is the frontend target. Automated Axe, desktop/mobile browser tests, keyboard semantics, reduced motion, text status, focus styles, theme parity, and headed review are evidence inputs, not a blanket conformance claim.

## Country and organisation overlays

Before clinical use, a deploying organisation must approve nursing scope, warning-score policy, escalation times, medication double-check policy, patient identification, observation frequency, record retention, privacy, downtime, local terminology, infection controls, clinical safety case, and workforce competencies. Those gates remain external to Phase 1 and cannot be bypassed through configuration defaults.

## Primary references

- WHO, Global patient safety action plan 2021-2030: https://www.who.int/publications/b/57613
- WHO, Medication Without Harm: https://www.who.int/initiatives/medication-without-harm
- WHO, SMART Guidelines: https://www.who.int/teams/digital-health-and-innovation/smart-guidelines/
- WHO, State of the world's nursing report 2025: https://www.who.int/publications/i/item/9789240110236
- ISO 18104:2023: https://www.iso.org/standard/81132.html
- ISO 27799:2025: https://www.iso.org/standard/84647.html
- HL7 FHIR R4: https://hl7.org/fhir/R4/
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
