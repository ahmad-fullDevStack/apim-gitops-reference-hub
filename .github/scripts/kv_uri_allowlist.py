"""kv_uri_allowlist: every Key Vault URI referenced from a team's folder must
point at a Key Vault on that team's allowlist.

Detects two failure modes:

1. A team references another team's vault (cross-team secret reference).
2. A team references a vault outside any declared allowlist (typo, copy-paste
   from another environment).

Scans every changed file under ``apim-config/`` for ``*.vault.azure.net``
hostnames and matches the DNS prefix against the allowlist of the team that
owns the file's folder.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from _common import (
    CIConfig,
    Violation,
    build_arg_parser,
    emit,
    extract_kv_hostnames,
    filter_existing,
    load_config,
    read_changed_files,
)


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    for rel_path in filter_existing(changed_files, repo_root):
        team = config.team_for_path(rel_path)
        if team is None:
            continue  # not a team-owned file
        text = (Path(repo_root) / rel_path).read_text(encoding="utf-8", errors="replace")
        for hostname in extract_kv_hostnames(text):
            if hostname not in {kv.lower() for kv in team.allowed_key_vaults}:
                violations.append(
                    Violation(
                        rule="kv-uri-allowlist",
                        path=rel_path,
                        message=(
                            f"team '{team.name}' is not allowed to reference vault "
                            f"'{hostname}'. Allowlist: {sorted(team.allowed_key_vaults)}"
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
