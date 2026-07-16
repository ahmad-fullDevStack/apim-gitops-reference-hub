"""path_scope: every changed file under a team's folder must be authored by a
member of that team's reviewer group.

This check is the **defence in depth** for the CODEOWNERS / branch-policy
path-scoped required-reviewer control. CODEOWNERS prevents *merge* without the
right reviewer; this check prevents the PR from even being valid if a single
PR touches multiple teams' folders, which is the most common way a buggy
required-reviewer policy gets bypassed.

Pass criteria
-------------
Every changed file must be in **exactly one** of:

- a single team's folder;
- a platform-owned path declared in ``config/ci.json::platform_paths``.

A PR that mixes a team-folder file with another team's folder file (or with a
platform-only file) fails. The intent is that each PR is reviewable by exactly
one ownership group.
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


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    teams_touched: dict[str, list[str]] = {}
    platform_touched: list[str] = []
    unowned: list[str] = []

    for path in changed_files:
        team = config.team_for_path(path)
        if team is not None:
            teams_touched.setdefault(team.name, []).append(path)
            continue
        if config.is_platform_path(path):
            platform_touched.append(path)
            continue
        # Allow files that are not under the apim-config tree at all (e.g.
        # workflow changes, infra changes). Those PRs are scoped by their own
        # CODEOWNERS entries.
        if not path.startswith(config.workspace_root.rstrip("/") + "/"):
            continue
        unowned.append(path)

    violations: list[Violation] = []

    if len(teams_touched) > 1:
        names = ", ".join(sorted(teams_touched))
        for _team_name, paths in sorted(teams_touched.items()):
            for p in paths:
                violations.append(
                    Violation(
                        rule="path-scope",
                        path=p,
                        message=(
                            f"PR touches multiple team folders ({names}); "
                            "split into one PR per team."
                        ),
                    )
                )

    if teams_touched and platform_touched:
        for p in platform_touched:
            violations.append(
                Violation(
                    rule="path-scope",
                    path=p,
                    message=(
                        "PR mixes platform-owned files with team-owned files; "
                        "platform changes must be a separate PR."
                    ),
                )
            )

    for p in unowned:
        violations.append(
            Violation(
                rule="path-scope",
                path=p,
                message=(
                    "File is under the workspace tree but not under any "
                    "team's folder or a declared platform path."
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


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess tests
    sys.exit(main())
