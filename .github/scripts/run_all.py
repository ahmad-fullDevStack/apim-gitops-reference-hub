"""run_all: orchestrator that runs all six CI checks against a single changed-file
list, prints a consolidated report, and returns a non-zero exit code on any
failure.

Used by ``.github/workflows/pr-validation.yml`` so the workflow has one step
to wire up. The Azure DevOps equivalent invokes this same script.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

import backend_allowlist
import base_inheritance
import freeze_workspace
import kv_uri_allowlist
import naming_convention
import path_scope
import secret_scan
import tier_check
import versioning
from _common import Violation, build_arg_parser, emit, load_config, read_changed_files

_CHECKS = (
    ("path-scope", path_scope.check),
    ("base-inheritance", base_inheritance.check),
    ("kv-uri-allowlist", kv_uri_allowlist.check),
    ("backend-allowlist", backend_allowlist.check),
    ("naming-convention", naming_convention.check),
    ("secret-scan", secret_scan.check),
    ("tier-check", tier_check.check),
    ("freeze-workspace", freeze_workspace.check),
    ("versioning", versioning.check),
)


def run(changed: Sequence[str], repo_root: str, config_path: str | None) -> int:
    config = load_config(config_path)
    all_violations: list[Violation] = []
    for name, fn in _CHECKS:
        violations = fn(changed, repo_root, config)
        print(f"\n=== {name}: {'PASS' if not violations else f'{len(violations)} violation(s)'} ===")
        if violations:
            all_violations.extend(violations)
    return emit(all_violations, stream=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser(__doc__ or "")
    args = parser.parse_args(argv)
    changed = read_changed_files(args.changed_files)
    return run(changed, args.repo_root, args.config)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
