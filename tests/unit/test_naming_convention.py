"""Tests for `naming_convention`."""

from __future__ import annotations

from pathlib import Path

import naming_convention
from _common import CIConfig


def test_correctly_prefixed_api_passes(ci_config: CIConfig, repo: Path) -> None:
    assert (
        naming_convention.check(
            [
                "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-orders-v1/specification.yaml",
            ],
            str(repo),
            ci_config,
        )
        == []
    )


def test_wrong_prefix_fails(ci_config: CIConfig, repo: Path) -> None:
    v = naming_convention.check(
        [
            "apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-orders-v1/specification.yaml",
        ],
        str(repo),
        ci_config,
    )
    assert len(v) == 1
    assert v[0].message.startswith("apis resource 'teamb-orders-v1'")


def test_per_resource_kind_works(ci_config: CIConfig, repo: Path) -> None:
    v = naming_convention.check(
        [
            "apim-config/workspaces/pensions-core/teams/team-a/named-values/bad-name.json",
            "apim-config/workspaces/pensions-core/teams/team-a/backends/bad-backend.json",
            "apim-config/workspaces/pensions-core/teams/team-a/products/bad-product.json",
            "apim-config/workspaces/pensions-core/teams/team-a/subscriptions/bad-sub.json",
            "apim-config/workspaces/pensions-core/teams/team-a/policy-fragments/bad-frag.xml",
        ],
        str(repo),
        ci_config,
    )
    assert len(v) == 5
    rules = {x.message.split(" resource ")[0] for x in v}
    assert rules == {
        "named-values",
        "backends",
        "products",
        "subscriptions",
        "policy-fragments",
    }


def test_file_directly_under_kind_uses_stem(ci_config: CIConfig, repo: Path) -> None:
    """A single JSON file under named-values/ is named after its stem."""
    v = naming_convention.check(
        [
            "apim-config/workspaces/pensions-core/teams/team-a/named-values/teamb-key.json",
        ],
        str(repo),
        ci_config,
    )
    assert len(v) == 1
    assert "'teamb-key'" in v[0].message


def test_duplicates_collapsed(ci_config: CIConfig, repo: Path) -> None:
    """Multiple files inside the same misnamed resource folder only yield one violation."""
    v = naming_convention.check(
        [
            "apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-x/specification.yaml",
            "apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-x/policy.xml",
        ],
        str(repo),
        ci_config,
    )
    assert len(v) == 1


def test_non_team_path_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    assert naming_convention.check(["docs/x.md"], str(repo), ci_config) == []


def test_team_path_not_matching_kind_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    """A file under team-a but not under any RESOURCE_KIND folder is not a resource definition."""
    assert (
        naming_convention.check(
            ["apim-config/workspaces/pensions-core/teams/team-a/README.md"],
            str(repo),
            ci_config,
        )
        == []
    )


def test_case_insensitive(ci_config: CIConfig, repo: Path) -> None:
    """Resource names ARE case-insensitive vs. the prefix."""
    assert (
        naming_convention.check(
            ["apim-config/workspaces/pensions-core/teams/team-a/apis/TEAMA-X/specification.yaml"],
            str(repo),
            ci_config,
        )
        == []
    )


def test_main_runs_end_to_end(tmp_path: Path, capsys, monkeypatch) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces",'
        '"teams":[{"name":"team-a","folder":"apim-config/workspaces/pensions-core/teams/team-a","prefix":"teama"}]}',
        encoding="utf-8",
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-a/apis/teamb-x/specification.yaml\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = naming_convention.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "naming-convention" in capsys.readouterr().out


def test_resource_name_for_returns_none_when_path_outside_team_folder() -> None:
    """Defensive branch: callers normally pre-filter, but the helper still guards."""
    assert (
        naming_convention._resource_name_for(
            "docs/x.md",
            "apim-config/workspaces/pensions-core/teams/team-a",
            "apis",
        )
        is None
    )
