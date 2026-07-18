"""Run the real registered-port Nursing Station Phase 2 seeded journey.

The runner reuses a healthy BulletTrain api_gateway when one already owns its
registered port and otherwise starts it. It starts Nursing Station only when its
registered port is free. Authoritative sibling services must already be running
on their registered ports. It never allocates an alternate port.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
BULLETTRAIN = WORKSPACE / "BulletTrain"
PORTS_PATH = BULLETTRAIN / "config" / "ports.json"
BULLETTRAIN_INTEGRATION_ENGINE_URL = "http://127.0.0.1"


def _find_service(value: Any, service: str) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    candidate = value.get(service)
    if isinstance(candidate, dict) and "port" in candidate:
        return candidate
    for child in value.values():
        found = _find_service(child, service)
        if found:
            return found
    return None


def port(service: str) -> int:
    registry = json.loads(PORTS_PATH.read_text(encoding="utf-8"))
    registry_key = {"hmis": "ehr_hmis"}.get(service, service)
    row = _find_service(registry, registry_key)
    if not row:
        raise RuntimeError(f"No BulletTrain registered port for {service}")
    return int(row["port"])


def listening(port_number: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(0.4)
        return connection.connect_ex(("127.0.0.1", port_number)) == 0


def terminate_process(process: subprocess.Popen[str]) -> None:
    """Stop the owned runtime, including the Windows venv-launcher child."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        return
    process.terminate()


def wait_json(url: str, timeout: float = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    detail = "no response"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code < 500:
                return response.json()
            detail = f"HTTP {response.status_code}"
        except (httpx.HTTPError, ValueError) as exc:
            detail = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for {url}: {detail}")


def main() -> int:
    inbound_secret = secrets.token_urlsafe(32)
    service_token = secrets.token_urlsafe(32)
    source_services = (
        "picis_system", "lis", "pacs_ris", "pharmacy_system",
        "blood_transfusion", "hmis",
    )
    base_urls = {name: f"http://127.0.0.1:{port(name)}" for name in source_services}
    for name in source_services:
        if not listening(port(name)):
            raise RuntimeError(f"Required registered service {name} is not listening on {port(name)}")

    hub_port = port("api_gateway")
    nursing_port = port("nursing_station")
    reuse_hub = listening(hub_port)
    if listening(nursing_port):
        raise RuntimeError(f"Refusing to conflict with existing nursing_station listener on {nursing_port}")

    with tempfile.TemporaryDirectory(prefix="nursing-phase2-") as temp:
        temp_path = Path(temp)
        hub_env = os.environ.copy()
        hub_env.update(
            {
                "AUTH_MODE": "off",
                "BT_PICIS_SYSTEM_BASE_URL": base_urls["picis_system"],
                "BT_LIS_BASE_URL": base_urls["lis"],
                "BT_PACS_RIS_BASE_URL": base_urls["pacs_ris"],
                "BT_PHARMACY_SYSTEM_BASE_URL": base_urls["pharmacy_system"],
                "BT_BLOOD_TRANSFUSION_BASE_URL": base_urls["blood_transfusion"],
                "BT_HMIS_BASE_URL": base_urls["hmis"],
                "BT_NURSING_STATION_BASE_URL": f"http://127.0.0.1:{nursing_port}",
                "BT_NURSING_STATION_WEBHOOK_HMAC_SECRET": inbound_secret,
            }
        )
        nursing_env = os.environ.copy()
        nursing_env.update(
            {
                "PYTHONPATH": str(ROOT / "backend"),
                "NURSING_STATION_DB": str(temp_path / "nursing.db"),
                "NURSING_STATION_HUB_URL": f"http://127.0.0.1:{hub_port}",
                "NURSING_STATION_HUB_TOKEN": service_token,
                "NURSING_STATION_INBOUND_HMAC_SECRET": inbound_secret,
            }
        )
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        with (temp_path / "hub.log").open("w", encoding="utf-8") as hub_log, (
            temp_path / "nursing.log"
        ).open("w", encoding="utf-8") as nursing_log:
            processes = []
            if not reuse_hub:
                processes.append(subprocess.Popen(
                    [str(BULLETTRAIN / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "services.api_gateway.main:app", "--host", "127.0.0.1", "--port", str(hub_port)],
                    cwd=BULLETTRAIN, env=hub_env, stdout=hub_log, stderr=subprocess.STDOUT,
                    creationflags=flags,
                ))
            processes.append(subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "nursing_station.main:app", "--host", "127.0.0.1", "--port", str(nursing_port)],
                    cwd=ROOT, env=nursing_env, stdout=nursing_log, stderr=subprocess.STDOUT,
                    creationflags=flags,
                ))
            try:
                wait_json(f"http://127.0.0.1:{hub_port}/health")
                health = wait_json(f"http://127.0.0.1:{nursing_port}/health")
                if health.get("integrations") != "configured-bullettrain-hub":
                    raise RuntimeError("Nursing Station did not report configured hub mediation")
                client = httpx.Client(base_url=f"http://127.0.0.1:{nursing_port}", timeout=30)
                login = client.post("/api/auth/login", json={"email": "amina.okafor@nursing.test", "password": "Nursing2026!"})
                login.raise_for_status()
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                refreshed = client.post("/api/patients/pat-005/integrations/refresh", headers=headers)
                refreshed.raise_for_status()
                refresh_body = refreshed.json()
                if not refresh_body.get("all_succeeded") or len(refresh_body.get("results", [])) != 5:
                    raise RuntimeError(f"Seeded refresh did not succeed: {refresh_body}")
                context = client.get("/api/patients/pat-005/integrations", headers=headers)
                context.raise_for_status()
                if any(not source.get("snapshot") for source in context.json()["sources"]):
                    raise RuntimeError("At least one authoritative source snapshot is missing")
                lis_source = next(source for source in context.json()["sources"] if source["source_system"] == "lis")
                critical_results = [
                    row for row in lis_source["snapshot"]["data"].get("results", [])
                    if row.get("interpretation_flag") in {"critical_low", "critical_high"}
                ]
                if not critical_results:
                    raise RuntimeError("The real seeded LIS context has no governed critical result")
                result = critical_results[0]
                event_id = f"evt-lis-nursing-{result['id']}"
                hub_event = {
                    "tenant_id": "tenant-st-brigids",
                    "actor_id": "lis",
                    "correlation_id": event_id,
                    "operation": "notify",
                    "standard": "fhir-r4-subscription-semantics",
                    "resource_type": "CriticalResultAlert",
                    "payload": {
                        "event_id": event_id,
                        "source_system": "lis",
                        "source_patient_id": "9991000003",
                        "result_id": result["id"],
                        "test_name": result["test_name"],
                        "result_value": result["value"],
                        "unit": result["unit"],
                        "interpretation": result["interpretation_flag"],
                        "observed_at": result["verified_at"] or result["tested_at"],
                        "severity": "critical",
                    },
                    "purpose_of_use": "treatment",
                    "scopes": ["nursing.critical-result.notify"],
                    "roles": ["system"],
                    "source_system": "lis",
                }
                delivered = httpx.post(
                    f"http://127.0.0.1:{hub_port}/v1/connectors/nursing_station/exchange",
                    json=hub_event,
                    headers={"Authorization": f"Bearer {service_token}"},
                    timeout=15,
                )
                if delivered.status_code >= 400:
                    raise RuntimeError(
                        f"BulletTrain alert delivery failed: HTTP "
                        f"{delivered.status_code} {delivered.text}"
                    )
                if delivered.json().get("status") != "success":
                    raise RuntimeError(f"BulletTrain alert delivery failed: {delivered.text}")
                alerts = client.get("/api/alerts", headers=headers)
                alerts.raise_for_status()
                if not any(row["event_id"] == event_id for row in alerts.json()["alerts"]):
                    raise RuntimeError("Accepted critical-result alert is missing from the nurse feed")
                manager = client.post("/api/auth/login", json={"email": "grace.mensah@nursing.test", "password": "Nursing2026!"})
                manager.raise_for_status()
                manager_headers = {"Authorization": f"Bearer {manager.json()['access_token']}"}
                report = client.post("/api/wards/ward-med-a/hmis-measures", headers=manager_headers)
                if report.status_code >= 400:
                    raise RuntimeError(f"HMIS submission failed: HTTP {report.status_code} {report.text}")
                encoded = json.dumps(report.json()["measures"]["counts"])
                if "9991000003" in encoded or "Ava Patel" in encoded or "pat-ava" in encoded:
                    raise RuntimeError("HMIS payload contains patient-level data")
                print(json.dumps({"status": "passed", "sources": 5, "patient": "pat-005", "hmis_receipt": True, "critical_alert": True, "ports": "registered"}))
                return 0
            finally:
                for process in reversed(processes):
                    terminate_process(process)
                for process in reversed(processes):
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
