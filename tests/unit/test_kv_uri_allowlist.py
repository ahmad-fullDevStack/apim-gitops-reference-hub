"""Tests for `kv_uri_allowlist`."""

from __future__ import annotations

from pathlib import Path

import kv_uri_allowlist
from _common import CIConfig


def _named_value(uri: str) -> str:
    return (
        '{"name":"x","properties":{"displayName":"x","secret":true,'
        f'"keyVault":{{"secretIdentifier":"{uri}"}}}}}}'
    )[:-1]  # trim the extra closing brace introduced by f-string escaping


def _named_value_clean(uri: str) -> str:
    import json
    return json.dumps(
        {
            "name": "x",
            "properties": {
                "displayName": "x",
                "secret": True,
                "keyVault": {"secretIdentifier": uri},
            },
        }
    )


def test_own_team_kv_reference_passes(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _named_value_clean("https://kv-pensions-core-team-a.vault.azure.net/secrets/x"),
        encoding="utf-8",
    )
    assert (
        kv_uri_allowlist.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_cross_team_kv_reference_fails(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _named_value_clean("https://kv-pensions-core-team-b.vault.azure.net/secrets/x"),
        encoding="utf-8",
    )
    v = kv_uri_allowlist.check(
        [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
    )
    assert len(v) == 1
    assert "kv-pensions-core-team-b" in v[0].message
    assert "team-a" in v[0].message


def test_uppercase_uri_is_normalised(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _named_value_clean(
            "https://KV-PENSIONS-CORE-TEAM-A.vault.azure.net/secrets/x"
        ),
        encoding="utf-8",
    )
    assert (
        kv_uri_allowlist.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_file_outside_team_folder_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/service/policy.xml"
    p.parent.mkdir(parents=True)
    p.write_text(
        "<policies><inbound><base/><send-request>"
        "<set-url>https://kv-pensions-core-team-b.vault.azure.net/secrets/x</set-url>"
        "</send-request></inbound></policies>",
        encoding="utf-8",
    )
    assert (
        kv_uri_allowlist.check(
            ["apim-config/service/policy.xml"], str(repo), ci_config
        )
        == []
    )


def test_no_kv_references_passes(ci_config: CIConfig, repo: Path) -> None:
    p = repo / "apim-config/workspaces/pensions-core/teams/team-a/named-values/teama-x.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"name":"x","properties":{"displayName":"x","value":""}}', encoding="utf-8")
    assert (
        kv_uri_allowlist.check(
            [str(p.relative_to(repo)).replace("\\", "/")], str(repo), ci_config
        )
        == []
    )


def test_deleted_file_is_skipped(ci_config: CIConfig, repo: Path) -> None:
    assert (
        kv_uri_allowlist.check(
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
        '"teams":[{"name":"team-a","folder":"apim-config/workspaces/pensions-core/teams/team-a",'
        '"prefix":"teama","allowed_key_vaults":["kv-team-a"]}]}',
        encoding="utf-8",
    )
    p = tmp_path / "apim-config/workspaces/pensions-core/teams/team-a/named-values/x.json"
    p.parent.mkdir(parents=True)
    p.write_text(
        _named_value_clean("https://kv-team-b.vault.azure.net/secrets/x"),
        encoding="utf-8",
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(
        "apim-config/workspaces/pensions-core/teams/team-a/named-values/x.json\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = kv_uri_allowlist.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "kv-uri-allowlist" in capsys.readouterr().out
