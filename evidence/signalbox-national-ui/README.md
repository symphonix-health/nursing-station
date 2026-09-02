# SignalBox evidence: national-capability UI (FR-NS-090..170)

`latest.json` records three HEADED SignalBox sessions, one per persona
(registered nurse, nurse in charge, clinical safety officer), each signed in
through the real login form and driving the real ward UI against the running
backend: every assertion names what the accessibility snapshot showed after
the click and what the API then reported. `screenshots/` are SignalBox's own
captures with the persona badge on the cursor.

Driver: BulletTrain `scripts/signalbox_nursing_national_ui.py`. The stack is
the one `scripts/headed_nursing_station_evidence.py --stack-only` holds up
(real backend, Vite frontend, registered hub). Nothing is seeded beyond what
the personas do through the UI; a refusal the pack demands (a registered
nurse answering an escalate-level escalation) is recorded as a refusal.
