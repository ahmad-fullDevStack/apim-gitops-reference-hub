"""naming_convention: resources under a team's folder must be prefixed with
that team's resource prefix.

A 'resource' here is any directory or top-level JSON/YAML file under
``apis/``, ``backends/``, ``products/``, ``subscriptions/``, ``named-values/``,
or ``policy-fragments/`` within a team's folder. The basename (directory name
or file stem) must start with ``<team.prefix>-``.

The rule prevents a Team A member from creating ``teamb-orders`` inside Team
A's folder and impersonating Team B's resources at the APIM level (where
resource names, not folder paths, are the identifier).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from _common import (
    CIConfig,
    Violation,
    build_arg_parser,
    emit,
    load_config,
    read_changed_files,
)

RESOURCE_KINDS: tuple[str, ...] = (
    "apis",
    "backends",
    "products",
    "subscriptions",
    "named-values",
    "policy-fragments",
    "version-sets",
)


def _resource_name_for(path: str, team_folder: str, kind: str) -> str | None:
    """Return the resource basename (directory or file stem) under ``kind``."""
    parts = path.split("/")
    team_parts = team_folder.rstrip("/").split("/")
    if parts[: len(team_parts)] != team_parts:
        return None
    suffix = parts[len(team_parts) :]
    if len(suffix) < 2 or suffix[0] != kind:
        return None
    second = suffix[1]
    if "." in second and len(suffix) == 2:
        return second.rsplit(".", 1)[0]
    return second


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    seen: set[tuple[str, str, str]] = set()
    for path in changed_files:
        team = config.team_for_path(path)
        if team is None:
            continue
        for kind in RESOURCE_KINDS:
            name = _resource_name_for(path, team.folder, kind)
            if name is None:
                continue
            key = (team.name, kind, name)
            if key in seen:
                continue
            seen.add(key)
            required_prefix = f"{team.prefix}-"
            if not name.lower().startswith(required_prefix.lower()):
                violations.append(
                    Violation(
                        rule="naming-convention",
                        path=path,
                        message=(
                            f"{kind} resource '{name}' under team '{team.name}' "
                            f"must be prefixed with '{required_prefix}'."
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
