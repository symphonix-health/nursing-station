# CAID post-build finding review

Run date: 2026-07-18

The CAID post-build gatekeeper passed. Each reported item was checked against the implementation before disposition.

## UX-01 `.btn` and `.btn-primary` visited state

Disposition: false positive.

Every `.btn` and `.btn-primary` use in `frontend/src/App.tsx` is a native `<button>`. The CSS `:visited` pseudo-class applies to hyperlinks with an `href`, not buttons, so adding a visited rule would not alter these controls. Hover, keyboard focus, disabled state, and accessible name/role behavior are exercised by the browser suite. The Axe run recorded zero WCAG A/AA violations at desktop and mobile viewports.

## POST-01 convergence artefacts

Disposition: resolved by the post-build run.

`CODE_REVIEW_FINDINGS.json`, `ARCHIVIST_DRAFTS.json`, and `ARCHIVIST_VERDICTS.json` now exist at the repository root. They are retained as review evidence. The initial finding was emitted during the same run that created them.

## Release implication

These findings do not change the clinical release gate. `safety/hazards.json` and `SAFETY_SCOPE.md` record the separate human approvals required before deployment.
