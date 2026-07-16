"""Tests for `freeze_workspace`."""

from __future__ import annotations

from pathlib import Path

import pytest
import freeze_workspace
from _common import CIConfig, DomainConfig


def _cfg(domain_names: list[str]) -> CIConfig:
    return CIConfig(
        workspace_root="apim-config/workspaces",
        platform_paths=[],
        teams=[],
        domains=[
            DomainConfig(name=n, tier="gold", leads_team=f"{n}-leads") for n in domain_names
        ],
    )


def _write_ws(repo: Path, ws_name: str) -> str:
    rel = f"apim-config/workspaces/{ws_name}/workspace.json"
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"name":"' + ws_name + '","tier":"gold"}', encoding="utf-8")
    return rel


def test_known_domain_passes(tmp_path: Path) -> None:
    rel = _write_ws(tmp_path, "pensions-core")
    assert (
        freeze_workspace.check([rel], str(tmp_path), _cfg(["pensions-core"])) == []
    )


def test_unknown_domain_fails(tmp_path: Path) -> None:
    rel = _write_ws(tmp_path, "newteam")
    v = freeze_workspace.check([rel], str(tmp_path), _cfg(["pensions-core"]))
    assert len(v) == 1
    assert "newteam" in v[0].message
    assert "freezes" in v[0].message


def test_non_workspace_json_ignored(tmp_path: Path) -> None:
    """policy.xml under a new workspace is not the workspace.json — skip."""
    assert (
        freeze_workspace.check(
            ["apim-config/workspaces/newteam/policy.xml"],
            str(tmp_path),
            _cfg(["pensions-core"]),
        )
        == []
    )


def test_nested_path_ignored(tmp_path: Path) -> None:
    """A workspace.json nested under teams/ is not a top-level workspace declaration."""
    assert (
        freeze_workspace.check(
            ["apim-config/workspaces/x/teams/t/workspace.json"],
            str(tmp_path),
            _cfg(["x"]),
        )
        == []
    )


def test_deleted_new_workspace_is_skipped(tmp_path: Path) -> None:
    """If the file is in the diff but doesn't exist on disk (deletion), don't flag."""
    assert (
        freeze_workspace.check(
            ["apim-config/workspaces/ghost/workspace.json"],
            str(tmp_path),
            _cfg(["pensions-core"]),
        )
        == []
    )


def test_path_outside_workspace_root_ignored(tmp_path: Path) -> None:
    assert (
        freeze_workspace.check(
            ["apim-config/other/x/workspace.json"], str(tmp_path), _cfg(["x"])
        )
        == []
    )


def test_main_runs(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces","teams":[],'
        '"domains":[{"name":"pensions-core","tier":"gold","leads_team":"pensions-core-leads"}]}',
        encoding="utf-8",
    )
    rel = _write_ws(tmp_path, "rogue")
    changed = tmp_path / "changed.txt"
    changed.write_text(rel + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = freeze_workspace.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "freeze-workspace" in capsys.readouterr().out
