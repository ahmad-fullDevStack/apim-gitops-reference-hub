"""Tests for `base_inheritance`."""

from __future__ import annotations

from pathlib import Path

import base_inheritance
from _common import CIConfig


def _policy(sections: dict[str, str]) -> str:
    body = "".join(f"<{name}>{content}</{name}>" for name, content in sections.items())
    return f"<?xml version='1.0'?><policies>{body}</policies>"


def test_policy_with_base_in_all_sections_passes(
    ci_config: CIConfig, repo: Path
) -> None:
    p = (
        repo
        / "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
    )
    p.parent.mkdir(parents=True)
    p.write_text(
        _policy(
            {
                "inbound": "<base />",
                "backend": "<base />",
                "outbound": "<base />",
                "on-error": "<base />",
            }
        ),
        encoding="utf-8",
    )
    assert (
        base_inheritance.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_missing_base_in_inbound_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
    p.parent.mkdir(parents=True)
    p.write_text(
        _policy(
            {
                "inbound": "<set-header name='x' exists-action='override'><value>v</value></set-header>",
                "backend": "<base />",
                "outbound": "<base />",
                "on-error": "<base />",
            }
        ),
        encoding="utf-8",
    )
    v = base_inheritance.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "<inbound>" in v[0].message


def test_absent_section_is_allowed(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
    p.parent.mkdir(parents=True)
    p.write_text(_policy({"inbound": "<base />"}), encoding="utf-8")
    assert (
        base_inheritance.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_malformed_xml_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
    p.parent.mkdir(parents=True)
    p.write_text("<not-closed>", encoding="utf-8")
    v = base_inheritance.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "well-formed" in v[0].message


def test_wrong_root_element_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
    p.parent.mkdir(parents=True)
    p.write_text("<?xml version='1.0'?><wrong/>", encoding="utf-8")
    v = base_inheritance.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "must be <policies>" in v[0].message


def test_non_policy_file_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    assert (
        base_inheritance.check(
            ["apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/specification.yaml"],
            str(repo),
            ci_config,
        )
        == []
    )


def test_deleted_file_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    """If the file is in the changed list but not on disk (deletion), the check skips it."""
    assert (
        base_inheritance.check(
            ["apim-config/workspaces/pensions-core/teams/team-a/apis/gone/policy.xml"],
            str(repo),
            ci_config,
        )
        == []
    )


def test_main_runs_end_to_end(
    tmp_path: Path, capsys, monkeypatch, ci_config: CIConfig
) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces","teams":[]}',
        encoding="utf-8",
    )
    p = tmp_path / "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
    p.parent.mkdir(parents=True)
    p.write_text(
        _policy({"inbound": "<set-header name='x' exists-action='override'><value>v</value></set-header>"}),
        encoding="utf-8",
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = base_inheritance.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "base-inheritance" in capsys.readouterr().out
