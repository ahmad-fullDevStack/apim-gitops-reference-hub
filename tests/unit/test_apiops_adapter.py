"""Tests for `scripts/apiops_adapter.py`.

The headline guarantee is the round-trip: governance layout -> APIOps native
-> governance layout must reproduce the source byte-for-byte. The remaining
tests pin the branch behaviour the round-trip alone does not exercise
(quarantine of unprefixed resources, workspace.json stripping, missing
optional files, and the CLI entrypoint).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _make_script_importable() -> None:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _adapter():
    import importlib

    import apiops_adapter

    importlib.reload(apiops_adapter)
    return apiops_adapter


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)).replace("\\", "/"): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


CONFIG = {
    "teams": [
        {"name": "team-a", "folder": "apim-config/workspaces/pensions-core/teams/team-a", "prefix": "teama"},
        {"name": "team-b", "folder": "apim-config/workspaces/pensions-core/teams/team-b", "prefix": "teamb"},
        {"name": "shared", "folder": "apim-config/workspaces/pensions-core/shared", "prefix": "contoso"},
    ]
}


def _build_governance_tree(root: Path) -> None:
    """A representative apim-config/ exercising every resource kind."""
    _write(root / "service" / "policy.xml", "<policies><inbound><base /></inbound></policies>")

    ws = root / "workspaces" / "pensions-core"
    _write(
        ws / "workspace.json",
        json.dumps(
            {
                "name": "pensions-core",
                "displayName": "Pensions Core",
                "description": "Shared domain workspace",
                "tier": "gold",
                "active": True,
                "ownerTeam": "pensions-core-leads",
            },
            indent=2,
        )
        + "\n",
    )
    _write(ws / "policy.xml", "<policies><inbound><base /></inbound></policies>")

    # shared/
    _write(
        ws / "shared" / "apis" / "contoso-orders-canonical-v1" / "specification.yaml",
        "openapi: 3.0.0\n",
    )
    _write(
        ws / "shared" / "apis" / "contoso-orders-canonical-v1" / "policy.xml",
        "<policies><inbound><base /></inbound></policies>",
    )
    _write(
        ws / "shared" / "backends" / "contoso-orders-canonical.json",
        json.dumps({"name": "contoso-orders-canonical", "properties": {"url": "https://x"}}) + "\n",
    )
    _write(
        ws / "shared" / "products" / "contoso-internal.json",
        json.dumps({"name": "contoso-internal", "properties": {"state": "published"}}) + "\n",
    )
    _write(
        ws / "shared" / "products" / "contoso-internal.policy.xml",
        "<policies><inbound><base /></inbound></policies>",
    )
    # product with no policy companion -> reverse policy branch stays False
    _write(
        ws / "shared" / "products" / "contoso-nopolicy.json",
        json.dumps({"name": "contoso-nopolicy", "properties": {"state": "published"}}) + "\n",
    )
    _write(
        ws / "shared" / "version-sets" / "contoso-orders.json",
        json.dumps({"name": "contoso-orders", "properties": {"versioningScheme": "Header"}}) + "\n",
    )

    # teams/team-a: api with nested operations + backend + named value
    _write(
        ws / "teams" / "team-a" / "apis" / "teama-orders-v1" / "specification.yaml",
        "openapi: 3.0.0\n",
    )
    _write(
        ws / "teams" / "team-a" / "apis" / "teama-orders-v1" / "policy.xml",
        "<policies><inbound><base /></inbound></policies>",
    )
    _write(
        ws / "teams" / "team-a" / "apis" / "teama-orders-v1" / "operations" / "get-order" / "policy.xml",
        "<policies><inbound><base /></inbound></policies>",
    )
    _write(
        ws / "teams" / "team-a" / "backends" / "teama-stub-orders.json",
        json.dumps({"name": "teama-stub-orders", "properties": {"url": "https://stub"}}) + "\n",
    )
    _write(
        ws / "teams" / "team-a" / "named-values" / "teama-orders-api-key.json",
        json.dumps({"name": "teama-orders-api-key", "properties": {"secret": True}}) + "\n",
    )

    # teams/team-b: only a named value (no apis dir) -> folder-kind skip branch
    _write(
        ws / "teams" / "team-b" / "named-values" / "teamb-claims-key.json",
        json.dumps({"name": "teamb-claims-key", "properties": {"secret": True}}) + "\n",
    )


def test_round_trip_is_identity(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    config = tmp_path / "ci.json"
    config.write_text(json.dumps(CONFIG), encoding="utf-8")

    native = tmp_path / "native"
    rebuilt = tmp_path / "rebuilt"
    adapter.to_native(src, native)
    routes = adapter.load_routes(config)
    adapter.to_governance(native, rebuilt, routes, base_root=src)

    assert _snapshot(rebuilt) == _snapshot(src)


def test_native_layout_has_apiops_shape(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    native = tmp_path / "native"
    adapter.to_native(src, native)

    ws = native / "workspaces" / "pensions-core"
    # team/shared folders are collapsed away; resources grouped by native type
    assert (ws / "backends" / "teama-stub-orders" / "backendInformation.json").exists()
    assert (ws / "backends" / "contoso-orders-canonical" / "backendInformation.json").exists()
    assert (ws / "named values" / "teamb-claims-key" / "namedValueInformation.json").exists()
    assert (ws / "version sets" / "contoso-orders" / "versionSetInformation.json").exists()
    assert (ws / "products" / "contoso-internal" / "productInformation.json").exists()
    assert (ws / "products" / "contoso-internal" / "policy.xml").exists()
    assert not (ws / "products" / "contoso-nopolicy" / "policy.xml").exists()
    assert (ws / "apis" / "teama-orders-v1" / "operations" / "get-order" / "policy.xml").exists()
    assert (native / "policy.xml").exists()
    assert not (ws / "teams").exists()


def test_to_native_wipes_stale_output(tmp_path: Path) -> None:
    """A resource removed from source must not survive in a reused dest dir.

    On self-hosted runners the build folder persists across runs. If to_native
    merged into it, a deleted API would linger, get re-published by the additive
    upsert, and never be pruned (prune reads desired state from this folder).
    """
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    native = tmp_path / "native"

    # First build: teama-orders-v1 is present.
    adapter.to_native(src, native)
    stale = native / "workspaces" / "pensions-core" / "apis" / "teama-orders-v1"
    assert stale.is_dir()

    # Remove the API from source, then rebuild into the SAME dest.
    import shutil as _shutil

    _shutil.rmtree(src / "workspaces" / "pensions-core" / "teams" / "team-a" / "apis" / "teama-orders-v1")
    adapter.to_native(src, native)

    # The stale API must be gone from the rebuilt artifact.
    assert not stale.exists()


def test_workspace_info_is_stripped(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    native = tmp_path / "native"
    adapter.to_native(src, native)

    info = json.loads(
        (native / "workspaces" / "pensions-core" / "workspaceInformation.json").read_text()
    )
    assert info["displayName"] == "Pensions Core"
    assert "tier" not in info
    assert "active" not in info
    assert "ownerTeam" not in info


def test_unprefixed_resource_is_quarantined(tmp_path: Path) -> None:
    adapter = _adapter()
    # Hand-built native tree: a backend whose name matches no team prefix.
    native = tmp_path / "native"
    res = native / "workspaces" / "pensions-core" / "backends" / "orphan-thing"
    _write(res / "backendInformation.json", json.dumps({"name": "orphan-thing"}) + "\n")
    base = tmp_path / "base"
    (base / "workspaces" / "pensions-core").mkdir(parents=True)

    config = tmp_path / "ci.json"
    config.write_text(json.dumps(CONFIG), encoding="utf-8")
    routes = adapter.load_routes(config)

    dest = tmp_path / "rebuilt"
    adapter.to_governance(native, dest, routes, base_root=base)

    quarantined = (
        dest / "workspaces" / "pensions-core" / "_unassigned" / "backends" / "orphan-thing.json"
    )
    assert quarantined.exists()


def test_optional_files_absent_is_tolerated(tmp_path: Path) -> None:
    adapter = _adapter()
    # Forward: a workspace dir with no workspace.json, no policy, no resources,
    # and no service policy at the root.
    src = tmp_path / "apim-config"
    (src / "workspaces" / "empty-ws").mkdir(parents=True)
    native = tmp_path / "native"
    adapter.to_native(src, native)

    # Reverse: a native tree with no root policy, a workspace with no policy,
    # no flat-kind dirs, no apis dir, and a base lacking workspace.json.
    native2 = tmp_path / "native2"
    (native2 / "workspaces" / "lonely-ws").mkdir(parents=True)
    base = tmp_path / "base"
    (base / "workspaces" / "lonely-ws").mkdir(parents=True)
    routes: dict[str, list[tuple[str, str]]] = {}
    dest = tmp_path / "rebuilt"
    adapter.to_governance(native2, dest, routes, base_root=base)

    # Nothing was produced for the empty workspaces; the calls simply no-op.
    assert not (dest / "workspaces" / "lonely-ws" / "workspace.json").exists()


def test_main_to_native(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    dest = tmp_path / "native"
    rc = adapter.main(["to-native", "--src", str(src), "--dest", str(dest)])
    assert rc == 0
    assert (dest / "workspaces" / "pensions-core" / "workspaceInformation.json").exists()


def test_main_to_governance(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    native = tmp_path / "native"
    adapter.to_native(src, native)
    config = tmp_path / "ci.json"
    config.write_text(json.dumps(CONFIG), encoding="utf-8")

    dest = tmp_path / "rebuilt"
    rc = adapter.main(
        [
            "to-governance",
            "--src",
            str(native),
            "--dest",
            str(dest),
            "--config",
            str(config),
            "--governance-base",
            str(src),
        ]
    )
    assert rc == 0
    assert _snapshot(dest) == _snapshot(src)


def test_to_native_team_scoped_emits_only_that_team(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    native = tmp_path / "native"
    adapter.to_native(src, native, team="team-a")

    ws = native / "workspaces" / "pensions-core"
    # team-a's own resources are published
    assert (ws / "apis" / "teama-orders-v1" / "apiInformation.json").exists() or (
        ws / "apis" / "teama-orders-v1"
    ).is_dir()
    assert (ws / "backends" / "teama-stub-orders" / "backendInformation.json").exists()
    assert (ws / "named values" / "teama-orders-api-key" / "namedValueInformation.json").exists()

    # nothing belonging to team-b, shared/, or the platform is emitted
    assert not (ws / "named values" / "teamb-claims-key").exists()
    assert not (ws / "backends" / "contoso-orders-canonical").exists()
    assert not (ws / "apis" / "contoso-orders-canonical-v1").exists()
    assert not (ws / "version sets").exists()
    assert not (ws / "products").exists()
    # platform-owned service + workspace policy must never be part of a team publish
    assert not (native / "policy.xml").exists()
    assert not (ws / "policy.xml").exists()
    assert not (ws / "workspaceInformation.json").exists()


def test_to_native_team_scoped_unknown_team_is_noop(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    native = tmp_path / "native"
    adapter.to_native(src, native, team="team-x")

    # No matching team folder -> nothing published anywhere.
    assert not (native / "workspaces" / "pensions-core" / "apis").exists()


def test_main_to_native_team_flag(tmp_path: Path) -> None:
    adapter = _adapter()
    src = tmp_path / "apim-config"
    _build_governance_tree(src)
    dest = tmp_path / "native"
    rc = adapter.main(
        ["to-native", "--src", str(src), "--dest", str(dest), "--team", "team-a"]
    )
    assert rc == 0
    ws = dest / "workspaces" / "pensions-core"
    assert (ws / "backends" / "teama-stub-orders" / "backendInformation.json").exists()
    assert not (ws / "named values" / "teamb-claims-key").exists()
