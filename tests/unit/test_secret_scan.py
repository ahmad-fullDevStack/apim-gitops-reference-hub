"""Tests for `secret_scan`."""

from __future__ import annotations

import json
from pathlib import Path

import secret_scan
from _common import CIConfig


def _nv(props: dict, name: str = "x") -> str:
    return json.dumps({"name": name, "properties": props})


def test_kv_reference_only_passes(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _nv(
            {
                "displayName": "x",
                "secret": True,
                "keyVault": {
                    "secretIdentifier": "https://kv-pensions-core-team-a.vault.azure.net/secrets/x"
                },
            }
        ),
        encoding="utf-8",
    )
    assert (
        secret_scan.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_secret_with_literal_value_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _nv({"displayName": "x", "secret": True, "value": "hunter2"}),
        encoding="utf-8",
    )
    v = secret_scan.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "marked secret" in v[0].message


def test_value_at_top_level_also_detected(ci_config: CIConfig, repo: Path) -> None:
    """secret flag and value live at the top level in some APIOps shapes."""
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        json.dumps({"name": "x", "secret": True, "value": "hunter2"}), encoding="utf-8"
    )
    v = secret_scan.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1


def test_value_and_kv_reference_both_present_fails(
    ci_config: CIConfig, repo: Path
) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _nv(
            {
                "displayName": "x",
                "value": "leftover",
                "keyVault": {
                    "secretIdentifier": "https://kv-pensions-core-team-a.vault.azure.net/secrets/x"
                },
            }
        ),
        encoding="utf-8",
    )
    v = secret_scan.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "both a literal value and a Key Vault" in v[0].message


def test_non_secret_with_literal_value_passes(ci_config: CIConfig, repo: Path) -> None:
    """Non-secret named values may carry literal values (this is how config gets shipped)."""
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _nv({"displayName": "x", "secret": False, "value": "PT10S"}), encoding="utf-8"
    )
    assert (
        secret_scan.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_malformed_json_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    v = secret_scan.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "not valid JSON" in v[0].message


def test_non_object_json_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text("[]", encoding="utf-8")
    v = secret_scan.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "JSON object" in v[0].message


def test_non_named_value_paths_skipped(ci_config: CIConfig, repo: Path) -> None:
    assert (
        secret_scan.check(
            [
                "apim-config/workspaces/pensions-core/teams/team-a/apis/teama-x/policy.xml",
                "README.md",
            ],
            str(repo),
            ci_config,
        )
        == []
    )


def test_deleted_named_value_skipped(ci_config: CIConfig, repo: Path) -> None:
    assert (
        secret_scan.check(
            ["apim-config/workspaces/pensions-core/teams/team-a/named-values/gone.json"],
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
    p = tmp_path / "apim-config/workspaces/pensions-core/teams/team-a/named-values/x.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"name": "x", "secret": True, "value": "hunter2"}), encoding="utf-8")
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-a/named-values/x.json\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = secret_scan.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "secret-scan" in capsys.readouterr().out


def test_has_kv_reference_top_level_shape() -> None:
    """Cover the top-level keyVault.secretIdentifier code path."""
    assert secret_scan._has_kv_reference(
        {"keyVault": {"secretIdentifier": "https://kv.vault.azure.net/secrets/x"}}
    )


def test_has_kv_reference_with_non_dict_properties() -> None:
    """Cover the branch where 'properties' exists but is not a dict (e.g. a list)."""
    assert not secret_scan._has_kv_reference({"properties": ["unexpected"]})


def test_has_kv_reference_empty_string_is_not_a_reference() -> None:
    assert not secret_scan._has_kv_reference({"keyVault": {"secretIdentifier": ""}})


def test_has_kv_reference_no_keyvault_at_all() -> None:
    assert not secret_scan._has_kv_reference({})


def test_has_kv_reference_properties_keyvault_empty_string() -> None:
    assert not secret_scan._has_kv_reference(
        {"properties": {"keyVault": {"secretIdentifier": ""}}}
    )


def test_literal_value_ignores_whitespace_only() -> None:
    """Whitespace-only literals are treated as empty by `_literal_value`."""
    assert secret_scan._literal_value({"value": "   "}) is None
    assert secret_scan._literal_value({"properties": {"value": "x"}}) == "x"
