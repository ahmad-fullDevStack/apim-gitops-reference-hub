"""prune_plan: compute which live APIM resources a team publish should DELETE.

The APIOps publisher runs in *additive upsert* mode (no ``COMMIT_ID``): it
creates/updates every artifact present in the scoped build folder but never
deletes a resource that is absent. That keeps a team publish from ever touching
another team's resources, but it also means removing an API from a spoke repo
does not remove it from APIM.

This module supplies the missing, deliberately *opt-in* delete half. Given:

* the central ``config/ci.json`` (team -> workspace + name prefix),
* the scoped native build the publisher just consumed (the desired state), and
* the list of resource names that currently exist live in APIM,

it returns the names that should be pruned: **live resources that carry this
team's name prefix but are no longer present in the team's desired state.**

Two safety properties fall straight out of the prefix rule:

* A prune can only ever delete ``<prefix>-*`` resources, so team-a's prune can
  never delete team-b's (or the shared / platform) resources in the shared
  workspace -- the same guarantee the scoped *build* gives the upsert path.
* Anything the team still declares is in the build folder, so it is never a
  delete candidate.

The workflow feeds the live names in (from ``az rest``) and issues the DELETEs;
this module is pure so the decision is unit-testable without touching Azure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# prune kind -> native subdir name emitted by apiops_adapter.to_native.
# APIOps v7 uses space-separated folder names for multi-word kinds.
KIND_NATIVE_SUBDIR: dict[str, str] = {
    "apis": "apis",
    "backends": "backends",
    "namedValues": "named values",
}


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def team_meta(config: dict, team_name: str) -> tuple[str, str]:
    """Return ``(workspace, prefix)`` for ``team_name`` from ci.json.

    The team folder is ``apim-config/workspaces/<workspace>/teams/<team>``; the
    workspace is the first path segment after ``workspaces/``.
    """
    for team in config.get("teams", []):
        if team["name"] == team_name:
            rel = team["folder"].split("workspaces/", 1)[1]
            workspace = rel.split("/", 1)[0]
            return workspace, team["prefix"]
    raise KeyError(f"team {team_name!r} not found in config")


def desired_names(build_root: Path, workspace: str, kind: str) -> set[str]:
    """Resource names the team still declares, from the scoped native build.

    In the native layout every resource of a kind is a directory named after the
    resource under ``workspaces/<ws>/<native-subdir>/``.
    """
    native_subdir = KIND_NATIVE_SUBDIR[kind]
    kind_dir = build_root / "workspaces" / workspace / native_subdir
    if not kind_dir.is_dir():
        return set()
    return {p.name for p in kind_dir.iterdir() if p.is_dir()}


def plan_deletions(live_names: list[str], desired: set[str], prefix: str) -> list[str]:
    """Live, team-prefixed names that are no longer desired -> delete list."""
    marker = prefix + "-"
    return sorted(
        name
        for name in dict.fromkeys(live_names)  # de-dupe, preserve nothing else
        if name.startswith(marker) and name not in desired
    )


def _read_live(path: str) -> list[str]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _cmd_meta(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    workspace, prefix = team_meta(config, args.team)
    # Tab-separated so the workflow can `read WS PREFIX < <(... meta ...)`.
    print(f"{workspace}\t{prefix}")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    workspace, prefix = team_meta(config, args.team)
    desired = desired_names(Path(args.build_root), workspace, args.kind)
    for name in plan_deletions(_read_live(args.live), desired, prefix):
        print(name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    meta = sub.add_parser("meta", help="print '<workspace>\\t<prefix>' for a team")
    meta.add_argument("--config", required=True, help="config/ci.json")
    meta.add_argument("--team", required=True, help="team name, e.g. team-a")
    meta.set_defaults(func=_cmd_meta)

    plan = sub.add_parser(
        "plan", help="print resource names to delete (one per line)"
    )
    plan.add_argument("--config", required=True, help="config/ci.json")
    plan.add_argument("--team", required=True, help="team name, e.g. team-a")
    plan.add_argument(
        "--build-root", required=True, help="scoped native build dir (desired state)"
    )
    plan.add_argument(
        "--kind", required=True, choices=sorted(KIND_NATIVE_SUBDIR), help="resource kind"
    )
    plan.add_argument(
        "--live",
        required=True,
        help="file with live resource names (one per line), or '-' for stdin",
    )
    plan.set_defaults(func=_cmd_plan)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
