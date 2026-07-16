"""Tests for `backend_allowlist`."""

from __future__ import annotations

import json
from pathlib import Path

import backend_allowlist
from _common import CIConfig


def test_own_team_backend_passes(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-stub-orders.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        json.dumps({"name": "teama-stub-orders", "url": "https://stub-orders-api.azurewebsites.net/api"}),
        encoding="utf-8",
    )
    assert (
        backend_allowlist.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_arm_shape_with_properties_url_passes(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-arm.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        json.dumps(
            {
                "name": "teama-arm",
                "properties": {"url": "https://orders.contoso.com/api"},
            }
        ),
        encoding="utf-8",
    )
    assert (
        backend_allowlist.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_disallowed_host_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        json.dumps({"name": "teama-x", "url": "https://evil.invalid/api"}),
        encoding="utf-8",
    )
    v = backend_allowlist.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "evil.invalid" in v[0].message


def test_missing_url_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"name": "teama-x"}), encoding="utf-8")
    v = backend_allowlist.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "missing a 'url'" in v[0].message


def test_url_without_hostname_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"name": "teama-x", "url": "not-a-url"}), encoding="utf-8")
    v = backend_allowlist.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "no hostname" in v[0].message


def test_malformed_json_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    v = backend_allowlist.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "not valid JSON" in v[0].message


def test_non_object_json_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text("[1,2,3]", encoding="utf-8")
    v = backend_allowlist.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "must be a JSON object" in v[0].message


def test_non_backend_path_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    assert (
        backend_allowlist.check(
            ["apim-config/workspaces/pensions-core/teams/team-a/apis/x.yaml"],
            str(repo),
            ci_config,
        )
        == []
    )


def test_backend_outside_any_team_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/backends/global.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"name": "g", "url": "https://x.invalid/"}), encoding="utf-8")
    assert (
        backend_allowlist.check(
            ["apim-config/workspaces/pensions-core/backends/global.json"], str(repo), ci_config
        )
        == []
    )


def test_main_runs_end_to_end(tmp_path: Path, capsys, monkeypatch) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces",'
        '"teams":[{"name":"team-a","folder":"apim-config/workspaces/pensions-core/teams/team-a",'
        '"prefix":"teama","allowed_backend_hosts":["ok.invalid"]}]}',
        encoding="utf-8",
    )
    p = tmp_path / "apim-config/workspaces/pensions-core/teams/team-a/backends/x.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"name": "x", "url": "https://nope.invalid/"}), encoding="utf-8")
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-a/backends/x.json\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = backend_allowlist.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "backend-allowlist" in capsys.readouterr().out


def test_properties_present_but_url_missing_falls_through(
    ci_config: CIConfig, repo: Path
) -> None:
    """Cover the branch where 'properties' is a dict without a string 'url'."""
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/backends/teama-x.json"
    p.parent.mkdir(parents=True)
    # properties is a dict but its 'url' is an integer (not str)
    p.write_text(json.dumps({"name": "teama-x", "properties": {"url": 123}}), encoding="utf-8")
    v = backend_allowlist.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "missing a 'url'" in v[0].message
