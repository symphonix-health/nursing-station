"""Drift lint: bidirectional policy/source consistency checks.

Two invariants per service (design doc section 6):

1. Every capability referenced by a gate in source must be declared in the
   policy (or in ``reserved_capabilities``). A gate naming an unknown
   capability is a startup-time failure waiting to happen.
2. Every capability in the policy must be referenced by at least one gate,
   or be explicitly marked in ``reserved_capabilities``. Dead capabilities
   mislead reviewers and inflate the audit surface.

Used by:
    - per-repo pytest (``test_policy_capability_names_declared``)
    - CI gate: ``python -m symphonix_rbac.lint --policy ... --src ...``
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path

_SKIP_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git",
              "dist", "build", ".next"}


@dataclass
class LintReport:
    undeclared_in_policy: list[str] = field(default_factory=list)
    unused_in_source: list[str] = field(default_factory=list)
    gates_found: int = 0

    @property
    def ok(self) -> bool:
        return not self.undeclared_in_policy and not self.unused_in_source

    def summary(self) -> str:
        lines = [f"gates found: {self.gates_found}"]
        if self.undeclared_in_policy:
            lines.append(f"[FAIL] capabilities used in source but not in policy: "
                         f"{sorted(set(self.undeclared_in_policy))}")
        if self.unused_in_source:
            lines.append(f"[WARN] capabilities in policy but unused in source: "
                         f"{sorted(set(self.unused_in_source))}")
        if self.ok:
            lines.append("[OK] policy/source capability sets are consistent")
        return "\n".join(lines)


def _py_files(src: Path):
    for p in src.rglob("*.py"):
        if not any(part in _SKIP_DIRS for part in p.parts):
            yield p


def find_capability_refs(src: Path) -> set[str]:
    """Find every literal capability string passed to a capability gate.

    Recognised gate shapes:
    - policy.require(...) / policy.allowed(...), require_capability(...)
      (direct engine calls; ``allowed`` covers imperative in-handler gates)
    - any local alias ending in ``_cap``/``_capability`` (per-module wrappers
      that forward to PolicyEngine.require with auth_dependency=...), e.g.
      ``_cap("care.submit_transfer_of_care")``.
    """
    refs: set[str] = set()

    def _is_gate_name(name: str) -> bool:
        return (
            name in ("require", "require_capability", "allowed")
            or name.endswith("_cap")
            or name.endswith("_capability")
        )

    for py in _py_files(src):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else "")
            if not _is_gate_name(name):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    refs.add(arg.value)
    return refs


def lint(policy_path: Path, src: Path) -> LintReport:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    declared = set()
    for caps in policy["roles"].values():
        declared.update(caps)
    reserved = set()
    for r in policy.get("reserved_capabilities", []):
        reserved.add(r if isinstance(r, str) else r["name"])
    declared |= reserved

    used = find_capability_refs(src)
    report = LintReport()
    report.gates_found = len(used)
    # Check 1: every capability a gate names must be declared (reserved counts
    # as declared - reserving a name before its first gate is the intended flow).
    report.undeclared_in_policy = sorted(used - declared)
    # Check 2: every granted capability must be used, OR be reserved.
    report.unused_in_source = sorted((declared - reserved) - used)
    return report


def main() -> int:  # pragma: no cover - thin CLI wrapper
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True, type=Path)
    ap.add_argument("--src", required=True, type=Path)
    args = ap.parse_args()
    report = lint(args.policy, args.src)
    print(report.summary())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())