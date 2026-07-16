"""Tests for `scripts/drift_fanout.py`.

The fan-out helper splits centrally-extracted APIM drift into per-team signals.
These tests pin the two decisions it makes: which teams get their own spoke
repo (fan-out targets) and when an ``_unassigned/`` quarantine constitutes a
drift alarm. The CLI entrypoints are exercised for both exit paths.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _make_script_importable() -> None:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _mod():
    import importlib

    import drift_fanout

    importlib.reload(drift_fanout)
    return drift_fanout


CONFIG = {
    "teams": [
        {
            "name": "team-a",
            "folder": "apim-config/workspaces/pensions-core/teams/team-a",
            "prefix": "teama",
        },
        {
            "name": "team-b",
            "folder": "apim-config/workspaces/pensions-core/teams/team-b",
            "prefix": "teamb",
        },
        {
            "name": "pensions-core-shared",
            "folder": "apim-config/workspaces/pensions-core/shared",
            "prefix": "contoso",
        },
    ]
}


def _write_config(root: Path) -> Path:
    path = root / "ci.json"
    path.write_text(json.dumps(CONFIG), encoding="utf-8")
    return path


def test_fanout_teams_excludes_shared_and_derives_location() -> None:
    mod = _mod()
    teams = mod.fanout_teams(CONFIG)

    names = [t["name"] for t in teams]
    assert names == ["team-a", "team-b"]  # shared slice is not a fan-out target
    assert teams[0] == {
        "name": "team-a",
        "prefix": "teama",
        "workspace": "pensions-core",
        "team_leaf": "team-a",
        "folder": "apim-config/workspaces/pensions-core/teams/team-a",
    }


def test_fanout_teams_ignores_folder_without_workspaces_marker() -> None:
    mod = _mod()
    config = {"teams": [{"name": "odd", "folder": "some/other/path", "prefix": "x"}]}
    assert mod.fanout_teams(config) == []


def test_fanout_teams_missing_teams_key_is_empty() -> None:
    mod = _mod()
    assert mod.fanout_teams({}) == []


def test_find_unassigned_reports_quarantined_files(tmp_path: Path) -> None:
    mod = _mod()
    gov = tmp_path / "extracted"
    quarantine = (
        gov / "workspaces" / "pensions-core" / "_unassigned" / "backends"
    )
    quarantine.mkdir(parents=True)
    (quarantine / "rogue.json").write_text("{}", encoding="utf-8")
    # A normal team folder must not be reported.
    owned = gov / "workspaces" / "pensions-core" / "teams" / "team-a" / "backends"
    owned.mkdir(parents=True)
    (owned / "teama-orders.json").write_text("{}", encoding="utf-8")

    findings = mod.find_unassigned(gov)
    assert findings == ["workspaces/pensions-core/_unassigned/backends/rogue.json"]


def test_find_unassigned_empty_when_clean(tmp_path: Path) -> None:
    mod = _mod()
    gov = tmp_path / "extracted"
    (gov / "workspaces" / "pensions-core" / "teams" / "team-a").mkdir(parents=True)
    assert mod.find_unassigned(gov) == []


def test_find_unassigned_ignores_quarantine_that_is_a_file(tmp_path: Path) -> None:
    mod = _mod()
    gov = tmp_path / "extracted"
    gov.mkdir()
    # A file literally named _unassigned must not be treated as a directory.
    (gov / "_unassigned").write_text("not a dir", encoding="utf-8")
    assert mod.find_unassigned(gov) == []


def test_main_teams_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    mod = _mod()
    config = _write_config(tmp_path)
    rc = mod.main(["teams", "--config", str(config)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [t["name"] for t in payload] == ["team-a", "team-b"]


def test_main_unassigned_clean_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    mod = _mod()
    gov = tmp_path / "extracted"
    gov.mkdir()
    rc = mod.main(["unassigned", "--governance-root", str(gov)])
    assert rc == 0
    assert "No unassigned resources." in capsys.readouterr().out


def test_main_unassigned_drift_exit_one(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    mod = _mod()
    gov = tmp_path / "extracted"
    quarantine = gov / "workspaces" / "pensions-core" / "_unassigned"
    quarantine.mkdir(parents=True)
    (quarantine / "rogue.json").write_text("{}", encoding="utf-8")
    rc = mod.main(["unassigned", "--governance-root", str(gov)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "DRIFT ALARM" in out
    assert "rogue.json" in out
