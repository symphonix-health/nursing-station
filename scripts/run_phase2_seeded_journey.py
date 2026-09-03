"""Run the real registered-port Nursing Station Phase 2 seeded journey.

The runner owns every absent dependency needed by the journey. It reuses an
existing API Gateway only through an explicit credential/auth contract; a
health response alone does not prove compatible connector routing. Every
runner-owned service uses an isolated database and all processes remain on
their canonical registered ports.
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
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(os.getenv("SYMPHONIX_WORKSPACE_ROOT", ROOT.parent)).resolve()
BULLETTRAIN = WORKSPACE / "BulletTrain"
PORTS_PATH = BULLETTRAIN / "config" / "ports.json"
BULLETTRAIN_INTEGRATION_ENGINE_URL = "http://127.0.0.1"


def emit_progress(stage: str, **details: Any) -> None:
    """Emit machine-readable lifecycle evidence for external supervisors."""

    print(
        "NURSING_PHASE2_PROGRESS "
        + json.dumps({"stage": stage, **details}, sort_keys=True),
        flush=True,
    )


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_hub_contract(*, reuse_hub: bool) -> tuple[str, str]:
    """Return the bearer token and auth mode for the exact gateway lifecycle.

    A listener identity from ``/health`` is necessary but not sufficient for
    reuse: it does not attest which connector URLs or authentication policy the
    existing process loaded. Reuse therefore requires explicit operator-owned
    configuration.

    A runner-owned gateway is launched in ``dev`` with a NAMED principal (see the
    hub_env block below), not with authentication off. The two halves must agree:
    this function tells the client which credential contract to build, and
    returning "off" while the hub runs in "dev" would send bare bearer tokens to
    a gateway expecting the dev assertion headers. That mismatch was introduced
    when the hub_env was hardened and is fixed here -- it is exactly the kind of
    half-change that a run catches and a read does not.
    """

    if not reuse_hub:
        return secrets.token_urlsafe(32), "dev"
    if not _enabled("NURSING_STATION_REUSE_REGISTERED_HUB"):
        raise RuntimeError(
            "Registered api_gateway port is already occupied. Refusing to infer "
            "connector routing or authentication from /health alone. Stop the "
            "owning runtime, or explicitly set NURSING_STATION_REUSE_REGISTERED_HUB=1 "
            "with NURSING_STATION_HUB_TOKEN and NURSING_STATION_HUB_AUTH_MODE."
        )
    token = os.getenv("NURSING_STATION_HUB_TOKEN", "").strip()
    auth_mode = os.getenv("NURSING_STATION_HUB_AUTH_MODE", "").strip().lower()
    if not token or not auth_mode:
        raise RuntimeError(
            "Explicit gateway reuse requires both NURSING_STATION_HUB_TOKEN and "
            "NURSING_STATION_HUB_AUTH_MODE; random credentials are never tried "
            "against an independently owned listener."
        )
    return token, auth_mode


def service_auth_headers(
    *,
    token: str,
    auth_mode: str,
    subject: str,
    role: str,
    scopes: str,
    tenant: str,
) -> dict[str, str]:
    """Build headers without leaking the dev assertion contract into OIDC."""

    headers = {"Authorization": f"Bearer {token}"}
    if auth_mode == "dev":
        headers.update(
            {
                "X-Dev-Subject": subject,
                "X-Dev-Roles": role,
                "X-Dev-Scopes": scopes,
                "X-Dev-Tenant": tenant,
            }
        )
    return headers


@dataclass(frozen=True)
class ServiceSpec:
    """Real sibling process required by the Phase 2 journey."""

    key: str
    repo: str
    workdir: str
    app: str
    health_service: str
    env: tuple[tuple[str, str], ...]

    @property
    def cwd(self) -> Path:
        return WORKSPACE / self.repo / self.workdir


def _sqlite_url(path: Path, *, async_driver: bool = True) -> str:
    prefix = "sqlite+aiosqlite:///" if async_driver else "sqlite:///"
    return prefix + path.resolve().as_posix()


def source_service_specs(temp_path: Path) -> tuple[ServiceSpec, ...]:
    """Return the real seeded services and their isolated runtime settings."""

    return (
        ServiceSpec(
            key="picis_system",
            repo="picis-system",
            workdir=".",
            app="picis_system.main:app",
            health_service="picis-system",
            env=(("PICIS_DATABASE_URL", _sqlite_url(temp_path / "picis.db", async_driver=False)),),
        ),
        ServiceSpec(
            key="lis",
            repo="lis",
            workdir="backend",
            app="src.main:app",
            health_service="lis",
            env=(
                ("LIS_DEBUG", "1"),
                ("LIS_AUTH_MODE", "dev"),
                ("LIS_DATABASE_URL", _sqlite_url(temp_path / "lis.db")),
            ),
        ),
        ServiceSpec(
            key="pacs_ris",
            repo="pacs-ris",
            workdir="backend",
            app="src.main:app",
            health_service="pacs-ris",
            env=(
                ("PACS_RIS_DEBUG", "1"),
                ("PACS_RIS_AUTH_MODE", "dev"),
                ("PACS_RIS_DATABASE_URL", _sqlite_url(temp_path / "pacs-ris.db")),
                ("PACS_RIS_BLOB_ROOT", str(temp_path / "pacs-ris-blobs")),
            ),
        ),
        ServiceSpec(
            key="pharmacy_system",
            repo="pharmacy-system",
            workdir="backend",
            app="src.main:app",
            health_service="pharmacy-system",
            env=(
                ("PHARMACY_SYSTEM_DEBUG", "1"),
                ("PHARMACY_SYSTEM_AUTH_MODE", "dev"),
                (
                    "PHARMACY_SYSTEM_DATABASE_URL",
                    _sqlite_url(temp_path / "pharmacy-system.db"),
                ),
            ),
        ),
        ServiceSpec(
            key="blood_transfusion",
            repo="blood-transfusion",
            workdir="backend",
            app="blood_transfusion.main:app",
            health_service="blood-transfusion",
            env=(
                ("BLOOD_TRANSFUSION_DEBUG", "true"),
                ("BLOOD_TRANSFUSION_RESET_ON_START", "true"),
                (
                    "BLOOD_TRANSFUSION_DATABASE_URL",
                    _sqlite_url(temp_path / "blood-transfusion.db"),
                ),
            ),
        ),
        ServiceSpec(
            key="hmis",
            repo="HMIS",
            workdir="backend",
            app="src.main:app",
            health_service="hmis-backend",
            env=(
                ("HMIS_DEBUG", "true"),
                ("HMIS_AUTH_MODE", "dev"),
                ("HMIS_MODE", "ci"),
                ("HMIS_SEED_PROFILE", "dev"),
                ("HMIS_BUILD_ID", "nursing-phase2-runner"),
                ("HMIS_DATABASE_URL", _sqlite_url(temp_path / "hmis.db")),
            ),
        ),
    )


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


def wait_json(
    url: str,
    timeout: float = 120,
    *,
    expected_service: str | None = None,
    process: subprocess.Popen[str] | None = None,
) -> dict[str, Any]:
    """Wait for a successful JSON response and verify service identity."""

    deadline = time.monotonic() + timeout
    detail = "no response"
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                f"Process {process.pid} exited {process.returncode} while waiting for {url}"
            )
        try:
            response = httpx.get(url, timeout=2)
            if response.is_success:
                body = response.json()
                if not isinstance(body, dict):
                    detail = f"expected JSON object, got {type(body).__name__}"
                elif expected_service and body.get("service") != expected_service:
                    raise RuntimeError(
                        f"Listener identity mismatch at {url}: expected service "
                        f"{expected_service!r}, got {body.get('service')!r}"
                    )
                else:
                    return body
            detail = f"HTTP {response.status_code}"
        except (httpx.HTTPError, ValueError) as exc:
            detail = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for {url}: {detail}")


def start_or_verify_service(
    spec: ServiceSpec,
    *,
    log_dir: Path,
    stack: ExitStack,
    owned_processes: list[subprocess.Popen[str]],
    log_paths: list[Path],
) -> None:
    """Start one real sibling, or verify a pre-existing listener exactly."""

    service_port = port(spec.key)
    health_url = f"http://127.0.0.1:{service_port}/health"
    if listening(service_port):
        wait_json(health_url, timeout=5, expected_service=spec.health_service)
        emit_progress("service_ready", service=spec.key, ownership="reused")
        return
    if not spec.cwd.is_dir():
        raise RuntimeError(f"Required service directory does not exist: {spec.cwd}")

    log_path = log_dir / f"{spec.key}.log"
    log_file = stack.enter_context(log_path.open("w", encoding="utf-8"))
    child_env = os.environ.copy()
    child_env.update(spec.env)
    child_env["PYTHONUNBUFFERED"] = "1"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            spec.app,
            "--host",
            "127.0.0.1",
            "--port",
            str(service_port),
        ],
        cwd=spec.cwd,
        env=child_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    owned_processes.append(process)
    log_paths.append(log_path)
    wait_json(
        health_url,
        expected_service=spec.health_service,
        process=process,
    )
    emit_progress(
        "service_ready",
        service=spec.key,
        ownership="runner",
        pid=process.pid,
    )


def _log_tail(log_paths: list[Path]) -> str:
    sections: list[str] = []
    for log_path in log_paths:
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            text = f"<unreadable: {exc}>"
        sections.append(f"--- {log_path.name} ---\n{text[-6000:]}")
    return "\n".join(sections)


def assert_no_audit_forward_failures(log_paths: list[Path]) -> None:
    """Reject a functionally green journey that discarded audit evidence."""

    failures: list[str] = []
    for log_path in log_paths:
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise RuntimeError(f"Cannot inspect audit evidence in {log_path}: {exc}") from exc
        failures.extend(
            f"{log_path.name}: {line.strip()}"
            for line in lines
            if "audit_forwarder: post " in line and " failed" in line
        )
    if failures:
        details = "\n".join(failures[-20:])
        raise RuntimeError(f"Mandatory audit forwarding failed:\n{details}")


def main() -> int:
    emit_progress("runner_started", workspace=str(WORKSPACE))
    inbound_secret = os.getenv(
        "BT_NURSING_STATION_WEBHOOK_HMAC_SECRET",
        "bt-uat-nursing-station-webhook-hmac",
    )
    source_services = (
        "picis_system",
        "lis",
        "pacs_ris",
        "pharmacy_system",
        "blood_transfusion",
        "hmis",
    )
    base_urls = {name: f"http://127.0.0.1:{port(name)}" for name in source_services}

    hub_port = port("api_gateway")
    nursing_port = port("nursing_station")
    reuse_hub = listening(hub_port)
    if reuse_hub:
        wait_json(
            f"http://127.0.0.1:{hub_port}/health",
            timeout=5,
            expected_service="api_gateway",
        )
    service_token, hub_auth_mode = resolve_hub_contract(reuse_hub=reuse_hub)
    if listening(nursing_port):
        raise RuntimeError(f"Refusing to conflict with existing nursing_station listener on {nursing_port}")

    with tempfile.TemporaryDirectory(prefix="nursing-phase2-") as temp:
        temp_path = Path(temp)
        hub_env = os.environ.copy()
        hub_env.update(
            {
                "PYTHONUNBUFFERED": "1",
                # AUTHENTICATED, not bypassed. This launched the BulletTrain hub
                # with authentication switched off, so every exchange in the
                # journey carried no subject, no roles and no scopes -- nothing
                # the run produced could evidence authorisation, tenant isolation
                # or audit attribution, which is most of what a governed journey
                # exists to demonstrate. AUTH_MODE=dev resolves a REAL principal:
                # BulletTrain's dependencies.py refuses a request presenting no
                # subject. Least privilege for a hub exchange caller, never admin
                # or superuser -- testing as a superuser hides every permission gap.
                "AUTH_MODE": "dev",
                "DEV_AUTH_SUBJECT": "nursing-station-phase2-journey",
                "DEV_AUTH_ROLES": "service",
                "DEV_AUTH_SCOPES": "connector:exchange",
                "DEV_AUTH_TENANT_ID": "t-platform",
                # The hub's connector_exchange policy is ABAC as well as RBAC: it
                # requires a purpose_of_use and a legal_basis, and denies without
                # them with reason_code "legal_basis_not_allowed". Measured
                # 2026-09-03 against the live governed gateway: a `service`
                # principal holding connector:exchange is refused, and so is an
                # `admin` one -- this is not a privilege gap that a bigger role
                # would close, and granting one would have hidden it.
                #
                # DECLARED, not inferred: this journey retrieves a patient's
                # clinical records into a nursing station for direct care, so the
                # purpose is `treatment` and the basis is `consent`. Both are
                # values the policy enumerates. If the programme decides a
                # different basis applies to this exchange, change it here -- the
                # point is that the journey asserts one explicitly rather than
                # running with authentication off, which asserted nothing.
                "DEV_AUTH_PURPOSE_OF_USE": "treatment",
                "DEV_AUTH_LEGAL_BASIS": "consent",
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
                "PYTHONUNBUFFERED": "1",
                "PYTHONPATH": str(ROOT / "backend"),
                "NURSING_STATION_DB": str(temp_path / "nursing.db"),
                "NURSING_STATION_HUB_URL": f"http://127.0.0.1:{hub_port}",
                "NURSING_STATION_HUB_TOKEN": service_token,
                "NURSING_STATION_HUB_AUTH_MODE": hub_auth_mode,
                "NURSING_STATION_INBOUND_HMAC_SECRET": inbound_secret,
            }
        )
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        owned_processes: list[subprocess.Popen[str]] = []
        log_paths: list[Path] = []
        with ExitStack() as stack:
            try:
                for spec in source_service_specs(temp_path):
                    start_or_verify_service(
                        spec,
                        log_dir=temp_path,
                        stack=stack,
                        owned_processes=owned_processes,
                        log_paths=log_paths,
                    )

                hub_process: subprocess.Popen[str] | None = None
                if not reuse_hub:
                    hub_log_path = temp_path / "hub.log"
                    hub_log = stack.enter_context(
                        hub_log_path.open("w", encoding="utf-8")
                    )
                    log_paths.append(hub_log_path)
                    bullettrain_python = BULLETTRAIN / ".venv" / "Scripts" / "python.exe"
                    if not bullettrain_python.is_file():
                        raise RuntimeError(
                            f"BulletTrain interpreter is not installed: {bullettrain_python}"
                        )
                    hub_process = subprocess.Popen(
                        [
                            str(bullettrain_python),
                            "-m",
                            "uvicorn",
                            "services.api_gateway.main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(hub_port),
                        ],
                        cwd=BULLETTRAIN,
                        env=hub_env,
                        stdout=hub_log,
                        stderr=subprocess.STDOUT,
                        creationflags=flags,
                    )
                    owned_processes.append(hub_process)

                nursing_log_path = temp_path / "nursing.log"
                nursing_log = stack.enter_context(
                    nursing_log_path.open("w", encoding="utf-8")
                )
                log_paths.append(nursing_log_path)
                nursing_process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "nursing_station.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(nursing_port),
                    ],
                    cwd=ROOT,
                    env=nursing_env,
                    stdout=nursing_log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
                owned_processes.append(nursing_process)

                wait_json(
                    f"http://127.0.0.1:{hub_port}/health",
                    expected_service="api_gateway",
                    process=hub_process,
                )
                emit_progress(
                    "service_ready",
                    service="api_gateway",
                    ownership="reused" if reuse_hub else "runner",
                )
                health = wait_json(
                    f"http://127.0.0.1:{nursing_port}/health",
                    process=nursing_process,
                )
                if health.get("integrations") != "configured-bullettrain-hub":
                    raise RuntimeError("Nursing Station did not report configured hub mediation")
                emit_progress(
                    "service_ready",
                    service="nursing_station",
                    ownership="runner",
                )
                client = httpx.Client(base_url=f"http://127.0.0.1:{nursing_port}", timeout=30)
                login = client.post("/api/auth/login", json={"email": "amina.okafor@nursing.test", "password": "Nursing2026!"})
                login.raise_for_status()
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                refreshed = client.post("/api/patients/pat-005/integrations/refresh", headers=headers)
                refreshed.raise_for_status()
                refresh_body = refreshed.json()
                if not refresh_body.get("all_succeeded") or len(refresh_body.get("results", [])) != 5:
                    raise RuntimeError(f"Seeded refresh did not succeed: {refresh_body}")
                emit_progress("authoritative_refresh_complete", sources=5)
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
                    headers=service_auth_headers(
                        token=service_token,
                        auth_mode=hub_auth_mode,
                        subject="lis",
                        role="system",
                        scopes="nursing.critical-result.notify",
                        tenant="tenant-st-brigids",
                    ),
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
                emit_progress("critical_alert_verified", event_id=event_id)
                manager = client.post("/api/auth/login", json={"email": "grace.mensah@nursing.test", "password": "Nursing2026!"})
                manager.raise_for_status()
                manager_headers = {"Authorization": f"Bearer {manager.json()['access_token']}"}
                report = client.post("/api/wards/ward-med-a/hmis-measures", headers=manager_headers)
                if report.status_code >= 400:
                    raise RuntimeError(f"HMIS submission failed: HTTP {report.status_code} {report.text}")
                report_body = report.json()
                receipt = report_body.get("receipt") or {}
                if not receipt.get("measures") or not receipt.get("measure_definitions"):
                    raise RuntimeError("HMIS receipt did not retain the quality dataset")
                encoded = json.dumps(report_body, sort_keys=True)
                if "9991000003" in encoded or "Ava Patel" in encoded or "pat-ava" in encoded:
                    raise RuntimeError("HMIS payload contains patient-level data")
                emit_progress("hmis_aggregate_verified", contains_patient_data=False)
                assert_no_audit_forward_failures(log_paths)
                emit_progress("audit_delivery_verified", failures=0)
                print(json.dumps({"status": "passed", "sources": 5, "patient": "pat-005", "hmis_receipt": True, "critical_alert": True, "ports": "registered"}))
                return 0
            except Exception:
                print(
                    "Phase 2 service diagnostics:\n" + _log_tail(log_paths),
                    file=sys.stderr,
                )
                raise
            finally:
                for process in reversed(owned_processes):
                    terminate_process(process)
                for process in reversed(owned_processes):
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
