"""Tests for `tier_check`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import tier_check
from _common import CIConfig


def _cfg() -> CIConfig:
    return CIConfig(
        workspace_root="apim-config/workspaces",
        platform_paths=[],
        teams=[],
        valid_tiers=["gold", "silver", "bronze"],
    )


def _write(repo: Path, rel: str, payload: object) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        p.write_text(payload, encoding="utf-8")
    else:
        p.write_text(json.dumps(payload), encoding="utf-8")
    return rel


def test_valid_tier_passes(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/pensions-core/workspace.json",
        {"name": "pensions-core", "tier": "gold", "active": True},
    )
    assert tier_check.check([rel], str(tmp_path), _cfg()) == []


def test_missing_tier_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/pensions-core/workspace.json",
        {"name": "pensions-core"},
    )
    v = tier_check.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "missing a string 'tier'" in v[0].message


def test_unknown_tier_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/workspace.json",
        {"name": "x", "tier": "platinum"},
    )
    v = tier_check.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "is not one of" in v[0].message


def test_active_bronze_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/sandbox/workspace.json",
        {"name": "sandbox", "tier": "bronze", "active": True},
    )
    v = tier_check.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "Bronze" in v[0].message


def test_inactive_bronze_passes(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/sandbox/workspace.json",
        {"name": "sandbox", "tier": "bronze", "active": False},
    )
    assert tier_check.check([rel], str(tmp_path), _cfg()) == []


def test_non_workspace_files_ignored(tmp_path: Path) -> None:
    assert tier_check.check(["README.md"], str(tmp_path), _cfg()) == []


def test_invalid_json_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/workspace.json",
        "{not json",
    )
    v = tier_check.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "not valid JSON" in v[0].message


def test_non_object_json_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/workspace.json",
        "[]",
    )
    v = tier_check.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "must be a JSON object" in v[0].message


def test_main_runs(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text(
        '{"workspace_root":"apim-config/workspaces","teams":[],'
        '"valid_tiers":["gold","silver","bronze"]}',
        encoding="utf-8",
    )
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/workspace.json",
        {"name": "x", "tier": "unknown"},
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(rel + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = tier_check.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "tier-check" in capsys.readouterr().out


def test_missing_file_is_skipped(tmp_path: Path) -> None:
    """A deleted workspace.json appears in the diff but is not on disk."""
    assert (
        tier_check.check(
            ["apim-config/workspaces/gone/workspace.json"], str(tmp_path), _cfg()
        )
        == []
    )
