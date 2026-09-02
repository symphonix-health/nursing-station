"""Direct evidence for NFR-NS-031: responsive layout at phone, tablet and desktop widths.

Two halves, deliberately. The stylesheet half pins the source rules that make
the phone layout what it is (an off-screen navigation drawer, 44px controls,
12px minimum text, single-column grids); the evidence half refuses a
responsive-audit report that was not produced by SignalBox in a HEADED,
persona-driven session against the running application, or that carries a
failed check for any route or width. A unit test or generated matrix alone is
not responsive evidence: the report is what a person could watch being made.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend/src/styles/design-system.css"
APP = ROOT / "frontend/src/App.tsx"
EVIDENCE = ROOT / "evidence/signalbox-responsive/latest.json"

ESTATE_CRITERIA = "L3-VIS-responsive.spec.ts"
REQUIRED_WIDTHS = ["mobile", "tablet", "desktop"]
REQUIRED_ROUTES = {"/ward", "/patients/pat-005", "/tasks", "/governance"}
MOBILE_CHECKS = {
    "R1_no_horizontal_scroll",
    "R6_sidebar_hidden_on_mobile",
    "R6_content_fills_mobile",
    "R6_fields_stack_on_mobile",
    "R2_touch_targets",
    "R5_text_size",
}


def _mobile_block() -> str:
    css = CSS.read_text(encoding="utf-8")
    start = css.index("@media (max-width: 640px) {")
    return css[start : css.index("\n}\n", start) + 3]


def test_phone_layout_hides_the_navigation_until_opened() -> None:
    block = _mobile_block()
    assert "transform: translateX(-100%)" in block, "the drawer must start off-screen on a phone"
    assert ".bt-shell.nav-open .bt-sidebar { transform: translateX(0)" in block
    assert ".nav-toggle { display: inline-flex; }" in block
    app = APP.read_text(encoding="utf-8")
    assert 'aria-controls="primary-navigation"' in app
    assert "aria-expanded={navOpen}" in app
    assert "setNavOpen(false) }, [location.pathname]" in app, "the drawer must close on navigation"


def test_phone_layout_meets_touch_and_legibility_minimums_in_source() -> None:
    block = _mobile_block()
    assert ".btn, .tabs button, .nav a, .skip-link, .field input, .field select { min-height: 44px; }" in block
    assert "{ font-size: 12px; }" in block
    for cls in (".eyebrow", ".metric-label", ".badge", ".sub", ".banner-label", ".table th", ".brand-sub"):
        assert cls in block, f"{cls} is not lifted to 12px on a phone"
    assert ".grid-3, .grid-2, .form-grid, .integration-grid, .seed-counts { grid-template-columns: 1fr; }" in block


def test_signalbox_headed_persona_audit_passed_every_route_and_width() -> None:
    assert EVIDENCE.is_file(), "evidence/signalbox-responsive/latest.json is missing; run the audit"
    report = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert report["headed"] is True, "responsive evidence must come from a headed session a person could watch"
    assert report["persona"], "responsive evidence must be persona-driven"
    assert report["session_id"].startswith("nursing-station-responsive-")
    assert ESTATE_CRITERIA in report["criteria"]
    assert report["passed"] is True, report.get("failing_checks")
    assert REQUIRED_ROUTES <= set(report["routes"]), sorted(report["routes"])
    for route, data in report["routes"].items():
        assert data["passed"] is True, f"{route}: {data['failing_checks']}"
        widths = [r["width_name"] for r in data["results"]]
        assert widths == REQUIRED_WIDTHS, f"{route}: widths {widths}"
        for result in data["results"]:
            assert result["passed"] is True, f"{route} {result['width_name']}: {result['failures']}"
            assert result["measure"]["horizontal_scroll"] is False
            if result["width_name"] == "mobile":
                assert set(result["checks"]) == MOBILE_CHECKS, sorted(result["checks"])
                assert result["measure"]["inner_width"] == 375
                assert result["measure"]["small_touch_targets"] <= 5
                assert result["measure"]["tiny_text_count"] <= 3
            shot = ROOT / result["screenshot"]
            assert shot.is_file() and shot.stat().st_size > 1000, f"{route} {result['width_name']}: screenshot missing"


# ---------------------------------------------------------------------------
# The running service serves the evidence (matrix rows RESP-SERVED/AUTH/UNKNOWN-ROUTE)
# ---------------------------------------------------------------------------
def test_responsive_evidence_is_served_to_signed_in_staff(client, headers) -> None:
    response = client.get("/api/governance/responsive-evidence", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "passed", body["failing_checks"]
    assert body["headed"] is True
    assert body["persona"] == "nurse"
    assert "L3-VIS-responsive.spec.ts" in body["criteria"]
    assert REQUIRED_ROUTES <= set(body["routes"])
    for route, entry in body["routes"].items():
        assert entry["passed"] is True, (route, entry["failing_checks"])
        assert entry["widths"] == REQUIRED_WIDTHS, (route, entry["widths"])
    detail = client.get("/api/governance/responsive-evidence", params={"route": "/ward"}, headers=headers)
    assert detail.status_code == 200
    assert detail.json()["route"] == "/ward"
    assert [r["width_name"] for r in detail.json()["results"]] == REQUIRED_WIDTHS


def test_responsive_evidence_is_refused_without_a_token(client) -> None:
    response = client.get("/api/governance/responsive-evidence")
    assert response.status_code == 401
    assert "routes" not in response.json()


def test_responsive_evidence_for_an_unaudited_route_is_not_invented(client, headers) -> None:
    response = client.get(
        "/api/governance/responsive-evidence", params={"route": "/never-audited"}, headers=headers
    )
    assert response.status_code == 404
    assert "/never-audited" in response.json()["detail"]


def test_absent_evidence_is_reported_absent_not_fabricated(client, headers, monkeypatch, tmp_path) -> None:
    from nursing_station import main

    monkeypatch.setattr(main, "RESPONSIVE_EVIDENCE_PATH", tmp_path / "missing.json")
    response = client.get("/api/governance/responsive-evidence", headers=headers)
    assert response.status_code == 503
    assert "absent" in response.json()["detail"]
