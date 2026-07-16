"""Tests for `path_scope` - the cross-team write detector."""

from __future__ import annotations

from pathlib import Path

import path_scope
from _common import CIConfig


def test_single_team_change_passes(ci_config: CIConfig, repo: Path) -> None:
    changed = [
        "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml",
        "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-y.json",
    ]
    assert path_scope.check(changed, str(repo), ci_config) == []


def test_two_team_change_fails_with_one_violation_per_file(
    ci_config: CIConfig, repo: Path
) -> None:
    changed = [
        "apim-config/workspaces/pensions-core/teams/team-a/apis/x.yaml",
        "apim-config/workspaces/pensions-core/teams/team-b/apis/y.yaml",
    ]
    v = path_scope.check(changed, str(repo), ci_config)
    assert len(v) == 2
    assert all(x.rule == "path-scope" for x in v)
    assert all("multiple team folders" in x.message for x in v)


def test_team_plus_platform_fails(ci_config: CIConfig, repo: Path) -> None:
    changed = [
        "apim-config/workspaces/pensions-core/teams/team-a/apis/x.yaml",
        "apim-config/service/loggers/app-insights.json",
    ]
    v = path_scope.check(changed, str(repo), ci_config)
    assert len(v) == 1
    assert v[0].path == "apim-config/service/loggers/app-insights.json"
    assert "mixes platform-owned" in v[0].message


def test_platform_only_change_passes(ci_config: CIConfig, repo: Path) -> None:
    assert path_scope.check(
        ["apim-config/service/policy.xml"], str(repo), ci_config
    ) == []


def test_outside_workspace_tree_is_ignored(ci_config: CIConfig, repo: Path) -> None:
    """A README change at repo root must not be flagged \u2014 it is scoped by its own CODEOWNERS entry."""
    assert (
        path_scope.check(["README.md", "docs/foo.md"], str(repo), ci_config) == []
    )


def test_unowned_file_under_workspace_tree_fails(ci_config: CIConfig, repo: Path) -> None:
    changed = ["apim-config/workspaces/pensions-core/teams/team-c/x"]
    v = path_scope.check(changed, str(repo), ci_config)
    assert len(v) == 1
    assert "not under any" in v[0].message


def test_main_writes_results_to_stdout_and_returns_exit_code(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces","teams":[]}', encoding="utf-8"
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-c/x\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    rc = path_scope.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "[path-scope]" in out


def test_main_returns_zero_on_clean_input(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces","teams":[]}', encoding="utf-8"
    )
    changed = tmp_path / "changed.txt"
    changed.write_text("README.md\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert path_scope.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    ) == 0
