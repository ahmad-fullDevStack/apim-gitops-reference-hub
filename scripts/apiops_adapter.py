"""apiops_adapter: translate between the governance source layout in this repo
and the artifact layout the APIOps extractor/publisher expects.

Two directions:

* ``to-native``     governance layout  -> APIOps artifacts (publisher input)
* ``to-governance`` APIOps artifacts    -> governance layout (drift comparison)

The governance layout nests every resource under ``teams/<team>/`` and
``shared/`` so that path-scoped required reviewers can express per-team
ownership (see docs/reference_architecture.md). APIOps has no concept of a team
folder: it groups resources by
type directly under the workspace. This adapter collapses that middle layer on
the way out and rebuilds it on the way back.

Round-trip safety: every artifact file is copied byte-for-byte, so
``to-native`` followed by ``to-governance`` reproduces the source exactly. The
only file whose *content* changes is ``workspace.json``: governance-only fields
(``tier``, ``active``, ``ownerTeam``) are stripped from the
``workspaceInformation.json`` handed to APIOps, and on the way back the
governance copy is preserved from the existing repo (``--governance-base``)
rather than reconstructed, because those fields do not exist in APIM at all.

Rebuilding team ownership on the reverse path relies on the naming convention
(``teama-*``, ``teamb-*``, ``contoso-*``) that the CI naming check already
enforces. A resource whose name matches no team prefix cannot be placed and is
quarantined under ``_unassigned/`` so the drift PR surfaces it for a human.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WORKSPACE_GOVERNANCE_FIELDS = ("tier", "active", "ownerTeam")

# governance subdir -> (native subdir, info filename, has policy companion)
# APIOps v7 uses space-separated folder names for multi-word resource kinds
# (e.g. `named values`, `version sets`), matching what the extractor emits.
FLAT_KINDS: dict[str, tuple[str, str, bool]] = {
    "backends": ("backends", "backendInformation.json", False),
    "named-values": ("named values", "namedValueInformation.json", False),
    "products": ("products", "productInformation.json", True),
    "version-sets": ("version sets", "versionSetInformation.json", False),
}
# governance subdir -> native subdir (copied as whole directory trees)
FOLDER_KINDS: dict[str, str] = {"apis": "apis"}

# reverse lookups, keyed by native subdir
NATIVE_FLAT = {native: (gov, info, pol) for gov, (native, info, pol) in FLAT_KINDS.items()}
NATIVE_FOLDER = {native: gov for gov, native in FOLDER_KINDS.items()}

QUARANTINE = "_unassigned"


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def _copy_tree(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


# --------------------------------------------------------------------------- #
# Forward: governance -> native
# --------------------------------------------------------------------------- #
def _strip_workspace_info(text: str) -> str:
    data = json.loads(text)
    for field in WORKSPACE_GOVERNANCE_FIELDS:
        data.pop(field, None)
    return json.dumps(data, indent=2) + "\n"


def _governance_containers(ws_dir: Path, team: str | None = None) -> list[Path]:
    # A team-scoped publish emits ONLY that team's container. `shared/` and
    # every other team are skipped so a team publish can never write another
    # team's resources into the shared workspace.
    if team is not None:
        team_dir = ws_dir / "teams" / team
        return [team_dir] if team_dir.is_dir() else []
    containers = []
    shared = ws_dir / "shared"
    if shared.is_dir():
        containers.append(shared)
    teams = ws_dir / "teams"
    if teams.is_dir():
        containers.extend(sorted(p for p in teams.iterdir() if p.is_dir()))
    return containers


def _container_to_native(container: Path, ws_native: Path) -> None:
    for gov_subdir, (native_subdir, info_file, has_policy) in FLAT_KINDS.items():
        src_dir = container / gov_subdir
        if not src_dir.is_dir():
            continue
        for json_file in sorted(src_dir.glob("*.json")):
            name = json_file.stem
            res_dir = ws_native / native_subdir / name
            _copy_file(json_file, res_dir / info_file)
            if has_policy:
                policy = src_dir / f"{name}.policy.xml"
                if policy.exists():
                    _copy_file(policy, res_dir / "policy.xml")
    for gov_subdir, native_subdir in FOLDER_KINDS.items():
        src_dir = container / gov_subdir
        if not src_dir.is_dir():
            continue
        for res in sorted(p for p in src_dir.iterdir() if p.is_dir()):
            _copy_tree(res, ws_native / native_subdir / res.name)


def to_native(src_root: Path, dest_root: Path, team: str | None = None) -> None:
    # Deterministic build: wipe any prior output so a stale artifact from an
    # earlier run cannot survive into this one. This matters on reused
    # self-hosted runners, where `dest_root` (e.g. build/apiops/) lives at the
    # workspace root that no `actions/checkout` step cleans -- without this a
    # resource deleted from the repo would linger in the build folder, get
    # re-published by the additive upsert, and (because prune reads desired
    # state from this folder) never be pruned.
    if dest_root.exists():
        shutil.rmtree(dest_root)

    # When `team` is set, this is a team-scoped publish: the service-level and
    # workspace-level policy plus workspaceInformation.json are platform-owned
    # and must NOT be emitted, so a team's publish cannot overwrite them.
    if team is None:
        service_policy = src_root / "service" / "policy.xml"
        if service_policy.exists():
            _copy_file(service_policy, dest_root / "policy.xml")

    workspaces = src_root / "workspaces"
    for ws_dir in sorted(p for p in workspaces.iterdir() if p.is_dir()):
        ws_native = dest_root / "workspaces" / ws_dir.name
        if team is None:
            ws_info = ws_dir / "workspace.json"
            if ws_info.exists():
                target = ws_native / "workspaceInformation.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    _strip_workspace_info(ws_info.read_text(encoding="utf-8")),
                    encoding="utf-8",
                )
            ws_policy = ws_dir / "policy.xml"
            if ws_policy.exists():
                _copy_file(ws_policy, ws_native / "policy.xml")
        for container in _governance_containers(ws_dir, team):
            _container_to_native(container, ws_native)


# --------------------------------------------------------------------------- #
# Reverse: native -> governance
# --------------------------------------------------------------------------- #
def load_routes(config_path: Path) -> dict[str, list[tuple[str, str]]]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    routes: dict[str, list[tuple[str, str]]] = {}
    for team in data["teams"]:
        rel = team["folder"].split("workspaces/", 1)[1]
        ws, subpath = rel.split("/", 1)
        routes.setdefault(ws, []).append((team["prefix"], subpath))
    return routes


def _route(ws: str, name: str, routes: dict[str, list[tuple[str, str]]]) -> str:
    for prefix, subpath in routes.get(ws, []):
        if name.startswith(prefix + "-"):
            return subpath
    return QUARANTINE


def to_governance(
    src_native: Path,
    dest_root: Path,
    routes: dict[str, list[tuple[str, str]]],
    base_root: Path,
) -> None:
    root_policy = src_native / "policy.xml"
    if root_policy.exists():
        _copy_file(root_policy, dest_root / "service" / "policy.xml")

    workspaces = src_native / "workspaces"
    for ws_native in sorted(p for p in workspaces.iterdir() if p.is_dir()):
        ws = ws_native.name
        dest_ws = dest_root / "workspaces" / ws

        base_info = base_root / "workspaces" / ws / "workspace.json"
        if base_info.exists():
            _copy_file(base_info, dest_ws / "workspace.json")
        ws_policy = ws_native / "policy.xml"
        if ws_policy.exists():
            _copy_file(ws_policy, dest_ws / "policy.xml")

        for native_subdir, (gov_subdir, info_file, has_policy) in NATIVE_FLAT.items():
            nd = ws_native / native_subdir
            if not nd.is_dir():
                continue
            for res in sorted(p for p in nd.iterdir() if p.is_dir()):
                name = res.name
                target = dest_ws / _route(ws, name, routes) / gov_subdir
                _copy_file(res / info_file, target / f"{name}.json")
                if has_policy and (res / "policy.xml").exists():
                    _copy_file(res / "policy.xml", target / f"{name}.policy.xml")

        for native_subdir, gov_subdir in NATIVE_FOLDER.items():
            nd = ws_native / native_subdir
            if not nd.is_dir():
                continue
            for res in sorted(p for p in nd.iterdir() if p.is_dir()):
                target = dest_ws / _route(ws, res.name, routes) / gov_subdir / res.name
                _copy_tree(res, target)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    fwd = sub.add_parser("to-native", help="governance layout -> APIOps artifacts")
    fwd.add_argument("--src", required=True, help="apim-config/ root")
    fwd.add_argument("--dest", required=True, help="output dir for APIOps artifacts")
    fwd.add_argument(
        "--team",
        default=None,
        help="scope the publish to a single team folder (e.g. team-a); "
        "omits shared/, other teams, and platform-owned workspace policy",
    )

    rev = sub.add_parser("to-governance", help="APIOps artifacts -> governance layout")
    rev.add_argument("--src", required=True, help="extracted APIOps artifacts root")
    rev.add_argument("--dest", required=True, help="output dir for governance layout")
    rev.add_argument("--config", required=True, help="config/ci.json")
    rev.add_argument(
        "--governance-base",
        required=True,
        help="existing apim-config/ root, used to preserve workspace.json",
    )

    args = parser.parse_args(argv)
    if args.command == "to-native":
        to_native(Path(args.src), Path(args.dest), team=args.team)
    else:
        routes = load_routes(Path(args.config))
        to_governance(
            Path(args.src), Path(args.dest), routes, Path(args.governance_base)
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
