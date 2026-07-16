"""Tests for `versioning`."""

from __future__ import annotations

from pathlib import Path

import pytest
import versioning
from _common import CIConfig


def _cfg() -> CIConfig:
    return CIConfig(workspace_root="apim-config/workspaces", teams=[])


def _write(repo: Path, rel: str, body: str) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return rel


_OK_SPEC = (
    "openapi: 3.0.3\n"
    "info:\n"
    "  title: t\n"
    "  version: 1.0.0\n"
    "paths: {}\n"
)


def test_valid_spec_passes(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        _OK_SPEC,
    )
    assert versioning.check([rel], str(tmp_path), _cfg()) == []


def test_missing_version_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: 3.0.3\ninfo:\n  title: t\npaths: {}\n",
    )
    v = versioning.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "info.version is required" in v[0].message


def test_invalid_yaml_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: [unclosed",
    )
    v = versioning.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "not valid YAML" in v[0].message


def test_non_dict_top_level_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "- 1\n- 2\n",
    )
    v = versioning.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "mapping at the top level" in v[0].message


def test_deprecated_without_date_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: 3.0.3\ndeprecated: true\ninfo:\n  title: t\n  version: 1.0.0\npaths: {}\n",
    )
    v = versioning.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "x-deprecation-date" in v[0].message


def test_deprecated_with_valid_date_passes(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: 3.0.3\ndeprecated: true\n"
        "info:\n  title: t\n  version: 1.0.0\n"
        "  x-deprecation-date: '2030-01-01'\npaths: {}\n",
    )
    assert versioning.check([rel], str(tmp_path), _cfg()) == []


def test_deprecation_field_wrong_type_fails(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: 3.0.3\n"
        "info:\n  title: t\n  version: 1.0.0\n  x-deprecation-date: 12345\n"
        "paths: {}\n",
    )
    v = versioning.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "must be null or an ISO-8601 string" in v[0].message


def test_deprecated_with_malformed_date_string_fails(tmp_path: Path) -> None:
    """Covers the ValueError branch in `_parse_iso_date` (non-ISO string)."""
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: 3.0.3\n"
        "deprecated: true\n"
        "info:\n  title: t\n  version: 1.0.0\n"
        "  x-deprecation-date: 'not-a-date'\n"
        "paths: {}\n",
    )
    v = versioning.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1
    assert "x-deprecation-date" in v[0].message


def test_x_deprecated_in_info_also_requires_date(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: 3.0.3\n"
        "info:\n  title: t\n  version: 1.0.0\n  x-deprecated: true\n"
        "paths: {}\n",
    )
    v = versioning.check([rel], str(tmp_path), _cfg())
    assert len(v) == 1


def test_non_api_file_ignored(tmp_path: Path) -> None:
    assert versioning.check(["README.md"], str(tmp_path), _cfg()) == []


def test_yml_extension_recognised(tmp_path: Path) -> None:
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yml",
        _OK_SPEC,
    )
    assert versioning.check([rel], str(tmp_path), _cfg()) == []


def test_main_runs(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "ci.json"
    cfg.write_text('{"workspace_root":"apim-config/workspaces","teams":[]}', encoding="utf-8")
    rel = _write(
        tmp_path,
        "apim-config/workspaces/x/teams/t/apis/t-a/specification.yaml",
        "openapi: 3.0.3\ninfo:\n  title: t\npaths: {}\n",
    )
    changed = tmp_path / "changed.txt"
    changed.write_text(rel + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = versioning.main(
        ["--config", str(cfg), "--changed-files", str(changed), "--repo-root", str(tmp_path)]
    )
    assert rc == 1
    assert "versioning" in capsys.readouterr().out
