"""tier_check: every ``workspace.json`` must declare a valid resiliency tier.

Source: PDF §"Resiliency, Reliability, RTO, and RPO Awareness". Each domain
workspace is classified Gold (regulated, monitored), Silver (best-effort), or
Bronze (sandbox). The tier drives downstream controls (e.g. JWT validation
required on Gold, no resiliency guarantees on Bronze).

This check runs on PRs that touch any ``workspace.json`` and rejects the PR
if the file is missing a ``tier`` field, has an unknown tier, or — for an
``active`` workspace — declares the Bronze tier (Bronze is sandbox-only and
must remain ``active: false`` for the demo POC).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from _common import (
    CIConfig,
    Violation,
    build_arg_parser,
    emit,
    filter_existing,
    load_config,
    read_changed_files,
)


def _is_workspace_json(path: str) -> bool:
    return path.endswith("/workspace.json")


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    ws_files = [p for p in changed_files if _is_workspace_json(p)]
    valid = {t.lower() for t in config.valid_tiers}
    for rel_path in filter_existing(ws_files, repo_root):
        try:
            payload = json.loads(
                (Path(repo_root) / rel_path).read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            violations.append(
                Violation(
                    rule="tier-check",
                    path=rel_path,
                    message=f"workspace.json is not valid JSON: {exc.msg}",
                )
            )
            continue
        if not isinstance(payload, dict):
            violations.append(
                Violation(
                    rule="tier-check",
                    path=rel_path,
                    message="workspace.json must be a JSON object",
                )
            )
            continue
        tier = payload.get("tier")
        if not isinstance(tier, str):
            violations.append(
                Violation(
                    rule="tier-check",
                    path=rel_path,
                    message=(
                        "workspace.json is missing a string 'tier' field. "
                        f"Allowed values: {sorted(valid)}."
                    ),
                )
            )
            continue
        if tier.lower() not in valid:
            violations.append(
                Violation(
                    rule="tier-check",
                    path=rel_path,
                    message=(
                        f"tier '{tier}' is not one of {sorted(valid)}."
                    ),
                )
            )
            continue
        active = bool(payload.get("active", False))
        if tier.lower() == "bronze" and active:
            violations.append(
                Violation(
                    rule="tier-check",
                    path=rel_path,
                    message=(
                        "Bronze tier carries no resiliency guarantees (PDF §Resiliency). "
                        "An active production workspace cannot be Bronze."
                    ),
                )
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser(__doc__ or "")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    changed = read_changed_files(args.changed_files)
    return emit(check(changed, args.repo_root, config))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
