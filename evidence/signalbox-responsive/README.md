# SignalBox responsive audit evidence (NFR-NS-031)

`latest.json` is the report of SignalBox's `browser_responsive_audit` tool run
through a HEADED, persona-bound session (the nurse persona, signed in through
the real login form against the running application), driven by BulletTrain's
`scripts/signalbox_responsive_audit.py`. The criteria are the estate's own,
from BulletTrain `frontend/e2e/L3-VIS-responsive.spec.ts`: R1 no horizontal
page scroll at 375, 768 and 1280 px; on a phone R6 navigation off-screen or a
rail under 80 px, content filling 80% of the viewport and fields stacking, R2
44 px touch targets (at most five exceptions), R5 no text under 12 px (at most
three exceptions).

`screenshots/` holds SignalBox's own capture at each width for each route.
`tests/test_responsive_layout.py` refuses a report that is not headed, not
persona-driven, missing a route or width, or carrying a failed check.

A unit test or generated matrix alone is not responsive evidence; regenerate
with the command recorded in `latest.json` under `regenerate`.
