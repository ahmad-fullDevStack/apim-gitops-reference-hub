"""drift_fanout: split centrally-extracted APIM drift into per-team signals.

In the hub-and-spoke model the hub owns the only extractor credential (Reader).
It extracts the whole APIM instance, folds the native layout back into the
governance layout with ``apiops_adapter to-governance`` (which routes each
resource into its owning team's folder by name prefix and quarantines
unprefixed resources under ``_unassigned/``), and then this module fans the
result out:

* :func:`fanout_teams` -- the teams that own their own spoke repo (folder under
  ``.../teams/<leaf>``). The shared slice stays platform-owned in the hub and is
  deliberately not fanned out.
* :func:`find_unassigned` -- resources APIM returned that match no team prefix.
  These are the drift alarm: something was published out-of-band or violates the
  naming convention, so no team folder can own it and a human must look.

The drift workflow consumes ``teams`` (as a build matrix) to open a
reconciliation PR in each team repo, and ``unassigned`` (as a gate) to alert the
platform team when APIM holds a resource that belongs to nobody.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

QUARANTINE = "_unassigned"


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def fanout_teams(config: dict) -> list[dict]:
    """Teams that own a spoke repo: those whose folder is under ``teams/``.

    The shared slice (``.../pensions-core/shared``) is platform-owned and stays
    in the hub, so it is intentionally excluded from the fan-out.
    """
    teams: list[dict] = []
    for team in config.get("teams", []):
        folder = team["folder"]
        marker = "workspaces/"
        if marker not in folder:
            continue
        rel = folder.split(marker, 1)[1]
        parts = rel.split("/")
        # Expect <workspace>/teams/<leaf>. Anything else (e.g. the shared slice
        # <workspace>/shared) is not a fan-out target.
        if len(parts) != 3 or parts[1] != "teams":
            continue
        teams.append(
            {
                "name": team["name"],
                "prefix": team["prefix"],
                "workspace": parts[0],
                "team_leaf": parts[2],
                "folder": folder,
            }
        )
    return teams


def find_unassigned(governance_root: Path) -> list[str]:
    """Relative posix paths of every file quarantined under an ``_unassigned/``.

    A non-empty result is the drift alarm: APIM returned resources that match no
    team prefix, so the reverse adapter could not place them.
    """
    findings: list[str] = []
    for quarantine_dir in governance_root.rglob(QUARANTINE):
        if not quarantine_dir.is_dir():
            continue
        for path in quarantine_dir.rglob("*"):
            if path.is_file():
                findings.append(path.relative_to(governance_root).as_posix())
    return sorted(findings)


def _cmd_teams(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    print(json.dumps(fanout_teams(config)))
    return 0


def _cmd_unassigned(args: argparse.Namespace) -> int:
    findings = find_unassigned(Path(args.governance_root))
    if findings:
        print("DRIFT ALARM: unassigned resources in APIM (no owning team):")
        for path in findings:
            print(f"  {path}")
        return 1
    print("No unassigned resources.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    teams = sub.add_parser("teams", help="emit fan-out team list as JSON (build matrix)")
    teams.add_argument("--config", required=True, help="config/ci.json")
    teams.set_defaults(func=_cmd_teams)

    unassigned = sub.add_parser(
        "unassigned", help="fail if APIM returned resources no team can own"
    )
    unassigned.add_argument(
        "--governance-root",
        required=True,
        help="routed governance tree produced by apiops_adapter to-governance",
    )
    unassigned.set_defaults(func=_cmd_unassigned)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
