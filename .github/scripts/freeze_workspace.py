"""freeze_workspace: enforce the "freeze new workspace creation" rule.

No new team-specific workspaces should be created. All new APIs must be placed
into one of the target domain workspaces.

A PR creates a new workspace if it adds a ``workspace.json`` whose containing
directory name is not already listed in ``config/ci.json::domains``. CODEOWNERS
routes new top-level paths to the platform team via the catch-all rule, but
this CI check makes the intent explicit and fails the PR with a clear message
instead of silently relying on review.
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
    load_config,
    read_changed_files,
)


def _workspace_dir_name(rel_path: str, workspace_root: str) -> str | None:
    """If ``rel_path`` is a workspace.json under workspace_root, return the dir name."""
    rel = rel_path.replace("\\", "/")
    root = workspace_root.rstrip("/") + "/"
    if not rel.startswith(root):
        return None
    if not rel.endswith("/workspace.json"):
        return None
    remainder = rel[len(root) :]
    parts = remainder.split("/")
    if len(parts) != 2 or parts[1] != "workspace.json":
        return None
    return parts[0]


def check(
    changed_files: Sequence[str],
    repo_root: str,
    config: CIConfig,
) -> list[Violation]:
    violations: list[Violation] = []
    known = {d.name for d in config.domains}
    for path in changed_files:
        ws = _workspace_dir_name(path, config.workspace_root)
        if ws is None:
            continue
        # Only flag *newly created* workspace.json files (path exists on disk but
        # not in the existing known-domain list). We treat "file on disk + dir
        # not in domains list" as the creation signal — the file is the diff.
        if ws not in known and (Path(repo_root) / path).is_file():
            violations.append(
                Violation(
                    rule="freeze-workspace",
                    path=path,
                    message=(
                        f"new workspace '{ws}' is not in config/ci.json::domains. "
                        "The workspace-creation policy freezes new "
                        "workspace creation; new APIs must go into one of the "
                        "existing target domain workspaces. If a new workspace "
                        "is genuinely required, add it to config/ci.json::domains "
                        "in a separate platform-team PR first."
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
