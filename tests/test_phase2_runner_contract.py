"""Fail-closed lifecycle contracts for the real Phase 2 journey runner."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from scripts import run_phase2_seeded_journey as runner
from scripts.run_phase2_seeded_journey import (
    HUB_IDENTITY_ENV_NAMES,
    build_runner_hub_env,
    is_hub_identity_env,
    resolve_hub_contract,
    runner_owned_hub_auth_env,
    runner_owned_hub_neutral_env,
    service_auth_headers,
)

# The principal a runner-owned gateway is launched with. Exact, not a pattern:
# a wildcard over DEV_AUTH_* would let an added key (a linked-patients list, an
# identity kind, a wider scope) widen the principal without any assertion
# noticing, so the whole DEV_AUTH_* set is pinned.
EXPECTED_HUB_PRINCIPAL = {
    "DEV_AUTH_SUBJECT": "nursing-station-phase2-journey",
    "DEV_AUTH_ROLES": "service",
    "DEV_AUTH_SCOPES": "connector:exchange",
    "DEV_AUTH_TENANT_ID": "t-platform",
    "DEV_AUTH_PURPOSE_OF_USE": "treatment",
    "DEV_AUTH_LEGAL_BASIS": "consent",
}
# Modes that authenticate nobody. BulletTrain refuses "off" in a deployed
# environment (bullettrain/security/auth/dependencies.py), and estate policy is
# that AUTH_MODE=off is being removed everywhere, so a runner-owned gateway must
# never be launched in either.
UNAUTHENTICATED_MODES = {"off", "disabled"}
PRIVILEGED_ROLES = {"admin", "superuser", "system_admin", "platform_admin"}
ANONYMOUS_SUBJECTS = {"", "anonymous", "unknown", "test-user", "admin", "system"}


def _split(value: str) -> list[str]:
    return [part for part in re.split(r"[ ,]+", value.strip()) if part]


def hub_contract_violations(auth_mode: str, hub_env: dict[str, str]) -> list[str]:
    """Return every way a runner-owned gateway contract breaks the estate rule.

    The rule: AUTH_MODE=dev with a NAMED, least-privilege principal -- never
    off, never superuser. The client half (``auth_mode``, from
    ``resolve_hub_contract``) and the hub half (``hub_env``, what the hub
    process is launched with) must also agree, or the client builds a bare
    bearer for a gateway that expects the dev assertion headers.
    """

    problems: list[str] = []
    if auth_mode in UNAUTHENTICATED_MODES:
        problems.append(f"client contract is {auth_mode!r}, which authenticates nobody")
    elif auth_mode != "dev":
        problems.append(f"client contract is {auth_mode!r}, expected 'dev'")
    hub_mode = hub_env.get("AUTH_MODE", "")
    if hub_mode in UNAUTHENTICATED_MODES:
        problems.append(f"hub is launched with AUTH_MODE={hub_mode!r}")
    if hub_mode != auth_mode:
        problems.append(f"client contract {auth_mode!r} != hub AUTH_MODE {hub_mode!r}")

    principal = {k: v for k, v in hub_env.items() if k.startswith("DEV_AUTH_")}
    if principal != EXPECTED_HUB_PRINCIPAL:
        extra = sorted(set(principal) - set(EXPECTED_HUB_PRINCIPAL))
        missing = sorted(set(EXPECTED_HUB_PRINCIPAL) - set(principal))
        changed = sorted(
            k for k in set(principal) & set(EXPECTED_HUB_PRINCIPAL)
            if principal[k] != EXPECTED_HUB_PRINCIPAL[k]
        )
        problems.append(
            f"DEV_AUTH_* principal drifted: extra={extra} missing={missing} changed={changed}"
        )

    if principal.get("DEV_AUTH_SUBJECT", "").strip().lower() in ANONYMOUS_SUBJECTS:
        problems.append("hub principal has no named subject")
    roles = set(_split(principal.get("DEV_AUTH_ROLES", "")))
    if not roles:
        problems.append("hub principal holds no role")
    if roles & PRIVILEGED_ROLES:
        problems.append(f"hub principal holds a privileged role: {sorted(roles & PRIVILEGED_ROLES)}")
    scopes = set(_split(principal.get("DEV_AUTH_SCOPES", "")))
    if scopes != {"connector:exchange"}:
        problems.append(f"hub principal scopes are {sorted(scopes)}, expected only connector:exchange")
    if any(s == "*" or s.endswith(":*") or s == "system:admin" for s in scopes):
        problems.append(f"hub principal holds a wildcard or admin scope: {sorted(scopes)}")
    return problems


def test_runner_owned_gateway_uses_isolated_auth_contract(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    token, auth_mode = resolve_hub_contract(reuse_hub=False)
    assert len(token) >= 32
    # A runner-owned gateway is launched in dev with a NAMED principal, never
    # with authentication off (see runner_owned_hub_auth_env).
    assert auth_mode == "dev"
    assert auth_mode not in UNAUTHENTICATED_MODES


def test_runner_owned_gateway_principal_is_named_and_least_privilege(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    _, auth_mode = resolve_hub_contract(reuse_hub=False)
    hub_env = runner_owned_hub_auth_env()
    assert hub_env["AUTH_MODE"] == "dev"
    principal = {k: v for k, v in hub_env.items() if k.startswith("DEV_AUTH_")}
    assert principal == EXPECTED_HUB_PRINCIPAL
    assert hub_contract_violations(auth_mode, hub_env) == []


def test_runner_owned_gateway_client_sends_dev_headers_the_hub_expects(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    token, auth_mode = resolve_hub_contract(reuse_hub=False)
    headers = service_auth_headers(
        token=token,
        auth_mode=auth_mode,
        subject="lis",
        role="system",
        scopes="nursing.critical-result.notify",
        tenant="tenant-st-brigids",
    )
    # The hub runs dev, whose principal comes from X-Dev-* assertions. A bare
    # bearer here is the half-change that returning "off" once produced.
    assert headers["X-Dev-Subject"] == "lis"
    assert headers["X-Dev-Roles"] == "system"
    assert headers["X-Dev-Tenant"] == "tenant-st-brigids"


@pytest.mark.parametrize(
    ("label", "auth_mode", "mutate"),
    [
        ("old off client contract against the dev hub", "off", lambda env: None),
        ("hub launched with AUTH_MODE=off", "dev", lambda env: env.update(AUTH_MODE="off")),
        ("hub launched with AUTH_MODE=disabled", "dev", lambda env: env.update(AUTH_MODE="disabled")),
        ("superuser role", "dev", lambda env: env.update(DEV_AUTH_ROLES="superuser")),
        ("admin alongside service", "dev", lambda env: env.update(DEV_AUTH_ROLES="service admin")),
        ("wildcard scope", "dev", lambda env: env.update(DEV_AUTH_SCOPES="*")),
        ("admin scope added", "dev", lambda env: env.update(DEV_AUTH_SCOPES="connector:exchange system:admin")),
        ("anonymous subject", "dev", lambda env: env.update(DEV_AUTH_SUBJECT="anonymous")),
        ("subject removed", "dev", lambda env: env.pop("DEV_AUTH_SUBJECT")),
        ("extra DEV_AUTH key widens the principal", "dev", lambda env: env.update(DEV_AUTH_IDENTITY_KIND="human_persona")),
        ("linked patients added", "dev", lambda env: env.update(DEV_AUTH_LINKED_PATIENTS="pat-005")),
    ],
)
def test_contract_check_rejects_the_contracts_the_estate_forbids(label, auth_mode, mutate):
    """Negative controls: the check above must be able to fail.

    Each case is a contract the estate forbids (off, superuser, wildcard, an
    unnamed or widened principal, or a client/hub disagreement). If the
    validator ever returned an empty list for one of these, the positive
    assertion on the real runner would be vacuous.
    """

    env = runner_owned_hub_auth_env()
    mutate(env)
    assert hub_contract_violations(auth_mode, env), label


def test_existing_gateway_is_not_inferred_from_open_port(monkeypatch):
    monkeypatch.delenv("NURSING_STATION_REUSE_REGISTERED_HUB", raising=False)
    monkeypatch.setenv("NURSING_STATION_HUB_TOKEN", "would-not-be-used")
    monkeypatch.setenv("NURSING_STATION_HUB_AUTH_MODE", "dev")
    with pytest.raises(RuntimeError, match="Refusing to infer"):
        resolve_hub_contract(reuse_hub=True)


def test_explicit_reuse_requires_token_and_auth_mode(monkeypatch):
    monkeypatch.setenv("NURSING_STATION_REUSE_REGISTERED_HUB", "1")
    monkeypatch.delenv("NURSING_STATION_HUB_TOKEN", raising=False)
    monkeypatch.delenv("NURSING_STATION_HUB_AUTH_MODE", raising=False)
    with pytest.raises(RuntimeError, match="requires both"):
        resolve_hub_contract(reuse_hub=True)


def test_explicit_reuse_preserves_operator_contract(monkeypatch):
    monkeypatch.setenv("NURSING_STATION_REUSE_REGISTERED_HUB", "true")
    monkeypatch.setenv("NURSING_STATION_HUB_TOKEN", "signed-operator-token")
    monkeypatch.setenv("NURSING_STATION_HUB_AUTH_MODE", "oidc")
    assert resolve_hub_contract(reuse_hub=True) == (
        "signed-operator-token",
        "oidc",
    )


def test_dev_headers_are_emitted_only_for_explicit_dev_auth():
    oidc = service_auth_headers(
        token="signed-token",
        auth_mode="oidc",
        subject="lis",
        role="system",
        scopes="nursing.critical-result.notify",
        tenant="tenant-st-brigids",
    )
    dev = service_auth_headers(
        token="dev-token",
        auth_mode="dev",
        subject="lis",
        role="system",
        scopes="nursing.critical-result.notify",
        tenant="tenant-st-brigids",
    )
    assert oidc == {"Authorization": "Bearer signed-token"}
    assert dev["X-Dev-Subject"] == "lis"
    assert dev["X-Dev-Tenant"] == "tenant-st-brigids"


# ---------------------------------------------------------------------------
# The COMPOSED hub environment.
#
# The tests above pin runner_owned_hub_auth_env(), the mapping. What the hub is
# actually launched with is that mapping merged into an inherited environment,
# and BulletTrain's dev authenticator also reads variables the mapping does not
# assign (DEV_AUTH_IDENTITY_KIND, DEV_AUTH_LINKED_PATIENTS) plus a handful that
# decide whether it authenticates at all (see HUB_IDENTITY_ENV_NAMES). Everything
# below therefore asserts on build_runner_hub_env()'s RESULT, fed hostile input.
# ---------------------------------------------------------------------------

# Every value a caller shell or a loaded .env could plausibly hand the hub to
# widen or reshape the principal. Lower-case and unknown DEV_AUTH_* names are
# included on purpose: Windows environment names are case-insensitive, and a key
# BulletTrain adds tomorrow must not need this list to be updated to be refused.
HOSTILE_INHERITED_ENV = {
    "AUTH_MODE": "off",
    "DEV_AUTH_SUBJECT": "superuser",
    "DEV_AUTH_ROLES": "admin superuser",
    "DEV_AUTH_SCOPES": "*",
    "DEV_AUTH_TENANT_ID": "t-somebody-else",
    "DEV_AUTH_PURPOSE_OF_USE": "emergency",
    "DEV_AUTH_LEGAL_BASIS": "vital_interest",
    "DEV_AUTH_IDENTITY_KIND": "human_persona",
    "DEV_AUTH_LINKED_PATIENTS": "pat-005",
    "Dev_Auth_Roles": "admin",
    "DEV_AUTH_A_KEY_BULLETTRAIN_ADDS_LATER": "widens",
    "OIDC_ISSUER": "https://issuer.hostile.invalid",
    "OIDC_JWKS_URL": "https://issuer.hostile.invalid/.well-known/jwks.json",
    "AUTH_PUBLIC_PATHS": "/v1",
    "PEP_PUBLIC_PATHS": "/v1",
    "ALLOW_DEV_AUTH_IN_K8S": "true",
}

SERVICE_ENV = {
    "PYTHONUNBUFFERED": "1",
    "BT_LIS_BASE_URL": "https://lis.example.invalid",
    "BT_NURSING_STATION_WEBHOOK_HMAC_SECRET": "runner-secret",
}


def _identity_view(env):
    return {k: v for k, v in env.items() if is_hub_identity_env(k)}


def test_composed_hub_env_is_the_runner_principal_whatever_the_caller_shell_holds():
    composed = build_runner_hub_env(HOSTILE_INHERITED_ENV, service_env=SERVICE_ENV)
    mapping = runner_owned_hub_auth_env()
    neutral = runner_owned_hub_neutral_env()

    for key, value in mapping.items():
        assert composed[key] == value, key
    for key in neutral:
        assert composed[key] == "", f"{key} must be pinned empty, not inherited"
    # No identity-affecting name survives except the ones the runner owns; in
    # particular the lower-case and unknown DEV_AUTH_* spellings are gone.
    assert set(_identity_view(composed)) == set(mapping) | set(neutral)
    assert not set(HOSTILE_INHERITED_ENV.values()) & set(_identity_view(composed).values())
    # The composed environment satisfies the estate contract as a whole: dev, a
    # named least-privilege principal, no widening extras. Empty pins read as
    # unset to BulletTrain, so they are set aside for this check and asserted
    # separately above.
    populated = {k: v for k, v in composed.items() if v != ""}
    assert hub_contract_violations("dev", populated) == []
    for key, value in SERVICE_ENV.items():
        assert composed[key] == value


@pytest.mark.parametrize("name", sorted(HOSTILE_INHERITED_ENV))
def test_no_single_inherited_identity_variable_changes_the_hub_environment(name):
    """One hostile variable at a time, so a sanitiser missing ONE name is named.

    With only that variable inherited, the composed environment must be byte for
    byte what an empty inheritance produces: nothing the caller holds may leave a
    trace in what the hub is launched with.
    """

    clean = build_runner_hub_env({}, service_env=SERVICE_ENV)
    hostile = build_runner_hub_env(
        {name: HOSTILE_INHERITED_ENV[name]}, service_env=SERVICE_ENV
    )
    assert hostile == clean, name


def test_composition_keeps_the_non_identity_environment_the_hub_needs():
    """The sanitiser is a filter, not a wipe.

    The PEP's own workload identity and the PDP address (POLICY_SERVICE_*) are
    inherited on purpose: without them every hub call is denied
    policy_unavailable. Production markers and internal enforcement only ever
    narrow the hub, so they must reach it too.
    """

    inherited = {
        "PATH": "C:/somewhere/bin",
        "POLICY_SERVICE_URL": "https://policy.example.invalid",
        "POLICY_SERVICE_SUBJECT": "gharra://agents/policy-enforcement-point",
        "BT_INTERNAL_ENFORCEMENT_MODE": "STRICT",
        "ENVIRONMENT": "production",
        "KUBERNETES_SERVICE_HOST": "10.0.0.1",
    }
    composed = build_runner_hub_env({**inherited, **HOSTILE_INHERITED_ENV})
    for key, value in inherited.items():
        assert composed[key] == value, key


@pytest.mark.parametrize(
    "name",
    ["AUTH_MODE", "DEV_AUTH_ROLES", "dev_auth_scopes", "OIDC_ISSUER", "AUTH_PUBLIC_PATHS"],
)
def test_service_env_is_refused_when_it_names_an_identity_variable(name):
    """A call site trying to set AUTH_MODE=off must fail loudly, not be papered over."""

    with pytest.raises(ValueError, match="identity-affecting"):
        build_runner_hub_env({}, service_env={name: "off"})


def test_composition_does_not_mutate_its_inputs():
    base = dict(HOSTILE_INHERITED_ENV)
    service = dict(SERVICE_ENV)
    build_runner_hub_env(base, service_env=service)
    assert base == HOSTILE_INHERITED_ENV
    assert service == SERVICE_ENV


def test_identity_env_classification_is_consistent():
    mapping = set(runner_owned_hub_auth_env())
    neutral = set(runner_owned_hub_neutral_env())
    assert not mapping & neutral, "a variable is either assigned or pinned empty, not both"
    assert all(is_hub_identity_env(k) for k in mapping | neutral)
    # Every name declared identity-affecting is handled: assigned or pinned. A
    # name listed here but neither would be dropped and then refilled from .env.
    assert HUB_IDENTITY_ENV_NAMES <= mapping | neutral
    assert set(runner_owned_hub_neutral_env().values()) == {""}


# ---------------------------------------------------------------------------
# The pin list must track what BulletTrain actually reads. Read as an AST, never
# as text: a regex over the file counts words in comments and docstrings.
# ---------------------------------------------------------------------------

BT_AUTH_DEPENDENCIES = runner.BULLETTRAIN / "bullettrain" / "security" / "auth" / "dependencies.py"
BT_PEP = runner.BULLETTRAIN / "bullettrain" / "security" / "pep.py"


def env_names_read(source: str) -> set[str]:
    """Names passed to os.getenv(...), os.environ.get(...) or os.environ[...]."""

    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        target = None
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            is_getenv = (
                isinstance(func, ast.Attribute)
                and func.attr == "getenv"
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            )
            is_environ_get = (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
            )
            if is_getenv or is_environ_get:
                target = node.args[0]
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
        ):
            target = node.slice
        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            names.add(target.value)
    return names


def test_bullettrain_auth_sources_are_present():
    for path in (BT_AUTH_DEPENDENCIES, BT_PEP):
        assert path.is_file(), (
            f"BulletTrain auth source not present at {path}; configure "
            "SYMPHONIX_WORKSPACE_ROOT or restore the required sibling. The hub "
            "environment pin list cannot be checked without it."
        )


def test_every_dev_auth_variable_bullettrain_reads_is_handled_by_the_runner():
    read = env_names_read(BT_AUTH_DEPENDENCIES.read_text(encoding="utf-8"))
    dev_auth = {name for name in read if name.startswith("DEV_AUTH_")}
    # A parse that found nothing must refuse to report, not pass vacuously.
    assert {"DEV_AUTH_SUBJECT", "DEV_AUTH_ROLES", "DEV_AUTH_SCOPES"} <= dev_auth, sorted(read)
    handled = set(runner_owned_hub_auth_env()) | set(runner_owned_hub_neutral_env())
    unhandled = sorted(dev_auth - handled)
    assert not unhandled, (
        f"BulletTrain's dev authenticator reads {unhandled}, which the runner "
        "neither assigns nor pins: an inherited value would reshape the hub "
        "principal. Add it to runner_owned_hub_neutral_env()."
    )


def test_every_pinned_identity_name_is_still_read_by_bullettrain():
    read = env_names_read(BT_AUTH_DEPENDENCIES.read_text(encoding="utf-8")) | env_names_read(
        BT_PEP.read_text(encoding="utf-8")
    )
    stale = sorted(name for name in HUB_IDENTITY_ENV_NAMES if name not in read)
    assert not stale, (
        f"{stale} are no longer read by BulletTrain's auth or PEP source; the pin "
        "list has drifted from the code it is meant to guard."
    )


def test_env_name_parser_finds_a_new_variable_and_ignores_prose():
    """Negative control: the drift check above can fail, and cannot be fooled by text."""

    source = (
        '"""Docstring naming os.getenv("DEV_AUTH_IN_A_DOCSTRING")."""\n'
        "import os\n"
        '# os.getenv("DEV_AUTH_IN_A_COMMENT")\n'
        'a = os.getenv("DEV_AUTH_NEW_WIDENER")\n'
        'b = os.environ.get("DEV_AUTH_VIA_GET", "x")\n'
        'c = os.environ["DEV_AUTH_VIA_INDEX"]\n'
    )
    found = env_names_read(source)
    assert found == {"DEV_AUTH_NEW_WIDENER", "DEV_AUTH_VIA_GET", "DEV_AUTH_VIA_INDEX"}
    handled = set(runner_owned_hub_auth_env()) | set(runner_owned_hub_neutral_env())
    assert found - handled, "a new DEV_AUTH_ variable must register as unhandled"


# ---------------------------------------------------------------------------
# main() must hand the hub the composed environment and nothing else. main() needs
# the whole fleet to run, so the call site is held structurally: the hub
# environment is built by build_runner_hub_env, never written afterwards, and is
# what the BulletTrain process is launched with.
# ---------------------------------------------------------------------------

RUNNER_SOURCE = Path(runner.__file__).read_text(encoding="utf-8")


def _main_function(source: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    return next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )


def _is_hub_env_name(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "hub_env"


def main_hub_env_violations(source: str) -> list[str]:
    """Every way main() could hand the hub something other than the composed env."""

    main = _main_function(source)
    problems: list[str] = []

    builds = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Assign)
        and any(_is_hub_env_name(target) for target in node.targets)
    ]
    if len(builds) != 1:
        problems.append(f"hub_env is assigned {len(builds)} times, expected exactly once")
    build_call = None
    if builds and isinstance(builds[0].value, ast.Call):
        callee = builds[0].value.func
        if isinstance(callee, ast.Name) and callee.id == "build_runner_hub_env":
            build_call = builds[0].value
    if build_call is None:
        problems.append("hub_env is not built by build_runner_hub_env(...)")
    else:
        service_env = next((kw.value for kw in build_call.keywords if kw.arg == "service_env"), None)
        if not isinstance(service_env, ast.Dict):
            problems.append("service_env is not a dict literal, so its keys cannot be checked")
        else:
            for key in service_env.keys:
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    problems.append("service_env has a non-literal key")
                elif is_hub_identity_env(key.value):
                    problems.append(f"service_env sets identity variable {key.value}")

    for node in ast.walk(main):
        if isinstance(node, ast.Subscript) and _is_hub_env_name(node.value) and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            problems.append("hub_env is written by subscript after it is built")
        if isinstance(node, ast.AugAssign) and _is_hub_env_name(node.target):
            problems.append("hub_env is augmented after it is built")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and _is_hub_env_name(node.func.value)
            and node.func.attr
            in {"update", "setdefault", "pop", "popitem", "clear", "__setitem__", "__delitem__"}
        ):
            problems.append(f"hub_env.{node.func.attr}() mutates it after it is built")

    hub_launches = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Popen"
        and any(
            kw.arg == "cwd" and isinstance(kw.value, ast.Name) and kw.value.id == "BULLETTRAIN"
            for kw in node.keywords
        )
    ]
    if len(hub_launches) != 1:
        problems.append(f"found {len(hub_launches)} BulletTrain launches, expected exactly one")
    for launch in hub_launches:
        env = next((kw.value for kw in launch.keywords if kw.arg == "env"), None)
        if env is None or not _is_hub_env_name(env):
            problems.append("the BulletTrain hub is not launched with env=hub_env")
    return problems


def test_main_hands_the_hub_only_the_composed_environment():
    assert main_hub_env_violations(RUNNER_SOURCE) == []


@pytest.mark.parametrize(
    ("label", "old", "new"),
    [
        (
            "AUTH_MODE=off written into hub_env after it is built",
            "        nursing_env = os.environ.copy()\n",
            '        hub_env["AUTH_MODE"] = "off"\n        nursing_env = os.environ.copy()\n',
        ),
        (
            "hub_env.update() after it is built",
            "        nursing_env = os.environ.copy()\n",
            '        hub_env.update({"DEV_AUTH_ROLES": "admin"})\n        nursing_env = os.environ.copy()\n',
        ),
        (
            "AUTH_MODE=off smuggled through service_env",
            '                "BT_LIS_BASE_URL": base_urls["lis"],\n',
            '                "AUTH_MODE": "off",\n                "BT_LIS_BASE_URL": base_urls["lis"],\n',
        ),
        (
            "hub_env no longer built by build_runner_hub_env",
            "hub_env = build_runner_hub_env(",
            "hub_env = dict(",
        ),
        (
            "hub launched with the raw shell environment",
            "env=hub_env,",
            "env=os.environ.copy(),",
        ),
    ],
)
def test_main_composition_check_rejects_a_hub_env_that_bypasses_the_builder(label, old, new):
    """Negative controls on the real runner source: each edit must be caught.

    The replacement is asserted to change the text, so a refactor of main() that
    stops matching fails here loudly instead of turning the control vacuous.
    """

    mutated = RUNNER_SOURCE.replace(old, new, 1)
    assert mutated != RUNNER_SOURCE, f"control no longer applies to main(): {label}"
    assert main_hub_env_violations(mutated), label
