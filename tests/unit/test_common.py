"""Tests for `_common`."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _common import (
    DEFAULT_CONFIG_PATH,
    CIConfig,
    DomainConfig,
    GatewayCapacity,
    TeamConfig,
    Violation,
    build_arg_parser,
    emit,
    extract_kv_hostnames,
    filter_existing,
    load_config,
    read_changed_files,
    under_workspace_teams,
)


def test_violation_format() -> None:
    v = Violation(rule="r", path="p/q", message="m")
    assert v.format() == "[r] p/q: m"


class TestTeamForPath:
    def test_returns_team_when_inside_folder(self, ci_config: CIConfig) -> None:
        team = ci_config.team_for_path(
            "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml"
        )
        assert team is not None and team.name == "team-a"

    def test_returns_none_when_outside_any_team_folder(self, ci_config: CIConfig) -> None:
        assert ci_config.team_for_path("apim-config/service/policy.xml") is None

    def test_normalises_backslashes(self, ci_config: CIConfig) -> None:
        team = ci_config.team_for_path(
            r"apim-config\workspaces\pensions-core\teams\team-b\apis\foo.json"
        )
        assert team is not None and team.name == "team-b"

    def test_folder_with_trailing_slash_in_config_still_matches(self) -> None:
        cfg = CIConfig(
            workspace_root="apim-config/workspaces",
            teams=[TeamConfig(name="t", folder="apim-config/workspaces/x/teams/t/", prefix="t")],
        )
        assert cfg.team_for_path("apim-config/workspaces/x/teams/t/file") is not None


class TestIsPlatformPath:
    def test_exact_match(self, ci_config: CIConfig) -> None:
        assert ci_config.is_platform_path(
            "apim-config/workspaces/pensions-core/workspace.json"
        )

    def test_prefix_match(self, ci_config: CIConfig) -> None:
        assert ci_config.is_platform_path("apim-config/service/loggers/app-insights.json")

    def test_no_match(self, ci_config: CIConfig) -> None:
        assert not ci_config.is_platform_path(
            "apim-config/workspaces/pensions-core/teams/team-a/apis/x.yaml"
        )

    def test_backslashes_handled(self, ci_config: CIConfig) -> None:
        assert ci_config.is_platform_path(r"apim-config\service\policy.xml")


class TestLoadConfig:
    def test_loads_minimal(self, tmp_path: Path) -> None:
        p = tmp_path / "ci.json"
        p.write_text(json.dumps({"workspace_root": "ws", "teams": []}), encoding="utf-8")
        cfg = load_config(p)
        assert cfg.workspace_root == "ws"
        assert cfg.teams == []
        assert cfg.platform_paths == []

    def test_loads_with_teams(self, tmp_path: Path) -> None:
        p = tmp_path / "ci.json"
        p.write_text(
            json.dumps(
                {
                    "workspace_root": "ws",
                    "platform_paths": ["pp"],
                    "teams": [
                        {
                            "name": "t",
                            "folder": "f",
                            "prefix": "p",
                            "allowed_key_vaults": ["kv"],
                            "allowed_backend_hosts": ["h"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert cfg.platform_paths == ["pp"]
        assert cfg.teams[0].allowed_key_vaults == ["kv"]
        assert cfg.teams[0].allowed_backend_hosts == ["h"]

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nope.json")

    def test_default_path_used(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "ci.json").write_text(
            json.dumps({"workspace_root": "x", "teams": []}), encoding="utf-8"
        )
        assert load_config(None).workspace_root == "x"

    def test_default_path_constant(self) -> None:
        assert DEFAULT_CONFIG_PATH.parts == ("config", "ci.json")


class TestReadChangedFiles:
    def test_from_file(self, tmp_path: Path) -> None:
        p = tmp_path / "changed.txt"
        p.write_text("a\nb\n\n# comment\nc\n", encoding="utf-8")
        assert read_changed_files(p) == ["a", "b", "c"]

    def test_normalises_windows_paths(self, tmp_path: Path) -> None:
        p = tmp_path / "changed.txt"
        p.write_text("foo\\bar\\baz.xml\n", encoding="utf-8")
        assert read_changed_files(p) == ["foo/bar/baz.xml"]

    def test_from_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("x\n y \n"))
        assert read_changed_files("-") == ["x", "y"]

    def test_none_means_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("z\n"))
        assert read_changed_files(None) == ["z"]


class TestEmit:
    def test_no_violations_returns_zero(self) -> None:
        buf = io.StringIO()
        assert emit([], stream=buf) == 0
        assert buf.getvalue() == ""

    def test_violations_return_one_and_print(self) -> None:
        buf = io.StringIO()
        v = Violation("r", "p", "m")
        assert emit([v], stream=buf) == 1
        assert "[r] p: m" in buf.getvalue()
        assert "1 violation(s) found." in buf.getvalue()


class TestBuildArgParser:
    def test_defaults(self) -> None:
        parser = build_arg_parser("desc")
        args = parser.parse_args([])
        assert args.changed_files == "-"
        assert args.config is None
        assert args.repo_root == "."

    def test_custom(self) -> None:
        parser = build_arg_parser("desc")
        args = parser.parse_args(
            ["--changed-files", "/tmp/x", "--config", "/tmp/c.json", "--repo-root", "/tmp/r"]
        )
        assert args.changed_files == "/tmp/x"
        assert args.config == "/tmp/c.json"
        assert args.repo_root == "/tmp/r"


class TestExtractKvHostnames:
    def test_finds_single(self) -> None:
        assert extract_kv_hostnames("see https://kv-team-a.vault.azure.net/secrets/x") == [
            "kv-team-a"
        ]

    def test_finds_multiple_lowercased(self) -> None:
        s = "https://KV-A.vault.azure.net/x https://kv-b.vault.azure.net/y"
        assert extract_kv_hostnames(s) == ["kv-a", "kv-b"]

    def test_returns_empty_when_no_match(self) -> None:
        assert extract_kv_hostnames("nothing here") == []


class TestUnderWorkspaceTeams:
    def test_true_for_team_path(self) -> None:
        assert under_workspace_teams(
            "apim-config/workspaces/pensions-core/teams/team-a/apis/x", "apim-config/workspaces"
        )

    def test_false_for_workspace_root_files(self) -> None:
        assert not under_workspace_teams(
            "apim-config/workspaces/pensions-core/policy.xml", "apim-config/workspaces"
        )

    def test_false_for_unrelated_path(self) -> None:
        assert not under_workspace_teams("docs/readme.md", "apim-config/workspaces")


class TestDomainsAndCapacity:
    def test_load_config_with_domains(self, tmp_path: Path) -> None:
        p = tmp_path / "ci.json"
        p.write_text(
            json.dumps(
                {
                    "workspace_root": "ws",
                    "teams": [],
                    "domains": [
                        {
                            "name": "pensions-core",
                            "tier": "gold",
                            "leads_team": "pc-leads",
                            "active": True,
                        }
                    ],
                    "valid_tiers": ["gold", "silver", "bronze"],
                    "gateway_capacity": {
                        "workspaces_per_instance": 100,
                        "workspaces_per_gateway": 30,
                        "target_active_workspaces": 10,
                    },
                }
            ),
            encoding="utf-8",
        )
        cfg = load_config(p)
        assert len(cfg.domains) == 1
        assert cfg.domains[0].name == "pensions-core"
        assert cfg.domains[0].active is True
        assert cfg.valid_tiers == ["gold", "silver", "bronze"]
        assert cfg.gateway_capacity.workspaces_per_gateway == 30

    def test_load_config_defaults_for_missing_optional_blocks(self, tmp_path: Path) -> None:
        p = tmp_path / "ci.json"
        p.write_text(
            json.dumps({"workspace_root": "ws", "teams": []}), encoding="utf-8"
        )
        cfg = load_config(p)
        assert cfg.domains == []
        assert cfg.valid_tiers == ["gold", "silver", "bronze"]
        assert isinstance(cfg.gateway_capacity, GatewayCapacity)
        assert cfg.gateway_capacity.workspaces_per_instance == 100

    def test_domain_for_workspace_dir(self) -> None:
        cfg = CIConfig(
            workspace_root="ws",
            domains=[
                DomainConfig(name="pensions-core", tier="gold", leads_team="pc-leads"),
                DomainConfig(name="sandbox", tier="bronze", leads_team="sbx-leads"),
            ],
        )
        d = cfg.domain_for_workspace_dir("pensions-core")
        assert d is not None and d.tier == "gold"
        assert cfg.domain_for_workspace_dir("unknown") is None

    def test_handles_backslashes(self) -> None:
        assert under_workspace_teams(
            r"apim-config\workspaces\pensions-core\teams\team-a\x", "apim-config/workspaces"
        )

    def test_workspace_root_with_trailing_slash(self) -> None:
        assert under_workspace_teams(
            "apim-config/workspaces/pensions-core/teams/team-a/x",
            "apim-config/workspaces/",
        )


class TestFilterExisting:
    def test_skips_missing(self, tmp_path: Path) -> None:
        (tmp_path / "exists.txt").write_text("x")
        result = filter_existing(["exists.txt", "missing.txt"], tmp_path)
        assert result == ["exists.txt"]

    def test_empty_input(self, tmp_path: Path) -> None:
        assert filter_existing([], tmp_path) == []
